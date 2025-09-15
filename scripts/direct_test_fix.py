#!/usr/bin/env python3
"""直接测试修复是否有效"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.chapter import ChapterService
from app.schemas.chapter import ChapterResponse


async def test_chapter_service_fix():
    """直接测试ChapterService的修复"""

    # 创建数据库连接
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db:
        try:
            chapter_service = ChapterService(db)

            # 测试获取章节列表 - 使用一个已知存在章节的小说ID
            # 先查看数据库中有哪些小说
            print("🔍 查询数据库中的章节...")

            from sqlalchemy import select, text
            from app.models.chapter import Chapter

            # 查询所有章节
            result = await db.execute(select(Chapter))
            chapters = result.scalars().all()

            if not chapters:
                print("❌ 数据库中没有章节数据")
                return

            print(f"✅ 找到 {len(chapters)} 个章节")

            # 取第一个章节的小说ID
            test_novel_id = chapters[0].novel_id
            print(f"🎯 测试小说ID: {test_novel_id}")

            # 测试修复后的方法
            print("📋 测试获取章节列表...")
            chapters_list = await chapter_service.get_chapters_by_novel(test_novel_id)

            print(f"✅ 成功获取章节列表: {len(chapters_list)} 个章节")

            # 测试转换为响应模型
            print("🔄 测试Pydantic模型转换...")

            for chapter in chapters_list:
                try:
                    chapter_response = ChapterResponse.from_orm(chapter)
                    print(f"  ✅ 章节 {chapter.id}: 标题={chapter_response.title}, 选项数={len(chapter_response.options)}")

                    for i, option in enumerate(chapter_response.options, 1):
                        print(f"    选项{i}: ID={option.id}, 文本='{option.option_text[:30]}...'")

                except Exception as e:
                    print(f"  ❌ 章节 {chapter.id} 转换失败: {e}")
                    return False

            print("🎉 所有测试通过！章节列表接口修复成功")
            return True

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_chapter_service_fix())
    if success:
        print("\n✅ 修复验证成功：MissingGreenlet错误已解决")
    else:
        print("\n❌ 修复验证失败：问题仍然存在")