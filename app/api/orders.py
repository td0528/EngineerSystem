"""
Purchase Orders API router - 采购订单管理
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, text
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date
import os
import shutil

from app.database.database import get_db
from app.models.orders import PurchaseOrder, OrderItem, Invoice
from app.models.materials import Material
from app.models.users import Supplier
from app.api.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploads/invoices"


class OrderItemCreate(BaseModel):
    material_id: int
    ordered_qty: int
    unit_price: Optional[float] = None
    required_date: Optional[date] = None  # Per-item required date
    workshop: Optional[str] = None  # Per-item workshop
    equipment: Optional[str] = None  # Per-item equipment
    purpose: Optional[str] = None  # Per-item purpose


class OrderCreate(BaseModel):
    po_number: Optional[str] = None  # Auto-generated if not provided
    order_type: str = "五金件"  # 五金件/机加工
    supplier_id: Optional[int] = None
    order_date: date
    items: List[OrderItemCreate]


class OrderUpdate(BaseModel):
    order_type: Optional[str] = None
    supplier_id: Optional[int] = None
    required_date: Optional[date] = None
    workshop: Optional[str] = None
    equipment: Optional[str] = None
    purpose: Optional[str] = None
    status: Optional[str] = None
    invoice_number: Optional[str] = None


@router.get("/")
async def get_orders(
    search: Optional[str] = None,
    order_type: Optional[str] = None,
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取采购订单列表"""
    query = db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.items)
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                PurchaseOrder.po_number.ilike(search_term),
                PurchaseOrder.workshop.ilike(search_term),
                PurchaseOrder.equipment.ilike(search_term)
            )
        )
    
    if order_type:
        query = query.filter(PurchaseOrder.order_type == order_type)
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    
    total = query.count()
    orders = query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": orders}


