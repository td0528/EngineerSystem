"""
Tasks API router - 任务系统
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import os
import shutil

from app.database.database import get_db
from app.models.tasks import Task, TaskAttachment, TaskComment
from app.models.users import User
from app.api.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploads/tasks"


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    is_public: bool = True
    priority: str = "普通"
    expected_completion: Optional[datetime] = None
    estimated_cost: Optional[float] = 0


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    expected_completion: Optional[datetime] = None
    actual_cost: Optional[float] = None


class TaskEvaluate(BaseModel):
    quality_score: int
    speed_score: int
    communication_score: int
    cost_control_score: int
    evaluation_comment: Optional[str] = None


class CommentCreate(BaseModel):
    content: str
    is_progress_update: bool = False


@router.get("/")
async def get_tasks(
    search: Optional[str] = None,
    status: Optional[str] = None,
    is_public: Optional[bool] = None,
    assignee_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    query = db.query(Task).options(
        joinedload(Task.creator),
        joinedload(Task.assignee)
    )
    
    if search:
        query = query.filter(Task.title.ilike(f"%{search}%"))
    if status:
        query = query.filter(Task.status == status)
    if is_public is not None:
        query = query.filter(Task.is_public == is_public)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    
    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": tasks}


@router.get("/public")
async def get_public_tasks(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """获取公共待认领任务"""
    tasks = db.query(Task).filter(
        Task.is_public == True,
        Task.status == "待认领"
    ).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    
    return tasks


@router.get("/{task_id}")
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """获取任务详情"""
    task = db.query(Task).options(
        joinedload(Task.creator),
        joinedload(Task.assignee),
        joinedload(Task.attachments),
        joinedload(Task.comments)
    ).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task


@router.post("/")
async def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    """创建新任务"""
    new_task = Task(
        **task_data.model_dump(),
        creator_id=1,  # TODO: Get from current user
        status="待认领" if task_data.is_public else "进行中"
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    return new_task


@router.put("/{task_id}")
async def update_task(task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)):
    """更新任务"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    for key, value in task_data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    
    if task_data.status == "已完成":
        task.actual_completion = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/claim")
async def claim_task(
    task_id: int,
    expected_completion: datetime,
    estimated_cost: float = 0,
    db: Session = Depends(get_db)
):
    """认领任务"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "待认领":
        raise HTTPException(status_code=400, detail="任务已被认领")
    
    task.assignee_id = 1  # TODO: Get from current user
    task.status = "进行中"
    task.expected_completion = expected_completion
    task.estimated_cost = estimated_cost
    
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/evaluate")
async def evaluate_task(task_id: int, eval_data: TaskEvaluate, db: Session = Depends(get_db)):
    """评价任务"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task.quality_score = eval_data.quality_score
    task.speed_score = eval_data.speed_score
    task.communication_score = eval_data.communication_score
    task.cost_control_score = eval_data.cost_control_score
    task.evaluation_comment = eval_data.evaluation_comment
    task.evaluated_by = 1  # TODO: Get from current user
    task.evaluated_at = datetime.utcnow()
    task.status = "已关闭"
    
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/attachments")
async def upload_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传附件"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # Save file
    file_name = f"task_{task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    attachment = TaskAttachment(
        task_id=task_id,
        file_name=file.filename,
        file_path=f"/uploads/tasks/{file_name}",
        file_type=file.content_type,
        file_size=file.size,
        uploaded_by=1  # TODO: Get from current user
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return attachment


@router.post("/{task_id}/comments")
async def add_comment(task_id: int, comment_data: CommentCreate, db: Session = Depends(get_db)):
    """添加评论/进度更新"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    comment = TaskComment(
        task_id=task_id,
        user_id=1,  # TODO: Get from current user
        content=comment_data.content,
        is_progress_update=comment_data.is_progress_update
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return comment
