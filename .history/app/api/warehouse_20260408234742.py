"""
Warehouse API router - 仓库管理
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.database.database import get_db
from app.models.warehouse import WarehouseStock, StockMovement, InboundRecord, OutboundRecord, add_operation_log
from app.models.orders import OrderItem, PurchaseOrder
from app.models.materials import Material
from app.models.users import Supplier
from app.api.auth import get_current_user

router = APIRouter()


class InboundCreate(BaseModel):
    order_item_id: int
    received_qty: int
    arrival_date: datetime
    receiver: str
    sap_status: str  # 未录入SAP/已录入SAP/直接领用
    direct_user: Optional[str] = None  # 直接领用人
    notes: Optional[str] = None

class InboundConfirm(BaseModel):
    # From portal the supplier gives the delivery quantity, the warehouse confirms it
    warehouse_receive_time: datetime
    received_qty: int
    sap_status: str = "未录入SAP"
    receiver: str
    notes: Optional[str] = None
    direct_use_workshop: Optional[str] = None
    direct_use_person: Optional[str] = None

class ReturnCreate(BaseModel):
    return_reason: str
    return_qty: Optional[int] = None  # If None, return all


class OutboundCreate(BaseModel):
    material_id: int
    quantity: int
    outbound_date: datetime
    withdraw_person: str
    sap_status: str  # 已录入/未录入
    has_receipt: str = "否"
    notes: Optional[str] = None


class StockUpdate(BaseModel):
    sap_qty: Optional[int] = None


class MarkSapRecordedRequest(BaseModel):
    inbound_ids: List[int]


@router.get("/stock")
async def get_warehouse_stock(
    search: Optional[str] = None,
    location: Optional[str] = None,
    low_stock: bool = False,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = 'asc',
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取仓库库存列表"""
    query = db.query(WarehouseStock).options(
        joinedload(WarehouseStock.material)
    )
    
    if search:
        # Replace hyphens with spaces for better tokenization
        clean_search = search.replace('-', ' ').strip()
        keywords = [k for k in clean_search.split() if k]
        
        if keywords:
            query = query.join(Material)
            conditions = []
            for keyword in keywords:
                term = f"%{keyword}%"
                conditions.append(
                    or_(
                        Material.sap_code.ilike(term),
                        Material.name_cn.ilike(term),
                        Material.name_vn.ilike(term)
                    )
                )
            query = query.filter(and_(*conditions))
    
    if location:
        query = query.filter(WarehouseStock.location == location)
    
    if low_stock:
        # Filter items where actual qty is below min stock
        if not search:  # Avoid joining if already joined
            query = query.join(Material)
        query = query.filter(
            (WarehouseStock.sap_qty + WarehouseStock.unrecorded_sap_qty - WarehouseStock.unrecorded_withdrawn_qty - WarehouseStock.recorded_withdrawn_qty) <= Material.min_stock
        )
    
    # Sorting
    if sort_by:
        # Join Material if sorting by material attributes and not already joined
        if sort_by in ['sap_code', 'name_cn'] and not search and not low_stock:
            query = query.join(Material)
            
        sort_col = None
        if sort_by == 'sap_code':
            sort_col = Material.sap_code
        elif sort_by == 'name_cn':
            sort_col = Material.name_cn
        elif sort_by == 'location':
            sort_col = WarehouseStock.location
        elif sort_by == 'sap_qty':
            sort_col = WarehouseStock.sap_qty
        elif sort_by == 'unrecorded_sap_qty':
            sort_col = WarehouseStock.unrecorded_sap_qty
        elif sort_by == 'unrecorded_withdrawn_qty':
            sort_col = WarehouseStock.unrecorded_withdrawn_qty
        elif sort_by == 'recorded_withdrawn_qty':
            sort_col = WarehouseStock.recorded_withdrawn_qty
        elif sort_by == 'actual_qty':
            sort_col = (WarehouseStock.sap_qty + WarehouseStock.unrecorded_sap_qty - WarehouseStock.unrecorded_withdrawn_qty - WarehouseStock.recorded_withdrawn_qty)
            
        if sort_col is not None:
            if sort_order == 'desc':
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())
    elif search:
        # Prioritize SAP code exact/prefix match if searching without explicit sort
        clean_search = search.replace('-', ' ').strip()
        query = query.order_by(
            desc(Material.sap_code.ilike(f"{clean_search}%")),
            Material.sap_code
        )
    else:
        # Default sort
        query = query.order_by(WarehouseStock.id.desc())
    
    total = query.count()
    stocks = query.offset(skip).limit(limit).all()
    
    # Calculate actual quantities
    result = []
    for stock in stocks:
        actual_qty = stock.sap_qty + stock.unrecorded_sap_qty - stock.unrecorded_withdrawn_qty - stock.recorded_withdrawn_qty
        result.append({
            "id": stock.id,
            "material_id": stock.material_id,
            "material": {
                "sap_code": stock.material.sap_code if stock.material else "已删除",
                "name_cn": stock.material.name_cn if stock.material else "物料不存在",
                "name_vn": stock.material.name_vn if stock.material else "",
                "image": stock.material.image if stock.material else None,
                "drawing_pdf": stock.material.drawing_pdf if stock.material else None,
                "min_stock": stock.material.min_stock if stock.material else 0
            },
            "location": stock.location,
            "sap_qty": stock.sap_qty,
            "actual_qty": actual_qty,
            "unrecorded_sap_qty": stock.unrecorded_sap_qty,
            "unrecorded_withdrawn_qty": stock.unrecorded_withdrawn_qty,
            "recorded_withdrawn_qty": stock.recorded_withdrawn_qty,
            "last_inbound_date": stock.last_inbound_date,
            "last_outbound_date": stock.last_outbound_date
        })
    
    return {"total": total, "items": result}


