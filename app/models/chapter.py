from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)  # 章节序号
    title = Column(String(200), nullable=False)  # 章节标题
    summary = Column(Text)  # 章节摘要
    content = Column(Text)  # 章节正文
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    novel = relationship("Novel", back_populates="chapters")
    options = relationship("Option", back_populates="chapter", cascade="all, delete-orphan")
    user_choices = relationship("UserChoice", back_populates="chapter", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chapter(id={self.id}, novel_id={self.novel_id}, chapter_number={self.chapter_number}, title='{self.title}')>"