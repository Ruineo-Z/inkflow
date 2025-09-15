"""管理员接口 - 仅用于开发环境"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.config import settings

router = APIRouter()


@router.post("/reset-sequences", summary="重置数据库序列（开发环境专用）")
async def reset_database_sequences(db: AsyncSession = Depends(get_db)):
    """
    重置所有表的ID序列到合理值
    ⚠️ 仅用于开发环境，生产环境禁用
    """

    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此功能仅在开发环境可用"
        )

    tables = [
        ("chapters", "chapters_id_seq"),
        ("options", "options_id_seq"),
        ("novels", "novels_id_seq"),
        ("users", "users_id_seq"),
        ("user_choices", "user_choices_id_seq")
    ]

    results = []

    try:
        for table_name, sequence_name in tables:
            # 查询当前最大ID
            result = await db.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"))
            max_id = result.scalar() or 0

            # 重置序列
            new_seq_value = max_id + 1

            try:
                await db.execute(text(f"ALTER SEQUENCE {sequence_name} RESTART WITH {new_seq_value}"))
                results.append({
                    "table": table_name,
                    "sequence": sequence_name,
                    "max_id": max_id,
                    "new_sequence_value": new_seq_value,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "table": table_name,
                    "sequence": sequence_name,
                    "max_id": max_id,
                    "error": str(e),
                    "status": "failed"
                })

        await db.commit()

        return {
            "message": "序列重置完成",
            "results": results
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置序列失败: {str(e)}"
        )


@router.post("/reset-chapter-sequence", summary="重置章节表序列")
async def reset_chapter_sequence(db: AsyncSession = Depends(get_db)):
    """
    仅重置chapters表的ID序列
    """

    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此功能仅在开发环境可用"
        )

    try:
        # 查询当前最大的chapter ID
        result = await db.execute(text("SELECT COALESCE(MAX(id), 0) FROM chapters"))
        max_id = result.scalar() or 0

        # 重置序列
        new_seq_value = max_id + 1
        await db.execute(text(f"ALTER SEQUENCE chapters_id_seq RESTART WITH {new_seq_value}"))
        await db.commit()

        return {
            "message": "章节表序列重置成功",
            "max_id": max_id,
            "new_sequence_value": new_seq_value
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置章节序列失败: {str(e)}"
        )