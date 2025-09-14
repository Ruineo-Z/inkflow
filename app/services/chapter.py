from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc, asc
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
        chapter = Chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            title=summary_data.title,
            summary=summary_data.summary,
            content=""  # 内容稍后通过流式输出填充
        )

        self.db.add(chapter)
        await self.db.commit()
        await self.db.refresh(chapter)
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

    async def create_chapter_options(
        self,
        chapter_id: int,
        options_data: List[Dict[str, str]]
    ) -> List[Option]:
        """创建章节选项"""
        options = []
        for i, option_data in enumerate(options_data, 1):
            option = Option(
                chapter_id=chapter_id,
                option_order=i,
                option_text=option_data["text"],
                impact_description=option_data.get("impact_hint", "")
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
            select(Chapter.chapter_number, Chapter.title, Chapter.summary)
            .where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number <= (latest_chapter_num - exclude_recent)
            )
            .order_by(asc(Chapter.chapter_number))
        )

        summaries = []
        for row in result.fetchall():
            summaries.append({
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

        # 1. 获取小说基础信息
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = result.scalar_one_or_none()

        if not novel:
            raise ValueError(f"Novel with id {novel_id} not found")

        # 2. 获取最近5章的完整内容
        recent_chapters = await self.get_recent_chapters(novel_id, limit=5)

        # 3. 获取其余章节的摘要
        chapter_summaries = await self.get_chapter_summaries(novel_id, exclude_recent=5)

        # 4. 获取选择的选项文本
        selected_option_text = None
        if selected_option_id:
            result = await self.db.execute(
                select(Option.option_text)
                .where(Option.id == selected_option_id)
            )
            selected_option_text = result.scalar_one_or_none()

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

        return ChapterContext(
            world_setting=novel.world_setting or "",
            protagonist_info=novel.protagonist_info or "",
            recent_chapters=recent_chapters_data,  # 现在是字典列表，不是Pydantic模型
            chapter_summaries=chapter_summaries,
            selected_option=selected_option_text
        )

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
            .where(Chapter.novel_id == novel_id)
            .order_by(asc(Chapter.chapter_number))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())