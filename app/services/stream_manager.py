"""
流式生成管理器

负责协调Redis缓存和PostgreSQL持久化:
- 实时写入Redis(每个chunk)
- 定时同步PostgreSQL(每5秒)
- 生成完成时最终写入PostgreSQL并清理Redis
- 从Redis流式推送给前端(支持断线重连)

设计原则:
- Redis承载99%的写入压力
- PostgreSQL每5秒批量更新(中间状态)
- 异常时让错误自然抛出,由上层统一处理
- 所有客户端统一从Redis获取数据(新生成和重连都是同一个接口)
"""
import asyncio
import logging
import uuid
import json
from datetime import datetime
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.chapter_cache import ChapterCacheService
from app.services.chapter import ChapterService
from app.models.chapter import Chapter, ChapterStatus

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

        # 在Redis中初始化generating数据 (Phase 2: 只存前端展示字段)
        await ChapterCacheService.set_generating_content(
            chapter_id=self.chapter_id,
            title=self.title,
            content=""
        )

        # 更新数据库中的章节状态和title
        chapter_service = ChapterService(self.db)

        # 先更新title
        result = await self.db.execute(
            select(Chapter).where(Chapter.id == self.chapter_id)
        )
        chapter = result.scalar_one_or_none()
        if chapter:
            chapter.title = title
            await self.db.commit()

        # 再更新状态
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

        # 实时写入Redis (Phase 2: 只存前端展示字段)
        await ChapterCacheService.set_generating_content(
            chapter_id=self.chapter_id,
            title=self.title,
            content=self.content_buffer
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
        options: list,
        summary: str = None
    ) -> None:
        """
        完成生成,最终写入PostgreSQL并清理Redis

        Args:
            final_content: 完整章节内容
            options: 章节选项列表
            summary: 章节摘要(可选)

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

        # 更新内容和summary
        result = await self.db.execute(
            select(Chapter).where(Chapter.id == self.chapter_id)
        )
        chapter = result.scalar_one_or_none()
        if chapter:
            chapter.content = final_content
            chapter.content_length = self.content_length
            if summary:
                chapter.summary = summary
            await self.db.commit()

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

        # 4. 清理Redis generating数据 (Phase 2: 生成完成时删除)
        await ChapterCacheService.delete_generating_content(self.chapter_id)

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

        # 2. 清理Redis数据 (Phase 2: 生成失败时删除)
        await ChapterCacheService.delete_generating_content(self.chapter_id)

        logger.warning(f"⚠️  章节 {self.chapter_id} 生成失败: {error_message}")

    @classmethod
    def generate_session_id(cls) -> str:
        """生成唯一的会话ID"""
        return str(uuid.uuid4())

    @staticmethod
    async def stream_to_client(
        chapter_id: int,
        db: AsyncSession
    ) -> AsyncGenerator[str, None]:
        """
        从Redis流式推送章节数据给前端（统一接口，支持新生成和断线重连）

        逻辑：
        1. 检查章节状态
        2. 如果正在生成或已完成：从Redis读取并流式推送
        3. 每100ms轮询一次Redis，推送增量内容
        4. 生成完成时推送complete事件并退出

        Args:
            chapter_id: 章节ID
            db: 数据库会话

        Yields:
            SSE格式的事件字符串

        Raises:
            ValueError: 章节不存在或状态异常
        """
        # 1. 查询章节状态
        chapter_service = ChapterService(db)
        chapter = await chapter_service.get_chapter_by_id(chapter_id)

        if not chapter:
            raise ValueError(f"章节 {chapter_id} 不存在")

        # 2. 检查章节状态
        if chapter.status == ChapterStatus.FAILED:
            # 生成失败，发送error事件
            yield f"event: error\ndata: {json.dumps({'error': '章节生成失败'}, ensure_ascii=False)}\n\n"
            return

        elif chapter.status == ChapterStatus.COMPLETED:
            # 已完成，直接推送完整数据
            # 加载options关系
            await db.refresh(chapter, ["options"])
            complete_data = {
                "chapter_id": chapter.id,
                "title": chapter.title,
                "content": chapter.content,
                "options": [
                    {
                        "id": opt.id,
                        "text": opt.option_text,
                        "impact_hint": opt.impact_description
                    }
                    for opt in chapter.options
                ]
            }
            yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
            return

        elif chapter.status != ChapterStatus.GENERATING:
            raise ValueError(f"章节 {chapter_id} 状态异常: {chapter.status}")

        # 3. 正在生成，从Redis流式推送
        redis_key = f"chapter:{chapter_id}:generating"
        last_content_length = 0
        no_update_count = 0
        title_sent = False  # 标志位:title是否已推送
        MAX_NO_UPDATE = 600  # 60秒无更新视为超时（600 * 100ms）- AI生成需要时间

        logger.info(f"📡 开始流式推送章节 {chapter_id}")

        while True:
            try:
                # 读取Redis数据
                data_str = await ChapterCacheService.get_generating_content(chapter_id)

                if data_str:
                    data = json.loads(data_str) if isinstance(data_str, str) else data_str
                    current_title = data.get('title', '')
                    current_content = data.get('content', '')
                    current_length = len(current_content)

                    # 首次推送title(只推送一次)
                    if current_title and not title_sent:
                        yield f"event: summary\ndata: {json.dumps({'title': current_title}, ensure_ascii=False)}\n\n"
                        title_sent = True

                    # 推送增量content
                    if current_length > last_content_length:
                        incremental = current_content[last_content_length:]
                        last_content_length = current_length
                        no_update_count = 0  # 重置无更新计数

                        yield f"event: content\ndata: {json.dumps({'text': incremental}, ensure_ascii=False)}\n\n"

                        logger.debug(f"📤 推送增量: {len(incremental)} 字符, 总计: {current_length}")
                    else:
                        no_update_count += 1

                # 检查章节状态是否变化
                await db.refresh(chapter)

                if chapter.status == ChapterStatus.COMPLETED:
                    # 生成完成
                    logger.info(f"✅ 章节 {chapter_id} 生成完成，推送complete事件")

                    # 加载options关系
                    await db.refresh(chapter, ["options"])
                    complete_data = {
                        "chapter_id": chapter.id,
                        "title": chapter.title,
                        "content": chapter.content,
                        "options": [
                            {
                                "id": opt.id,
                                "text": opt.option_text,
                                "impact_hint": opt.impact_description
                            }
                            for opt in chapter.options
                        ]
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                    break

                elif chapter.status == ChapterStatus.FAILED:
                    # 生成失败
                    logger.warning(f"⚠️  章节 {chapter_id} 生成失败")
                    yield f"event: error\ndata: {json.dumps({'error': '章节生成失败'}, ensure_ascii=False)}\n\n"
                    break

                # 超时检测
                if no_update_count >= MAX_NO_UPDATE:
                    logger.warning(f"⚠️  章节 {chapter_id} 超时（10秒无更新）")
                    yield f"event: error\ndata: {json.dumps({'error': '生成超时'}, ensure_ascii=False)}\n\n"
                    break

                # 等待100ms
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ 流式推送出错 {chapter_id}: {e}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                break

        logger.info(f"📡 章节 {chapter_id} 流式推送结束")


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