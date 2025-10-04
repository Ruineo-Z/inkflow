"""
章节生成缓存服务
使用Redis存储生成中的章节数据，支持流式断线重连

Phase 2设计原则：
- Redis中的数据仅用于前端展示,只存储前端需要显示的字段
- 不设置TTL,生成成功或失败时主动删除
- Key格式: chapter:{chapter_id}:generating
"""
import json
import logging
from typing import Optional, Dict, Any, List

import redis.asyncio as redis
from app.db.redis import RedisClient

logger = logging.getLogger(__name__)


class ChapterCacheService:
    """章节缓存服务 - 管理Redis中的章节生成数据"""

    @staticmethod
    async def set_generating_content(
        chapter_id: int,
        title: str,
        content: str,
        options: List[str] = None
    ) -> None:
        """
        设置生成中的章节内容

        Phase 2设计: 只存储前端展示需要的字段(title, content, options)

        Args:
            chapter_id: 章节ID
            title: 章节标题
            content: 当前已生成内容(纯文本)
            options: 章节选项列表(只存文本,不存tags和impact_hint)

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = f"chapter:{chapter_id}:generating"

        data = {
            "title": title,
            "content": content,
            "options": options or []
        }

        await redis_client.set(key, json.dumps(data, ensure_ascii=False))
        logger.info(f"✅ Redis: 保存生成中章节 {chapter_id}, 内容长度: {len(content)}, 选项数: {len(data['options'])}")

    @staticmethod
    async def get_generating_content(chapter_id: int) -> Optional[Dict[str, Any]]:
        """
        获取生成中的章节内容

        Args:
            chapter_id: 章节ID

        Returns:
            Optional[Dict]: 章节数据 {title, content, options}，如果不存在返回None

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = f"chapter:{chapter_id}:generating"

        data = await redis_client.get(key)
        if not data:
            logger.info(f"Redis: 章节 {chapter_id} 不在生成缓存中")
            return None

        try:
            result = json.loads(data)
            logger.info(f"✅ Redis: 读取生成中章节 {chapter_id}, 内容长度: {len(result.get('content', ''))}")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️  Redis数据错误 - 无效的JSON {chapter_id}: {e}")
            return None

    @staticmethod
    async def delete_generating_content(chapter_id: int) -> None:
        """
        删除生成中的章节内容

        Phase 2设计: 生成成功或失败时主动删除,不设置TTL

        Args:
            chapter_id: 章节ID

        Raises:
            redis.RedisError: Redis操作失败
        """
        redis_client = await RedisClient.get_client()
        key = f"chapter:{chapter_id}:generating"

        await redis_client.delete(key)
        logger.info(f"✅ Redis: 删除章节 {chapter_id} 生成缓存")