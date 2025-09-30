"""
流式生成管理器

负责协调Redis缓存和PostgreSQL持久化:
- 实时写入Redis(每个chunk)
- 定时同步PostgreSQL(每5秒)
- 生成完成时最终写入PostgreSQL并清理Redis

设计原则:
- Redis承载99%的写入压力
- PostgreSQL每5秒批量更新(中间状态)
- 异常时让错误自然抛出,由上层统一处理
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chapter_cache import ChapterCacheService
from app.services.chapter import ChapterService
from app.models.chapter import ChapterStatus

logger = logging.getLogger(__name__)


class StreamGenerationManager:
    """流式生成管理器 - 协调Redis和PostgreSQL的数据流转"""

    SYNC_INTERVAL = 5  # PostgreSQL同步间隔(秒)

    def __init__(
        self,
        chapter_id: int,
        novel_id: int,
        session_id: str,
        db: AsyncSession
    ):
        """
        初始化流式生成管理器

        Args:
            chapter_id: 章节ID
            novel_id: 小说ID
            session_id: 生成会话ID
            db: 数据库会话
        """
        self.chapter_id = chapter_id
        self.novel_id = novel_id
        self.session_id = session_id
        self.db = db

        # 内容累积器
        self.title: str = ""
        self.content_buffer: str = ""
        self.content_length: int = 0

        # 同步控制
        self._last_sync_time: float = 0
        self._sync_task: Optional[asyncio.Task] = None
        self._generation_started: bool = False

    async def start_generation(self, title: str) -> None:
        """
        开始生成流程

        Args:
            title: 章节标题

        Raises:
            redis.RedisError: Redis操作失败
        """
        self.title = title
        self._generation_started = True

        # 在Redis中初始化generating数据
        await ChapterCacheService.set_generating_content(
            chapter_id=self.chapter_id,
            session_id=self.session_id,
            title=self.title,
            content="",
            content_length=0,
            novel_id=self.novel_id
        )

        # 更新数据库中的章节状态
        chapter_service = ChapterService(self.db)
        await chapter_service.update_chapter_status(
            self.chapter_id,
            ChapterStatus.GENERATING,
            session_id=self.session_id,
            generation_started_at=datetime.now()
        )

        logger.info(f"✅ 章节 {self.chapter_id} 开始生成: {title}")

    async def append_chunk(self, chunk: str) -> None:
        """
        追加内容chunk

        Args:
            chunk: 新生成的内容片段

        Raises:
            redis.RedisError: Redis写入失败
        """
        if not self._generation_started:
            raise RuntimeError("Generation not started. Call start_generation() first.")

        self.content_buffer += chunk
        self.content_length += len(chunk)

        # 实时写入Redis
        await ChapterCacheService.set_generating_content(
            chapter_id=self.chapter_id,
            session_id=self.session_id,
            title=self.title,
            content=self.content_buffer,
            content_length=self.content_length,
            novel_id=self.novel_id
        )

        # 检查是否需要同步PostgreSQL
        current_time = asyncio.get_event_loop().time()
        if current_time - self._last_sync_time >= self.SYNC_INTERVAL:
            await self._sync_to_postgresql()
            self._last_sync_time = current_time

    async def _sync_to_postgresql(self) -> None:
        """
        同步当前内容到PostgreSQL(中间状态)

        Raises:
            SQLAlchemy exceptions: 数据库操作失败
        """
        try:
            chapter_service = ChapterService(self.db)
            await chapter_service.update_chapter_content(
                chapter_id=self.chapter_id,
                content=self.content_buffer,
                content_length=self.content_length
            )
            await self.db.commit()

            logger.info(f"🔄 章节 {self.chapter_id} 同步到PostgreSQL: {self.content_length} 字符")
        except Exception as e:
            logger.error(f"❌ PostgreSQL同步失败 {self.chapter_id}: {e}")
            # 不阻断生成流程,继续依赖Redis
            # 让错误抛出,由上层决定如何处理
            raise

    async def complete_generation(
        self,
        final_content: str,
        options: list
    ) -> None:
        """
        完成生成,最终写入PostgreSQL并清理Redis

        Args:
            final_content: 完整章节内容
            options: 章节选项列表

        Raises:
            redis.RedisError: Redis操作失败
            SQLAlchemy exceptions: 数据库操作失败
        """
        if not self._generation_started:
            raise RuntimeError("Generation not started.")

        # 更新内容
        self.content_buffer = final_content
        self.content_length = len(final_content)

        # 1. 最终写入PostgreSQL
        chapter_service = ChapterService(self.db)
        await chapter_service.update_chapter_content(
            chapter_id=self.chapter_id,
            content=final_content,
            content_length=self.content_length
        )

        # 2. 创建选项
        await chapter_service.create_chapter_options(
            chapter_id=self.chapter_id,
            options_data=options
        )

        # 3. 更新状态为completed
        await chapter_service.update_chapter_status(
            self.chapter_id,
            ChapterStatus.COMPLETED,
            generation_completed_at=datetime.now()
        )

        await self.db.commit()

        # 4. 清理Redis generating数据
        await ChapterCacheService.complete_generation(self.chapter_id)

        logger.info(f"✅ 章节 {self.chapter_id} 生成完成: {self.content_length} 字符, {len(options)} 个选项")

    async def fail_generation(self, error_message: str) -> None:
        """
        标记生成失败

        Args:
            error_message: 错误信息

        Raises:
            redis.RedisError: Redis操作失败
        """
        if not self._generation_started:
            return

        # 1. 更新数据库状态
        try:
            chapter_service = ChapterService(self.db)
            await chapter_service.update_chapter_status(
                self.chapter_id,
                ChapterStatus.FAILED
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"❌ 更新失败状态到数据库失败 {self.chapter_id}: {e}")

        # 2. 更新Redis状态
        await ChapterCacheService.fail_generation(self.chapter_id, error_message)

        logger.warning(f"⚠️  章节 {self.chapter_id} 生成失败: {error_message}")

    @classmethod
    def generate_session_id(cls) -> str:
        """生成唯一的会话ID"""
        return str(uuid.uuid4())


@asynccontextmanager
async def managed_stream_generation(
    chapter_id: int,
    novel_id: int,
    session_id: str,
    db: AsyncSession
) -> AsyncGenerator[StreamGenerationManager, None]:
    """
    流式生成的上下文管理器(确保异常时正确清理)

    Usage:
        async with managed_stream_generation(...) as manager:
            await manager.start_generation(title)
            await manager.append_chunk(chunk)
            await manager.complete_generation(content, options)

    Raises:
        异常会自动调用fail_generation并重新抛出
    """
    manager = StreamGenerationManager(chapter_id, novel_id, session_id, db)

    try:
        yield manager
    except Exception as e:
        # 异常时标记失败
        try:
            await manager.fail_generation(str(e))
        except Exception as cleanup_error:
            logger.error(f"❌ 清理失败状态时出错: {cleanup_error}")

        # 重新抛出原始异常
        raise