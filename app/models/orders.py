"""
Purchase Order models - 采购订单管理
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base
import enum


class OrderType(str, enum.Enum):
    """订单类型"""
    HARDWARE = "五金件"
    MACHINING = "机加工"


class OrderStatus(str, enum.Enum):
    """订单状态"""
    DRAFT = "草稿"
    SUBMITTED = "已提交"
    CONFIRMED = "已确认"
    PARTIAL_RECEIVED = "部分到货"
    COMPLETED = "已完成"
    CANCELLED = "已取消"


class PurchaseOrder(Base):
    """Purchase Order model - 采购订单"""
    __tablename__ = "purchase_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String(50), unique=True, index=True, nullable=False)  # PO号
    order_type = Column(String(20), default="五金件")  # 五金件/机加工
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    status = Column(String(20), default="草稿")
    
    # Dates
    order_date = Column(Date, nullable=False)  # 采购日期
    required_date = Column(Date)  # 需求日期
    arrival_date = Column(Date)  # 到达日期 (自动更新)
    
    # Details
    workshop = Column(String(50))  # 使用车间
    equipment = Column(String(200))  # 设备
    purpose = Column(Text)  # 作用
    total_amount = Column(Float, default=0)
    currency = Column(String(10), default="VND")
    
    # Invoice
    invoice_number = Column(String(100))  # 发票号
    invoice_file = Column(String(255))  # 发票文件路径
    
    # Tracking
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Order Item model - 订单明细"""
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    
    # Quantities
    ordered_qty = Column(Integer, nullable=False)  # 订货数量
    received_qty = Column(Integer, default=0)  # 收货数量
    
    # Price
    unit_price = Column(Float)  # 单价
    total_price = Column(Float)  # 总价
    currency = Column(String(10), default="VND")  # 货币: VND / USD
    
    # Per-item details (each material has its own)
    required_date = Column(Date)  # 需求日期
    workshop = Column(String(50))  # 使用车间
    equipment = Column(String(200))  # 使用设备
    purpose = Column(Text)  # 作用说明
    
    # Status
    is_fully_received = Column(Boolean, default=False)
    
    # Invoice tracking per item
    invoice_number = Column(String(100))
    
    # New fields for enhanced PO workflow
    arrival_date = Column(Date)  # 到货时间
    item_status = Column(String(20), default="未下单")  # 未下单/已下单/已送货/已收货/已开发票
    quotation_file = Column(String(255))  # 报价单PDF路径
    delivery_note = Column(String(255))  # 送货单PDF路径
    actual_delivery_date = Column(Date)  # 实际送货日期
    invoice_file = Column(String(255))  # 发票PDF路径
    quotation_date = Column(Date)  # 报价日期
    invoice_date = Column(Date)  # 发票日期
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order = relationship("PurchaseOrder", back_populates="items")
    material = relationship("Material", back_populates="order_items")
    inbound_records = relationship("InboundRecord", back_populates="order_item")


class Invoice(Base):
    """Invoice model - 发票管理"""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(100), index=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    order_type = Column(String(20))  # 五金件/机加工
    amount = Column(Float)
    tax_amount = Column(Float)
    total_amount = Column(Float)
    invoice_date = Column(Date)
    file_path = Column(String(255))  # PDF发票路径
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Related order items (JSON array of order_item_ids)
    related_items = Column(Text)  # JSON string


class SupplierQuote(Base):
    """Supplier Quote - 供应商报价（门户系统用）"""
    __tablename__ = "supplier_quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    quoted_price = Column(Float, nullable=False)
    quoted_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    invoice_number = Column(String(100))
    invoice_file = Column(String(255))
