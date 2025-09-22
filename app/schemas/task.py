from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待开始
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskType(str, Enum):
    """任务类型枚举"""
    FIRST_CHAPTER_GENERATION = "first_chapter_generation"    # 第一章生成
    CHAPTER_GENERATION = "chapter_generation"                # 章节生成
    NOVEL_OUTLINE_GENERATION = "novel_outline_generation"    # 小说大纲生成


# === 请求模型 ===

class StartGenerationTaskRequest(BaseModel):
    """启动生成任务请求"""
    novel_id: int = Field(description="小说ID")
    task_type: TaskType = Field(description="任务类型")
    input_data: Optional[dict] = Field(None, description="输入数据")


class CancelTaskRequest(BaseModel):
    """取消任务请求"""
    task_id: str = Field(description="任务ID")


# === 响应模型 ===

class TaskProgressResponse(BaseModel):
    """任务进度响应"""
    task_id: str = Field(description="任务ID")
    status: TaskStatus = Field(description="任务状态")
    progress_percentage: int = Field(description="进度百分比")
    current_step: Optional[str] = Field(None, description="当前步骤")
    total_steps: int = Field(description="总步骤数")

    # 结果数据（仅在完成时有值）
    result_data: Optional[dict] = Field(None, description="结果数据")
    error_message: Optional[str] = Field(None, description="错误信息")

    # 时间信息
    created_at: datetime = Field(description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True


class StartTaskResponse(BaseModel):
    """启动任务响应"""
    task_id: str = Field(description="任务ID")
    status: TaskStatus = Field(description="初始状态")
    message: str = Field(description="启动消息")


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: list[TaskProgressResponse] = Field(description="任务列表")
    total: int = Field(description="总数量")


# === 内部事件模型 ===

class TaskProgressUpdate(BaseModel):
    """任务进度更新事件"""
    task_id: str = Field(description="任务ID")
    progress_percentage: int = Field(description="进度百分比")
    current_step: Optional[str] = Field(None, description="当前步骤描述")
    status: Optional[TaskStatus] = Field(None, description="状态更新")
    result_data: Optional[dict] = Field(None, description="结果数据")
    error_message: Optional[str] = Field(None, description="错误信息")


# === 流式事件模型 ===

class TaskStreamEvent(BaseModel):
    """任务流式事件模型"""
    event: str = Field(description="事件类型：progress/complete/error")
    data: TaskProgressUpdate = Field(description="事件数据")