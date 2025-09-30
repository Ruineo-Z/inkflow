"""
章节生成缓存服务
使用Redis存储生成中的章节数据，支持流式断线重连

错误处理策略：
- 服务层让异常自然抛出，由API层统一处理
- RedisError表示基础设施错误，应该抛出让调用者知晓
- ValueError表示数据验证错误，分别处理
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import redis.asyncio as redis
from app.db.redis import RedisClient
from app.models.chapter import ChapterStatus

logger = logging.getLogger(__name__)


class ChapterCacheService:
    """章节缓存服务 - 管理Redis中的章节生成数据"""

    # Redis Key前缀
    KEY_GENERATING = "chapter:generating:{chapter_id}"
    KEY_STATUS = "chapter:status:{chapter_id}"

    # TTL设置（秒）
    TTL_COMPLETED = 3600  # 完成后缓存1小时
    TTL_FAILED = 600      # 失败后缓存10分钟

    @classmethod
    async def set_generating_content(
        cls,
        chapter_id: int,
        session_id: str,
        title: str,
        content: str,
        content_length: int,
        novel_id: int
    ) -> None:
        """
        保存生成中的章节内容到Redis

        Args:
            chapter_id: 章节ID
            session_id: 生成会话ID
            title: 章节标题
            content: 当前已生成内容
            content_length: 内容长度
            novel_id: 小说ID

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = cls.KEY_GENERATING.format(chapter_id=chapter_id)

        data = {
            "chapter_id": chapter_id,
            "novel_id": novel_id,
            "session_id": session_id,
            "title": title,
            "content": content,
            "content_length": content_length,
            "updated_at": int(datetime.now().timestamp())
        }

        await redis_client.set(key, json.dumps(data))
        await cls.set_status(chapter_id, ChapterStatus.GENERATING)

        logger.info(f"✅ Redis: 保存生成中章节 {chapter_id}, 长度: {content_length}")

    @classmethod
    async def get_generating_content(cls, chapter_id: int) -> Optional[Dict[str, Any]]:
        """
        获取生成中的章节内容

        Args:
            chapter_id: 章节ID

        Returns:
            Optional[Dict]: 章节数据，如果不存在返回None

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = cls.KEY_GENERATING.format(chapter_id=chapter_id)

        data = await redis_client.get(key)
        if not data:
            logger.info(f"Redis: 章节 {chapter_id} 不在生成缓存中")
            return None

        # 分离处理：JSON解析错误（数据错误）和Redis错误（基础设施错误）
        try:
            result = json.loads(data)
            logger.info(f"✅ Redis: 读取生成中章节 {chapter_id}, 长度: {result.get('content_length', 0)}")
            return result
        except json.JSONDecodeError as e:
            # 数据错误：记录警告并返回None，不影响系统运行
            logger.warning(f"⚠️  Redis数据错误 - 无效的JSON {chapter_id}: {e}")
            return None

    @classmethod
    async def set_status(cls, chapter_id: int, status: ChapterStatus) -> None:
        """
        设置章节状态

        Args:
            chapter_id: 章节ID
            status: 章节状态

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = cls.KEY_STATUS.format(chapter_id=chapter_id)

        await redis_client.set(key, status.value)
        logger.info(f"✅ Redis: 设置章节 {chapter_id} 状态为 {status.value}")

    @classmethod
    async def get_status(cls, chapter_id: int) -> Optional[ChapterStatus]:
        """
        获取章节状态

        Args:
            chapter_id: 章节ID

        Returns:
            Optional[ChapterStatus]: 章节状态，如果不存在返回None

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = cls.KEY_STATUS.format(chapter_id=chapter_id)

        status_str = await redis_client.get(key)
        if not status_str:
            return None

        # 分离处理：数据验证错误和Redis错误
        try:
            status = ChapterStatus(status_str)
            logger.info(f"✅ Redis: 读取章节 {chapter_id} 状态: {status.value}")
            return status
        except ValueError as e:
            # 数据错误：记录警告并返回None，不影响系统运行
            logger.warning(f"⚠️  Redis数据错误 - 无效的状态值 {chapter_id}: {status_str}")
            return None

    @classmethod
    async def complete_generation(cls, chapter_id: int) -> None:
        """
        标记章节生成完成，清理生成缓存

        Args:
            chapter_id: 章节ID

        Raises:
            redis.RedisError: Redis操作失败

        Note:
            完成后的章节数据从PostgreSQL读取，不在Redis缓存
            避免数据冗余和一致性问题
        """
        redis_client = await RedisClient.get_client()

        # 1. 删除generating数据
        generating_key = cls.KEY_GENERATING.format(chapter_id=chapter_id)
        await redis_client.delete(generating_key)

        # 2. 更新状态为completed（保留TTL，避免永久占用）
        status_key = cls.KEY_STATUS.format(chapter_id=chapter_id)
        await redis_client.setex(status_key, cls.TTL_COMPLETED, ChapterStatus.COMPLETED.value)

        logger.info(f"✅ Redis: 章节 {chapter_id} 生成完成，已清理缓存")

    @classmethod
    async def fail_generation(cls, chapter_id: int, error_message: str) -> None:
        """
        标记章节生成失败

        Args:
            chapter_id: 章节ID
            error_message: 错误信息

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()

        # 1. 删除generating数据
        generating_key = cls.KEY_GENERATING.format(chapter_id=chapter_id)
        await redis_client.delete(generating_key)

        # 2. 设置状态为failed，保留10分钟
        status_key = cls.KEY_STATUS.format(chapter_id=chapter_id)
        await redis_client.setex(status_key, cls.TTL_FAILED, ChapterStatus.FAILED.value)

        # 3. 保存错误信息
        error_key = f"chapter:error:{chapter_id}"
        error_data = {
            "chapter_id": chapter_id,
            "error": error_message,
            "failed_at": int(datetime.now().timestamp())
        }
        await redis_client.setex(error_key, cls.TTL_FAILED, json.dumps(error_data))

        logger.warning(f"⚠️  Redis: 章节 {chapter_id} 生成失败: {error_message}")

    @classmethod
    async def clear_chapter_cache(cls, chapter_id: int) -> None:
        """
        清除章节所有缓存数据（使用pipeline确保原子性）

        Args:
            chapter_id: 章节ID

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()

        keys_to_delete = [
            cls.KEY_GENERATING.format(chapter_id=chapter_id),
            cls.KEY_STATUS.format(chapter_id=chapter_id),
            f"chapter:error:{chapter_id}"
        ]

        # 使用pipeline确保原子性
        pipeline = redis_client.pipeline()
        for key in keys_to_delete:
            pipeline.delete(key)
        await pipeline.execute()

        logger.info(f"✅ Redis: 清除章节 {chapter_id} 所有缓存")