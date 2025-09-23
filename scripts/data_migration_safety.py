"""
安全的数据迁移脚本 - 保护老用户数据
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import asyncpg
from app.core.config import settings

logger = logging.getLogger(__name__)

class DataMigrationSafety:
    """数据迁移安全管理器"""

    def __init__(self):
        self.backup_dir = Path("data_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.connection: asyncpg.Connection = None

    async def connect(self):
        """连接数据库"""
        try:
            # 使用原始 asyncpg，不依赖 SQLAlchemy
            database_url = settings.DATABASE_URL.replace("+asyncpg", "")
            self.connection = await asyncpg.connect(database_url)
            logger.info("✅ 数据库连接成功")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise

    async def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            await self.connection.close()
            logger.info("🔌 数据库连接已关闭")

    async def backup_table(self, table_name: str) -> str:
        """备份指定表的数据"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"{table_name}_backup_{timestamp}.json"

            # 查询表结构
            schema_query = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
            """
            schema_result = await self.connection.fetch(schema_query)

            # 查询表数据
            data_query = f"SELECT * FROM {table_name};"
            data_result = await self.connection.fetch(data_query)

            # 转换为JSON可序列化格式
            backup_data = {
                "table_name": table_name,
                "backup_time": timestamp,
                "schema": [dict(row) for row in schema_result],
                "data": []
            }

            for row in data_result:
                row_data = {}
                for col, value in row.items():
                    # 处理特殊类型
                    if isinstance(value, datetime):
                        row_data[col] = value.isoformat()
                    elif hasattr(value, '__dict__'):  # 枚举类型
                        row_data[col] = str(value)
                    else:
                        row_data[col] = value
                backup_data["data"].append(row_data)

            # 保存备份文件
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 表 {table_name} 备份完成: {backup_file}")
            logger.info(f"📊 备份数据: {len(backup_data['data'])} 条记录")

            return str(backup_file)

        except Exception as e:
            logger.error(f"❌ 备份表 {table_name} 失败: {e}")
            raise

    async def backup_all_user_data(self) -> Dict[str, str]:
        """备份所有用户相关数据"""
        user_tables = [
            "users",
            "novels",
            "chapters",
            "chapter_options",
            "user_choices",
            "generation_tasks"
        ]

        backup_files = {}

        for table in user_tables:
            try:
                # 检查表是否存在
                exists_query = f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = '{table}'
                );
                """
                exists = await self.connection.fetchval(exists_query)

                if exists:
                    backup_file = await self.backup_table(table)
                    backup_files[table] = backup_file
                else:
                    logger.warning(f"⚠️  表 {table} 不存在，跳过备份")

            except Exception as e:
                logger.error(f"❌ 备份表 {table} 时出错: {e}")
                # 继续备份其他表
                continue

        return backup_files

    async def validate_data_integrity(self) -> bool:
        """验证数据完整性"""
        try:
            logger.info("🔍 开始验证数据完整性...")

            # 检查用户数据
            user_count = await self.connection.fetchval("SELECT COUNT(*) FROM users")
            novel_count = await self.connection.fetchval("SELECT COUNT(*) FROM novels")
            chapter_count = await self.connection.fetchval("SELECT COUNT(*) FROM chapters")

            logger.info(f"📊 数据统计: 用户 {user_count}, 小说 {novel_count}, 章节 {chapter_count}")

            # 检查外键完整性
            orphan_novels = await self.connection.fetchval("""
                SELECT COUNT(*) FROM novels n
                LEFT JOIN users u ON n.user_id = u.id
                WHERE u.id IS NULL
            """)

            orphan_chapters = await self.connection.fetchval("""
                SELECT COUNT(*) FROM chapters c
                LEFT JOIN novels n ON c.novel_id = n.id
                WHERE n.id IS NULL
            """)

            if orphan_novels > 0:
                logger.error(f"❌ 发现 {orphan_novels} 个孤立小说（没有对应用户）")
                return False

            if orphan_chapters > 0:
                logger.error(f"❌ 发现 {orphan_chapters} 个孤立章节（没有对应小说）")
                return False

            logger.info("✅ 数据完整性验证通过")
            return True

        except Exception as e:
            logger.error(f"❌ 数据完整性验证失败: {e}")
            return False

    async def create_migration_checkpoint(self) -> str:
        """创建迁移检查点（完整备份）"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_dir = self.backup_dir / f"checkpoint_{timestamp}"
            checkpoint_dir.mkdir(exist_ok=True)

            logger.info(f"📍 创建迁移检查点: {checkpoint_dir}")

            # 备份所有用户数据
            backup_files = await self.backup_all_user_data()

            # 验证数据完整性
            integrity_ok = await self.validate_data_integrity()

            # 创建检查点信息文件
            checkpoint_info = {
                "checkpoint_time": timestamp,
                "database_url": settings.DATABASE_URL,
                "backup_files": backup_files,
                "data_integrity": integrity_ok,
                "migration_notes": "迁移前自动检查点 - 保护老用户数据"
            }

            info_file = checkpoint_dir / "checkpoint_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_info, f, ensure_ascii=False, indent=2)

            # 移动备份文件到检查点目录
            for table, backup_file in backup_files.items():
                backup_path = Path(backup_file)
                new_path = checkpoint_dir / backup_path.name
                backup_path.rename(new_path)
                checkpoint_info["backup_files"][table] = str(new_path)

            # 更新检查点信息
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_info, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 迁移检查点创建完成: {checkpoint_dir}")
            return str(checkpoint_dir)

        except Exception as e:
            logger.error(f"❌ 创建迁移检查点失败: {e}")
            raise

async def create_pre_migration_backup():
    """在迁移前创建备份的便捷函数"""
    safety_manager = DataMigrationSafety()

    try:
        await safety_manager.connect()
        checkpoint_path = await safety_manager.create_migration_checkpoint()
        logger.info(f"🎉 迁移前备份完成: {checkpoint_path}")
        return checkpoint_path
    finally:
        await safety_manager.disconnect()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(create_pre_migration_backup())