"""
Devices API router - 设备监控（雏形）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.database.database import get_db
from app.models.devices import Device, DeviceData

router = APIRouter()


class DeviceCreate(BaseModel):
    name: str
    code: str
    device_type: Optional[str] = None
    location: Optional[str] = None
    workshop: Optional[str] = None
    ip_address: Optional[str] = None
    mqtt_topic: Optional[str] = None
    http_endpoint: Optional[str] = None


class DeviceDataCreate(BaseModel):
    device_id: int
    data_type: str
    value: float
    unit: Optional[str] = None
    raw_data: Optional[dict] = None


@router.get("/")
async def get_devices(
    workshop: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取设备列表"""
    query = db.query(Device).filter(Device.is_active == True)
    
    if workshop:
        query = query.filter(Device.workshop == workshop)
    if status:
        query = query.filter(Device.status == status)
    
    devices = query.offset(skip).limit(limit).all()
    return devices


@router.get("/{device_id}")
async def get_device(device_id: int, db: Session = Depends(get_db)):
    """获取设备详情"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.post("/")
async def create_device(device_data: DeviceCreate, db: Session = Depends(get_db)):
    """创建设备"""
    if db.query(Device).filter(Device.code == device_data.code).first():
        raise HTTPException(status_code=400, detail="设备编号已存在")
    
    device = Device(**device_data.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.post("/data")
async def add_device_data(data: DeviceDataCreate, db: Session = Depends(get_db)):
    """添加设备数据（MQTT/HTTP回调用）"""
    device = db.query(Device).filter(Device.id == data.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    device_data = DeviceData(
        device_id=data.device_id,
        data_type=data.data_type,
        value=data.value,
        unit=data.unit,
        raw_data=data.raw_data
    )
    db.add(device_data)
    
    # Update device status
    device.last_online = datetime.utcnow()
    device.status = "运行"
    
    db.commit()
    
    return {"success": True}


@router.get("/{device_id}/data")
async def get_device_data(
    device_id: int,
    data_type: Optional[str] = None,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """获取设备数据（用于图表）"""
    query = db.query(DeviceData).filter(
        DeviceData.device_id == device_id,
        DeviceData.timestamp >= datetime.utcnow() - timedelta(hours=hours)
    )
    
    if data_type:
        query = query.filter(DeviceData.data_type == data_type)
    
    data = query.order_by(DeviceData.timestamp.asc()).all()
    
    return data


@router.get("/status/summary")
async def get_status_summary(db: Session = Depends(get_db)):
    """获取设备状态汇总"""
    total = db.query(Device).filter(Device.is_active == True).count()
    running = db.query(Device).filter(Device.status == "运行").count()
    stopped = db.query(Device).filter(Device.status == "停止").count()
    fault = db.query(Device).filter(Device.status == "故障").count()
    
    return {
        "total": total,
        "running": running,
        "stopped": stopped,
        "fault": fault,
        "unknown": total - running - stopped - fault
    }
