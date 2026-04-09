"""
Supplier Portal API router - 供应商门户
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session, joinedload
from app.database.database import get_db
from app.api.auth import get_current_user
from app.models.orders import PurchaseOrder, OrderItem, SupplierQuote
from app.models.users import Supplier
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
import shutil
from app.models.warehouse import ReturnRecord, add_operation_log

router = APIRouter()

INVOICE_DIR = "uploads/invoices"
DELIVERY_NOTES_DIR = "uploads/delivery_notes"
QUOTATION_DIR = "uploads/quotations"


class QuoteUpdate(BaseModel):
    quoted_price: float
    notes: Optional[str] = None


@router.get("/orders")
async def get_supplier_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """获取供应商的采购订单列表"""
    if not isinstance(current_user, Supplier):
        raise HTTPException(status_code=403, detail="仅供应商可访问")
    
    supplier_id = current_user.id
    
    query = db.query(PurchaseOrder).filter(
        PurchaseOrder.supplier_id == supplier_id
    ).options(joinedload(PurchaseOrder.items))
    
    if status:
        query = query.filter(PurchaseOrder.status == status)
    
    total = query.count()
    orders = query.order_by(PurchaseOrder.order_date.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "orders": orders}


@router.get("/orders/{order_id}")
async def get_supplier_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """获取订单详情"""
    if not isinstance(current_user, Supplier):
        raise HTTPException(status_code=403, detail="仅供应商可访问")
    
    supplier_id = current_user.id
    
    order = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.supplier_id == supplier_id
    ).options(joinedload(PurchaseOrder.items).joinedload(OrderItem.material)).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    return order


@router.post("/orders/{order_id}/items/{item_id}/quote")
async def submit_quote(
    order_id: int,
    item_id: int,
    quote_data: QuoteUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """供应商提交报价"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        # Admin - get supplier_id from order
        order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        supplier_id = order.supplier_id
    elif isinstance(current_user, Supplier):
        supplier_id = current_user.id
        # Verify order belongs to supplier
        order = db.query(PurchaseOrder).filter(
            PurchaseOrder.id == order_id,
            PurchaseOrder.supplier_id == supplier_id
        ).first()
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # Get order item
    item = db.query(OrderItem).filter(
        OrderItem.id == item_id,
        OrderItem.order_id == order_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="订单项不存在")
    
    # Create or update quote
    quote = db.query(SupplierQuote).filter(
        SupplierQuote.order_item_id == item_id,
        SupplierQuote.supplier_id == supplier_id
    ).first()
    
    if quote:
        quote.quoted_price = quote_data.quoted_price
        quote.notes = quote_data.notes
        quote.quoted_date = datetime.utcnow()
    else:
        quote = SupplierQuote(
            order_item_id=item_id,
            supplier_id=supplier_id,
            quoted_price=quote_data.quoted_price,
            notes=quote_data.notes
        )
        db.add(quote)
    
    # Update order item price
    item.unit_price = quote_data.quoted_price
    item.total_price = quote_data.quoted_price * item.ordered_qty
    
    # Update order total
    order.total_amount = sum(i.total_price or 0 for i in order.items)
    
    db.commit()
    db.refresh(quote)
    
    return quote


