import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc, asc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chapter import Chapter
from app.models.option import Option, UserChoice
from app.models.novel import Novel
from app.schemas.chapter import (
    ChapterSummary,
    ChapterContext,
    ChapterResponse,
    OptionResponse
)

logger = logging.getLogger(__name__)


class ChapterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_chapter_with_summary(
        self,
        novel_id: int,
        chapter_number: int,
        summary_data: ChapterSummary
    ) -> Chapter:
        """创建章节并保存摘要信息"""

        # 计算章节ID：对于这个小说，章节ID = 章节号
        # 这样第1章ID=1，第2章ID=2，逻辑更清晰
        chapter_id = await self._calculate_chapter_id(novel_id, chapter_number)

        chapter = Chapter(
            id=chapter_id,  # 手动指定ID
            novel_id=novel_id,
            chapter_number=chapter_number,
            title=summary_data.title,
            summary=summary_data.summary,
            content=""  # 内容稍后通过流式输出填充
        )

        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)

        # 更新小说的总章节数
        await self._update_novel_total_chapters(novel_id)

        return chapter

    async def update_chapter_content(self, chapter_id: int, content: str) -> Chapter:
        """更新章节正文内容"""
        result = await self.db.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        chapter = result.scalar_one_or_none()

        if chapter:
            chapter.content = content
            await self.db.commit()
            await self.db.refresh(chapter)

        return chapter

    async def create_chapter_with_options(
        self,
        novel_id: int,
        title: str,
        summary: str,
        content: str,
        options_data: List[Dict[str, Any]]
    ) -> Chapter:
        """创建章节并保存完整内容和选项"""

        # 获取下一个章节号
        result = await self.db.execute(
            select(func.coalesce(func.max(Chapter.chapter_number), 0) + 1)
            .where(Chapter.novel_id == novel_id)
        )
        chapter_number = result.scalar()

        # 计算章节ID
        chapter_id = await self._calculate_chapter_id(novel_id, chapter_number)

        # 创建章节
        chapter = Chapter(
            id=chapter_id,
            novel_id=novel_id,
            chapter_number=chapter_number,
            title=title,
            summary=summary,
            content=content
        )

        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)

        # 创建选项
        if options_data:
            await self.create_chapter_options(chapter.id, options_data)

        # 更新小说的总章节数
        await self._update_novel_total_chapters(novel_id)

        return chapter

    async def create_chapter_options(
        self,
        chapter_id: int,
        options_data: List[Dict[str, str]]
    ) -> List[Option]:
        """创建章节选项"""

        options = []
        for i, option_data in enumerate(options_data, 1):
            # 计算选项ID：章节ID * 10 + 选项顺序
            # 例如：章节1001的第1个选项 = 10011
            option_id = self._calculate_option_id(chapter_id, i)

            # 提取标签数据
            tags = option_data.get("tags", {})
            weight_factors = option_data.get("weight_factors", {})

            # 构建权重因子JSON（如果AI没有生成，则基于标签计算默认值）
            if not weight_factors:
                weight_factors = self._calculate_default_weight_factors(tags)

            option = Option(
                id=option_id,  # 手动指定ID
                chapter_id=chapter_id,
                option_order=i,
                option_text=option_data["text"],
                impact_description=option_data.get("impact_hint", ""),
                # 添加标签字段
                action_type=tags.get("action_type"),
                narrative_impact=tags.get("narrative_impact"),
                character_focus=tags.get("character_focus"),
                pacing=tags.get("pacing"),  # 使用Schema处理后的字段名
                emotional_tone=tags.get("emotional_tone"),
                # 添加权重因子JSON
                weight_factors=weight_factors
            )
            options.append(option)
            self.db.add(option)

        await self.db.commit()
        for option in options:
            await self.db.refresh(option)

        return options

    async def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        """根据ID获取章节详情"""
        result = await self.db.execute(
            select(Chapter)
            .options(selectinload(Chapter.options))
            .where(Chapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_chapter_number(self, novel_id: int) -> int:
        """获取小说的最新章节号"""
        result = await self.db.execute(
            select(Chapter.chapter_number)
            .where(Chapter.novel_id == novel_id)
            .order_by(desc(Chapter.chapter_number))
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        return latest if latest is not None else 0

    async def get_recent_chapters(
        self,
        novel_id: int,
        limit: int = 5
    ) -> List[Chapter]:
        """获取最近的几个章节（完整内容）"""
        result = await self.db.execute(
            select(Chapter)
            .options(selectinload(Chapter.options))
            .where(Chapter.novel_id == novel_id)
            .order_by(desc(Chapter.chapter_number))
            .limit(limit)
        )
        chapters = list(result.scalars().all())
        # 按章节号正序返回
        return sorted(chapters, key=lambda x: x.chapter_number)

    async def get_chapter_summaries(
        self,
        novel_id: int,
        exclude_recent: int = 5
    ) -> List[Dict[str, Any]]:
        """获取除最近几章外的其他章节摘要"""
        # 先获取最新的章节号
        latest_chapter_num = await self.get_latest_chapter_number(novel_id)

        if latest_chapter_num <= exclude_recent:
            return []  # 如果总章节数不超过排除数量，返回空列表

        # 获取较早章节的摘要
        result = await self.db.execute(
            select(Chapter.id, Chapter.chapter_number, Chapter.title, Chapter.summary)
            .where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number <= (latest_chapter_num - exclude_recent)
            )
            .order_by(asc(Chapter.chapter_number))
        )

        summaries = []
        for row in result.fetchall():
            summaries.append({
                "id": row.id,
                "chapter_number": row.chapter_number,
                "title": row.title,
                "summary": row.summary
            })

        return summaries

    async def get_generation_context(
        self,
        novel_id: int,
        selected_option_id: Optional[int] = None
    ) -> ChapterContext:
        """获取章节生成所需的上下文信息"""

        logger.info(f"📋 开始构建章节生成上下文，小说ID: {novel_id}")
        if selected_option_id:
            logger.info(f"🎯 选择的选项ID: {selected_option_id}")
        else:
            logger.info(f"🎯 无选项ID，生成第一章")

        # 1. 获取小说基础信息
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = result.scalar_one_or_none()

        if not novel:
            raise ValueError(f"Novel with id {novel_id} not found")

        # 2. 获取最近5章的完整内容
        recent_chapters = await self.get_recent_chapters(novel_id, limit=5)
        recent_chapter_ids = [ch.id for ch in recent_chapters]
        logger.info(f"📚 使用完整章节内容的章节ID: {recent_chapter_ids}")

        # 3. 获取其余章节的摘要
        chapter_summaries = await self.get_chapter_summaries(novel_id, exclude_recent=5)
        summary_chapter_ids = [summary['id'] for summary in chapter_summaries]
        logger.info(f"📝 使用摘要的章节ID: {summary_chapter_ids}")

        # 4. 获取选择的选项文本
        selected_option_text = None
        if selected_option_id:
            result = await self.db.execute(
                select(Option.option_text)
                .where(Option.id == selected_option_id)
            )
            selected_option_text = result.scalar_one_or_none()
            if selected_option_text:
                logger.info(f"✅ 找到选项文本: {selected_option_text[:100]}...")
            else:
                logger.warning(f"⚠️ 选项ID {selected_option_id} 未找到对应文本")

        # 5. 手动构建章节数据，避免循环引用
        recent_chapters_data = []
        for chapter in recent_chapters:
            chapter_data = {
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "summary": chapter.summary,
                "content": chapter.content,
                "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
                "updated_at": chapter.updated_at.isoformat() if chapter.updated_at else None,
                "novel_id": chapter.novel_id,
                "options": [
                    {
                        "id": opt.id,
                        "option_order": opt.option_order,
                        "option_text": opt.option_text,
                        "impact_description": opt.impact_description,
                        "created_at": opt.created_at.isoformat() if opt.created_at else None
                    } for opt in chapter.options
                ]
            }
            recent_chapters_data.append(chapter_data)

        # 构建上下文完成日志
        context = ChapterContext(
            world_setting=novel.background_setting or "",
            protagonist_info=novel.character_setting or "",
            recent_chapters=recent_chapters_data,  # 现在是字典列表，不是Pydantic模型
            chapter_summaries=chapter_summaries,
            selected_option=selected_option_text
        )

        logger.info(f"✅ 上下文构建完成:")
        logger.info(f"   📚 完整内容章节数: {len(recent_chapters_data)}")
        logger.info(f"   📝 摘要章节数: {len(chapter_summaries)}")
        logger.info(f"   🎯 选项文本: {'有' if selected_option_text else '无'}")

        return context

    async def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        """根据ID获取章节信息（包含选项）"""
        result = await self.db.execute(
            select(Chapter)
            .options(selectinload(Chapter.options))
            .where(Chapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_user_choice(
        self,
        user_id: int,
        novel_id: int
    ) -> Optional[int]:
        """获取用户对该小说最新章节的选择选项ID"""

        # 1. 获取最新章节ID
        result = await self.db.execute(
            select(Chapter.id)
            .where(Chapter.novel_id == novel_id)
            .order_by(desc(Chapter.chapter_number))
            .limit(1)
        )
        latest_chapter_id = result.scalar_one_or_none()

        if not latest_chapter_id:
            return None  # 没有章节

        # 2. 获取用户对最新章节的选择
        choice_result = await self.db.execute(
            select(UserChoice.option_id)
            .where(
                UserChoice.user_id == user_id,
                UserChoice.chapter_id == latest_chapter_id
            )
        )

        return choice_result.scalar_one_or_none()

    async def save_user_choice(
        self,
        user_id: int,
        chapter_id: int,
        option_id: int
    ) -> UserChoice:
        """保存用户的选择记录"""

        # 检查是否已经有选择记录，避免重复选择
        existing_choice = await self.db.execute(
            select(UserChoice)
            .where(
                UserChoice.user_id == user_id,
                UserChoice.chapter_id == chapter_id
            )
        )

        if existing_choice.scalar_one_or_none():
            raise ValueError("User has already made a choice for this chapter")

        # 创建新的选择记录
        choice = UserChoice(
            user_id=user_id,
            chapter_id=chapter_id,
            option_id=option_id
        )

        self.db.add(choice)
        await self.db.commit()
        await self.db.refresh(choice)

        return choice

    async def get_user_choice(
        self,
        user_id: int,
        chapter_id: int
    ) -> Optional[UserChoice]:
        """获取用户在特定章节的选择"""
        result = await self.db.execute(
            select(UserChoice)
            .where(
                UserChoice.user_id == user_id,
                UserChoice.chapter_id == chapter_id
            )
        )
        return result.scalar_one_or_none()

    async def get_chapters_by_novel(
        self,
        novel_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Chapter]:
        """获取小说的所有章节列表"""
        result = await self.db.execute(
            select(Chapter)
            .options(selectinload(Chapter.options))
            .where(Chapter.novel_id == novel_id)
            .order_by(asc(Chapter.chapter_number))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_chapters_by_novel_with_user_choices(
        self,
        novel_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取小说的所有章节列表，包含用户选择信息"""

        # 1. 获取章节列表（包含选项）
        result = await self.db.execute(
            select(Chapter)
            .options(selectinload(Chapter.options))
            .where(Chapter.novel_id == novel_id)
            .order_by(asc(Chapter.chapter_number))
            .offset(skip)
            .limit(limit)
        )
        chapters = list(result.scalars().all())

        if not chapters:
            return []

        # 2. 获取用户对这些章节的选择
        chapter_ids = [chapter.id for chapter in chapters]
        user_choices_result = await self.db.execute(
            select(UserChoice.chapter_id, UserChoice.option_id)
            .where(
                UserChoice.user_id == user_id,
                UserChoice.chapter_id.in_(chapter_ids)
            )
        )

        # 构建章节ID到选择选项ID的映射
        user_choices_map = {
            row.chapter_id: row.option_id
            for row in user_choices_result.fetchall()
        }

        # 3. 构建返回数据，将章节信息和用户选择合并
        chapters_with_choices = []
        for chapter in chapters:
            chapter_dict = {
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "novel_id": chapter.novel_id,
                "title": chapter.title,
                "summary": chapter.summary,
                "content": chapter.content,
                "created_at": chapter.created_at,
                "updated_at": chapter.updated_at,
                "options": [
                    {
                        "id": opt.id,
                        "option_order": opt.option_order,
                        "option_text": opt.option_text,
                        "impact_description": opt.impact_description,
                        "created_at": opt.created_at
                    } for opt in chapter.options
                ],
                "selected_option_id": user_choices_map.get(chapter.id)
            }
            chapters_with_choices.append(chapter_dict)

        return chapters_with_choices

    async def get_chapter_by_id_with_user_choice(
        self,
        chapter_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取单个章节详情，包含用户选择信息"""

        # 1. 获取章节详情（包含选项）
        result = await self.db.execute(
            select(Chapter)
            .options(selectinload(Chapter.options))
            .where(Chapter.id == chapter_id)
        )
        chapter = result.scalar_one_or_none()

        if not chapter:
            return None

        # 2. 获取用户对该章节的选择
        user_choice_result = await self.db.execute(
            select(UserChoice.option_id)
            .where(
                UserChoice.user_id == user_id,
                UserChoice.chapter_id == chapter_id
            )
        )
        selected_option_id = user_choice_result.scalar_one_or_none()

        # 3. 构建返回数据
        chapter_data = {
            "id": chapter.id,
            "chapter_number": chapter.chapter_number,
            "novel_id": chapter.novel_id,
            "title": chapter.title,
            "summary": chapter.summary,
            "content": chapter.content,
            "created_at": chapter.created_at,
            "updated_at": chapter.updated_at,
            "options": [
                {
                    "id": opt.id,
                    "option_order": opt.option_order,
                    "option_text": opt.option_text,
                    "impact_description": opt.impact_description,
                    "created_at": opt.created_at
                } for opt in chapter.options
            ],
            "selected_option_id": selected_option_id
        }

        return chapter_data

    async def _update_novel_total_chapters(self, novel_id: int) -> None:
        """更新小说的总章节数"""
        # 查询当前小说的章节总数
        result = await self.db.execute(
            select(func.count(Chapter.id))
            .where(Chapter.novel_id == novel_id)
        )
        total_chapters = result.scalar() or 0

        # 更新小说表的 total_chapters 字段
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = result.scalar_one_or_none()

        if novel:
            novel.total_chapters = total_chapters
            await self.db.commit()
            await self.db.refresh(novel)

    async def _reset_chapter_sequence(self) -> None:
        """重置章节ID序列到下一个可用值"""
        try:
            # 查询当前最大的chapter ID
            result = await self.db.execute(
                select(func.max(Chapter.id))
            )
            max_id = result.scalar() or 0

            # 重置序列到最大ID + 1
            new_seq_value = max_id + 1
            await self.db.execute(
                text(f"ALTER SEQUENCE chapters_id_seq RESTART WITH {new_seq_value}")
            )
            await self.db.commit()

        except Exception as e:
            # 如果重置失败，记录错误但不影响主流程
            print(f"Warning: Failed to reset chapter sequence: {e}")

    async def _reset_option_sequence(self) -> None:
        """重置选项ID序列到下一个可用值"""
        try:
            # 查询当前最大的option ID
            result = await self.db.execute(
                select(func.max(Option.id))
            )
            max_id = result.scalar() or 0

            # 重置序列到最大ID + 1
            new_seq_value = max_id + 1
            await self.db.execute(
                text(f"ALTER SEQUENCE options_id_seq RESTART WITH {new_seq_value}")
            )
            await self.db.commit()

        except Exception as e:
            # 如果重置失败，记录错误但不影响主流程
            print(f"Warning: Failed to reset option sequence: {e}")

    def enable_auto_sequence_reset(self) -> None:
        """启用自动序列重置"""
        self._auto_reset_sequence = True

    def disable_auto_sequence_reset(self) -> None:
        """禁用自动序列重置"""
        self._auto_reset_sequence = False

    async def _calculate_chapter_id(self, novel_id: int, chapter_number: int) -> int:
        """
        计算章节ID
        策略：使用 novel_id * 1000 + chapter_number 确保不同小说的章节ID不冲突
        例如：
        - 小说1的第1章：ID = 1001
        - 小说1的第2章：ID = 1002
        - 小说2的第1章：ID = 2001
        """
        return novel_id * 1000 + chapter_number

    def _calculate_option_id(self, chapter_id: int, option_order: int) -> int:
        """
        计算选项ID
        策略：使用 chapter_id * 10 + option_order 确保选项ID有逻辑意义
        例如：
        - 章节1001的第1个选项：ID = 10011
        - 章节1001的第2个选项：ID = 10012
        - 章节1002的第1个选项：ID = 10021
        """
        return chapter_id * 10 + option_order

    def _calculate_default_weight_factors(self, tags: dict) -> dict:
        """
        基于标签计算默认权重因子
        当AI没有生成weight_factors时，使用此方法基于标签推导合理的权重值
        """
        # 默认权重值（中性）
        weights = {
            "risk_preference": 0.5,
            "exploration_desire": 0.5,
            "pacing_preference": 0.5,
            "relationship_focus": 0.5,
            "action_orientation": 0.5
        }

        # 基于action_type调整权重
        action_type = tags.get("action_type", "")
        if action_type == "risky":
            weights["risk_preference"] = 0.8
            weights["action_orientation"] = 0.7
        elif action_type == "conservative":
            weights["risk_preference"] = 0.2
            weights["action_orientation"] = 0.3
        elif action_type == "aggressive":
            weights["action_orientation"] = 0.9
            weights["risk_preference"] = 0.6
        elif action_type == "diplomatic":
            weights["relationship_focus"] = 0.8
            weights["action_orientation"] = 0.4

        # 基于narrative_impact调整权重
        narrative_impact = tags.get("narrative_impact", "")
        if narrative_impact == "exploration":
            weights["exploration_desire"] = 0.8
        elif narrative_impact == "relationship":
            weights["relationship_focus"] = 0.8

        # 基于pacing调整权重
        pacing = tags.get("pacing", "")
        if pacing == "fast":
            weights["pacing_preference"] = 0.8
        elif pacing == "slow":
            weights["pacing_preference"] = 0.2

        return weights