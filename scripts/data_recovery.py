"""
数据恢复和回滚机制
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

class DataRecoveryManager:
    """数据恢复管理器"""

    def __init__(self):
        self.backup_dir = Path("data_backups")
        self.connection: asyncpg.Connection = None

    async def connect(self):
        """连接数据库"""
        try:
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

    def list_available_backups(self) -> List[Dict[str, Any]]:
        """列出可用的备份检查点"""
        backups = []

        if not self.backup_dir.exists():
            logger.warning("⚠️  备份目录不存在")
            return backups

        for checkpoint_dir in self.backup_dir.glob("checkpoint_*"):
            if checkpoint_dir.is_dir():
                info_file = checkpoint_dir / "checkpoint_info.json"
                if info_file.exists():
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f:
                            checkpoint_info = json.load(f)
                        checkpoint_info["checkpoint_path"] = str(checkpoint_dir)
                        backups.append(checkpoint_info)
                    except Exception as e:
                        logger.error(f"❌ 读取检查点信息失败 {checkpoint_dir}: {e}")

        # 按时间排序，最新的在前
        backups.sort(key=lambda x: x["checkpoint_time"], reverse=True)
        return backups

    async def restore_table_from_backup(self, table_name: str, backup_file: str) -> bool:
        """从备份文件恢复表数据"""
        try:
            logger.info(f"🔄 开始恢复表 {table_name} 从 {backup_file}")

            # 读取备份数据
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            if backup_data["table_name"] != table_name:
                raise ValueError(f"备份文件表名不匹配: 期望 {table_name}, 实际 {backup_data['table_name']}")

            # 清空现有数据（谨慎操作）
            await self.connection.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
            logger.info(f"🗑️  已清空表 {table_name}")

            # 恢复数据
            if backup_data["data"]:
                # 构建插入语句
                columns = list(backup_data["data"][0].keys())
                placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
                insert_query = f"""
                INSERT INTO {table_name} ({", ".join(columns)})
                VALUES ({placeholders})
                """

                # 批量插入数据
                for row_data in backup_data["data"]:
                    values = []
                    for col in columns:
                        value = row_data[col]
                        # 处理日期时间字符串
                        if isinstance(value, str) and "T" in value and value.endswith("Z"):
                            try:
                                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                            except:
                                pass
                        values.append(value)

                    await self.connection.execute(insert_query, *values)

                logger.info(f"✅ 恢复了 {len(backup_data['data'])} 条记录到表 {table_name}")
            else:
                logger.info(f"ℹ️  表 {table_name} 没有数据需要恢复")

            return True

        except Exception as e:
            logger.error(f"❌ 恢复表 {table_name} 失败: {e}")
            return False

    async def restore_from_checkpoint(self, checkpoint_path: str) -> bool:
        """从检查点恢复所有数据"""
        try:
            checkpoint_dir = Path(checkpoint_path)
            info_file = checkpoint_dir / "checkpoint_info.json"

            if not info_file.exists():
                raise FileNotFoundError(f"检查点信息文件不存在: {info_file}")

            # 读取检查点信息
            with open(info_file, 'r', encoding='utf-8') as f:
                checkpoint_info = json.load(f)

            logger.info(f"🔄 开始从检查点恢复数据: {checkpoint_info['checkpoint_time']}")

            # 检查数据完整性
            if not checkpoint_info.get("data_integrity", False):
                logger.warning("⚠️  此检查点的数据完整性验证曾经失败，谨慎恢复")

            # 按依赖顺序恢复表（避免外键约束问题）
            restore_order = [
                "users",           # 用户表（无依赖）
                "novels",          # 小说表（依赖用户）
                "chapters",        # 章节表（依赖小说）
                "chapter_options", # 章节选项（依赖章节）
                "user_choices",    # 用户选择（依赖用户和章节选项）
                "generation_tasks" # 生成任务（依赖用户和小说）
            ]

            restored_tables = []
            for table_name in restore_order:
                backup_file = checkpoint_info["backup_files"].get(table_name)
                if backup_file and Path(backup_file).exists():
                    success = await self.restore_table_from_backup(table_name, backup_file)
                    if success:
                        restored_tables.append(table_name)
                    else:
                        logger.error(f"❌ 恢复表 {table_name} 失败，中止恢复过程")
                        return False
                else:
                    logger.warning(f"⚠️  表 {table_name} 的备份文件不存在，跳过")

            logger.info(f"🎉 数据恢复完成，已恢复表: {restored_tables}")
            return True

        except Exception as e:
            logger.error(f"❌ 从检查点恢复数据失败: {e}")
            return False

    async def verify_recovery(self) -> bool:
        """验证恢复后的数据完整性"""
        try:
            logger.info("🔍 验证恢复后的数据完整性...")

            # 基本数据统计
            user_count = await self.connection.fetchval("SELECT COUNT(*) FROM users")
            novel_count = await self.connection.fetchval("SELECT COUNT(*) FROM novels")
            chapter_count = await self.connection.fetchval("SELECT COUNT(*) FROM chapters")

            logger.info(f"📊 恢复后数据统计: 用户 {user_count}, 小说 {novel_count}, 章节 {chapter_count}")

            # 外键完整性检查
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

            if orphan_novels > 0 or orphan_chapters > 0:
                logger.error(f"❌ 数据完整性验证失败: 孤立小说 {orphan_novels}, 孤立章节 {orphan_chapters}")
                return False

            logger.info("✅ 数据恢复验证通过")
            return True

        except Exception as e:
            logger.error(f"❌ 恢复验证失败: {e}")
            return False

async def interactive_recovery():
    """交互式数据恢复"""
    recovery_manager = DataRecoveryManager()

    try:
        await recovery_manager.connect()

        # 列出可用备份
        backups = recovery_manager.list_available_backups()

        if not backups:
            print("❌ 没有找到可用的备份检查点")
            return

        print("\n📋 可用的备份检查点:")
        for i, backup in enumerate(backups):
            print(f"{i+1}. {backup['checkpoint_time']} - {backup.get('migration_notes', '无描述')}")
            print(f"   数据完整性: {'✅' if backup.get('data_integrity') else '⚠️'}")

        # 用户选择
        while True:
            try:
                choice = input(f"\n请选择要恢复的检查点 (1-{len(backups)}, 0=取消): ")
                if choice == "0":
                    print("取消恢复操作")
                    return

                idx = int(choice) - 1
                if 0 <= idx < len(backups):
                    break
                else:
                    print("❌ 选择无效，请重新输入")
            except ValueError:
                print("❌ 请输入有效数字")

        selected_backup = backups[idx]
        print(f"\n⚠️  您选择恢复检查点: {selected_backup['checkpoint_time']}")
        print("🚨 注意: 这会清空当前数据并恢复到选择的时间点！")

        confirm = input("确认恢复? (输入 'YES' 确认): ")
        if confirm != "YES":
            print("❌ 用户取消恢复操作")
            return

        # 执行恢复
        success = await recovery_manager.restore_from_checkpoint(selected_backup["checkpoint_path"])

        if success:
            # 验证恢复
            verify_ok = await recovery_manager.verify_recovery()
            if verify_ok:
                print("🎉 数据恢复成功并通过验证！")
            else:
                print("⚠️  数据恢复完成但验证失败，请检查数据完整性")
        else:
            print("❌ 数据恢复失败")

    finally:
        await recovery_manager.disconnect()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(interactive_recovery())