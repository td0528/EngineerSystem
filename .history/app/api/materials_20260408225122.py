"""
Materials API router - 物料管理
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, desc
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import os
import shutil
import csv
import io
import openpyxl

from app.database.database import get_db
from app.models.materials import Material, MaterialPrice, MaterialSupplier, Quotation
from app.models.configurations import ConfigOption
from app.models.material_notes import MaterialNote
from app.models.warehouse import WarehouseStock
from app.api.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploads/materials"


class MaterialCreate(BaseModel):
    sap_code: str
    name_cn: str
    name_vn: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    workshop: Optional[str] = None
    equipment: Optional[str] = None
    purchase_link: Optional[str] = None
    specification: Optional[str] = None
    unit: Optional[str] = "个"
    min_stock: Optional[int] = 0


class MaterialUpdate(BaseModel):
    sap_code: Optional[str] = None
    name_cn: Optional[str] = None
    name_vn: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    workshop: Optional[str] = None
    equipment: Optional[str] = None
    purchase_link: Optional[str] = None
    specification: Optional[str] = None
    unit: Optional[str] = None
    min_stock: Optional[int] = None


class PriceCreate(BaseModel):
    price: float
    currency: str = "VND"
    supplier_id: Optional[int] = None
    notes: Optional[str] = None


@router.get("/")
async def get_materials(
    search: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    workshop: Optional[str] = None,
    sap_code: Optional[str] = Query(None),
    name_cn: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    workshops: Optional[str] = Query(None),  # Comma-separated list for multi-select
    equipments: Optional[str] = Query(None),  # Comma-separated list for multi-select
    subcategories: Optional[str] = Query(None),  # Comma-separated list for multi-select
    locations: Optional[str] = Query(None),  # Comma-separated list for multi-select
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query('asc'),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取物料列表，支持模糊搜索"""
    query = db.query(Material)
    
    # Smart Fuzzy search on SAP code, Chinese name, Vietnamese name
    if search:
        # Replace hyphens with spaces for better tokenization of copies like "SAP - Name"
        clean_search = search.replace('-', ' ').strip()
        keywords = [k for k in clean_search.split() if k]
        
        if keywords:
            # Create a list of AND conditions: each keyword must match at least one field
            conditions = []
            for keyword in keywords:
                term = f"%{keyword}%"
                conditions.append(
                    or_(
                        Material.sap_code.ilike(term),
                        Material.name_cn.ilike(term),
                        Material.name_vn.ilike(term),
                        Material.equipment.ilike(term)
                    )
                )
            # Apply all conditions using AND
            query = query.filter(and_(*conditions))
    
    # Specific column filters
    if category:
        query = query.filter(Material.category == category)
    if subcategory:
        query = query.filter(Material.subcategory.ilike(f"%{subcategory}%"))
    if workshop:
        query = query.filter(Material.workshop == workshop)
    
    # New filters
    if sap_code:
        query = query.filter(Material.sap_code.ilike(f"%{sap_code}%"))
    if name_cn:
        query = query.filter(Material.name_cn.ilike(f"%{name_cn}%"))
    if location:
        query = query.filter(Material.location.ilike(f"%{location}%"))
    if equipment:
        query = query.filter(Material.equipment.ilike(f"%{equipment}%"))
    
    # Multi-select filters (comma-separated values)
    if workshops:
        workshop_list = [w.strip() for w in workshops.split(',') if w.strip()]
        if workshop_list:
            query = query.filter(Material.workshop.in_(workshop_list))
    if equipments:
        equipment_list = [e.strip() for e in equipments.split(',') if e.strip()]
        if equipment_list:
            query = query.filter(Material.equipment.in_(equipment_list))
    if subcategories:
        subcategory_list = [s.strip() for s in subcategories.split(',') if s.strip()]
        if subcategory_list:
            query = query.filter(Material.subcategory.in_(subcategory_list))
    if locations:
        location_list = [l.strip() for l in locations.split(',') if l.strip()]
        if location_list:
            query = query.filter(Material.location.in_(location_list))
    
    total = query.count()
    
    # Sorting
    if sort_by:
        sort_col = getattr(Material, sort_by, None)
        if sort_col is not None:
            if sort_order == 'desc':
                query = query.order_by(desc(sort_col))
            else:
                query = query.order_by(sort_col)
        else:
            query = query.order_by(Material.sap_code)
    else:
        # Default sort
        if search:
            clean_search = search.replace('-', ' ').strip()
            query = query.order_by(
                desc(Material.sap_code.ilike(f"{clean_search}%")),
                Material.sap_code
            )
        else:
            query = query.order_by(Material.sap_code)
            
    materials = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": materials}


