"""
Configuration API router - 配置管理
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.database.database import get_db
from app.models.configurations import ConfigOption
from app.api.auth import get_current_user

router = APIRouter()

ALLOWED_OPTION_TYPES = ["equipment", "subcategory", "workshop", "category", "location", "withdraw_person"]


class OptionCreate(BaseModel):
    option_value: str
    parent_value: Optional[str] = None
    display_order: Optional[int] = 0


@router.get("/{option_type}")
async def get_options(
    option_type: str, 
    parent_value: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取指定类型的配置选项"""
    if option_type not in ALLOWED_OPTION_TYPES:
        raise HTTPException(status_code=400, detail="无效的选项类型")
    
    query = db.query(ConfigOption).filter(
        ConfigOption.option_type == option_type,
        ConfigOption.is_active == True
    )
    
    if parent_value:
        query = query.filter(ConfigOption.parent_value == parent_value)
        
    options = query.order_by(ConfigOption.display_order, ConfigOption.option_value).all()
    
    return [
        {
            "id": o.id, 
            "value": o.option_value, 
            "parent_value": o.parent_value,
            "order": o.display_order
        } 
        for o in options
    ]


@router.post("/{option_type}")
async def add_option(
    option_type: str,
    data: OptionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """添加配置选项"""
    if option_type not in ALLOWED_OPTION_TYPES:
        raise HTTPException(status_code=400, detail="无效的选项类型")
    
    # Check admin role for all except location
    if option_type != "location" and not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail="仅管理员可操作该类型")
    
    # Check if value exists
    existing_query = db.query(ConfigOption).filter(
        ConfigOption.option_type == option_type,
        ConfigOption.option_value == data.option_value,
        ConfigOption.is_active == True
    )
    
    if data.parent_value:
        existing_query = existing_query.filter(ConfigOption.parent_value == data.parent_value)
        
    existing = existing_query.first()
    
    if existing:
        raise HTTPException(status_code=400, detail="该选项已存在")
    
    option = ConfigOption(
        option_type=option_type,
        option_value=data.option_value,
        parent_value=data.parent_value,
        display_order=data.display_order
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    
    return {"id": option.id, "value": option.option_value}


@router.delete("/{option_id}")
async def delete_option(
    option_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """删除配置选项"""
    option = db.query(ConfigOption).filter(ConfigOption.id == option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="选项不存在")
        
    # Check admin role for all except location
    if option.option_type != "location" and not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail="仅管理员可操作该类型")
    
    # Soft delete
    option.is_active = False
    db.commit()
    
    return {"message": "选项已删除"}


@router.post("/sync-from-orders")
async def sync_from_orders(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """从采购订单同步设备和车间选项（仅管理员）"""
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    from app.models.orders import PurchaseOrder
    
    # Sync workshops
    workshops = db.query(PurchaseOrder.workshop).distinct().filter(
        PurchaseOrder.workshop.isnot(None),
        PurchaseOrder.workshop != ""
    ).all()
    
    workshop_added = 0
    for (ws,) in workshops:
        existing = db.query(ConfigOption).filter(
            ConfigOption.option_type == "workshop",
            ConfigOption.option_value == ws,
            ConfigOption.is_active == True
        ).first()
        if not existing:
            db.add(ConfigOption(option_type="workshop", option_value=ws))
            workshop_added += 1
    
    # Sync equipment
    equipments = db.query(PurchaseOrder.equipment).distinct().filter(
        PurchaseOrder.equipment.isnot(None),
        PurchaseOrder.equipment != ""
    ).all()
    
    equipment_added = 0
    for (eq,) in equipments:
        existing = db.query(ConfigOption).filter(
            ConfigOption.option_type == "equipment",
            ConfigOption.option_value == eq,
            ConfigOption.is_active == True
        ).first()
        if not existing:
            db.add(ConfigOption(option_type="equipment", option_value=eq))
            equipment_added += 1
    
    db.commit()
    
    return {
        "message": "同步完成",
        "workshops_added": workshop_added,
        "equipment_added": equipment_added
    }


@router.post("/sync-from-materials")
async def sync_from_materials(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """从物料数据同步设备、车间和细分类别（仅管理员）"""
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    from app.models.materials import Material
    
    added = {"workshop": 0, "equipment": 0, "subcategory": 0, "category": 0}
    
    # Sync workshops
    for (val,) in db.query(Material.workshop).distinct().filter(Material.workshop.isnot(None), Material.workshop != "").all():
        if not db.query(ConfigOption).filter(ConfigOption.option_type == "workshop", ConfigOption.option_value == val, ConfigOption.is_active == True).first():
            db.add(ConfigOption(option_type="workshop", option_value=val))
            added["workshop"] += 1
    
    # Sync equipment
    for (val,) in db.query(Material.equipment).distinct().filter(Material.equipment.isnot(None), Material.equipment != "").all():
        if not db.query(ConfigOption).filter(ConfigOption.option_type == "equipment", ConfigOption.option_value == val, ConfigOption.is_active == True).first():
            db.add(ConfigOption(option_type="equipment", option_value=val))
            added["equipment"] += 1
    
    # Sync subcategory
    for (val,) in db.query(Material.subcategory).distinct().filter(Material.subcategory.isnot(None), Material.subcategory != "").all():
        if not db.query(ConfigOption).filter(ConfigOption.option_type == "subcategory", ConfigOption.option_value == val, ConfigOption.is_active == True).first():
            db.add(ConfigOption(option_type="subcategory", option_value=val))
            added["subcategory"] += 1
    
    # Sync category
    for (val,) in db.query(Material.category).distinct().filter(Material.category.isnot(None), Material.category != "").all():
        if not db.query(ConfigOption).filter(ConfigOption.option_type == "category", ConfigOption.option_value == val, ConfigOption.is_active == True).first():
            db.add(ConfigOption(option_type="category", option_value=val))
            added["category"] += 1
            
    # Sync location
    if "location" not in added:
        added["location"] = 0
    for (val,) in db.query(Material.location).distinct().filter(Material.location.isnot(None), Material.location != "").all():
        if not db.query(ConfigOption).filter(ConfigOption.option_type == "location", ConfigOption.option_value == val, ConfigOption.is_active == True).first():
            db.add(ConfigOption(option_type="location", option_value=val))
            added["location"] += 1
    
    db.commit()
    
    return {"message": "同步完成", "added": added}
