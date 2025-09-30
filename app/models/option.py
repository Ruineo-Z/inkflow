from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    option_order = Column(Integer, nullable=False)  # 选项顺序 (1, 2, 3)
    option_text = Column(Text, nullable=False)  # 选项文本内容
    impact_description = Column(Text)  # 对后续剧情的影响描述
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 新增：标签系统字段
    action_type = Column(String(20), nullable=True)  # 行动倾向类型
    narrative_impact = Column(String(20), nullable=True)  # 叙事影响类型
    character_focus = Column(String(20), nullable=True)  # 角色发展焦点
    pacing = Column(String(10), nullable=True)  # 节奏控制类型
    emotional_tone = Column(String(20), nullable=True)  # 情感色彩

    # 权重因子（JSON格式存储）
    weight_factors = Column(JSON, nullable=True)  # 存储权重因子字典

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