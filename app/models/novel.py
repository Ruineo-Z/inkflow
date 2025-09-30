from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base

class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text)  # 小说描述
    theme = Column(String(50), nullable=False, default='modern')  # 主题：武侠、科幻等
    status = Column(String(20), nullable=False, default='draft')  # 状态：草稿、进行中、完成
    background_setting = Column(Text)  # 背景设定
    character_setting = Column(Text)  # 角色设定
    outline = Column(Text)  # 大纲
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    user = relationship("User", back_populates="novels")
    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")