@router.get("/items")
async def get_order_items(
    search: Optional[str] = None,
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('desc'),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取所有订单明细（Excel样式逐行显示）"""
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).join(
        Material, OrderItem.material_id == Material.id
    ).options(
        joinedload(OrderItem.order).joinedload(PurchaseOrder.supplier),
        joinedload(OrderItem.material)
    )
    
    # Filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                PurchaseOrder.po_number.ilike(search_term),
                Material.sap_code.ilike(search_term),
                Material.name_cn.ilike(search_term),
                PurchaseOrder.workshop.ilike(search_term)
            )
        )
    
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    
    if status:
        query = query.filter(PurchaseOrder.status == status)
    
    # Sorting
    if sort_by:
        if sort_by == 'order_date':
            sort_col = PurchaseOrder.order_date
        elif sort_by == 'po_number':
            sort_col = PurchaseOrder.po_number
        elif sort_by == 'supplier_name':
            sort_col = Supplier.name
            query = query.outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        elif sort_by == 'sap_code':
            sort_col = Material.sap_code
        elif sort_by == 'material_name':
            sort_col = Material.name_cn
        elif sort_by == 'workshop':
            sort_col = PurchaseOrder.workshop
        else:
            sort_col = PurchaseOrder.order_date
            
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())
    else:
        from sqlalchemy import case
        query = query.order_by(
            case((OrderItem.item_status == '未下单', 0), (OrderItem.item_status == None, 0), else_=1),
            PurchaseOrder.order_date.desc(), 
            PurchaseOrder.id.desc()
        )
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    
    # Format response
    result = []
    for item in items:
        result.append({
            "id": item.id,
            "order_id": item.order_id,
            "po_number": item.order.po_number,
            "order_date": item.order.order_date.isoformat() if item.order.order_date else None,
            "supplier_name": item.order.supplier.name if item.order.supplier else "-",
            "supplier_id": item.order.supplier_id,
            "material_id": item.material_id,
            "sap_code": item.material.sap_code,
            "material_name": item.material.name_cn,
            "ordered_qty": item.ordered_qty,
            "received_qty": item.received_qty or 0,
            "unit_price": item.unit_price,
            "total_price": item.total_price,
            "material_image": item.material.image,
            "material_pdf": item.material.drawing_pdf,
            # Per-item fields (new)
            "required_date": item.required_date.isoformat() if item.required_date else None,
            "workshop": item.workshop,
            "equipment": item.equipment,
            "purpose": item.purpose,
            # New PO enhancement fields
            "arrival_date": item.arrival_date.isoformat() if item.arrival_date else None,
            "item_status": item.item_status or "等待采购",
            "quotation_file": item.quotation_file,
            "currency": item.currency or "VND",
            "status": item.order.status
        })
    
    return {"total": total, "items": result}


@router.put("/items/{item_id}")
async def update_order_item(item_id: int, data: dict, db: Session = Depends(get_db)):
    """更新单个订单明细"""
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="订单明细不存在")
    
    # Update allowed fields
    if "ordered_qty" in data:
        item.ordered_qty = data["ordered_qty"]
        item.total_price = (item.unit_price or 0) * data["ordered_qty"]
    if "unit_price" in data:
        item.unit_price = data["unit_price"]
        item.total_price = data["unit_price"] * (item.ordered_qty or 0)
    if "currency" in data and data["currency"] in ["VND", "USD"]:
        item.currency = data["currency"]
    
    # Per-item fields
    if "required_date" in data:
        from datetime import datetime
        if data["required_date"]:
            item.required_date = datetime.strptime(data["required_date"], "%Y-%m-%d").date()
        else:
            item.required_date = None
    if "workshop" in data:
        item.workshop = data["workshop"]
        # Sync to material
        if data["workshop"] and item.material:
            existing = set(item.material.workshop.split(',')) if item.material.workshop else set()
            existing.discard('')
            existing.add(data["workshop"])
            item.material.workshop = ','.join(sorted(existing))
    if "equipment" in data:
        item.equipment = data["equipment"]
        # Sync to material
        if data["equipment"] and item.material:
            existing = set(item.material.equipment.split(',')) if item.material.equipment else set()
            existing.discard('')
            existing.add(data["equipment"])
            item.material.equipment = ','.join(sorted(existing))
    if "purpose" in data:
        item.purpose = data["purpose"]
    
    # New fields for PO enhancements
    if "arrival_date" in data:
        from datetime import datetime
        if data["arrival_date"]:
            item.arrival_date = datetime.strptime(data["arrival_date"], "%Y-%m-%d").date()
        else:
            item.arrival_date = None
    
    # Allow explicit status update (for supplier/admin actions)
    if "item_status" in data and data["item_status"] in ["未下单", "已下单", "已确认", "已送货", "已收货", "已开发票", "退货中"]:
        item.item_status = data["item_status"]
    else:
        # Auto-calculate status: if supplier and arrival_date are set, auto-set to "已下单"
        order = item.order
        if order.supplier_id and item.arrival_date:
            if item.item_status in [None, "未下单"]:
                item.item_status = "已下单"
        elif not order.supplier_id or not item.arrival_date:
            if item.item_status not in ["已送货", "已收货", "已开发票"]:
                item.item_status = "未下单"
    
    # Recalculate order total
    order = item.order
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    
    db.commit()
    return {"message": "更新成功"}


@router.delete("/items/{item_id}")
async def delete_order_item(
    item_id: int, 
    force: bool = False,
    password: Optional[str] = None,
    db: Session = Depends(get_db)):
    """删除单个订单明细"""
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="订单明细不存在")
    
    # Check deletion constraints
    if force:
        if password != "970528":
            raise HTTPException(status_code=401, detail="强制删除密码错误")
    else:
        if item.item_status not in [None, "未下单", "已下单"]:
            raise HTTPException(status_code=400, detail="只能删除状态为'未下单'或'已下单'的订单项")
    
    from app.models.warehouse import StockMovement, InboundRecord, ReturnRecord, OperationLog
    from app.models.orders import SupplierQuote
    
    # Cascade delete auxiliary records
    db.query(ReturnRecord).filter(ReturnRecord.order_item_id == item_id).delete()
    db.query(SupplierQuote).filter(SupplierQuote.order_item_id == item_id).delete()
    db.query(InboundRecord).filter(InboundRecord.order_item_id == item_id).delete()
    db.query(StockMovement).filter(StockMovement.order_item_id == item_id).delete()
    db.query(OperationLog).filter(OperationLog.order_item_id == item_id).delete()
    db.flush()
    
    order = item.order
    db.delete(item)
    
    # Recalculate order total
    order.total_amount = sum(i.total_price or 0 for i in order.items if i.id != item_id)
    
    # Delete order if no items left
    remaining = db.query(OrderItem).filter(OrderItem.order_id == order.id).count()
    if remaining == 0:
        db.delete(order)
    
    db.commit()
    return {"message": "删除成功"}


class BatchDeleteRequest(BaseModel):
    ids: List[int]
    force: bool = False
    password: Optional[str] = None

@router.post("/items/batch-delete")
async def batch_delete_order_items(request: BatchDeleteRequest, db: Session = Depends(get_db)):
    """批量删除订单明细"""
    if not request.ids:
        raise HTTPException(status_code=400, detail="请选择要删除的明细")
    
    items = db.query(OrderItem).filter(OrderItem.id.in_(request.ids)).all()
    if not items:
        raise HTTPException(status_code=404, detail="未找到要删除的明细")
    
    # Check deletion constraints
    if request.force:
        if request.password != "970528":
            raise HTTPException(status_code=401, detail="强制删除密码错误")
    else:
        for item in items:
            if item.item_status not in [None, "未下单", "已下单"]:
                raise HTTPException(status_code=400, detail=f"行号为 {item.id} 的状态不允许删除（仅限未下单/已下单）")
    
    # Track affected orders
    affected_orders = set()
    from app.models.warehouse import StockMovement, InboundRecord, ReturnRecord, OperationLog
    from app.models.orders import SupplierQuote
    
    for item in items:
        # Cascade delete auxiliary records
        db.query(ReturnRecord).filter(ReturnRecord.order_item_id == item.id).delete()
        db.query(SupplierQuote).filter(SupplierQuote.order_item_id == item.id).delete()
        db.query(InboundRecord).filter(InboundRecord.order_item_id == item.id).delete()
        db.query(StockMovement).filter(StockMovement.order_item_id == item.id).delete()
        db.query(OperationLog).filter(OperationLog.order_item_id == item.id).delete()
        
        affected_orders.add(item.order_id)
        db.delete(item)
    
    db.flush()
    
    # Recalculate totals and clean up empty orders
    for order_id in affected_orders:
        order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
        if order:
            remaining = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
            if not remaining:
                db.delete(order)
            else:
                order.total_amount = sum(i.total_price or 0 for i in remaining)
    
    db.commit()
    return {"message": f"已删除 {len(items)} 条明细", "deleted_count": len(items)}


@router.post("/items/{item_id}/move")
async def move_order_item(item_id: int, data: dict, db: Session = Depends(get_db)):
    """将订单明细移动到不同供应商的订单"""
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="订单明细不存在")
    
    new_supplier_id = data.get("new_supplier_id")
    # Convert empty/0 to None for consistent comparison
    if not new_supplier_id:
        new_supplier_id = None
    
    old_order = item.order
    old_supplier_id = old_order.supplier_id
    
    # If same supplier, no need to move
    if new_supplier_id == old_supplier_id:
        return {"message": "供应商未变更", "po_number": old_order.po_number}
    
    # Validate new supplier if provided
    new_supplier = None
    if new_supplier_id:
        new_supplier = db.query(Supplier).filter(Supplier.id == new_supplier_id).first()
        if not new_supplier:
            raise HTTPException(status_code=400, detail="供应商不存在")
    
    # Find or create order for new supplier with same date
    target_order = None
    if new_supplier_id:
        # Look for existing order with same supplier and date
        target_order = db.query(PurchaseOrder).filter(
            PurchaseOrder.supplier_id == new_supplier_id,
            PurchaseOrder.order_date == old_order.order_date
        ).first()
    else:
        # Look for order without supplier on same date
        target_order = db.query(PurchaseOrder).filter(
            PurchaseOrder.supplier_id == None,
            PurchaseOrder.order_date == old_order.order_date
        ).first()
    
    if not target_order:
        # Create new order
        date_str = old_order.order_date.strftime('%Y%m%d')
        prefix = new_supplier.name if new_supplier else "PO"
        base_po = f"{prefix}_{date_str}"
        
        # Check for existing POs with same base
        existing_count = db.query(PurchaseOrder).filter(
            PurchaseOrder.po_number.like(f"{base_po}%")
        ).count()
        
        po_number = base_po if existing_count == 0 else f"{base_po}_{existing_count + 1}"
        
        target_order = PurchaseOrder(
            po_number=po_number,
            order_type=old_order.order_type,
            supplier_id=new_supplier_id,
            order_date=old_order.order_date,
            status="已提交"
        )
        db.add(target_order)
        db.flush()
    
    # Store IDs before modifying relationships
    old_order_id = old_order.id
    target_order_id = target_order.id
    item_total_price = item.total_price or 0
    
    # Use raw SQL update to bypass ORM cascade="delete-orphan" 
    # which would delete the item when changing order_id
    db.execute(
        text(f"UPDATE order_items SET order_id = {target_order_id} WHERE id = {item_id}")
    )
    
    # Recalculate old order total using raw query
    old_order.total_amount = (old_order.total_amount or 0) - item_total_price
    if old_order.total_amount < 0:
        old_order.total_amount = 0
    
    # Delete old order if empty
    remaining = db.query(OrderItem).filter(
        OrderItem.order_id == old_order_id
    ).count()
    if remaining == 0:
        db.delete(old_order)
    
    # Recalculate target order total
    target_order.total_amount = (target_order.total_amount or 0) + item_total_price
    
    db.commit()
    return {"message": "已移动到新订单", "new_po_number": target_order.po_number}


@router.get("/by-po/{po_number}")
async def get_order_by_po(po_number: str, db: Session = Depends(get_db)):
    """根据PO号获取订单详情（入库时用）"""
    order = db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.items).joinedload(OrderItem.material)
    ).filter(PurchaseOrder.po_number == po_number).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # Return items that can still be received
    receivable_items = [
        {
            "id": item.id,
            "material": {
                "id": item.material.id,
                "sap_code": item.material.sap_code,
                "name_cn": item.material.name_cn,
                "name_vn": item.material.name_vn,
                "image": item.material.image
            },
            "ordered_qty": item.ordered_qty,
            "received_qty": item.received_qty,
            "remaining_qty": item.ordered_qty - item.received_qty,
            "is_fully_received": item.is_fully_received,
            "can_receive": item.ordered_qty > item.received_qty
        }
        for item in order.items
    ]
    
    return {
        "order": {
            "id": order.id,
            "po_number": order.po_number,
            "order_type": order.order_type,
            "supplier": order.supplier,
            "order_date": order.order_date,
            "required_date": order.required_date,
            "status": order.status
        },
        "items": receivable_items
    }


@router.get("/{order_id}")
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """获取订单详情"""
    order = db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.items).joinedload(OrderItem.material)
    ).filter(PurchaseOrder.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    return order


@router.post("/")
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """创建采购订单"""
    try:
        # Validate supplier exists (if provided)
        supplier = None
        if order_data.supplier_id:
            supplier = db.query(Supplier).filter(Supplier.id == order_data.supplier_id).first()
            if not supplier:
                raise HTTPException(status_code=400, detail=f"供应商不存在 (ID: {order_data.supplier_id})")
        
        # Auto-generate PO number if not provided
        if not order_data.po_number:
            date_str = order_data.order_date.strftime('%Y%m%d')
            prefix = supplier.name if supplier else "PO"
            base_po = f"{prefix}_{date_str}"
            
            # Check for existing POs with same base
            existing_count = db.query(PurchaseOrder).filter(
                PurchaseOrder.po_number.like(f"{base_po}%")
            ).count()
            
            if existing_count == 0:
                po_number = base_po
            else:
                po_number = f"{base_po}-{existing_count}"
        else:
            po_number = order_data.po_number
            # Check if PO number exists
            if db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first():
                raise HTTPException(status_code=400, detail="PO号码已存在")
        
        # Validate items
        if not order_data.items or len(order_data.items) == 0:
            raise HTTPException(status_code=400, detail="订单必须包含至少一个物料")
        
        # Validate all materials exist
        for idx, item_data in enumerate(order_data.items):
            material = db.query(Material).filter(Material.id == item_data.material_id).first()
            if not material:
                raise HTTPException(status_code=400, detail=f"物料不存在 (ID: {item_data.material_id}, 行: {idx+1})")
        
        # Create order
        new_order = PurchaseOrder(
            po_number=po_number,
            order_type=order_data.order_type,
            supplier_id=order_data.supplier_id,
            order_date=order_data.order_date,
            status="已提交"
        )
        db.add(new_order)
        db.flush()
        
        # Create order items and record prices
        total_amount = 0
        for item_data in order_data.items:
            item = OrderItem(
                order_id=new_order.id,
                material_id=item_data.material_id,
                ordered_qty=item_data.ordered_qty,
                unit_price=item_data.unit_price,
                total_price=(item_data.unit_price or 0) * item_data.ordered_qty,
                required_date=item_data.required_date,
                workshop=item_data.workshop,
                equipment=item_data.equipment,
                purpose=item_data.purpose
            )
            total_amount += item.total_price or 0
            db.add(item)
            
            # Sync workshop/equipment to material record
            if item_data.workshop or item_data.equipment:
                material = db.query(Material).filter(Material.id == item_data.material_id).first()
                if material:
                    # Workshop: Append to comma-separated list if not exists
                    if item_data.workshop:
                        existing_workshops = set(material.workshop.split(',')) if material.workshop else set()
                        existing_workshops.discard('')
                        existing_workshops.add(item_data.workshop)
                        material.workshop = ','.join(sorted(existing_workshops))
                    
                    # Equipment: Append to comma-separated list if not exists
                    if item_data.equipment:
                        existing_equipment = set(material.equipment.split(',')) if material.equipment else set()
                        existing_equipment.discard('')
                        existing_equipment.add(item_data.equipment)
                        material.equipment = ','.join(sorted(existing_equipment))
            
            # Auto-record price history from order
            if item_data.unit_price and item_data.unit_price > 0:
                from app.models.materials import MaterialPrice
                price_record = MaterialPrice(
                    material_id=item_data.material_id,
                    price=item_data.unit_price,
                    currency="VND",
                    supplier_id=order_data.supplier_id,
                    notes=f"采购订单 {po_number}"
                )
                db.add(price_record)
        
        new_order.total_amount = total_amount
        db.commit()
        db.refresh(new_order)
        
        return new_order
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建订单失败: {str(e)}")


@router.put("/{order_id}")
async def update_order(order_id: int, order_data: OrderUpdate, db: Session = Depends(get_db)):
    """更新采购订单"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    for key, value in order_data.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/invoice")
