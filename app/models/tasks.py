"""
Task models - 任务系统
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base


class Task(Base):
    """Task model - 任务"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Task source
    source_image = Column(String(255))  # 问题照片
    
    # Assignment
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"))  # 可为空（公共区域待认领）
    is_public = Column(Boolean, default=True)  # 是否公开待认领
    
    # Status
    status = Column(String(20), default="待认领")  # 待认领/进行中/待审核/已完成/已关闭
    priority = Column(String(20), default="普通")  # 紧急/高/普通/低
    
    # Time tracking
    expected_completion = Column(DateTime)  # 预计完成时间
    actual_completion = Column(DateTime)  # 实际完成时间
    
    # Cost
    estimated_cost = Column(Float, default=0)  # 预估费用
    actual_cost = Column(Float, default=0)  # 实际费用
    
    # Evaluation scores (1-5)
    quality_score = Column(Integer)  # 完成质量
    speed_score = Column(Integer)  # 响应速度  
    communication_score = Column(Integer)  # 沟通配合
    cost_control_score = Column(Integer)  # 成本控制
    evaluation_comment = Column(Text)  # 评价内容
    evaluated_by = Column(Integer, ForeignKey("users.id"))
    evaluated_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", back_populates="tasks_created", foreign_keys=[creator_id])
    assignee = relationship("User", back_populates="tasks_assigned", foreign_keys=[assignee_id])
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")


class TaskAttachment(Base):
    """Task Attachment model - 任务附件"""
    __tablename__ = "task_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50))  # image/pdf/doc/etc
    file_size = Column(Integer)  # bytes
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship("Task", back_populates="attachments")


class TaskComment(Base):
    """Task Comment model - 任务评论/进度"""
    __tablename__ = "task_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_progress_update = Column(Boolean, default=False)  # 是否进度更新
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship("Task", back_populates="comments")