@router.get("/stock/{material_id}")
async def get_stock_by_material(material_id: int, db: Session = Depends(get_db)):
    """获取指定物料的库存详情"""
    stock = db.query(WarehouseStock).options(
        joinedload(WarehouseStock.material)
    ).filter(WarehouseStock.material_id == material_id).first()
    
    if not stock:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    
    actual_qty = stock.sap_qty + stock.unrecorded_sap_qty - stock.unrecorded_withdrawn_qty - stock.recorded_withdrawn_qty
    
    return {
        **stock.__dict__,
        "actual_qty": actual_qty
    }


@router.put("/stock/{stock_id}/sap-qty")
async def update_sap_qty(stock_id: int, data: StockUpdate, db: Session = Depends(get_db)):
    """更新SAP数量（仅可通过此接口更新）"""
    stock = db.query(WarehouseStock).filter(WarehouseStock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    
    if data.sap_qty is not None:
        stock.sap_qty = data.sap_qty
        stock.actual_qty = stock.sap_qty + stock.unrecorded_sap_qty - stock.unrecorded_withdrawn_qty - stock.recorded_withdrawn_qty
    
    db.commit()
    db.refresh(stock)
    return stock


@router.get("/pending-inbound")
async def get_pending_inbound(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取待入库列表（供应商已送货的单据，包含部分退货中仍有可收数量的）"""
    query = db.query(OrderItem).options(
        joinedload(OrderItem.order).joinedload(PurchaseOrder.supplier),
        joinedload(OrderItem.material)
    ).filter(OrderItem.item_status.in_(["已送货", "退货中"]))
    
    total = query.count()
    items = query.order_by(OrderItem.actual_delivery_date.desc(), OrderItem.id.desc()).offset(skip).limit(limit).all()
    
    result = []
    for item in items:
        # Calculate pending return qty for this order item
        from sqlalchemy import func as sa_func
        pending_return_qty = db.query(sa_func.coalesce(sa_func.sum(ReturnRecord.return_qty), 0)).filter(
            ReturnRecord.order_item_id == item.id,
            ReturnRecord.status == "待处理"
        ).scalar() or 0
        
        # Calculate remaining: deduct both received and pending returns
        remaining = item.ordered_qty - item.received_qty - pending_return_qty
        
        result.append({
            "id": item.id,
            "order_id": item.order_id,
            "po_number": item.order.po_number if item.order else "",
            "supplier_name": item.order.supplier.name if item.order and item.order.supplier else "",
            "material_id": item.material_id,
            "material": {
                "sap_code": item.material.sap_code if item.material else "",
                "name_cn": item.material.name_cn if item.material else "",
                "name_vn": item.material.name_vn if item.material else "",
                "image": item.material.image if item.material else None,
                "drawing_pdf": item.material.drawing_pdf if item.material else None,
            },
            "ordered_qty": item.ordered_qty,
            "received_qty": item.received_qty,
            "remaining_qty": max(0, remaining),
            "pending_return_qty": pending_return_qty,
            "order_date": item.order.order_date.isoformat() if item.order and item.order.order_date else None,
            "required_date": item.required_date.isoformat() if item.required_date else None,
            "actual_delivery_date": item.actual_delivery_date.isoformat() if item.actual_delivery_date else None,
            "workshop": item.workshop,
            "equipment": item.equipment,
            "notes": item.purpose
        })
    
    # Filter out items with no remaining receivable qty
    result = [r for r in result if r["remaining_qty"] > 0]
    
    return {"total": len(result), "items": result}


@router.post("/inbound/{item_id}")
async def confirm_inbound(item_id: int, confirm_data: InboundConfirm, db: Session = Depends(get_db)):
    """从待入库列表中确认入库操作"""
    # Get order item
    order_item = db.query(OrderItem).options(
        joinedload(OrderItem.order),
        joinedload(OrderItem.material)
    ).filter(OrderItem.id == item_id).first()
    
    if not order_item:
        raise HTTPException(status_code=404, detail="订单项不存在")
    
    # Calculate pending return qty
    from sqlalchemy import func as sa_func
    pending_return_qty = db.query(sa_func.coalesce(sa_func.sum(ReturnRecord.return_qty), 0)).filter(
        ReturnRecord.order_item_id == item_id,
        ReturnRecord.status == "待处理"
    ).scalar() or 0
    
    # Check if can receive more (deduct pending returns)
    remaining = order_item.ordered_qty - order_item.received_qty - pending_return_qty
    if confirm_data.received_qty > remaining:
        raise HTTPException(status_code=400, detail=f"到货数量超过可收数量（订单{order_item.ordered_qty} - 已收{order_item.received_qty} - 退货中{pending_return_qty} = 可收{remaining}）")
    
    # Get or create warehouse stock
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.material_id == order_item.material_id
    ).first()
    
    if not stock:
        stock = WarehouseStock(material_id=order_item.material_id)
        db.add(stock)
        db.flush()
    
    # Create inbound record
    inbound = InboundRecord(
        order_item_id=item_id,
        received_qty=confirm_data.received_qty,
        arrival_date=order_item.actual_delivery_date if order_item.actual_delivery_date else datetime.utcnow(),
        warehouse_receive_time=confirm_data.warehouse_receive_time,
        receiver=confirm_data.receiver,
        sap_status=confirm_data.sap_status,
        notes=confirm_data.notes,
        direct_use_workshop=confirm_data.direct_use_workshop if confirm_data.sap_status == "直接领用" else None,
        direct_use_person=confirm_data.direct_use_person if confirm_data.sap_status == "直接领用" else None,
    )
    db.add(inbound)
    
    # Update order item
    order_item.received_qty += confirm_data.received_qty
    if order_item.received_qty >= order_item.ordered_qty:
        order_item.is_fully_received = True
        # Only mark as "已收货" when fully received
        order_item.item_status = "已收货"
    # else: keep status as "已送货" so it stays in pending inbound board
    
    # Update stock based on SAP status
    if confirm_data.sap_status == "直接领用":
        pass
    elif confirm_data.sap_status == "未录入SAP":
        stock.unrecorded_sap_qty += confirm_data.received_qty
    elif confirm_data.sap_status == "已录入SAP":
        stock.sap_qty += confirm_data.received_qty
    
    stock.last_inbound_date = confirm_data.warehouse_receive_time
    stock.actual_qty = stock.sap_qty + stock.unrecorded_sap_qty - stock.unrecorded_withdrawn_qty - stock.recorded_withdrawn_qty
    
    # Create movement record
    movement = StockMovement(
        stock_id=stock.id,
        material_id=order_item.material_id,
        movement_type="入库",
        quantity=confirm_data.received_qty,
        movement_date=confirm_data.warehouse_receive_time,
        order_item_id=item_id,
        sap_status=confirm_data.sap_status,
        operator=confirm_data.receiver,
        notes=confirm_data.notes
    )
    db.add(movement)
    
    # Check if all items in order are received
    order = order_item.order
    all_received = all(item.is_fully_received for item in order.items)
    if all_received:
        order.status = "已完成"
    else:
        order.status = "部分到货"
    
    db.commit()
    
    add_operation_log(
        db,
        action="仓库收货",
        detail=f"仓库确认收货，入库数量：{confirm_data.received_qty}",
        operator=confirm_data.receiver,
        order_item_id=item_id,
        supplier_id=order.supplier_id,
        quantity=confirm_data.received_qty
    )
    
    return {"success": True, "message": "入库成功", "inbound_id": inbound.id}


@router.post("/inbound/{record_id}/photo")
async def upload_inbound_photo(record_id: int, db: Session = Depends(get_db)):
    """上传直接领用的现场照片"""
    from fastapi import UploadFile, File
    import os
    
    record = db.query(InboundRecord).filter(InboundRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="入库记录不存在")
    
    return {"upload_url": f"/warehouse/inbound/{record_id}/photo/upload"}


from fastapi import UploadFile, File

@router.post("/inbound/{record_id}/photo/upload")
async def do_upload_inbound_photo(record_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """实际上传照片文件"""
    import os
    
    record = db.query(InboundRecord).filter(InboundRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="入库记录不存在")
    
    upload_dir = "uploads/inbound_photos"
    os.makedirs(upload_dir, exist_ok=True)
    
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"inbound_{record_id}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    
    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)
    
    record.direct_use_photo = f"/{filepath}"
    db.commit()
    
    return {"success": True, "photo_path": record.direct_use_photo}

from app.models.warehouse import ReturnRecord

@router.post("/return/{item_id}")
async def return_item(item_id: int, return_data: ReturnCreate, db: Session = Depends(get_db)):
    """对供应商已送货/已收货的物料进行退货处理"""
    order_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not order_item:
        raise HTTPException(status_code=404, detail="订单项不存在")
        
    if order_item.item_status not in ["已送货", "已收货"]:
        raise HTTPException(status_code=400, detail="只能对已送货或已收货的物料进行退货，当前状态：" + order_item.item_status)
    
    max_return_qty = order_item.ordered_qty - (order_item.received_qty or 0)
    return_qty = return_data.return_qty or max_return_qty
    
    if return_qty <= 0:
        raise HTTPException(status_code=400, detail="无可退货数量（已全部收货）")
    if return_qty > max_return_qty:
        raise HTTPException(status_code=400, detail=f"退货数量不能超过 {max_return_qty}（订单数量{order_item.ordered_qty} - 已收货{order_item.received_qty or 0}）")
    
    # Determine status: if there's still remaining receivable qty, keep as 已送货
    total_pending_returns = return_qty
    # Check for existing pending returns
    existing_pending = db.query(ReturnRecord).filter(
        ReturnRecord.order_item_id == item_id,
        ReturnRecord.status == "待处理"
    ).all()
    for r in existing_pending:
        total_pending_returns += (r.return_qty or 0)
    
    remaining_receivable = order_item.ordered_qty - (order_item.received_qty or 0) - total_pending_returns
    if remaining_receivable > 0:
        # Still has items to receive, keep as 已送货
        order_item.item_status = "已送货"
    else:
        # All qty accounted for (received + returning), mark as 退货中
        order_item.item_status = "退货中"
    
    # Create return record
    ret_record = ReturnRecord(
        order_item_id=item_id,
        return_date=datetime.utcnow(),
        return_reason=return_data.return_reason,
        return_qty=return_qty,
        status="待处理"
    )
    db.add(ret_record)
    
    db.commit()
    
    add_operation_log(
        db,
        action="收货前退货",
        detail=f"退货原因：{return_data.return_reason}",
        operator=current_user.name if hasattr(current_user, 'name') else "仓库管理员",
        order_item_id=item_id,
        supplier_id=order_item.order.supplier_id,
        quantity=return_qty
    )
    return {"success": True, "message": "退货指令已下达，已通知供应商处理"}


class BatchReturnInbound(BaseModel):
    inbound_ids: list
    return_reason: str
    return_qty: Optional[int] = None

@router.post("/return-inbound")
async def return_inbound_items(
    data: BatchReturnInbound, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """对已入库的记录进行退货（批量支持）"""
    if not data.inbound_ids:
        raise HTTPException(status_code=400, detail="请选择至少一条入库记录")
    
    returned_count = 0
    for inbound_id in data.inbound_ids:
        record = db.query(InboundRecord).filter(InboundRecord.id == inbound_id).first()
        if not record:
            continue
        
        order_item = db.query(OrderItem).filter(OrderItem.id == record.order_item_id).first()
        if not order_item:
            continue
        
        # Determine return qty: use user-specified or fall back to inbound record qty
        max_qty = record.received_qty or 0
        qty = data.return_qty if data.return_qty and data.return_qty <= max_qty else max_qty
        
        if qty <= 0:
            continue
        
        # Create return record
        ret_record = ReturnRecord(
            order_item_id=record.order_item_id,
            return_date=datetime.utcnow(),
            return_reason=data.return_reason,
            return_qty=qty,
            status="待处理"
        )
        db.add(ret_record)
        
        # Adjust received qty and warehouse stock
        order_item.received_qty = max(0, (order_item.received_qty or 0) - qty)
        order_item.item_status = "退货中"
        
        # Reduce warehouse stock
        stock = db.query(WarehouseStock).filter(
            WarehouseStock.material_id == order_item.material_id
        ).first()
        if stock:
            stock.unrecorded_sap_qty = max(0, (stock.unrecorded_sap_qty or 0) - qty)
            stock.actual_qty = stock.calculate_actual_qty()
            
        add_operation_log(
            db,
            action="收货后退货",
            detail=f"对入库单(ID:{record.id})退货。原因：{data.return_reason}",
            operator=current_user.name if hasattr(current_user, 'name') else "仓库管理员",
            order_item_id=order_item.id,
            supplier_id=order_item.order.supplier_id,
            quantity=qty
        )
        
        # Update or remove the inbound record
        if qty >= max_qty:
            db.delete(record)
        else:
            record.received_qty -= qty
        returned_count += 1
    
    db.commit()
    return {"success": True, "message": f"已退货 {returned_count} 条记录，已通知供应商处理"}

@router.get("/received-inbound")
async def get_received_inbound(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sap_status: Optional[str] = None,
    supplier_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取已入库列表（InboundRecords）"""
    query = db.query(InboundRecord).options(
        joinedload(InboundRecord.order_item).joinedload(OrderItem.order).joinedload(PurchaseOrder.supplier),
        joinedload(InboundRecord.order_item).joinedload(OrderItem.material)
    )

    # Join chain for filtering
    query = query.join(InboundRecord.order_item).join(OrderItem.order).join(PurchaseOrder.supplier).join(OrderItem.material)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                PurchaseOrder.po_number.ilike(term),
                Material.sap_code.ilike(term),
                Material.name_cn.ilike(term),
                Material.name_vn.ilike(term),
                Supplier.name.ilike(term)
            )
        )

    if sap_status:
        query = query.filter(InboundRecord.sap_status == sap_status)

    if supplier_name:
        query = query.filter(Supplier.name == supplier_name)
    
    total = query.count()
    records = query.order_by(InboundRecord.warehouse_receive_time.desc(), InboundRecord.id.desc()).offset(skip).limit(limit).all()

    supplier_options = [
        name for (name,) in db.query(Supplier.name)
        .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
        .join(OrderItem, OrderItem.order_id == PurchaseOrder.id)
        .join(InboundRecord, InboundRecord.order_item_id == OrderItem.id)
        .distinct()
        .order_by(Supplier.name.asc())
        .all()
        if name
    ]
    
    result = []
    for rec in records:
        item = rec.order_item
        if not item: continue
        
        result.append({
            "id": rec.id,
            "order_item_id": rec.order_item_id,
            "order_id": item.order_id,
            "po_number": item.order.po_number if item.order else "",
            "supplier_name": item.order.supplier.name if item.order and item.order.supplier else "",
            "material_id": item.material_id,
            "material": {
                "sap_code": item.material.sap_code if item.material else "",
                "name_cn": item.material.name_cn if item.material else "",
                "name_vn": item.material.name_vn if item.material else "",
                "image": item.material.image if item.material else None,
                "drawing_pdf": item.material.drawing_pdf if item.material else None,
            },
            "received_qty": rec.received_qty,
            "warehouse_receive_time": rec.warehouse_receive_time.isoformat() if rec.warehouse_receive_time else None,
            "arrival_date": rec.arrival_date.isoformat() if rec.arrival_date else None,
            "receiver": rec.receiver,
            "sap_status": rec.sap_status,
            "direct_use_workshop": rec.direct_use_workshop,
            "direct_use_person": rec.direct_use_person,
            "direct_use_photo": rec.direct_use_photo,
            "notes": rec.notes
        })
        
    return {"total": total, "items": result, "supplier_options": supplier_options}


