#!/usr/bin/env python3
"""
重置章节表的ID序列
仅用于开发环境，生产环境慎用！
"""

import asyncio
import asyncpg
from app.core.config import settings


async def reset_chapter_sequence():
    """重置chapters表的ID序列"""

    # 从配置中获取数据库连接信息
    database_url = settings.DATABASE_URL.replace("+asyncpg", "")

    try:
        conn = await asyncpg.connect(database_url)

        # 查询当前最大的chapter ID
        max_id = await conn.fetchval("SELECT COALESCE(MAX(id), 0) FROM chapters")

        print(f"当前chapters表最大ID: {max_id}")

        # 重置序列到最大ID + 1
        new_seq_value = max_id + 1
        await conn.execute(f"ALTER SEQUENCE chapters_id_seq RESTART WITH {new_seq_value}")

        print(f"✅ chapters_id_seq 序列已重置为: {new_seq_value}")

        # 验证重置结果
        current_seq = await conn.fetchval("SELECT currval('chapters_id_seq')")
        print(f"当前序列值: {current_seq}")

        await conn.close()

    except Exception as e:
        print(f"❌ 重置序列失败: {e}")


async def reset_all_sequences():
    """重置所有表的ID序列"""

    database_url = settings.DATABASE_URL.replace("+asyncpg", "")

    tables = [
        ("chapters", "chapters_id_seq"),
        ("options", "options_id_seq"),
        ("novels", "novels_id_seq"),
        ("users", "users_id_seq"),
        ("user_choices", "user_choices_id_seq")
    ]

    try:
        conn = await asyncpg.connect(database_url)

        for table_name, sequence_name in tables:
            # 查询当前最大ID
            max_id = await conn.fetchval(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")

            # 重置序列
            new_seq_value = max_id + 1

            try:
                await conn.execute(f"ALTER SEQUENCE {sequence_name} RESTART WITH {new_seq_value}")
                print(f"✅ {table_name}: 序列重置为 {new_seq_value}")
            except Exception as e:
                print(f"⚠️  {table_name}: 序列重置失败 - {e}")

        await conn.close()
        print("\n🎉 所有序列重置完成!")

    except Exception as e:
        print(f"❌ 连接数据库失败: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        print("🔄 重置所有表的ID序列...")
        asyncio.run(reset_all_sequences())
    else:
        print("🔄 重置chapters表的ID序列...")
        asyncio.run(reset_chapter_sequence())
        print("\n💡 使用 --all 参数可重置所有表的序列")