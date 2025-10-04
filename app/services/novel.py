from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.novel import Novel
from app.schemas.novel import NovelCreate, NovelUpdate


class NovelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, novel_data: NovelCreate) -> Novel:
        novel = Novel(**novel_data.model_dump())
        self.db.add(novel)
        await self.db.commit()
        await self.db.refresh(novel)
        return novel

    async def get_by_id(self, novel_id: int) -> Optional[Novel]:
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Novel]:
        result = await self.db.execute(
            select(Novel).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user_id(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Novel]:
        result = await self.db.execute(
            select(Novel)
            .where(Novel.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_with_details(self, novel_id: int) -> Optional[Novel]:
        """获取小说详情（目前等同于get_by_id）"""
        return await self.get_by_id(novel_id)

    async def update(self, novel_id: int, novel_data: NovelUpdate) -> Optional[Novel]:
        novel = await self.get_by_id(novel_id)
        if not novel:
            return None

        update_data = novel_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(novel, field, value)

        await self.db.commit()
        await self.db.refresh(novel)
        return novel

    async def update_chapter_count(self, novel_id: int, count: int) -> Optional[Novel]:
        await self.db.execute(
            update(Novel)
            .where(Novel.id == novel_id)
            .values(total_chapters=count)
        )
        await self.db.commit()
        return await self.get_by_id(novel_id)

    async def delete(self, novel_id: int) -> bool:
        novel = await self.get_by_id(novel_id)
        if not novel:
            return False

        await self.db.delete(novel)
        await self.db.commit()
        return True