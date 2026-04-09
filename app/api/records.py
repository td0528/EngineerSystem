"""
Records API router - 记录功能
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import os
import shutil

from app.database.database import get_db
from app.models.records import Record
from app.models.tasks import Task
from app.api.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploads/records"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class RecordCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    record_type: Optional[str] = None  # 点子/维修记录/创建想法


class RecordUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    result_description: Optional[str] = None


@router.get("/")
async def get_records(
    status: Optional[str] = None,
    record_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取记录列表"""
    query = db.query(Record)
    
    if status:
        query = query.filter(Record.status == status)
    if record_type:
        query = query.filter(Record.record_type == record_type)
    
    total = query.count()
    records = query.order_by(Record.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": records}


@router.get("/{record_id}")
async def get_record(record_id: int, db: Session = Depends(get_db)):
    """获取记录详情"""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@router.post("/")
async def create_record(
    title: Optional[str] = None,
    description: Optional[str] = None,
    record_type: Optional[str] = None,
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """创建新记录（带图片）"""
    image_path = None
    
    if file:
        file_name = f"record_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        image_path = f"/uploads/records/{file_name}"
    
    new_record = Record(
        user_id=1,  # TODO: Get from current user
        title=title,
        description=description,
        record_type=record_type,
        image_path=image_path
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    return new_record


@router.put("/{record_id}")
async def update_record(record_id: int, record_data: RecordUpdate, db: Session = Depends(get_db)):
    """更新记录"""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    for key, value in record_data.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    
    if record_data.status == "已完成":
        record.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(record)
    return record


@router.post("/{record_id}/convert-to-task")
async def convert_to_task(record_id: int, db: Session = Depends(get_db)):
    """将记录转换为任务"""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    # Create task from record
    task = Task(
        title=record.title or "来自记录的任务",
        description=record.description,
        source_image=record.image_path,
        creator_id=record.user_id,
        is_public=True,
        status="待认领"
    )
    db.add(task)
    db.flush()
    
    # Update record
    record.task_id = task.id
    record.status = "已添加任务"
    
    db.commit()
    db.refresh(task)
    
    return {"success": True, "task_id": task.id}


@router.delete("/{record_id}")
async def delete_record(record_id: int, db: Session = Depends(get_db)):
    """删除记录"""
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    record.status = "已删除"
    db.commit()
    
    return {"success": True}
