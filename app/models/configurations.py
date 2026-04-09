"""
Configuration models - 配置管理
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.database.database import Base


class ConfigOption(Base):
    """可配置选项（设备、细分类别、车间等）"""
    __tablename__ = "config_options"
    
    id = Column(Integer, primary_key=True, index=True)
    option_type = Column(String(50), nullable=False, index=True)  # equipment/subcategory/workshop
    option_value = Column(String(200), nullable=False)
    parent_value = Column(String(200), nullable=True)  # For subcategory: linking to parent category
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
