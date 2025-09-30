from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ChapterStatus(str, PyEnum):
    """章节生成状态枚举"""
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)  # 章节序号
    title = Column(String(200), nullable=False)  # 章节标题
    summary = Column(Text)  # 章节摘要
    content = Column(Text)  # 章节正文

    # 流式生成相关字段
    status = Column(
        Enum(ChapterStatus),
        nullable=False,
        default=ChapterStatus.COMPLETED,
        server_default="completed"
    )
    session_id = Column(String(100), nullable=True)  # 生成会话ID
    content_length = Column(
        Integer,
        nullable=False,
        default=0,           # Python层默认值（ORM创建对象时使用）
        server_default='0'   # 数据库层默认值（直接SQL插入时使用）
    )  # 内容长度（用于断线重连判断差异）
    generation_started_at = Column(DateTime(timezone=True), nullable=True)  # 生成开始时间
    generation_completed_at = Column(DateTime(timezone=True), nullable=True)  # 生成完成时间

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    novel = relationship("Novel", back_populates="chapters")
    options = relationship("Option", back_populates="chapter", cascade="all, delete-orphan")
    user_choices = relationship("UserChoice", back_populates="chapter", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chapter(id={self.id}, novel_id={self.novel_id}, chapter_number={self.chapter_number}, title='{self.title}')>"