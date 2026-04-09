"""
User and supplier models for authentication and authorization
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    full_name_vn = Column(String(100))  # Vietnamese name
    department = Column(String(50))  # 主线, 正极, 负极, 配件, 通用
    phone = Column(String(20))
    avatar = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks_created = relationship("Task", back_populates="creator", foreign_keys="Task.creator_id")
    tasks_assigned = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")
    records = relationship("Record", back_populates="user")


class Supplier(Base):
    """Supplier model - 供应商"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(50), unique=True, index=True)  # Supplier code for login
    password_hash = Column(String(255))  # For supplier portal login
    contact_person = Column(String(100))
    phone = Column(String(50))
    email = Column(String(100))
    address = Column(String(500))
    tax_id = Column(String(50))
    bank_account = Column(String(100))
    bank_name = Column(String(100))
    payment_terms = Column(String(100))  # 付款条款
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")
    material_suppliers = relationship("MaterialSupplier", back_populates="supplier")