@router.put("/inbound/{record_id}/sap-status")
async def update_inbound_sap_status(
    record_id: int,
    db: Session = Depends(get_db)
):
    """更新入库记录SAP状态（仅允许 未录入SAP -> 已录入SAP）"""
    record = db.query(InboundRecord).filter(InboundRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="入库记录不存在")
    
    if record.sap_status != "未录入SAP":
        raise HTTPException(status_code=400, detail=f"当前状态为'{record.sap_status}'，不可更改")

    item = db.query(OrderItem).filter(OrderItem.id == record.order_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="关联订单项不存在")

    stock = db.query(WarehouseStock).filter(WarehouseStock.material_id == item.material_id).first()
    if stock:
        qty = max(0, int(record.received_qty or 0))

        stock.unrecorded_sap_qty = max(0, (stock.unrecorded_sap_qty or 0) - qty)
        stock.sap_qty = (stock.sap_qty or 0) + qty

        transfer_withdraw = min((stock.unrecorded_withdrawn_qty or 0), qty)
        if transfer_withdraw > 0:
            stock.unrecorded_withdrawn_qty = max(0, (stock.unrecorded_withdrawn_qty or 0) - transfer_withdraw)
            stock.recorded_withdrawn_qty = (stock.recorded_withdrawn_qty or 0) + transfer_withdraw

        stock.actual_qty = stock.calculate_actual_qty()
    
    record.sap_status = "已录入SAP"
    db.commit()
    
    return {"message": "SAP状态已更新为'已录入SAP'", "sap_status": record.sap_status}


