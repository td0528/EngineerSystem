"""
Warehouse models - 仓库管理
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base
import enum


class MovementType(str, enum.Enum):
    """出入库类型"""
    INBOUND = "入库"
    OUTBOUND = "出库"


class SAPStatus(str, enum.Enum):
    """SAP录入状态"""
    NOT_RECORDED = "未录入SAP"
    RECORDED = "已录入SAP"
    DIRECT_USE = "直接领用"


class WarehouseStock(Base):
    """Warehouse Stock model - 仓库库存"""
    __tablename__ = "warehouse_stock"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), unique=True, nullable=False)
    location = Column(String(50))  # 库位
    
    # Quantities - 核心公式: 实际数量 = SAP数量 + 未录入SAP数量 - 未录入SAP已领取数量 - 录入SAP已领取数量
    sap_qty = Column(Integer, default=0)  # SAP数量
    actual_qty = Column(Integer, default=0)  # 实际数量（计算值）
    unrecorded_sap_qty = Column(Integer, default=0)  # 未录入SAP数量
    unrecorded_withdrawn_qty = Column(Integer, default=0)  # 未录入SAP已领取数量
    recorded_withdrawn_qty = Column(Integer, default=0)  # 录入SAP已领取数量
    
    last_inbound_date = Column(DateTime)
    last_outbound_date = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    material = relationship("Material", back_populates="warehouse_stock")
    movements = relationship("StockMovement", back_populates="stock")
    
    def calculate_actual_qty(self):
        """计算实际数量"""
        return self.sap_qty + self.unrecorded_sap_qty - self.unrecorded_withdrawn_qty - self.recorded_withdrawn_qty


class StockMovement(Base):
    """Stock Movement model - 出入库记录"""
    __tablename__ = "stock_movements"
    
    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("warehouse_stock.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    
    movement_type = Column(String(20), nullable=False)  # 入库/出库
    quantity = Column(Integer, nullable=False)
    movement_date = Column(DateTime, default=datetime.utcnow)
    
    # For inbound
    order_item_id = Column(Integer, ForeignKey("order_items.id"))  # 关联订单项
    sap_status = Column(String(20))  # 未录入SAP/已录入SAP/直接领用
    
    # Personnel
    operator = Column(String(50))  # 操作人/收货人/领用人
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    stock = relationship("WarehouseStock", back_populates="movements")


class InboundRecord(Base):
    """Inbound Record model - 入库记录"""
    __tablename__ = "inbound_records"
    
    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    
    received_qty = Column(Integer, nullable=False)  # 到货数量
    arrival_date = Column(DateTime, nullable=False)  # 到达时间
    warehouse_receive_time = Column(DateTime, nullable=True)  # 仓库实际查收、点击入库的时间
    receiver = Column(String(50))  # 收货人
    
    sap_status = Column(String(20), nullable=False)  # 未录入SAP/已录入SAP/直接领用
    direct_user = Column(String(50))  # 直接领用人（如果直接领用）
    direct_use_workshop = Column(String(100), nullable=True)  # 领用车间
    direct_use_person = Column(String(50), nullable=True)  # 领用人
    direct_use_photo = Column(String(500), nullable=True)  # 领用现场照片路径
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order_item = relationship("OrderItem", back_populates="inbound_records")


class OutboundRecord(Base):
    """Outbound Record model - 出库记录"""
    __tablename__ = "outbound_records"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    
    quantity = Column(Integer, nullable=False)  # 出库数量
    outbound_date = Column(DateTime, nullable=False)  # 出库时间
    withdraw_person = Column(String(50))  # 领用人
    
    # Relationships
    material = relationship("Material")
    
    sap_status = Column(String(20), nullable=False)  # 已录入/未录入
    
    has_receipt = Column(String(50), default="否")  # 是/否/其他 收据处理
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReturnRecord(Base):
    """Return Record model - 退货及重新交货记录"""
    __tablename__ = "return_records"
    
    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    
    return_date = Column(DateTime, default=datetime.utcnow)  # 仓库退货操作时间
    return_reason = Column(Text)  # 仓库填写的退货说明
    return_qty = Column(Integer)  # 退货数量
    
    redelivery_date = Column(DateTime)  # 供应商最新重新交货时间
    supplier_explanation = Column(Text)  # 供应商重新送货说明
    status = Column(String(20), default="待处理")  # '待处理' / '已重新发货'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order_item = relationship("OrderItem")


class OperationLog(Base):
    """Operation Log model - 操作历史记录"""
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    
    action = Column(String(50), nullable=False)  # 操作类型
    detail = Column(Text)  # 详细描述
    operator = Column(String(100))  # 操作人
    quantity = Column(Integer, nullable=True)  # 相关数量
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order_item = relationship("OrderItem")


def add_operation_log(db, action: str, detail: str, operator: str = None, 
                      order_item_id: int = None, supplier_id: int = None, quantity: int = None):
    """Helper to add operation log entry"""
    log = OperationLog(
        order_item_id=order_item_id,
        supplier_id=supplier_id,
        action=action,
        detail=detail,
        operator=operator,
        quantity=quantity
    )
    db.add(log)
