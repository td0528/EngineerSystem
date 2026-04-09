"""
Device models - 设备监控
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from datetime import datetime
from app.database.database import Base


class Device(Base):
    """Device model - 设备"""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True)  # 设备编号
    
    device_type = Column(String(50))  # 设备类型
    location = Column(String(100))  # 位置
    workshop = Column(String(50))  # 车间
    
    # Connection info
    ip_address = Column(String(50))
    mqtt_topic = Column(String(200))
    http_endpoint = Column(String(500))
    
    # Status
    status = Column(String(20), default="未知")  # 运行/停止/故障/维护/未知
    last_online = Column(DateTime)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeviceData(Base):
    """Device Data model - 设备数据记录"""
    __tablename__ = "device_data"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    data_type = Column(String(50))  # temperature/pressure/speed/etc
    value = Column(Float)
    unit = Column(String(20))
    raw_data = Column(JSON)  # Raw JSON data from MQTT/HTTP
    
    created_at = Column(DateTime, default=datetime.utcnow)
