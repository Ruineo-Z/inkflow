from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    option_order = Column(Integer, nullable=False)  # 选项顺序 (1, 2, 3)
    option_text = Column(Text, nullable=False)  # 选项文本内容
    impact_description = Column(Text)  # 对后续剧情的影响描述
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    chapter = relationship("Chapter", back_populates="options")
    user_choices = relationship("UserChoice", back_populates="option", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Option(id={self.id}, chapter_id={self.chapter_id}, order={self.option_order})>"


class UserChoice(Base):
    __tablename__ = "user_choices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    option_id = Column(Integer, ForeignKey("options.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User", back_populates="choices")
    chapter = relationship("Chapter", back_populates="user_choices")
    option = relationship("Option", back_populates="user_choices")

    def __repr__(self):
        return f"<UserChoice(id={self.id}, user_id={self.user_id}, chapter_id={self.chapter_id}, option_id={self.option_id})>"