async def upload_invoice(
    order_id: int,
    invoice_number: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传发票"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # Save file
    file_name = f"invoice_{order.po_number}_{invoice_number}.pdf"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    order.invoice_number = invoice_number
    order.invoice_file = f"/uploads/invoices/{file_name}"
    db.commit()
    
    return {"invoice_url": order.invoice_file}


@router.get("/suppliers/search")
async def search_suppliers(
    q: str = Query(""),
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """供应商搜索（下拉选择用）"""
    query = db.query(Supplier).filter(Supplier.is_active == True)
    
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Supplier.name.ilike(search_term),
                Supplier.code.ilike(search_term)
            )
        )
    
    suppliers = query.limit(limit).all()
    
    return [
        {"id": s.id, "code": s.code, "name": s.name}
        for s in suppliers
    ]


@router.post("/suppliers")
async def create_supplier(
    name: str,
    code: str,
    password: str,
    contact_person: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """创建供应商"""
    from app.api.auth import get_password_hash
    
    if db.query(Supplier).filter(Supplier.code == code).first():
        raise HTTPException(status_code=400, detail="供应商代码已存在")
    
    new_supplier = Supplier(
        name=name,
        code=code,
        password_hash=get_password_hash(password),
        contact_person=contact_person,
        phone=phone,
        email=email
    )
    db.add(new_supplier)
    db.commit()
    db.refresh(new_supplier)
    
    return new_supplier


@router.get("/suppliers/all")
async def get_all_suppliers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取所有供应商（包括禁用的）"""
    suppliers = db.query(Supplier).offset(skip).limit(limit).all()
    return suppliers


@router.put("/suppliers/{supplier_id}/password")
async def reset_supplier_password(
    supplier_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """重置供应商密码"""
    from app.api.auth import get_password_hash
    
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    new_password = data.get("password")
    if not new_password:
        raise HTTPException(status_code=400, detail="密码不能为空")
    
    supplier.password_hash = get_password_hash(new_password)
    db.commit()
    
    return {"message": "密码已重置"}


@router.put("/suppliers/{supplier_id}/status")
async def toggle_supplier_status(
    supplier_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """启用/禁用供应商"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    supplier.is_active = data.get("is_active", True)
    db.commit()
    
    return {"message": "状态已更新", "is_active": supplier.is_active}


@router.delete("/suppliers/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db)
):
    """删除供应商"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    
    # Check if supplier has orders
    order_count = db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == supplier_id).count()
    if order_count > 0:
        raise HTTPException(status_code=400, detail=f"此供应商有 {order_count} 个订单，无法删除。请先禁用。")
    
    db.delete(supplier)
    db.commit()
    
    return {"message": "供应商已删除"}


# ===== NEW: Quotation PDF Upload =====
QUOTATION_DIR = "uploads/quotations"

@router.post("/items/{item_id}/quotation")
async def upload_quotation(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传订单明细的报价单PDF"""
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="订单明细不存在")
    
    # Ensure directory exists
    os.makedirs(QUOTATION_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"quotation_{item_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = os.path.join(QUOTATION_DIR, filename)
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update item
    item.quotation_file = filepath
    db.commit()
    
    return {"message": "报价单上传成功", "path": filepath}


@router.get("/items/{item_id}/quotation")
async def get_quotation(item_id: int, db: Session = Depends(get_db)):
    """获取报价单文件路径"""
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item or not item.quotation_file:
        raise HTTPException(status_code=404, detail="报价单不存在")
    return {"path": item.quotation_file}


# ===== NEW: Price History for Materials =====
@router.get("/materials/{material_id}/price-history")
async def get_material_price_history(
    material_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取物料的历史价格（用于下拉选择）"""
    # Get distinct prices from order items for this material
    items = db.query(OrderItem).filter(
        OrderItem.material_id == material_id,
        OrderItem.unit_price != None
    ).order_by(OrderItem.created_at.desc()).limit(limit * 2).all()
    
    # Deduplicate prices while preserving order
    seen = set()
    prices = []
    for item in items:
        if item.unit_price not in seen:
            seen.add(item.unit_price)
            prices.append({
                "price": item.unit_price,
                "date": item.created_at.isoformat() if item.created_at else None,
                "supplier": item.order.supplier.name if item.order and item.order.supplier else None
            })
            if len(prices) >= limit:
                break
    
    return prices


# ===== Order Import from Excel/CSV =====

ORDER_IMPORT_COLUMN_MAPPING = {
    "sap_code": ["sap", "sap号", "sap号码", "sap_code", "sap code", "编码", "料号"],
    "material_name": ["物料", "物料名称", "名称", "material", "material_name"],
    "ordered_qty": ["数量", "qty", "quantity", "ordered_qty", "订购数量"],
    "unit_price": ["单价", "price", "unit_price", "价格"],
    "supplier": ["供应商", "supplier", "vendor", "供货商"],
    "workshop": ["车间", "workshop"],
    "equipment": ["设备", "equipment", "machine"],
    "item_status": ["状态", "status", "item_status"],
    "arrival_date": ["到货时间", "到货日期", "arrival", "arrival_date"],
    "order_date": ["采购日期", "订单日期", "order_date", "date", "日期"],
    "po_number": ["po号", "po", "po_number", "订单号"],
}


@router.post("/import")
async def import_orders(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从Excel/CSV导入采购订单数据"""
    import pandas as pd
    import io
    
    content = await file.read()
    errors = []
    
    # Read file
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    
    if df.empty:
        raise HTTPException(status_code=400, detail="文件中没有数据")
    
    # Map columns
    column_map = {}
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for field, aliases in ORDER_IMPORT_COLUMN_MAPPING.items():
            if col_lower in aliases or col_lower == field:
                column_map[field] = col
                break
    
    # Validate required columns
    if "sap_code" not in column_map and "material_name" not in column_map:
        raise HTTPException(status_code=400, detail="缺少必需列: SAP号码 或 物料名称")
    if "ordered_qty" not in column_map:
        raise HTTPException(status_code=400, detail="缺少必需列: 数量")
    
    # Process rows - group by supplier + date
    orders_created = 0
    items_created = 0
    order_cache = {}  # key: (supplier_id, order_date_str) -> PurchaseOrder
    
    today = date.today()
    
    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row (1-indexed header + 1)
        
        try:
            # Find material
            material = None
            sap_code = str(row.get(column_map.get("sap_code", ""), "")).strip() if "sap_code" in column_map else ""
            mat_name = str(row.get(column_map.get("material_name", ""), "")).strip() if "material_name" in column_map else ""
            
            # Remove NaN
            if sap_code.lower() == "nan":
                sap_code = ""
            if mat_name.lower() == "nan":
                mat_name = ""
            
            if sap_code:
                material = db.query(Material).filter(Material.sap_code == sap_code).first()
            if not material and mat_name:
                material = db.query(Material).filter(Material.name_cn == mat_name).first()
            
            if not material:
                errors.append(f"第{row_num}行: 未找到物料 (SAP: {sap_code}, 名称: {mat_name})")
                continue
            
            # Parse quantity
            try:
                qty = int(float(str(row.get(column_map.get("ordered_qty", ""), 0))))
                if qty <= 0:
                    errors.append(f"第{row_num}行: 数量必须大于0")
                    continue
            except (ValueError, TypeError):
                errors.append(f"第{row_num}行: 数量格式错误")
                continue
            
            # Parse unit price
            unit_price = None
            if "unit_price" in column_map:
                try:
                    price_val = row.get(column_map["unit_price"], "")
                    if pd.notna(price_val) and str(price_val).strip():
                        unit_price = float(str(price_val).strip())
                except (ValueError, TypeError):
                    pass
            
            # Find supplier
            supplier_id = None
            supplier_name_val = ""
            if "supplier" in column_map:
                supplier_name_val = str(row.get(column_map["supplier"], "")).strip()
                if supplier_name_val and supplier_name_val.lower() != "nan":
                    supplier = db.query(Supplier).filter(Supplier.name == supplier_name_val).first()
                    if supplier:
                        supplier_id = supplier.id
                    else:
                        errors.append(f"第{row_num}行: 未找到供应商 '{supplier_name_val}'，已跳过供应商匹配")
            
            # Parse order date
            order_date = today
            if "order_date" in column_map:
                date_val = row.get(column_map["order_date"], "")
                if pd.notna(date_val):
                    try:
                        if isinstance(date_val, (datetime, date)):
                            order_date = date_val if isinstance(date_val, date) else date_val.date()
                        else:
                            date_str = str(date_val).strip()
                            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"]:
                                try:
                                    order_date = datetime.strptime(date_str, fmt).date()
                                    break
                                except ValueError:
                                    continue
                    except Exception:
                        pass
            
            # Find or create order
            cache_key = (supplier_id, order_date.isoformat())
            if cache_key not in order_cache:
                # Check for existing order
                q = db.query(PurchaseOrder).filter(
                    PurchaseOrder.order_date == order_date,
                    PurchaseOrder.supplier_id == supplier_id
                )
                existing_order = q.first()
                
                if existing_order:
                    order_cache[cache_key] = existing_order
                else:
                    # Create new order
                    date_str = order_date.strftime('%Y%m%d')
                    if supplier_id:
                        s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
                        prefix = s.name if s else "PO"
                    else:
                        prefix = "PO"
                    base_po = f"{prefix}_{date_str}"
                    
                    existing_count = db.query(PurchaseOrder).filter(
                        PurchaseOrder.po_number.like(f"{base_po}%")
                    ).count()
                    
                    po_number = base_po if existing_count == 0 else f"{base_po}-{existing_count}"
                    
                    new_order = PurchaseOrder(
                        po_number=po_number,
                        supplier_id=supplier_id,
                        order_date=order_date,
                        status="已提交"
                    )
                    db.add(new_order)
                    db.flush()
                    order_cache[cache_key] = new_order
                    orders_created += 1
            
            order = order_cache[cache_key]
            
            # Parse optional fields
            workshop = ""
            if "workshop" in column_map:
                ws = str(row.get(column_map["workshop"], "")).strip()
                if ws and ws.lower() != "nan":
                    workshop = ws
            
            equipment = ""
            if "equipment" in column_map:
                eq = str(row.get(column_map["equipment"], "")).strip()
                if eq and eq.lower() != "nan":
                    equipment = eq
            
            item_status = None
            if "item_status" in column_map:
                st = str(row.get(column_map["item_status"], "")).strip()
                if st and st.lower() != "nan" and st in ["未下单", "已下单", "已送货", "已收货", "已开发票"]:
                    item_status = st
            
            arrival_date = None
            if "arrival_date" in column_map:
                ad_val = row.get(column_map["arrival_date"], "")
                if pd.notna(ad_val):
                    try:
                        if isinstance(ad_val, (datetime, date)):
                            arrival_date = ad_val if isinstance(ad_val, date) else ad_val.date()
                        else:
                            ad_str = str(ad_val).strip()
                            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"]:
                                try:
                                    arrival_date = datetime.strptime(ad_str, fmt).date()
                                    break
                                except ValueError:
                                    continue
                    except Exception:
                        pass
            
            # Create order item
            new_item = OrderItem(
                order_id=order.id,
                material_id=material.id,
                ordered_qty=qty,
                unit_price=unit_price,
                total_price=(unit_price or 0) * qty,
                workshop=workshop or None,
                equipment=equipment or None,
                item_status=item_status,
                arrival_date=arrival_date
            )
            db.add(new_item)
            items_created += 1
            
        except Exception as e:
            errors.append(f"第{row_num}行: {str(e)}")
            continue
    
    # Recalculate order totals
    for order in order_cache.values():
        db.flush()
        total = sum(i.total_price or 0 for i in db.query(OrderItem).filter(OrderItem.order_id == order.id).all())
        order.total_amount = total
    
    db.commit()
    
    return {
        "orders_created": orders_created,
        "items_created": items_created,
        "errors": errors
    }

