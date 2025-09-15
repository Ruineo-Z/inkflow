from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# === 基础模型 ===

class ChapterBase(BaseModel):
    title: str = Field(description="章节标题")
    summary: Optional[str] = Field(None, description="章节摘要")
    content: Optional[str] = Field(None, description="章节正文")


class OptionBase(BaseModel):
    option_text: str = Field(description="选项文本内容")
    impact_description: Optional[str] = Field(None, description="对后续剧情的影响描述")


# === 请求模型 ===

class GenerateChapterRequest(BaseModel):
    # 移除selected_option_id字段
    # 后端将自动从数据库查询用户的最新选择
    # 如果是第一章生成，将通过章节数量判断
    pass


class SaveUserChoiceRequest(BaseModel):
    option_id: int = Field(description="用户选择的选项ID")


# === 响应模型 ===

class OptionResponse(OptionBase):
    id: int
    option_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChapterResponse(ChapterBase):
    id: int
    chapter_number: int
    novel_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    options: List[OptionResponse] = []
    selected_option_id: Optional[int] = Field(None, description="用户选择的选项ID")

    class Config:
        from_attributes = True


class UserChoiceResponse(BaseModel):
    id: int
    user_id: int
    chapter_id: int
    option_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# === AI生成专用模型 ===

class ChapterSummary(BaseModel):
    """章节摘要生成模型（结构化输出用）"""
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要")
    key_events: List[str] = Field(description="关键事件列表")
    conflicts: List[str] = Field(description="冲突点列表")


class ChapterOption(BaseModel):
    """章节选项模型"""
    text: str = Field(description="选项文本")
    impact_hint: str = Field(description="选择影响提示")


class ChapterFullContent(BaseModel):
    """完整章节内容模型（流式输出用）"""
    title: str = Field(description="章节标题")
    content: str = Field(description="章节正文内容")
    options: List[ChapterOption] = Field(description="三个选择选项")


# === 上下文模型 ===

class ChapterContext(BaseModel):
    """章节生成上下文信息"""
    world_setting: str = Field(description="世界观设定")
    protagonist_info: str = Field(description="主角信息")
    recent_chapters: List[dict] = Field(default=[], description="最近的章节完整内容")
    chapter_summaries: List[dict] = Field(default=[], description="其他章节摘要")
    selected_option: Optional[str] = Field(None, description="用户选择的选项文本")


# === 流式输出事件模型 ===

class StreamEvent(BaseModel):
    """流式输出事件模型"""
    event: str = Field(description="事件类型：summary/content/options/complete/error")
    data: dict = Field(description="事件数据")