@router.post("/inbound/actions/mark-sap-recorded")
async def mark_inbound_sap_recorded(
    data: MarkSapRecordedRequest,
    db: Session = Depends(get_db)
):
    """批量将未录入SAP改为已录入SAP，并同步库存数量桶"""
    if not data.inbound_ids:
        raise HTTPException(status_code=400, detail="请至少选择一条记录")

    updated = 0
    for rid in data.inbound_ids:
        record = db.query(InboundRecord).filter(InboundRecord.id == rid).first()
        if not record or record.sap_status != "未录入SAP":
            continue

        item = db.query(OrderItem).filter(OrderItem.id == record.order_item_id).first()
        if not item:
            continue

        stock = db.query(WarehouseStock).filter(WarehouseStock.material_id == item.material_id).first()
        if stock:
            qty = max(0, int(record.received_qty or 0))
            stock.unrecorded_sap_qty = max(0, (stock.unrecorded_sap_qty or 0) - qty)
            stock.sap_qty = (stock.sap_qty or 0) + qty

            transfer_withdraw = min((stock.unrecorded_withdrawn_qty or 0), qty)
            if transfer_withdraw > 0:
                stock.unrecorded_withdrawn_qty = max(0, (stock.unrecorded_withdrawn_qty or 0) - transfer_withdraw)
                stock.recorded_withdrawn_qty = (stock.recorded_withdrawn_qty or 0) + transfer_withdraw

            stock.actual_qty = stock.calculate_actual_qty()

        record.sap_status = "已录入SAP"
        updated += 1

    db.commit()
    return {"success": True, "updated": updated}

