from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum
from app.db.database import Base


class TaskStatus(enum.Enum):
    """任务状态枚举"""
    PENDING = "PENDING"      # 等待开始
    RUNNING = "RUNNING"      # 运行中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"        # 失败
    CANCELLED = "CANCELLED"  # 已取消


class TaskType(enum.Enum):
    """任务类型枚举"""
    FIRST_CHAPTER_GENERATION = "FIRST_CHAPTER_GENERATION"    # 第一章生成
    CHAPTER_GENERATION = "CHAPTER_GENERATION"                # 章节生成
    NOVEL_OUTLINE_GENERATION = "NOVEL_OUTLINE_GENERATION"    # 小说大纲生成


class GenerationTask(Base):
    """章节生成任务表 - 简化版，只存储核心业务信息"""
    __tablename__ = "generation_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)

    # 只保留最终状态，实时状态存储在Redis中
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)

    # 任务相关数据
    input_data = Column(Text, nullable=True)  # JSON格式的输入参数
    result_data = Column(Text, nullable=True)  # JSON格式的最终结果数据
    error_message = Column(Text, nullable=True)  # 最终错误信息

    # 生成的章节ID（仅在章节生成任务中使用）
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)

    # 简化时间戳 - 移除实时更新字段
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)  # 只在最终完成时更新

    # 移除的字段（现在存储在Redis中）：
    # ❌ progress_percentage - 实时进度存储在Redis
    # ❌ current_step - 实时状态存储在Redis
    # ❌ total_steps - 不需要存储
    # ❌ started_at - 不需要存储
    # ❌ updated_at - 减少数据库写入

    # 关联关系
    user = relationship("User", back_populates="generation_tasks")
    novel = relationship("Novel", back_populates="generation_tasks")
    chapter = relationship("Chapter", back_populates="generation_task")