from typing import Optional, List, Dict, Union, Literal, Annotated
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, Discriminator

# 小说基础模式
class NovelBase(BaseModel):
    title: str
    world_setting: Optional[str] = None
    protagonist_info: Optional[str] = None

# 创建小说请求模式
class NovelCreate(NovelBase):
    user_id: int

# 更新小说请求模式
class NovelUpdate(BaseModel):
    title: Optional[str] = None
    world_setting: Optional[str] = None
    protagonist_info: Optional[str] = None
    total_chapters: Optional[int] = None

# 小说响应模式
class NovelResponse(NovelBase):
    id: int
    total_chapters: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 小说详情响应模式
class NovelDetail(NovelResponse):
    pass

# === 第一个流程：用户创建小说所需的数据模型 ===

# 小说类型枚举
class NovelGenre(str, Enum):
    WUXIA = "wuxia"  # 武侠
    SCIFI = "scifi"   # 科幻

# 武侠世界观设定
class WuxiaWorldSetting(BaseModel):
    background: str = Field(description="世界背景")
    dynasty: str = Field(description="朝代设定")
    martial_arts_system: str = Field(description="武功体系")
    major_sects: List[str] = Field(description="主要门派")

# 科幻世界观设定
class SciFiWorldSetting(BaseModel):
    background: str = Field(description="世界背景")
    technology_level: str = Field(description="科技水平")
    space_setting: str = Field(description="太空设定")
    alien_races: List[str] = Field(description="外星种族")

# 主角初始信息
class ProtagonistProfile(BaseModel):
    name: str = Field(description="主角姓名")
    personality: str = Field(description="性格特点")
    background: str = Field(description="背景故事")
    motivation: str = Field(description="主要动机")

# 完整小说初始信息
class NovelFullProfile(BaseModel):
    title: str = Field(description="小说标题")
    summary: str = Field(description="小说简介")
    world_setting: Union[WuxiaWorldSetting, SciFiWorldSetting] = Field(description="世界观设定")
    protagonist: ProtagonistProfile = Field(description="主角信息")