@router.post("/outbound")
async def create_outbound(outbound_data: OutboundCreate, db: Session = Depends(get_db)):
    """出库操作"""
    # Get warehouse stock
    stock = db.query(WarehouseStock).filter(
        WarehouseStock.material_id == outbound_data.material_id
    ).first()
    
    if not stock:
        raise HTTPException(status_code=404, detail="库存记录不存在")
    
    # Calculate actual qty
    actual_qty = stock.sap_qty + stock.unrecorded_sap_qty - stock.unrecorded_withdrawn_qty - stock.recorded_withdrawn_qty
    if outbound_data.quantity > actual_qty:
        raise HTTPException(status_code=400, detail=f"出库数量超过实际库存（实际: {actual_qty}）")
    
    # Create outbound record
    outbound = OutboundRecord(
        material_id=outbound_data.material_id,
        quantity=outbound_data.quantity,
        outbound_date=outbound_data.outbound_date,
        withdraw_person=outbound_data.withdraw_person,
        sap_status=outbound_data.sap_status,
        has_receipt=outbound_data.has_receipt,
        notes=outbound_data.notes
    )
    db.add(outbound)
    
    # Update stock based on SAP status
    if outbound_data.sap_status == "未录入":
        stock.unrecorded_withdrawn_qty += outbound_data.quantity
    else:  # 已录入
        stock.recorded_withdrawn_qty += outbound_data.quantity
    
    stock.last_outbound_date = outbound_data.outbound_date
    stock.actual_qty = stock.sap_qty + stock.unrecorded_sap_qty - stock.unrecorded_withdrawn_qty - stock.recorded_withdrawn_qty
    
    # Create movement record
    movement = StockMovement(
        stock_id=stock.id,
        material_id=outbound_data.material_id,
        movement_type="出库",
        quantity=outbound_data.quantity,
        movement_date=outbound_data.outbound_date,
        sap_status=outbound_data.sap_status,
        operator=outbound_data.withdraw_person,
        notes=outbound_data.notes
    )
    db.add(movement)
    
    db.commit()
    
    return {"success": True, "message": "出库成功"}


