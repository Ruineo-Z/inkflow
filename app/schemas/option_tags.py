"""
选项标签定义
用于分析用户选择偏好和实现动态叙事指导
"""
from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """行动倾向标签"""
    ACTIVE = "active"           # 主动出击，直接行动
    CONSERVATIVE = "conservative"  # 谨慎观察，稳妥应对
    RISKY = "risky"            # 冒险尝试，不确定后果
    DIPLOMATIC = "diplomatic"   # 交涉协商，和平解决
    AGGRESSIVE = "aggressive"   # 强势对抗，激烈冲突


class NarrativeImpact(str, Enum):
    """叙事影响标签"""
    EXPLORATION = "exploration"     # 探索新内容，扩展世界观
    DEVELOPMENT = "development"     # 推进主线，发展剧情
    RESOLUTION = "resolution"       # 解决冲突，收束线索
    RELATIONSHIP = "relationship"   # 人际关系，情感发展
    WORLDBUILDING = "worldbuilding" # 世界观建设，背景补充


class CharacterFocus(str, Enum):
    """角色发展焦点标签"""
    SELF_GROWTH = "self_growth"         # 主角个人成长
    RELATIONSHIP = "relationship"        # 人际关系发展
    WORLD_INTERACTION = "world_interaction"  # 与世界环境互动
    SKILL_DEVELOPMENT = "skill_development"  # 技能或能力发展
    MORAL_CHOICE = "moral_choice"       # 道德选择和价值观


class PacingType(str, Enum):
    """节奏控制标签"""
    SLOW = "slow"       # 慢节奏，详细描述，深入思考
    MEDIUM = "medium"   # 中等节奏，平衡发展
    FAST = "fast"       # 快节奏，快速推进，即时反应


class EmotionalTone(str, Enum):
    """情感色彩标签"""
    POSITIVE = "positive"   # 积极向上，乐观
    NEUTRAL = "neutral"     # 中性，客观
    DARK = "dark"          # 黑暗，悲伤，严肃
    HUMOROUS = "humorous"  # 幽默，轻松
    MYSTERIOUS = "mysterious"  # 神秘，悬疑


class OptionTags(BaseModel):
    """选项标签集合"""
    action_type: ActionType = Field(description="行动倾向类型")
    narrative_impact: NarrativeImpact = Field(description="对叙事的影响类型")
    character_focus: CharacterFocus = Field(description="角色发展焦点")
    pacing: PacingType = Field(alias="pacing_type", description="节奏控制类型")
    emotional_tone: EmotionalTone = Field(description="情感色彩")


class OptionWeightFactors(BaseModel):
    """选项权重因子"""
    risk_preference: float = Field(ge=0.0, le=1.0, description="风险偏好权重(0-1)")
    exploration_desire: float = Field(ge=0.0, le=1.0, description="探索欲望权重(0-1)")
    pacing_preference: float = Field(ge=0.0, le=1.0, description="节奏偏好权重(0-1)")
    relationship_focus: float = Field(ge=0.0, le=1.0, description="关系关注权重(0-1)")
    action_orientation: float = Field(ge=0.0, le=1.0, description="行动导向权重(0-1)")


class TaggedChapterOption(BaseModel):
    """带标签的章节选项"""
    id: Optional[int] = None
    text: str = Field(description="选项文本内容")
    impact_hint: str = Field(description="选择后果提示")

    # 标签系统
    tags: OptionTags = Field(description="选项标签集合")
    weight_factors: OptionWeightFactors = Field(description="权重因子")

    # 元数据
    display_order: int = Field(default=1, description="显示顺序")
    is_enabled: bool = Field(default=True, description="是否可选")


class UserPreferenceProfile(BaseModel):
    """用户偏好画像"""
    user_id: int

    # 基于选择历史计算的偏好值
    risk_preference: float = Field(ge=0.0, le=1.0, description="风险偏好(0保守-1冒险)")
    exploration_desire: float = Field(ge=0.0, le=1.0, description="探索欲望(0低-1高)")
    pacing_preference: float = Field(ge=0.0, le=1.0, description="节奏偏好(0慢-1快)")
    relationship_focus: float = Field(ge=0.0, le=1.0, description="关系关注度(0低-1高)")
    action_orientation: float = Field(ge=0.0, le=1.0, description="行动导向(0被动-1主动)")

    # 偏好的标签类型统计
    preferred_action_types: Dict[str, float] = Field(default_factory=dict, description="偏好的行动类型分布")
    preferred_narrative_impacts: Dict[str, float] = Field(default_factory=dict, description="偏好的叙事影响分布")
    preferred_emotional_tones: Dict[str, float] = Field(default_factory=dict, description="偏好的情感色彩分布")

    # 元数据
    total_choices: int = Field(default=0, description="总选择次数")
    last_updated: Optional[str] = Field(default=None, description="最后更新时间")
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0, description="偏好数据可信度")


class ChapterGuidanceContext(BaseModel):
    """章节指导上下文"""
    chapter_num: int
    genre: str
    user_preferences: Optional[UserPreferenceProfile] = None

    # 故事状态分析
    unresolved_conflicts: int = Field(default=0, description="未解决冲突数量")
    character_development_level: float = Field(ge=0.0, le=1.0, default=0.5, description="角色发展程度")
    world_building_completeness: float = Field(ge=0.0, le=1.0, default=0.5, description="世界观完整度")

    # 最近章节的选择模式
    recent_choice_pattern: list[str] = Field(default_factory=list, description="最近的选择模式")
    story_coherence_score: float = Field(ge=0.0, le=1.0, default=0.8, description="故事连贯性评分")


class NarrativeGuidance(BaseModel):
    """叙事指导结果"""
    stage: str = Field(description="当前叙事阶段")
    focus: str = Field(description="焦点内容")

    # 选项生成指导
    recommended_option_distribution: Dict[str, float] = Field(description="推荐的选项类型分布")
    pacing_guidance: str = Field(description="节奏控制指导")
    emotional_guidance: str = Field(description="情感氛围指导")

    # 个性化调整
    personalization_notes: Optional[str] = Field(default=None, description="个性化调整说明")
    confidence: float = Field(ge=0.0, le=1.0, description="指导可信度")