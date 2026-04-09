"""
Document models - 资料管理
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.database import Base


class Document(Base):
    """Document model - 文档主表"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    
    # Classification
    category = Column(String(50))  # 图纸/验厂资料/合同/规定
    subcategory = Column(String(50))
    tags = Column(String(500))  # JSON array of tags
    
    # Current version info
    current_version = Column(String(20), default="1.0")
    current_file_path = Column(String(500))
    file_type = Column(String(20))  # pdf/docx/xlsx
    file_size = Column(Integer)
    
    # Full-text search content (extracted from PDF/Word/Excel)
    search_content = Column(Text)  # Extracted text for FTS
    
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    versions = relationship("DocumentVersion", back_populates="document", order_by="desc(DocumentVersion.created_at)")


class DocumentVersion(Base):
    """Document Version model - 版本历史"""
    __tablename__ = "document_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    version = Column(String(20), nullable=False)  # 0.1, 0.2, 1.0, etc.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    
    change_notes = Column(Text)  # 变更说明
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="versions")
