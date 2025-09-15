"""数据库迁移管理模块"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseMigrationManager:
    """数据库迁移管理器"""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.alembic_cfg = self._get_alembic_config()

    def _get_alembic_config(self) -> Config:
        """获取 Alembic 配置"""
        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent
        alembic_ini_path = project_root / "alembic.ini"

        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"Alembic配置文件不存在: {alembic_ini_path}")

        config = Config(str(alembic_ini_path))
        # 设置数据库连接字符串
        config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))
        return config

    async def get_current_revision(self) -> Optional[str]:
        """获取当前数据库版本"""
        try:
            async with self.engine.begin() as conn:
                # 检查 alembic_version 表是否存在
                result = await conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'alembic_version'
                    )
                """))
                table_exists = result.scalar()

                if not table_exists:
                    logger.info("alembic_version 表不存在，数据库未初始化")
                    return None

                # 获取当前版本
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar()
                return version
        except Exception as e:
            logger.error(f"获取数据库版本失败: {e}")
            return None

    def get_latest_revision(self) -> Optional[str]:
        """获取最新的迁移版本"""
        try:
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            return script_dir.get_current_head()
        except Exception as e:
            logger.error(f"获取最新迁移版本失败: {e}")
            return None

    async def needs_migration(self) -> bool:
        """检查是否需要执行迁移"""
        current_rev = await self.get_current_revision()
        latest_rev = self.get_latest_revision()

        logger.info(f"当前数据库版本: {current_rev}")
        logger.info(f"最新迁移版本: {latest_rev}")

        # 如果当前版本为空或者与最新版本不同，则需要迁移
        return current_rev != latest_rev

    def run_migrations_sync(self) -> bool:
        """同步执行数据库迁移"""
        try:
            logger.info("开始执行数据库迁移...")
            command.upgrade(self.alembic_cfg, "head")
            logger.info("✅ 数据库迁移执行成功！所有表结构已更新到最新版本")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库迁移执行失败: {e}")
            return False

    async def run_migrations(self) -> bool:
        """异步执行数据库迁移"""
        loop = asyncio.get_event_loop()
        try:
            # 在线程池中运行同步的迁移操作
            await loop.run_in_executor(None, self.run_migrations_sync)
            return True
        except Exception as e:
            logger.error(f"异步执行数据库迁移失败: {e}")
            return False

    async def auto_migrate(self) -> bool:
        """自动迁移：检查并执行必要的数据库迁移"""
        try:
            if await self.needs_migration():
                logger.info("检测到需要执行数据库迁移")
                return await self.run_migrations()
            else:
                logger.info("数据库已是最新版本，无需迁移")
                return True
        except Exception as e:
            logger.error(f"自动迁移检查失败: {e}")
            return False


async def run_auto_migration(engine: AsyncEngine) -> bool:
    """运行自动迁移的便捷函数"""
    migration_manager = DatabaseMigrationManager(engine)
    return await migration_manager.auto_migrate()