@router.get("/search")
async def search_materials(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """物料模糊搜索（下拉选择用）"""
    # Replace hyphens with spaces for better tokenization
    clean_search = q.replace('-', ' ').strip()
    keywords = [k for k in clean_search.split() if k]
    
    if not keywords:
        return []

    # Build validation query
    query = db.query(Material)
    
    # Each keyword must match at least one field
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
    
    # Prioritize matches starting with the search term
    # We use boolean expression: sap_code.ilike(f"{clean_search}%") which returns True (1) or False (0)
    # Sorting by desc() puts True first.
    query = query.order_by(
        desc(Material.sap_code.ilike(f"{clean_search}%")),
        Material.sap_code
    )
    
    materials = query.limit(limit).all()
    
    return [
        {
            "id": m.id,
            "sap_code": m.sap_code,
            "name_cn": m.name_cn,
            "name_vn": m.name_vn,
            "workshop": m.workshop,
            "location": m.location
        }
        for m in materials
    ]

@router.get("/next-sap-code")
async def get_next_sap_code(db: Session = Depends(get_db)):
    """获取下一个可用的SAP号码（自动递增，仅限1开头的6位数字）"""
    # Get all SAP codes
    all_materials = db.query(Material.sap_code).all()
    
    max_num = 99999  # Start from 100000
    for (code,) in all_materials:
        if code:
            code_str = str(code).strip()
            # Only consider pure numeric codes with exactly 6 digits and starting with '1'
            if len(code_str) == 6 and code_str.startswith("1") and code_str.isdigit():
                num = int(code_str)
                if 100000 <= num <= 199999 and num > max_num:
                    max_num = num
    
    next_code = str(max_num + 1)
    
    return {"next_sap_code": next_code}


def _sync_location_to_config(db: Session, location: str):
    """助手方法：如果由于物料变动引入了新库位名称，自动注册到配置字典"""
    if not location:
        return
    location = location.strip()
    if not location:
        return
        
    exists = db.query(ConfigOption).filter(
        ConfigOption.option_type == "location",
        ConfigOption.option_value == location
    ).first()
    
    if not exists:
        new_loc = ConfigOption(
            option_type="location",
            option_value=location,
            is_active=True
        )
        db.add(new_loc)
        db.commit()


class MaterialLocationUpdate(BaseModel):
    location: Optional[str] = None

@router.put("/{material_id}/location")
async def update_material_location(
    material_id: int,
    location_data: MaterialLocationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """更新物料库位（用于仓库行内编辑）"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    # Update material location
    material.location = location_data.location
    
    # Synchronize with WarehouseStock location
    from app.models.warehouse import WarehouseStock
    stock = db.query(WarehouseStock).filter(WarehouseStock.material_id == material_id).first()
    if stock:
        stock.location = location_data.location
        
    db.commit()
    
    # Auto-register new location to dictionary
    _sync_location_to_config(db, location_data.location)
    
    return {"message": "库位更新成功", "location": material.location}


@router.get("/{material_id}")
async def get_material(material_id: int, db: Session = Depends(get_db)):
    """获取物料详情"""
    material = db.query(Material).options(
        joinedload(Material.prices),
        joinedload(Material.suppliers),
        joinedload(Material.quotations),
        joinedload(Material.warehouse_stock),
        joinedload(Material.notes)
    ).filter(Material.id == material_id).first()
    
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    return material


@router.post("/")
async def create_material(material_data: MaterialCreate, db: Session = Depends(get_db)):
    """创建新物料"""
    # Check if SAP code exists
    if db.query(Material).filter(Material.sap_code == material_data.sap_code).first():
        raise HTTPException(status_code=400, detail="SAP号码已存在")
    
    new_material = Material(**material_data.model_dump())
    db.add(new_material)
    db.commit()
    db.refresh(new_material)
    
    # Auto-create warehouse stock record
    stock = WarehouseStock(
        material_id=new_material.id,
        location=new_material.location
    )
    db.add(stock)
    db.commit()
    
    # Auto-register new location to dictionary
    if new_material.location:
        _sync_location_to_config(db, new_material.location)
    
    return new_material


@router.put("/{material_id}")
async def update_material(material_id: int, material_data: MaterialUpdate, db: Session = Depends(get_db)):
    """更新物料信息"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    update_data = material_data.model_dump(exclude_unset=True)
    
    # Check SAP code uniqueness if being changed
    if "sap_code" in update_data and update_data["sap_code"] != material.sap_code:
        existing = db.query(Material).filter(
            Material.sap_code == update_data["sap_code"],
            Material.id != material_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"SAP号码 {update_data['sap_code']} 已被其他物料使用")
    
    for key, value in update_data.items():
        setattr(material, key, value)
    
    # Mirror location changes to warehouse stock and globally register new string
    if "location" in update_data:
        from app.models.warehouse import WarehouseStock
        stock = db.query(WarehouseStock).filter(WarehouseStock.material_id == material_id).first()
        if stock:
            stock.location = update_data["location"]
            
        if update_data["location"]:
            _sync_location_to_config(db, update_data["location"])
            
    db.commit()
    db.refresh(material)
    return material


@router.post("/{material_id}/image")
async def upload_material_image(
    material_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传物料图片"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Save file
    file_ext = file.filename.split(".")[-1]
    file_name = f"{material.sap_code}_image.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    timestamp = int(datetime.utcnow().timestamp())
    material.image = f"/uploads/materials/{file_name}?t={timestamp}"
    db.commit()
    
    return {"image_url": material.image}


@router.post("/{material_id}/drawing")
async def upload_material_drawing(
    material_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传物料图纸PDF"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_name = f"{material.sap_code}_drawing.pdf"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    timestamp = int(datetime.utcnow().timestamp())
    material.drawing_pdf = f"/uploads/materials/{file_name}?t={timestamp}"
    db.commit()
    
    return {"drawing_url": material.drawing_pdf}


@router.delete("/{material_id}")
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    """删除物料（硬删除，同时删除关联数据）"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    db.delete(material)
    db.commit()
    
    return {"message": "物料已删除"}


@router.post("/batch-delete")
async def batch_delete_materials(ids: List[int], db: Session = Depends(get_db)):
    """批量删除物料（硬删除，同时删除关联数据）"""
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的物料")
    
    materials = db.query(Material).filter(Material.id.in_(ids)).all()
    count = len(materials)
    for m in materials:
        db.delete(m)
    db.commit()
    
    return {"message": f"已删除 {count} 个物料", "deleted_count": count}


@router.delete("/{material_id}/image")
async def delete_material_image(material_id: int, db: Session = Depends(get_db)):
    """删除物料图片"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    if material.image:
        # Try to delete the file
        file_path = material.image.replace("/uploads/", "uploads/")
        if os.path.exists(file_path):
            os.remove(file_path)
        
        material.image = None
        db.commit()
    
    return {"message": "图片已删除"}


@router.delete("/{material_id}/drawing")
async def delete_material_drawing(material_id: int, db: Session = Depends(get_db)):
    """删除物料图纸PDF"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    if material.drawing_pdf:
        # Try to delete the file
        file_path = material.drawing_pdf.replace("/uploads/", "uploads/")
        if os.path.exists(file_path):
            os.remove(file_path)
        
        material.drawing_pdf = None
        db.commit()
    
    return {"message": "图纸已删除"}


@router.post("/{material_id}/prices")
async def add_material_price(material_id: int, price_data: PriceCreate, db: Session = Depends(get_db)):
    """添加价格记录"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    new_price = MaterialPrice(
        material_id=material_id,
        **price_data.model_dump()
    )
    db.add(new_price)
    db.commit()
    db.refresh(new_price)
    
    return new_price


@router.get("/{material_id}/prices")
async def get_material_prices(material_id: int, db: Session = Depends(get_db)):
    """获取物料价格历史"""
    prices = db.query(MaterialPrice).filter(
        MaterialPrice.material_id == material_id
    ).order_by(MaterialPrice.created_at.desc()).all()
    
    return prices


@router.get("/{material_id}/price-history")
async def get_price_history(
    material_id: int,
    supplier_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取完整价格历史（含采购订单数据，按供应商分组）"""
    from app.models.orders import OrderItem, PurchaseOrder
    from app.models.users import Supplier
    
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    # Get all prices from MaterialPrice table
    price_query = db.query(MaterialPrice).filter(
        MaterialPrice.material_id == material_id
    )
    if supplier_id:
        price_query = price_query.filter(MaterialPrice.supplier_id == supplier_id)
    
    prices = price_query.order_by(MaterialPrice.effective_date.asc()).all()
    
    # Get prices from order items
    order_items = db.query(
        OrderItem.unit_price,
        OrderItem.created_at,
        PurchaseOrder.supplier_id,
        PurchaseOrder.po_number,
        Supplier.name.label('supplier_name')
    ).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).join(
        Supplier, PurchaseOrder.supplier_id == Supplier.id
    ).filter(
        OrderItem.material_id == material_id,
        OrderItem.unit_price > 0
    )
    
    if supplier_id:
        order_items = order_items.filter(PurchaseOrder.supplier_id == supplier_id)
    
    order_items = order_items.order_by(OrderItem.created_at.asc()).all()
    
    # Get all suppliers for this material
    supplier_ids = set()
    for p in prices:
        if p.supplier_id:
            supplier_ids.add(p.supplier_id)
    for item in order_items:
        if item.supplier_id:
            supplier_ids.add(item.supplier_id)
    
    suppliers = db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all() if supplier_ids else []
    
    # Group by supplier
    supplier_prices = {}
    for s in suppliers:
        supplier_prices[s.id] = {
            "supplier_id": s.id,
            "supplier_name": s.name,
            "prices": []
        }
    
    # Add "unknown" supplier group
    supplier_prices[0] = {
        "supplier_id": None,
        "supplier_name": "未知供应商",
        "prices": []
    }
    
    # Add MaterialPrice records
    for p in prices:
        sid = p.supplier_id or 0
        if sid not in supplier_prices:
            supplier_prices[sid] = {"supplier_id": sid, "supplier_name": f"供应商{sid}", "prices": []}
        supplier_prices[sid]["prices"].append({
            "price": p.price,
            "date": p.effective_date.isoformat() if p.effective_date else None,
            "source": "价格记录",
            "notes": p.notes
        })
    
    # Add OrderItem prices
    for item in order_items:
        sid = item.supplier_id or 0
        if sid not in supplier_prices:
            supplier_prices[sid] = {"supplier_id": sid, "supplier_name": item.supplier_name, "prices": []}
        supplier_prices[sid]["prices"].append({
            "price": item.unit_price,
            "date": item.created_at.isoformat() if item.created_at else None,
            "source": f"采购订单 {item.po_number}",
            "notes": None
        })
    
    # Sort each supplier's prices by date
    for sid in supplier_prices:
        supplier_prices[sid]["prices"].sort(key=lambda x: x["date"] or "")
    
    # Remove empty supplier groups
    result = [v for v in supplier_prices.values() if v["prices"]]
    
    return {
        "material": {
            "id": material.id,
            "sap_code": material.sap_code,
            "name_cn": material.name_cn
        },
        "suppliers": result
    }


@router.get("/categories/all")
async def get_categories(db: Session = Depends(get_db)):
    """获取所有分类"""
    categories = db.query(Material.category).distinct().filter(Material.category.isnot(None)).all()
    subcategories = db.query(Material.subcategory).distinct().filter(Material.subcategory.isnot(None)).all()
    workshops = db.query(Material.workshop).distinct().filter(Material.workshop.isnot(None)).all()
    
    return {
        "categories": [c[0] for c in categories],
        "subcategories": [s[0] for s in subcategories],
        "workshops": [w[0] for w in workshops]
    }


# ============ 报价单管理 ============

class QuotationCreate(BaseModel):
    supplier_name: str
    price: float
    currency: str = "VND"
    notes: Optional[str] = None


@router.post("/{material_id}/quotations")
async def add_quotation(material_id: int, data: QuotationCreate, db: Session = Depends(get_db)):
    """添加报价单"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    quotation = Quotation(
        material_id=material_id,
        supplier_name=data.supplier_name,
        price=data.price,
        currency=data.currency,
        notes=data.notes
    )
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    
    return quotation


@router.get("/{material_id}/quotations")
async def get_quotations(material_id: int, db: Session = Depends(get_db)):
    """获取物料报价单列表"""
    from app.models.materials import QuotationAttachment
    
    quotations = db.query(Quotation).options(
        joinedload(Quotation.attachments)
    ).filter(
        Quotation.material_id == material_id
    ).order_by(Quotation.created_at.desc()).all()
    
    return quotations


@router.delete("/quotations/{quotation_id}")
async def delete_quotation(quotation_id: int, db: Session = Depends(get_db)):
    """删除报价单"""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="报价单不存在")
    
    # Delete associated files
    from app.models.materials import QuotationAttachment
    attachments = db.query(QuotationAttachment).filter(
        QuotationAttachment.quotation_id == quotation_id
    ).all()
    
    for att in attachments:
        file_path = att.file_path.replace("/uploads/", "uploads/")
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Also delete old file_path if exists
    if quotation.file_path:
        old_path = quotation.file_path.replace("/uploads/", "uploads/")
        if os.path.exists(old_path):
            os.remove(old_path)
    
    db.delete(quotation)
    db.commit()
    
    return {"message": "报价单已删除"}


QUOTATION_UPLOAD_DIR = "uploads/quotations"


@router.post("/quotations/{quotation_id}/attachments")
async def upload_quotation_attachment(
    quotation_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传报价单附件"""
    from app.models.materials import QuotationAttachment
    
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="报价单不存在")
    
    # Validate file type
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="只支持PDF和图片文件")
    
    # Ensure upload directory exists
    os.makedirs(QUOTATION_UPLOAD_DIR, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "pdf"
    file_name = f"q{quotation_id}_{timestamp}.{file_ext}"
    file_path = os.path.join(QUOTATION_UPLOAD_DIR, file_name)
    
    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Determine file type
    file_type = "pdf" if file.content_type == "application/pdf" else "image"
    
    # Create attachment record
    attachment = QuotationAttachment(
        quotation_id=quotation_id,
        file_path=f"/uploads/quotations/{file_name}",
        file_name=file.filename,
        file_type=file_type,
        file_size=len(content)
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return {
        "id": attachment.id,
        "file_path": attachment.file_path,
        "file_name": attachment.file_name,
        "file_type": attachment.file_type
    }


@router.delete("/quotation-attachments/{attachment_id}")
async def delete_quotation_attachment(attachment_id: int, db: Session = Depends(get_db)):
    """删除报价单附件"""
    from app.models.materials import QuotationAttachment
    
    attachment = db.query(QuotationAttachment).filter(
        QuotationAttachment.id == attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    # Delete file
    file_path = attachment.file_path.replace("/uploads/", "uploads/")
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.delete(attachment)
    db.commit()
    
    return {"message": "附件已删除"}


# Column mapping configuration
COLUMN_MAPPING = {
    "sap_code": ["sap", "code", "sap_code", "sap号", "编码", "料号", "sap #", "no."],
    "name_cn": ["name", "name_cn", "cn_name", "中文名称", "品名", "名称", "中文名", "material description", "description"],
    "name_vn": ["name_vn", "vn_name", "越南名称", "越语名", "vietnamese", "越南语", "越南语名称", "vn", "越语"],
    "category": ["category", "type", "种类", "类别", "分类", "material type"],
    "subcategory": ["subcategory", "sub_type", "子类", "细分"],
    "workshop": ["workshop", "department", "車間", "车间", "部门", "user dept"],
    "location": ["location", "position", "库位", "位置", "货架", "bin/shelf"],
    "unit": ["unit", "uom", "单位", "base unit"],
    "min_stock": ["min_stock", "safety_stock", "stock_min", "安全库存", "最低库存", "min"],
    "specification": ["spec", "specification", "规格", "参数", "型号", "tech spec"],
    "equipment": ["equipment", "machine", "设备", "适用机型"],
    "purchase_link": ["link", "url", "链接", "购买链接"]
}

@router.post("/import")
async def import_materials(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从CSV或Excel导入物料数据"""
    filename = file.filename
    content_type = file.content_type
    
    # Read file content
    contents = await file.read()
    
    # Parse data
    rows = []
    
    try:
        if filename.endswith('.csv'):
            # Handle CSV
            # Detect encoding
            try:
                text = contents.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = contents.decode('gbk')
            
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
        elif filename.endswith(('.xls', '.xlsx')):
            # Handle Excel
            workbook = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
        else:
            raise HTTPException(status_code=400, detail="只支持CSV或Excel文件")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
        
    if not rows:
        raise HTTPException(status_code=400, detail="文件为空")
        
    # Process headers
    headers = [str(h).lower().strip() if h else "" for h in rows[0]]
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="文件没有数据行")
        
    # Map columns
    mapping = {}
    for field, keywords in COLUMN_MAPPING.items():
        for i, h in enumerate(headers):
            if any(k in h for k in keywords):
                mapping[field] = i
                break
    
    if "sap_code" not in mapping:
        raise HTTPException(status_code=400, detail="未找到SAP号码列 (SAP/Code/编码)")
    if "name_cn" not in mapping:
        raise HTTPException(status_code=400, detail="未找到名称列 (Name/名称/品名)")
        
    # Process data rows
    added = 0
    updated = 0
    errors = []
    
    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            # Extract data using mapping
            data = {}
            for field, col_idx in mapping.items():
                if col_idx < len(row):
                    val = row[col_idx]
                    # Clean data
                    if val is None:
                        continue
                    if isinstance(val, str):
                        val = val.strip()
                        if val == "":
                            continue
                    data[field] = val
            
            sap_code = str(data.get("sap_code", "")).strip()
            if not sap_code:
                continue
                
            name_cn = str(data.get("name_cn", "")).strip()
            if not name_cn:
                continue
            
            # Upsert
            material = db.query(Material).filter(Material.sap_code == sap_code).first()
            
            # Fill default values
            if "unit" not in data:
                data["unit"] = "个"
            if "min_stock" in data:
                try:
                    data["min_stock"] = int(float(data["min_stock"]))
                except:
                    data["min_stock"] = 0
            
            if material:
                # Update
                for k, v in data.items():
                    if k != "sap_code": # Don't update SAP code
                        setattr(material, k, v)
                updated += 1
            else:
                # Create
                new_material = Material(**data)
                db.add(new_material)
                db.flush() # Get ID
                
                # Auto create stock record
                stock = WarehouseStock(
                    material_id=new_material.id,
                    location=data.get("location")
                )
                db.add(stock)
                added += 1
                
        except Exception as e:
            errors.append(f"第 {row_idx} 行出错: {str(e)}")
            
    db.commit()
    
    return {
        "added": added,
        "updated": updated,
        "total": added + updated,
        "errors": errors[:10] # Return first 10 errors
    }


@router.get("/export/with-prices")
async def export_materials_with_prices(db: Session = Depends(get_db)):
    """导出物料数据含供应商价格历史"""
    from app.models.orders import OrderItem, PurchaseOrder
    from app.models.users import Supplier
    from fastapi.responses import StreamingResponse
    
    # Get all active materials
    materials = db.query(Material).order_by(Material.sap_code).all()
    
    # Get all supplier price data
    supplier_prices_map = {}  # material_id -> {supplier_id: [prices]}
    
    # From OrderItems
    order_prices = db.query(
        OrderItem.material_id,
        PurchaseOrder.supplier_id,
        Supplier.name.label('supplier_name'),
        OrderItem.unit_price,
        OrderItem.created_at
    ).join(
        PurchaseOrder, OrderItem.order_id == PurchaseOrder.id
    ).join(
        Supplier, PurchaseOrder.supplier_id == Supplier.id
    ).filter(
        OrderItem.unit_price > 0
    ).order_by(OrderItem.created_at.desc()).all()
    
    for item in order_prices:
        if item.material_id not in supplier_prices_map:
            supplier_prices_map[item.material_id] = {}
        
        if item.supplier_id not in supplier_prices_map[item.material_id]:
            supplier_prices_map[item.material_id][item.supplier_id] = {
                "name": item.supplier_name,
                "prices": []
            }
        
        # Limit to 5 most recent prices per supplier
        if len(supplier_prices_map[item.material_id][item.supplier_id]["prices"]) < 5:
            supplier_prices_map[item.material_id][item.supplier_id]["prices"].append(item.unit_price)
    
    # Build CSV content
    headers = [
        "SAP号码", "中文名称", "越南语名称", "种类", "细分", 
        "车间", "库位", "设备", "单位", "最低库存", "规格", "供应商价格历史"
    ]
    
    rows = []
    for m in materials:
        supplier_price_str = ""
        
        if m.id in supplier_prices_map:
            parts = []
            for sid, data in supplier_prices_map[m.id].items():
                prices_str = ",".join(str(int(p)) for p in data["prices"])
                parts.append(f"{data['name']}: {prices_str}")
            supplier_price_str = " | ".join(parts)
        
        rows.append([
            m.sap_code or "",
            m.name_cn or "",
            m.name_vn or "",
            m.category or "",
            m.subcategory or "",
            m.workshop or "",
            m.location or "",
            m.equipment or "",
            m.unit or "",
            str(m.min_stock or 0),
            m.specification or "",
            supplier_price_str
        ])
    
    # Generate CSV
    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    
    csv_content = output.getvalue()
    output.close()
    
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=materials_with_prices_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


# ===== Material Notes CRUD =====

class NoteCreate(BaseModel):
    content: str

class NoteUpdate(BaseModel):
    content: str


@router.get("/{material_id}/notes")
async def get_material_notes(material_id: int, db: Session = Depends(get_db)):
    """获取物料的所有说明记录"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    notes = db.query(MaterialNote).filter(
        MaterialNote.material_id == material_id
    ).order_by(MaterialNote.created_at.desc()).all()
    
    return [{"id": n.id, "content": n.content, "created_at": n.created_at.isoformat() if n.created_at else None} for n in notes]


@router.post("/{material_id}/notes")
async def add_material_note(material_id: int, data: NoteCreate, db: Session = Depends(get_db)):
    """为物料添加一条说明"""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    note = MaterialNote(material_id=material_id, content=data.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat() if note.created_at else None}


@router.put("/notes/{note_id}")
async def update_material_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    """编辑一条说明"""
    note = db.query(MaterialNote).filter(MaterialNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="说明记录不存在")
    
    note.content = data.content
    db.commit()
    db.refresh(note)
    return {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat() if note.created_at else None}


@router.delete("/notes/{note_id}")
async def delete_material_note(note_id: int, db: Session = Depends(get_db)):
    """删除一条说明"""
    note = db.query(MaterialNote).filter(MaterialNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="说明记录不存在")
    
    db.delete(note)
    db.commit()
    return {"message": "说明已删除"}
