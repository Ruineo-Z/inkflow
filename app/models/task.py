from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum
from app.db.database import Base


class TaskStatus(enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待开始
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskType(enum.Enum):
    """任务类型枚举"""
    FIRST_CHAPTER_GENERATION = "first_chapter_generation"    # 第一章生成
    CHAPTER_GENERATION = "chapter_generation"                # 章节生成
    NOVEL_OUTLINE_GENERATION = "novel_outline_generation"    # 小说大纲生成


class GenerationTask(Base):
    """章节生成任务表"""
    __tablename__ = "generation_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)

    # 任务相关数据
    input_data = Column(Text, nullable=True)  # JSON格式的输入参数
    result_data = Column(Text, nullable=True)  # JSON格式的结果数据
    error_message = Column(Text, nullable=True)  # 错误信息

    # 进度信息
    progress_percentage = Column(Integer, default=0)  # 进度百分比
    current_step = Column(String(100), nullable=True)  # 当前步骤描述
    total_steps = Column(Integer, default=100)  # 总步骤数

    # 生成的章节ID（仅在章节生成任务中使用）
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    user = relationship("User", back_populates="generation_tasks")
    novel = relationship("Novel", back_populates="generation_tasks")
    chapter = relationship("Chapter", back_populates="generation_task")