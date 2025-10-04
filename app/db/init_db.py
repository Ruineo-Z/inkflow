import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.database import Base

logger = logging.getLogger(__name__)

async def create_database():
    """创建数据库表"""
    engine = create_async_engine(settings.DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        # 删除所有表
        await conn.run_sync(Base.metadata.drop_all)
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    logger.info("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_database())