@router.delete("/outbound/{record_id}")
async def delete_outbound_record(record_id: int, db: Session = Depends(get_db)):
    """删除出库记录并回滚库存"""
    outbound = db.query(OutboundRecord).filter(OutboundRecord.id == record_id).first()
    if not outbound:
        raise HTTPException(status_code=404, detail="出库记录不存在")

    stock = db.query(WarehouseStock).filter(
        WarehouseStock.material_id == outbound.material_id
    ).first()

    if stock:
        # Rollback stock
        if outbound.sap_status == "未录入" or outbound.sap_status == "未录入SAP":
            stock.unrecorded_withdrawn_qty = max(0, stock.unrecorded_withdrawn_qty - outbound.quantity)
        else:
            stock.recorded_withdrawn_qty = max(0, stock.recorded_withdrawn_qty - outbound.quantity)
            
        stock.actual_qty = (stock.sap_qty or 0) + (stock.unrecorded_sap_qty or 0) - (stock.unrecorded_withdrawn_qty or 0) - (stock.recorded_withdrawn_qty or 0)
        
        # Try to find and delete the corresponding StockMovement
        # Since there's no direct foreign key, we match on exact details
        movement = db.query(StockMovement).filter(
            StockMovement.material_id == outbound.material_id,
            StockMovement.movement_type == "出库",
            StockMovement.quantity == outbound.quantity,
            StockMovement.operator == outbound.withdraw_person,
            StockMovement.movement_date == outbound.outbound_date
        ).first()
        
        if movement:
            db.delete(movement)
            
    db.delete(outbound)
    db.commit()
    
    return {"success": True, "message": "出库记录已删除，库存已回滚"}


