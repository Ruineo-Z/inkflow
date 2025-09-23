from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举 - 匹配数据库枚举值"""
    PENDING = "PENDING"      # 等待开始
    RUNNING = "RUNNING"      # 运行中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"        # 失败
    CANCELLED = "CANCELLED"  # 已取消


class TaskType(str, Enum):
    """任务类型枚举"""
    FIRST_CHAPTER_GENERATION = "FIRST_CHAPTER_GENERATION"    # 第一章生成
    CHAPTER_GENERATION = "CHAPTER_GENERATION"                # 章节生成
    NOVEL_OUTLINE_GENERATION = "NOVEL_OUTLINE_GENERATION"    # 小说大纲生成


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
    status: str = Field(description="任务状态")
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
    status: str = Field(description="初始状态")
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
    status: Optional[str] = Field(None, description="状态更新")
    result_data: Optional[dict] = Field(None, description="结果数据")
    error_message: Optional[str] = Field(None, description="错误信息")


# === 流式事件模型 ===

class TaskStreamEvent(BaseModel):
    """任务流式事件模型"""
    event: str = Field(description="事件类型：progress/complete/error")
    data: TaskProgressUpdate = Field(description="事件数据")


# === 新增的渐进增强接口模型 ===

class TaskStatusResponse(BaseModel):
    """任务状态查询响应（不含内容）"""
    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态")
    progress_percentage: int = Field(description="进度百分比")
    current_step: Optional[str] = Field(None, description="当前步骤")
    created_at: datetime = Field(description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")


class ContentChunk(BaseModel):
    """内容块模型"""
    position: int = Field(description="块位置索引")
    text: str = Field(description="文本内容")
    timestamp: Optional[datetime] = Field(None, description="生成时间戳")


class TaskContentResponse(BaseModel):
    """任务内容查询响应"""
    task_id: str = Field(description="任务ID")
    total_chunks: int = Field(description="总内容块数")
    from_position: int = Field(description="返回内容的起始位置")
    chunks: list[ContentChunk] = Field(description="内容块列表")
    is_complete: bool = Field(description="任务是否已完成")
    final_result: Optional[dict] = Field(None, description="最终结果（仅在完成时）")