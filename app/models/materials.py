"""
Material models - 物料管理
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base
from app.models.material_notes import MaterialNote
import enum


class MaterialCategory(str, enum.Enum):
    """物料种类"""
    ELECTRICAL = "电气"
    MECHANICAL = "机械"
    MOLD = "模具"
    CONSUMABLE = "耗材"


class Workshop(str, enum.Enum):
    """使用车间"""
    MAIN_LINE = "主线"
    POSITIVE = "正极"
    NEGATIVE = "负极"
    ACCESSORIES = "配件"
    GENERAL = "通用"


class Material(Base):
    """Material model - 物料主数据"""
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True)
    sap_code = Column(String(50), unique=True, index=True, nullable=False)  # SAP号码
    name_cn = Column(String(200), nullable=False, index=True)  # 中文名称
    name_vn = Column(String(200), index=True)  # 越南语名称
    location = Column(String(50))  # 库位
    image = Column(String(255))  # 图片路径
    drawing_pdf = Column(String(255))  # 图纸PDF路径
    category = Column(String(50))  # 种类: 电气/机械/模具/耗材
    subcategory = Column(String(50))  # 细分: 同步带/伺服/马达/轴承等
    workshop = Column(String(50))  # 使用车间
    equipment = Column(String(200))  # 使用设备
    purchase_link = Column(String(500))  # 购买链接
    specification = Column(Text)  # 规格描述
    unit = Column(String(20), default="个")  # 单位
    min_stock = Column(Integer, default=0)  # 最低库存
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - cascade delete all related data
    prices = relationship("MaterialPrice", back_populates="material", order_by="desc(MaterialPrice.created_at)", cascade="all, delete-orphan")
    suppliers = relationship("MaterialSupplier", back_populates="material", cascade="all, delete-orphan")
    quotations = relationship("Quotation", back_populates="material", cascade="all, delete-orphan")
    warehouse_stock = relationship("WarehouseStock", back_populates="material", uselist=False, cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="material", cascade="all, delete-orphan")
    notes = relationship("MaterialNote", back_populates="material", order_by="desc(MaterialNote.created_at)", cascade="all, delete-orphan")


class MaterialPrice(Base):
    """价格历史记录"""
    __tablename__ = "material_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="VND")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    effective_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    material = relationship("Material", back_populates="prices")


class MaterialSupplier(Base):
    """物料-供应商关联"""
    __tablename__ = "material_suppliers"
    
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    is_preferred = Column(Boolean, default=False)  # 首选供应商
    lead_time_days = Column(Integer)  # 交货周期
    min_order_qty = Column(Integer)  # 最小订购量
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    material = relationship("Material", back_populates="suppliers")
    supplier = relationship("Supplier", back_populates="material_suppliers")


class Quotation(Base):
    """报价单"""
    __tablename__ = "quotations"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    supplier_name = Column(String(100))  # 供应商名称（备用）
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="VND")
    valid_until = Column(DateTime)
    file_path = Column(String(255))  # 报价单PDF/图片（兼容旧数据）
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    material = relationship("Material", back_populates="quotations")
    attachments = relationship("QuotationAttachment", back_populates="quotation", cascade="all, delete-orphan")


class QuotationAttachment(Base):
    """报价单附件"""
    __tablename__ = "quotation_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(200))
    file_type = Column(String(20))  # pdf/image
    file_size = Column(Integer)  # bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    quotation = relationship("Quotation", back_populates="attachments")

