"""
Record models - 记录功能
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base


class Record(Base):
    """Record model - 快速记录"""
    __tablename__ = "records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200))
    description = Column(Text)
    image_path = Column(String(500))  # 拍照上传的图片
    
    record_type = Column(String(50))  # 点子/维修记录/创建想法
    
    # Status
    status = Column(String(20), default="待处理")  # 待处理/已完成/已添加任务/已删除
    
    # If converted to task
    task_id = Column(Integer, ForeignKey("tasks.id"))
    
    # If marked as completed
    result_description = Column(Text)  # 效果叙述
    completed_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="records")