@router.get("/outbound-history")
async def get_outbound_history(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    has_receipt: Optional[str] = None,
    withdraw_person: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取出库历史列表"""
    from sqlalchemy import or_
    query = db.query(OutboundRecord).options(
        joinedload(OutboundRecord.material)
    )
    
    if search:
        search_filter = f"%{search}%"
        query = query.join(Material).filter(
            or_(
                Material.sap_code.ilike(search_filter),
                Material.name_cn.ilike(search_filter),
                OutboundRecord.withdraw_person.ilike(search_filter)
            )
        )

    if has_receipt:
        query = query.filter(OutboundRecord.has_receipt == has_receipt)

    if withdraw_person:
        query = query.filter(OutboundRecord.withdraw_person == withdraw_person)
        
    total = query.count()
    records = query.order_by(OutboundRecord.outbound_date.desc(), OutboundRecord.id.desc()).offset(skip).limit(limit).all()
    
    result = []
    for rec in records:
        result.append({
            "id": rec.id,
            "material_id": rec.material_id,
            "quantity": rec.quantity,
            "outbound_date": rec.outbound_date.isoformat() if rec.outbound_date else None,
            "withdraw_person": rec.withdraw_person,
            "sap_status": rec.sap_status,
            "has_receipt": rec.has_receipt,
            "notes": rec.notes,
            "material": {
                "sap_code": rec.material.sap_code if rec.material else "",
                "name_cn": rec.material.name_cn if rec.material else "",
                "image": rec.material.image if rec.material else None,
                "drawing_pdf": rec.material.drawing_pdf if rec.material else None,
            }
        })
        
    withdraw_person_options = [
        p for (p,) in db.query(OutboundRecord.withdraw_person)
        .filter(OutboundRecord.withdraw_person.isnot(None), OutboundRecord.withdraw_person != "")
        .distinct()
        .order_by(OutboundRecord.withdraw_person.asc())
        .all()
        if p
    ]

    return {"total": total, "items": result, "withdraw_person_options": withdraw_person_options}

@router.get("/movements/{material_id}")
async def get_movements(
    material_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取物料出入库记录"""
    movements = db.query(StockMovement).filter(
        StockMovement.material_id == material_id
    ).order_by(StockMovement.movement_date.desc()).offset(skip).limit(limit).all()
    
    return movements


@router.get("/unrecorded-inbound/{material_id}")
async def get_unrecorded_inbound_records(material_id: int, db: Session = Depends(get_db)):
    """获取某物料未录入SAP的入库记录"""
    records = db.query(InboundRecord).join(OrderItem, InboundRecord.order_item_id == OrderItem.id).join(PurchaseOrder, OrderItem.order_id == PurchaseOrder.id).filter(
        OrderItem.material_id == material_id,
        InboundRecord.sap_status == "未录入SAP"
    ).order_by(InboundRecord.warehouse_receive_time.desc(), InboundRecord.id.desc()).all()

    items = []
    for rec in records:
        item = db.query(OrderItem).options(joinedload(OrderItem.order).joinedload(PurchaseOrder.supplier)).filter(OrderItem.id == rec.order_item_id).first()
        items.append({
            "id": rec.id,
            "received_qty": rec.received_qty,
            "warehouse_receive_time": rec.warehouse_receive_time.isoformat() if rec.warehouse_receive_time else None,
            "po_number": item.order.po_number if item and item.order else "",
            "supplier_name": item.order.supplier.name if item and item.order and item.order.supplier else "",
            "receiver": rec.receiver,
            "notes": rec.notes
        })

    return {"items": items}


@router.get("/direct-use-history/{material_id}")
async def get_direct_use_history(material_id: int, db: Session = Depends(get_db)):
    """获取某物料直接领用历史"""
    records = db.query(InboundRecord).join(OrderItem, InboundRecord.order_item_id == OrderItem.id).join(PurchaseOrder, OrderItem.order_id == PurchaseOrder.id).filter(
        OrderItem.material_id == material_id,
        InboundRecord.sap_status == "直接领用"
    ).order_by(InboundRecord.warehouse_receive_time.desc(), InboundRecord.id.desc()).all()

    items = []
    for rec in records:
        item = db.query(OrderItem).options(joinedload(OrderItem.order).joinedload(PurchaseOrder.supplier)).filter(OrderItem.id == rec.order_item_id).first()
        items.append({
            "id": rec.id,
            "received_qty": rec.received_qty,
            "warehouse_receive_time": rec.warehouse_receive_time.isoformat() if rec.warehouse_receive_time else None,
            "po_number": item.order.po_number if item and item.order else "",
            "supplier_name": item.order.supplier.name if item and item.order and item.order.supplier else "",
            "direct_use_person": rec.direct_use_person,
            "direct_use_workshop": rec.direct_use_workshop,
            "direct_use_photo": rec.direct_use_photo,
            "receiver": rec.receiver
        })

    return {"items": items}


@router.get("/locations")
async def get_locations(db: Session = Depends(get_db)):
    """获取所有库位"""
    locations = db.query(WarehouseStock.location).distinct().filter(
        WarehouseStock.location.isnot(None)
    ).all()
    
    return [loc[0] for loc in locations]


class TraceabilityRequest(BaseModel):
    material_ids: List[int]

@router.post("/traceability")
async def get_materials_traceability(request: TraceabilityRequest, db: Session = Depends(get_db)):
    """获取物料的完整入库出库溯源历史"""
    from app.models.warehouse import OperationLog, ReturnRecord
    from datetime import datetime, date
    
    result = []
    
    def to_dt(val):
        if isinstance(val, datetime): return val
        if isinstance(val, date): return datetime.combine(val, datetime.min.time())
        return datetime.min

    for mat_id in request.material_ids:
        material = db.query(Material).filter(Material.id == mat_id).first()
        if not material:
            continue
            
        mat_data = {
            "material_id": mat_id,
            "sap_code": material.sap_code,
            "name_cn": material.name_cn,
            "image": material.image,
            "drawing_pdf": material.drawing_pdf,
            "inbound_history": [],
            "outbound_history": []
        }
        
        # 1. Inbound history (from OrderItem and OperationLog events)
        order_items = db.query(OrderItem).options(
            joinedload(OrderItem.order).joinedload(PurchaseOrder.supplier)
        ).filter(OrderItem.material_id == mat_id).all()
        
        for item in order_items:
            history_events = []
            logs = db.query(OperationLog).filter(
                OperationLog.order_item_id == item.id
            ).order_by(OperationLog.created_at.asc()).all()
            
            for log in logs:
                history_events.append({
                    "time": log.created_at,
                    "action": log.action,
                    "operator": log.operator,
                    "quantity": log.quantity,
                    "detail": log.detail,
                    "delivery_note": item.delivery_note,
                    "quotation_file": item.quotation_file,
                    "invoice_file": item.invoice_file,
                    "direct_use_photo": None,
                    "direct_use_person": None,
                    "direct_use_workshop": None
                })

            inbound_records = db.query(InboundRecord).filter(InboundRecord.order_item_id == item.id).order_by(InboundRecord.warehouse_receive_time.asc(), InboundRecord.id.asc()).all()
            for rec in inbound_records:
                history_events.append({
                    "time": rec.warehouse_receive_time or rec.created_at,
                    "action": f"仓库收货({rec.sap_status})",
                    "operator": rec.receiver,
                    "quantity": rec.received_qty,
                    "detail": rec.notes,
                    "delivery_note": item.delivery_note,
                    "quotation_file": item.quotation_file,
                    "invoice_file": item.invoice_file,
                    "direct_use_photo": rec.direct_use_photo,
                    "direct_use_person": rec.direct_use_person,
                    "direct_use_workshop": rec.direct_use_workshop
                })
                
            # Fallback for old records without OperationLog
            if not logs:
                confirmed_at = item.order.updated_at if getattr(item.order, "updated_at", None) else item.order.order_date
                history_events.append({
                    "time": confirmed_at,
                    "action": "确认订单",
                    "operator": "系统生成",
                    "quantity": item.ordered_qty,
                    "detail": "基于老数据构造",
                    "delivery_note": item.delivery_note,
                    "quotation_file": item.quotation_file,
                    "invoice_file": item.invoice_file,
                    "direct_use_photo": None,
                    "direct_use_person": None,
                    "direct_use_workshop": None
                })
                if item.actual_delivery_date:
                    history_events.append({
                        "time": item.actual_delivery_date,
                        "action": "上传送货单",
                        "operator": "系统生成",
                        "quantity": item.ordered_qty,
                        "detail": "老记录送货日期",
                        "delivery_note": item.delivery_note,
                        "quotation_file": item.quotation_file,
                        "invoice_file": item.invoice_file,
                        "direct_use_photo": None,
                        "direct_use_person": None,
                        "direct_use_workshop": None
                    })

            history_events.sort(key=lambda e: to_dt(e.get("time")), reverse=False)
                    
            mat_data["inbound_history"].append({
                "order_item_id": item.id,
                "po_number": item.order.po_number if item.order else "",
                "supplier_name": item.order.supplier.name if item.order and item.order.supplier else "",
                "ordered_qty": item.ordered_qty,
                "first_time": history_events[0]["time"] if history_events else datetime.min,
                "events": history_events
            })
        
        # Sort inbound history by first event time desc
        mat_data["inbound_history"].sort(key=lambda x: to_dt(x["first_time"]), reverse=True)
        
        # 2. Outbound history
        outbound_records = db.query(OutboundRecord).filter(OutboundRecord.material_id == mat_id).order_by(OutboundRecord.outbound_date.desc()).all()
        for out in outbound_records:
            mat_data["outbound_history"].append({
                "outbound_date": out.outbound_date,
                "quantity": out.quantity,
                "withdraw_person": out.withdraw_person
            })
            
        result.append(mat_data)
        
    return {"data": result}

