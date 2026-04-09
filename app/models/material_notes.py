"""
MaterialNote model - 物料说明/规格记录
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base


class MaterialNote(Base):
    """物料说明记录 - 每个物料可以有多条说明"""
    __tablename__ = "material_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    material = relationship("Material", back_populates="notes")
