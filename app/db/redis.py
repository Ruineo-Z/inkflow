"""Redis客户端管理"""
from typing import Optional
import logging
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端单例"""

    _instance: Optional[redis.Redis] = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        """获取Redis客户端实例"""
        if cls._instance is None:
            try:
                cls._instance = await redis.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True,
                    encoding="utf-8",
                    max_connections=50,
                )
                logger.info(f"✅ Redis连接已创建: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except redis.RedisError as e:
                logger.error(f"❌ Redis连接创建失败: {e}")
                raise
        return cls._instance

    @classmethod
    async def close(cls):
        """关闭Redis连接"""
        if cls._instance:
            try:
                await cls._instance.close()
                logger.info("✅ Redis连接已关闭")
            except Exception as e:
                logger.warning(f"⚠️  Redis关闭时出错(可忽略): {e}")
            finally:
                cls._instance = None


async def get_redis() -> redis.Redis:
    """依赖注入函数 - 获取Redis客户端"""
    return await RedisClient.get_client()