@router.post("/orders/{order_id}/invoice")
async def upload_supplier_invoice(
    order_id: int,
    invoice_number: str = Form(...),
    item_ids: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """供应商上传发票"""
    if not isinstance(current_user, Supplier):
        raise HTTPException(status_code=403, detail="仅供应商可访问")
    
    supplier_id = current_user.id
    
    # Verify order belongs to supplier
    order = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.supplier_id == supplier_id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # Ensure directory exists
    os.makedirs(INVOICE_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"invoice_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = f"{INVOICE_DIR}/{filename}"
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update order
    order.invoice_number = invoice_number
    order.invoice_file = filepath
    order.status = "已开票"
    
    db.commit()
    
    return {"message": "发票上传成功", "path": filepath}


@router.get("/summary")
async def get_supplier_summary(
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """获取供应商汇总信息"""
    if not isinstance(current_user, Supplier):
        raise HTTPException(status_code=403, detail="仅供应商可访问")
    
    supplier_id = current_user.id
    
    # Count orders by status
    total_orders = db.query(PurchaseOrder).filter(
        PurchaseOrder.supplier_id == supplier_id
    ).count()
    
    pending_orders = db.query(PurchaseOrder).filter(
        PurchaseOrder.supplier_id == supplier_id,
        PurchaseOrder.status == "待处理"
    ).count()
    
    # Count items
    total_items = db.query(OrderItem).join(
        PurchaseOrder
    ).filter(
        PurchaseOrder.supplier_id == supplier_id
    ).count()
    
    pending_items = db.query(OrderItem).join(
        PurchaseOrder
    ).filter(
        PurchaseOrder.supplier_id == supplier_id,
        OrderItem.item_status == "已下单"
    ).count()
    
    delivering_items = db.query(OrderItem).join(
        PurchaseOrder
    ).filter(
        PurchaseOrder.supplier_id == supplier_id,
        OrderItem.item_status.in_(["已送货", "已收货"])
    ).count()
    
    completed_items = db.query(OrderItem).join(
        PurchaseOrder
    ).filter(
        PurchaseOrder.supplier_id == supplier_id,
        OrderItem.item_status == "已开发票"
    ).count()
    
    return {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "total_items": total_items,
        "pending_items": pending_items,
        "delivering_items": delivering_items,
        "completed_items": completed_items
    }


class ItemStatusUpdate(BaseModel):
    item_status: str


@router.put("/orders/{order_id}/items/{item_id}/status")
async def update_item_status(
    order_id: int,
    item_id: int,
    status_data: ItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """供应商更新订单项状态（送货中/已开票）"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        target_supplier_id = None
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    # Validate status - suppliers can set these statuses
    allowed_statuses = ["已下单", "已送货", "已开发票"]
    if status_data.item_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"状态只能是: {', '.join(allowed_statuses)}")
    
    # Verify order
    query = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id)
    if target_supplier_id is not None:
        query = query.filter(PurchaseOrder.supplier_id == target_supplier_id)
    order = query.first()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # Get order item
    item = db.query(OrderItem).filter(
        OrderItem.id == item_id,
        OrderItem.order_id == order_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="订单项不存在")
    
    # Update status
    item.item_status = status_data.item_status
    db.commit()
    
    return {"message": "状态更新成功", "item_status": item.item_status}


@router.post("/orders/{order_id}/items/{item_id}/quotation")
async def upload_item_quotation(
    order_id: int,
    item_id: int,
    supplier_id: int,  # 从token中获取
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """供应商上传订单项报价单PDF"""
    # Verify order belongs to supplier
    order = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == order_id,
        PurchaseOrder.supplier_id == supplier_id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    item = db.query(OrderItem).filter(
        OrderItem.id == item_id,
        OrderItem.order_id == order_id
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="订单项不存在")
    
    # Ensure directory exists
    os.makedirs(QUOTATION_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"quotation_{supplier_id}_{item_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = f"{QUOTATION_DIR}/{filename}"
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update item
    item.quotation_file = filepath
    item.quotation_date = datetime.now().date()  # Always use today's date
    db.commit()
    
    return {"message": "报价单上传成功", "path": filepath}


class BatchStatusUpdate(BaseModel):
    item_ids: list
    item_status: str


@router.get("/items")
async def get_supplier_items(
    supplier_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    material_name: Optional[str] = None,
    order_date: Optional[str] = None,
    arrival_date: Optional[str] = None,
    quotation_date: Optional[str] = None,
    delivery_date: Optional[str] = None,
    invoice_date: Optional[str] = None,
    locked_ids: Optional[str] = None,
    sort_by: Optional[str] = "date_desc",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取供应商的所有订单项（扁平列表，Excel样式）"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        if not supplier_id:
            raise HTTPException(status_code=400, detail="管理员请提供 supplier_id 参数")
        target_supplier_id = supplier_id
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    from app.models.materials import Material
    from sqlalchemy import or_, text
    
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).join(
        Material, OrderItem.material_id == Material.id
    ).options(
        joinedload(OrderItem.order),
        joinedload(OrderItem.material)
    ).filter(
        PurchaseOrder.supplier_id == target_supplier_id,
        OrderItem.item_status != "未下单"  # Hide items not yet ordered from supplier
    )
    
    from sqlalchemy import and_
    optional_filters = []
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        optional_filters.append(
            or_(
                PurchaseOrder.po_number.ilike(search_term),
                Material.sap_code.ilike(search_term),
                Material.name_cn.ilike(search_term)
            )
        )
    
    # Status filter
    if status:
        status_list = [s.strip() for s in status.split(',')]
        if len(status_list) > 1:
            optional_filters.append(OrderItem.item_status.in_(status_list))
        else:
            optional_filters.append(OrderItem.item_status == status)
    
    # Column filters
    if material_name:
        optional_filters.append(Material.name_cn.ilike(f"%{material_name}%"))
    if order_date:
        optional_filters.append(text("CAST(purchase_orders.order_date AS TEXT) LIKE :date_od").bindparams(date_od=f"%{order_date}%"))
    if arrival_date:
        optional_filters.append(text("CAST(order_items.arrival_date AS TEXT) LIKE :date_ad").bindparams(date_ad=f"%{arrival_date}%"))
    if quotation_date:
        optional_filters.append(text("CAST(order_items.quotation_date AS TEXT) LIKE :date_qd").bindparams(date_qd=f"%{quotation_date}%"))
    if delivery_date:
        optional_filters.append(text("CAST(order_items.actual_delivery_date AS TEXT) LIKE :date_dd").bindparams(date_dd=f"%{delivery_date}%"))
    if invoice_date:
        optional_filters.append(text("CAST(order_items.invoice_date AS TEXT) LIKE :date_id").bindparams(date_id=f"%{invoice_date}%"))
    
    if optional_filters:
        query = query.filter(and_(*optional_filters))
    
    # Sorting
    sort_map = {
        'date_desc': PurchaseOrder.order_date.desc(),
        'date_asc': PurchaseOrder.order_date.asc(),
        'arrival_date_desc': OrderItem.arrival_date.desc(),
        'arrival_date_asc': OrderItem.arrival_date.asc(),
        'quotation_date_desc': OrderItem.quotation_date.desc(),
        'quotation_date_asc': OrderItem.quotation_date.asc(),
        'delivery_date_desc': OrderItem.actual_delivery_date.desc(),
        'delivery_date_asc': OrderItem.actual_delivery_date.asc(),
        'invoice_date_desc': OrderItem.invoice_date.desc(),
        'invoice_date_asc': OrderItem.invoice_date.asc(),
        'order_date_desc': PurchaseOrder.order_date.desc(),
        'order_date_asc': PurchaseOrder.order_date.asc(),
    }
    
    order_clause = sort_map.get(sort_by, PurchaseOrder.order_date.desc())
    
    # Get total count before pagination
    total = query.count()
    
    # Handle locked_ids - ensure selected items are always included
    locked_id_list = []
    if locked_ids:
        try:
            locked_id_list = [int(x.strip()) for x in locked_ids.split(',') if x.strip()]
        except:
            pass
    
    items = query.order_by(order_clause).offset(skip).limit(limit).all()
    
    # If there are locked IDs not in the result, fetch them separately
    if locked_id_list:
        current_ids = {item.id for item in items}
        missing_ids = [lid for lid in locked_id_list if lid not in current_ids]
        if missing_ids:
            locked_items = db.query(OrderItem).join(
                PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
            ).join(
                Material, OrderItem.material_id == Material.id
            ).options(
                joinedload(OrderItem.order),
                joinedload(OrderItem.material)
            ).filter(
                OrderItem.id.in_(missing_ids),
                PurchaseOrder.supplier_id == target_supplier_id
            ).all()
            items = list(items) + locked_items
    
    # Format response
    result = []
    for item in items:
        order = item.order
        material = item.material
        result.append({
            "id": item.id,
            "order_id": order.id if order else None,
            "po_number": order.po_number if order else "",
            "order_date": str(order.order_date) if order and order.order_date else None,
            "arrival_date": str(item.arrival_date) if item.arrival_date else None,
            "material_id": material.id if material else None,
            "sap_code": material.sap_code if material else "",
            "material_name": material.name_cn if material else "",
            "material_name_vn": material.name_vn if material else "",
            "material_image": material.image if material else None,
            "material_pdf": material.drawing_pdf if material else None,
            "ordered_qty": item.ordered_qty,
            "received_qty": item.received_qty or 0,
            "unit_price": item.unit_price,
            "currency": item.currency or "VND",
            "total_price": item.total_price,
            "item_status": item.item_status,
            "quotation_file": item.quotation_file,
            "quotation_date": str(item.quotation_date) if item.quotation_date else None,
            "delivery_note": item.delivery_note,
            "actual_delivery_date": str(item.actual_delivery_date) if item.actual_delivery_date else None,
            "invoice_file": item.invoice_file,
            "invoice_date": str(item.invoice_date) if item.invoice_date else None,
            "invoice_number": item.invoice_number if hasattr(item, 'invoice_number') else None,
            "purchase_link": material.purchase_link if material and hasattr(material, 'purchase_link') else None,
        })
    
    return {"total": total, "items": result}


class BatchConfirmRequest(BaseModel):
    item_ids: list[int]

@router.post("/batch-confirm")
async def batch_confirm_items(
    data: BatchConfirmRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """供应商批量确认订单"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        target_supplier_id = None
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    updated_count = 0
    
    for item_id in data.item_ids:
        query = db.query(OrderItem).join(
            PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
        ).filter(
            OrderItem.id == item_id,
            OrderItem.item_status == "已下单"
        )
        
        if target_supplier_id is not None:
            query = query.filter(PurchaseOrder.supplier_id == target_supplier_id)
            
        item = query.first()
        if item:
            item.item_status = "已确认"
            
            # Record confirmation time in operation logs
            from app.models.warehouse import add_operation_log
            add_operation_log(
                db,
                action="确认订单",
                detail=f"批量确认订单",
                operator=getattr(current_user, "name", "管理员"),
                order_item_id=item.id,
                supplier_id=target_supplier_id if target_supplier_id else item.order.supplier_id,
                quantity=item.ordered_qty
            )
            
            updated_count += 1
            
    db.commit()
    return {"message": f"成功确认 {updated_count} 条订单", "updated": updated_count}


@router.put("/items/batch-status")
async def batch_update_item_status(
    data: BatchStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """批量更新订单项状态"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        # Admin - no supplier restriction
        target_supplier_id = None
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    # Validate status
    valid_statuses = ["未下单", "已下单", "已确认", "已送货", "已收货", "已开发票", "退货中"]
    if data.item_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态: {data.item_status}")
    
    updated_count = 0
    for item_id in data.item_ids:
        query = db.query(OrderItem).join(
            PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
        ).filter(OrderItem.id == item_id)
        
        if target_supplier_id is not None:
            query = query.filter(PurchaseOrder.supplier_id == target_supplier_id)
        
        item = query.first()
        
        if item:
            item.item_status = data.item_status
            updated_count += 1
    
    db.commit()
    return {"message": f"已更新 {updated_count} 条记录", "updated": updated_count}


# ===== NEW: Admin Supplier Documents View =====
@router.get("/admin/documents")
async def get_all_supplier_documents(
    supplier_id: Optional[int] = None,
    document_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """管理员查看所有供应商文档"""
    from app.models.users import User
    
    if not isinstance(current_user, User):
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).options(
        joinedload(OrderItem.order),
        joinedload(OrderItem.material)
    )
    
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    
    # Filter by document type
    if document_type == "quotation":
        query = query.filter(OrderItem.quotation_file.isnot(None))
    elif document_type == "delivery":
        query = query.filter(OrderItem.delivery_note.isnot(None))
    elif document_type == "invoice":
        query = query.filter(OrderItem.invoice_file.isnot(None))
    
    total = query.count()
    items = query.order_by(PurchaseOrder.order_date.desc()).offset(skip).limit(limit).all()
    
    result = []
    for item in items:
        result.append({
            "id": item.id,
            "order_id": item.order_id,
            "po_number": item.order.po_number if item.order else "",
            "supplier_name": item.order.supplier.name if item.order and item.order.supplier else "",
            "material_name": item.material.name_cn if item.material else "",
            "sap_code": item.material.sap_code if item.material else "",
            "ordered_qty": item.ordered_qty,
            "unit_price": item.unit_price,
            "currency": item.currency or "VND",
            "item_status": item.item_status,
            "quotation_file": item.quotation_file,
            "delivery_note": item.delivery_note,
            "invoice_file": item.invoice_file,
        })
    
    return {"total": total, "items": result}


@router.get("/admin/suppliers")
async def get_all_suppliers_for_admin(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """管理员获取所有供应商列表"""
    from app.models.users import User
    
    if not isinstance(current_user, User):
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    
    suppliers = db.query(Supplier).all()
    return [{"id": s.id, "name": s.name, "code": s.code} for s in suppliers]


@router.post("/delivery-notes")
async def upload_delivery_notes(
    file: UploadFile = File(...),
    delivery_date: str = Form(None),
    item_ids: str = Form(None),
    item_qtys: str = Form(None),
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """供应商上传送货单"""
    import json
    # Parse item_ids
    try:
        item_id_list = json.loads(item_ids) if item_ids else []
    except:
        raise HTTPException(status_code=400, detail="无效的item_ids格式")

    from app.models.users import User
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        if not item_id_list:
            raise HTTPException(status_code=400, detail="请选择至少一个订单项")
        first_item = db.query(OrderItem).filter(OrderItem.id == item_id_list[0]).first()
        if not first_item or not first_item.order:
            raise HTTPException(status_code=404, detail="订单记录不存在")
        supplier_id = first_item.order.supplier_id
    elif isinstance(current_user, Supplier):
        supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权执行此操作")
    
    # Parse item_qtys (JSON map of item_id -> delivery_qty)
    try:
        qty_map = json.loads(item_qtys) if item_qtys else {}
    except:
        qty_map = {}
    
    if not item_id_list:
        raise HTTPException(status_code=400, detail="请选择至少一个订单项")
    
    # Ensure directory exists
    os.makedirs(DELIVERY_NOTES_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"delivery_{supplier_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = f"{DELIVERY_NOTES_DIR}/{filename}"  # Use forward slash for web URLs
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update each item with delivery note path and date
    from app.models.materials import Material
    from app.models.orders import SupplierQuote
    updated_count = 0
    for item_id in item_id_list:
        item = db.query(OrderItem).join(
            PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
        ).filter(
            OrderItem.id == item_id,
            PurchaseOrder.supplier_id == supplier_id
        ).first()
        
        if item:
            item.delivery_note = filepath
            if delivery_date:
                item.actual_delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d").date()
            
            # Handle partial delivery quantities
            item_id_str = str(item_id)
            log_quantity = item.ordered_qty # Default to ordered_qty for logging
            if item_id_str in qty_map:
                delivery_qty = float(qty_map[item_id_str])
                log_quantity = delivery_qty # Use specific delivery_qty for logging
                if delivery_qty < item.ordered_qty:
                    # Partial delivery - split the order item
                    remaining_qty = item.ordered_qty - delivery_qty
                    
                    # Create new item for the remaining quantity
                    new_item = OrderItem(
                        order_id=item.order_id,
                        material_id=item.material_id,
                        ordered_qty=remaining_qty,
                        received_qty=0,
                        unit_price=item.unit_price,
                        total_price=(item.unit_price or 0) * remaining_qty,
                        item_status="已下单",
                        arrival_date=item.arrival_date,
                        workshop=item.workshop,
                        equipment=item.equipment,
                        quotation_file=item.quotation_file,
                        quotation_date=item.quotation_date,
                    )
                    db.add(new_item)
                    
                    # Update original item with delivered quantity
                    item.ordered_qty = delivery_qty
                    item.total_price = (item.unit_price or 0) * delivery_qty
            
            item.item_status = "已送货"
            add_operation_log(
                db, 
                action="上传送货单", 
                detail=f"上传送货单：{file.filename}", 
                operator=getattr(current_user, "name", "管理员"), 
                order_item_id=item.id, 
                supplier_id=supplier_id, 
                quantity=log_quantity
            )
            updated_count += 1
    
    db.commit()
    
    return {"message": f"送货单上传成功，已关联 {updated_count} 项", "path": filepath}


@router.get("/admin/delivery-notes")
async def get_all_delivery_notes(
    supplier_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """管理员查看所有送货单"""
    from app.models.users import User
    
    if not isinstance(current_user, User):
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).filter(
        OrderItem.delivery_note.isnot(None)
    ).options(
        joinedload(OrderItem.order),
        joinedload(OrderItem.material)
    )
    
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    
    total = query.count()
    items = query.order_by(OrderItem.actual_delivery_date.desc()).offset(skip).limit(limit).all()
    
    result = []
    for item in items:
        result.append({
            "id": item.id,
            "order_id": item.order_id,
            "po_number": item.order.po_number if item.order else "",
            "supplier_name": item.order.supplier.name if item.order and item.order.supplier else "",
            "material_name": item.material.name_cn if item.material else "",
            "sap_code": item.material.sap_code if item.material else "",
            "ordered_qty": item.ordered_qty,
            "delivery_note": item.delivery_note,
            "actual_delivery_date": str(item.actual_delivery_date) if item.actual_delivery_date else None,
            "item_status": item.item_status,
        })
    
    return {"total": total, "items": result}


@router.post("/invoice/{item_id}")
async def upload_invoice(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """供应商上传发票"""
    from app.models.users import User
    
    if isinstance(current_user, User):
        # Admin user - find item without supplier filter
        item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    elif isinstance(current_user, Supplier):
        supplier_id = current_user.id
        item = db.query(OrderItem).join(
            PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
        ).filter(
            OrderItem.id == item_id,
            PurchaseOrder.supplier_id == supplier_id
        ).first()
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    if not item:
        raise HTTPException(status_code=404, detail="订单项不存在")
    
    # Block invoicing if not in 已收货 status
    if item.item_status != "已收货":
        raise HTTPException(status_code=400, detail=f"只有仓库确认收货后才能开发票，当前状态：{item.item_status}")
    
    # Block invoicing if received quantity doesn't match ordered quantity
    if (item.received_qty or 0) < item.ordered_qty:
        raise HTTPException(status_code=400, detail=f"收货数量与采购订单不符（已收 {item.received_qty or 0}/{item.ordered_qty}），不允许开发票")
    
    # Block invoicing if there are pending returns
    from app.models.warehouse import ReturnRecord
    pending_returns = db.query(ReturnRecord).filter(
        ReturnRecord.order_item_id == item_id,
        ReturnRecord.status == "待处理"
    ).count()
    if pending_returns > 0:
        raise HTTPException(status_code=400, detail="该物料存在未处理的退货，不允许开发票")
    
    # Ensure directory exists
    os.makedirs(INVOICE_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"invoice_{item_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = f"{INVOICE_DIR}/{filename}"  # Use forward slash for web URLs
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update item
    item.invoice_file = filepath
    item.invoice_date = datetime.now().date()
    if item.item_status in ["已送货", "已收货"]:
        item.item_status = "已开发票"
        
    add_operation_log(
        db, 
        action="上传发票", 
        detail=f"上传发票：{file.filename}", 
        operator=getattr(current_user, "name", "管理员"), 
        order_item_id=item.id, 
        supplier_id=supplier_id
    )
    
    db.commit()
    
    return {"message": "发票上传成功", "path": filepath}


@router.delete("/document/{item_id}/{doc_type}")
async def delete_document(
    item_id: int, 
    doc_type: str, 
    single: bool = False,
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """供应商删除单据 (支持报价单、送货单、发票)"""
    from app.models.users import User
    
    import os
    from app.models.orders import SupplierQuote
    
    if isinstance(current_user, User):
        # Admin - no supplier filter needed
        supplier_id = None
    elif isinstance(current_user, Supplier):
        supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    # 查找该记录以确认权限和获取文件路径
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).filter(OrderItem.id == item_id)
    
    if supplier_id is not None:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    
    item = query.first()
    
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
        
    file_path = None
    target_items = []

    if doc_type == "quotation":
        file_path = item.quotation_file
        if single:
            target_items = [item]
        else:
            target_items = db.query(OrderItem).filter(OrderItem.quotation_file == file_path).all()
    elif doc_type == "delivery":
        file_path = item.delivery_note
        if single:
            target_items = [item]
        else:
            target_items = db.query(OrderItem).filter(OrderItem.delivery_note == file_path).all()
    elif doc_type == "invoice":
        file_path = item.invoice_file
        if single:
            target_items = [item]
        else:
            target_items = db.query(OrderItem).filter(OrderItem.invoice_file == file_path).all()
    else:
        raise HTTPException(status_code=400, detail="无效的文档类型")
    
    # Clear the file reference and rollback status
    for target_item in target_items:
        if doc_type == "quotation":
            target_item.quotation_file = None
            target_item.quotation_date = None
        elif doc_type == "delivery":
            target_item.delivery_note = None
            target_item.actual_delivery_date = None
            target_item.item_status = "已下单"
        elif doc_type == "invoice":
            target_item.invoice_file = None
            target_item.invoice_date = None
            target_item.item_status = "已送货"
            
        action_name = "删除" + ("报价单" if doc_type == "quotation" else "送货单" if doc_type == "delivery" else "发票")
        add_operation_log(
            db, 
            action=action_name, 
            detail=f"删除了{action_name}", 
            operator=getattr(current_user, "name", "管理员"), 
            order_item_id=target_item.id, 
            supplier_id=supplier_id
        )
    
    # Optionally delete file from disk (only if no other items reference it)
    if file_path and not single:
        remaining = 0
        if doc_type == "quotation":
            remaining = db.query(OrderItem).filter(OrderItem.quotation_file == file_path, OrderItem.id.notin_([t.id for t in target_items])).count()
        elif doc_type == "delivery":
            remaining = db.query(OrderItem).filter(OrderItem.delivery_note == file_path, OrderItem.id.notin_([t.id for t in target_items])).count()
        elif doc_type == "invoice":
            remaining = db.query(OrderItem).filter(OrderItem.invoice_file == file_path, OrderItem.id.notin_([t.id for t in target_items])).count()
        
        if remaining == 0 and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
    
    db.commit()
    
    return {"message": f"已删除 {len(target_items)} 条记录的{doc_type}文件"}


# ===== Unit Price Update =====
class PriceUpdate(BaseModel):
    unit_price: float
    currency: str = "VND"

@router.put("/items/{item_id}/price")
async def update_item_price(
    item_id: int,
    data: PriceUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """修改订单项单价（同步重算总价和订单总额）"""
    from app.models.users import User
    
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="订单项不存在")
    
    # Permission check
    if isinstance(current_user, Supplier):
        order = db.query(PurchaseOrder).filter(PurchaseOrder.id == item.order_id).first()
        if not order or order.supplier_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权修改")
    elif not (isinstance(current_user, User) and getattr(current_user, "is_superuser", False)):
        raise HTTPException(status_code=403, detail="无权修改")
    
    # Update price
    item.unit_price = data.unit_price
    item.total_price = data.unit_price * (item.ordered_qty or 0)
    if data.currency in ["VND", "USD"]:
        item.currency = data.currency
    
    # Recalculate order total
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == item.order_id).first()
    if order:
        all_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        order.total_amount = sum((i.total_price or 0) for i in all_items)
    
    db.commit()
    
    return {
        "message": "单价更新成功",
        "unit_price": item.unit_price,
        "total_price": item.total_price,
        "order_total": order.total_amount if order else None
    }


# ===== Admin Items View =====
@router.get("/admin/items")
async def get_all_supplier_items(
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """管理员查看所有供应商订单项"""
    from app.models.users import User
    from app.models.materials import Material
    from sqlalchemy import or_
    
    if not isinstance(current_user, User):
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).join(
        Material, OrderItem.material_id == Material.id
    ).options(
        joinedload(OrderItem.order),
        joinedload(OrderItem.material)
    ).filter(
        OrderItem.item_status != "未下单"
    )
    
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    
    if status:
        status_list = [s.strip() for s in status.split(',')]
        if len(status_list) > 1:
            query = query.filter(OrderItem.item_status.in_(status_list))
        else:
            query = query.filter(OrderItem.item_status == status)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                PurchaseOrder.po_number.ilike(search_term),
                Material.sap_code.ilike(search_term),
                Material.name_cn.ilike(search_term)
            )
        )
    
    total = query.count()
    items = query.order_by(PurchaseOrder.order_date.desc()).offset(skip).limit(limit).all()
    
    result = []
    for item in items:
        order = item.order
        material = item.material
        result.append({
            "id": item.id,
            "order_id": order.id if order else None,
            "po_number": order.po_number if order else "",
            "order_date": str(order.order_date) if order and order.order_date else None,
            "supplier_name": order.supplier.name if order and order.supplier else "",
            "material_name": material.name_cn if material else "",
            "sap_code": material.sap_code if material else "",
            "ordered_qty": item.ordered_qty,
            "unit_price": item.unit_price,
            "currency": item.currency or "VND",
            "total_price": item.total_price,
            "item_status": item.item_status,
            "quotation_file": item.quotation_file,
            "delivery_note": item.delivery_note,
            "invoice_file": item.invoice_file,
        })
    
    return {"total": total, "items": result}


# ===== Batch Quotation Upload =====
@router.post("/quotations")
async def upload_batch_quotation(
    file: UploadFile = File(...),
    quotation_date: str = Form(None),
    item_ids: str = Form(None),
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """供应商批量上传报价单"""
    import json
    # Parse item_ids
    try:
        item_id_list = json.loads(item_ids) if item_ids else []
    except:
        raise HTTPException(status_code=400, detail="无效的item_ids格式")

    from app.models.users import User
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        if not item_id_list:
            raise HTTPException(status_code=400, detail="请选择至少一个订单项")
        first_item = db.query(OrderItem).filter(OrderItem.id == item_id_list[0]).first()
        if not first_item or not first_item.order:
            raise HTTPException(status_code=404, detail="订单记录不存在")
        supplier_id = first_item.order.supplier_id
    elif isinstance(current_user, Supplier):
        supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权执行此操作")
    
    if not item_id_list:
        raise HTTPException(status_code=400, detail="请选择至少一个订单项")
    
    # Ensure directory exists
    os.makedirs(QUOTATION_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"quotation_{supplier_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = f"{QUOTATION_DIR}/{filename}"
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update each item with quotation file path and date
    updated_count = 0
    for item_id in item_id_list:
        item = db.query(OrderItem).join(
            PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
        ).filter(
            OrderItem.id == item_id,
            PurchaseOrder.supplier_id == supplier_id
        ).first()
        
        if item:
            item.quotation_file = filepath
            item.quotation_date = datetime.now().date()  # Always use today's date
            updated_count += 1
    
    db.commit()
    
    return {"message": f"报价单上传成功，已关联 {updated_count} 项", "path": filepath}


# ===== Batch Invoice Upload =====
@router.post("/invoices")
async def upload_batch_invoice(
    file: UploadFile = File(...),
    invoice_date: str = Form(None),
    item_ids: str = Form(None),
    db: Session = Depends(get_db),
    current_user: Supplier = Depends(get_current_user)
):
    """供应商批量上传发票"""
    import json
    # Parse item_ids
    try:
        item_id_list = json.loads(item_ids) if item_ids else []
    except:
        raise HTTPException(status_code=400, detail="无效的item_ids格式")

    from app.models.users import User
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        if not item_id_list:
            raise HTTPException(status_code=400, detail="请选择至少一个订单项")
        first_item = db.query(OrderItem).filter(OrderItem.id == item_id_list[0]).first()
        if not first_item or not first_item.order:
            raise HTTPException(status_code=404, detail="订单记录不存在")
        supplier_id = first_item.order.supplier_id
    elif isinstance(current_user, Supplier):
        supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权执行此操作")
    
    if not item_id_list:
        raise HTTPException(status_code=400, detail="请选择至少一个订单项")
    
    # Ensure directory exists
    os.makedirs(INVOICE_DIR, exist_ok=True)
    
    # Generate filename
    ext = os.path.splitext(file.filename)[1] or ".pdf"
    filename = f"invoice_{supplier_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    filepath = f"{INVOICE_DIR}/{filename}"
    
    # Save file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update each item with invoice file path and date
    updated_count = 0
    for item_id in item_id_list:
        item = db.query(OrderItem).join(
            PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
        ).filter(
            OrderItem.id == item_id,
            PurchaseOrder.supplier_id == supplier_id
        ).first()
        
        if item:
            item.invoice_file = filepath
            if invoice_date:
                item.invoice_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
            # Set status to invoiced (已开发票)
            if item.item_status in ["已送货", "已收货"]:
                item.item_status = "已开发票"
            updated_count += 1
    
    db.commit()
    
    return {"message": f"发票上传成功，已关联 {updated_count} 项", "path": filepath}


class InvoiceReassign(BaseModel):
    invoice_file: str

@router.put("/items/{item_id}/invoice")
async def reassign_item_invoice(
    item_id: int,
    data: InvoiceReassign,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """更改已开发票项的关联发票（仅允许更换发票组）"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        target_supplier_id = None
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
        
    query = db.query(OrderItem).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).filter(OrderItem.id == item_id)
    
    if target_supplier_id is not None:
        query = query.filter(PurchaseOrder.supplier_id == target_supplier_id)
        
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="项不存在或无权操作")
        
    if item.item_status != "已开发票":
        raise HTTPException(status_code=400, detail="只能修改「已开发票」状态的物料")
        
    old_invoice = item.invoice_file
    item.invoice_file = data.invoice_file
    db.commit()
    
    return {
        "message": f"发票关联已更新: {old_invoice} -> {data.invoice_file}",
        "new_invoice": data.invoice_file
    }


# ===== Returns Management =====

class RedeliveryCreate(BaseModel):
    redelivery_date: str
    explanation: str

from app.models.warehouse import ReturnRecord

@router.get("/returns")
async def get_supplier_returns(
    supplier_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取供应商相关的退货记录"""
    from app.models.users import User
    from app.models.materials import Material
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        target_supplier_id = supplier_id
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    if not target_supplier_id:
        raise HTTPException(status_code=400, detail="请提供 supplier_id")
    
    # Get return records for this supplier's items
    query = db.query(ReturnRecord).join(
        OrderItem, ReturnRecord.order_item_id == OrderItem.id
    ).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).filter(
        PurchaseOrder.supplier_id == target_supplier_id,
        ReturnRecord.status == "待处理"
    ).options(
        joinedload(ReturnRecord.order_item).joinedload(OrderItem.order),
        joinedload(ReturnRecord.order_item).joinedload(OrderItem.material)
    )
    
    total = query.count()
    returns = query.order_by(ReturnRecord.return_date.desc()).offset(skip).limit(limit).all()
    
    result = []
    for ret in returns:
        item = ret.order_item
        order = item.order if item else None
        material = item.material if item else None
        
        result.append({
            "id": ret.id,
            "order_item_id": item.id if item else None,
            "po_number": order.po_number if order else "",
            "material": {
                "id": material.id if material else None,
                "sap_code": material.sap_code if material else "",
                "name_cn": material.name_cn if material else "",
                "name_vn": material.name_vn if material else "",
                "image": material.image if material else None,
                "drawing_pdf": material.drawing_pdf if material else None,
            } if material else None,
            "ordered_qty": item.ordered_qty if item else 0,
            "remaining_qty": (item.ordered_qty - (item.received_qty or 0)) if item else 0,
            "actual_delivery_date": str(item.actual_delivery_date) if item and item.actual_delivery_date else None,
            "item_status": item.item_status if item else "",
            "return_info": {
                "return_date": str(ret.return_date) if ret.return_date else None,
                "return_reason": ret.return_reason,
                "return_qty": ret.return_qty,
                "status": ret.status,
                "redelivery_date": str(ret.redelivery_date) if ret.redelivery_date else None,
                "supplier_explanation": ret.supplier_explanation,
            }
        })
    
    return {"total": total, "items": result}


@router.post("/returns/{item_id}/redeliver")
async def process_redelivery(
    item_id: int,
    data: RedeliveryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """供应商确认重新送货"""
    from app.models.users import User
    
    if isinstance(current_user, User) and getattr(current_user, "is_superuser", False):
        target_supplier_id = None
    elif isinstance(current_user, Supplier):
        target_supplier_id = current_user.id
    else:
        raise HTTPException(status_code=403, detail="无权访问")
    
    # Find the return record
    ret = db.query(ReturnRecord).filter(
        ReturnRecord.id == item_id,
        ReturnRecord.status == "待处理"
    ).first()
    
    if not ret:
        raise HTTPException(status_code=404, detail="退货记录不存在或已处理")
    
    # Verify supplier owns this item
    order_item = ret.order_item
    if not order_item:
        raise HTTPException(status_code=404, detail="关联订单项不存在")
    
    order = order_item.order
    if not order:
        raise HTTPException(status_code=404, detail="关联订单不存在")
    
    if target_supplier_id is not None and order.supplier_id != target_supplier_id:
        raise HTTPException(status_code=403, detail="无权操作此退货记录")
    
    # Update return record
    ret.status = "已重新送货"
    ret.redelivery_date = datetime.strptime(data.redelivery_date, "%Y-%m-%d").date()
    ret.supplier_explanation = data.explanation
    
    # Check if there are other pending return records for this order item
    other_pending_returns = db.query(ReturnRecord).filter(
        ReturnRecord.order_item_id == order_item.id,
        ReturnRecord.id != ret.id,
        ReturnRecord.status == "待处理"
    ).count()
    
    if other_pending_returns > 0:
        # Still have pending returns, keep status as 退货中
        order_item.item_status = "退货中"
    else:
        # No more pending returns, set to 已送货
        order_item.item_status = "已送货"
    
    order_item.actual_delivery_date = datetime.strptime(data.redelivery_date, "%Y-%m-%d").date()
    
    add_operation_log(
        db, 
        action="重新补货", 
        detail=f"预计重新交货：{data.redelivery_date}。说明：{data.explanation}", 
        operator=getattr(current_user, "name", "管理员"), 
        order_item_id=order_item.id, 
        supplier_id=target_supplier_id, 
        quantity=ret.return_qty
    )
    
    db.commit()
    
    return {"message": "重新送货信息已记录", "status": "已重新送货"}
