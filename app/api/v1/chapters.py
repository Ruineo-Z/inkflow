import asyncio
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.chapter import ChapterService
from app.services.chapter_generator import chapter_generator
from app.services.novel import NovelService
from app.services.stream_manager import StreamGenerationManager
from app.models.chapter import Chapter, ChapterStatus
from app.schemas.chapter import (
    GenerateChapterRequest,
    SaveUserChoiceRequest,
    ChapterResponse,
    UserChoiceResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/novels/{novel_id}/chapters/generate", summary="开始生成章节")
async def generate_chapter(
    novel_id: int,
    request: GenerateChapterRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    开始生成章节（立即返回chapter_id，不阻塞）

    注意：用户选择已通过 /chapters/{chapter_id}/choice 接口保存，
    生成时无需传递选项ID。

    返回：
    {
        "chapter_id": 123,
        "status": "generating"
    }

    前端接下来应该调用 GET /chapters/{chapter_id}/stream 获取流式数据
    """
    try:
        # 1. 验证小说
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(novel_id)

        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )

        if novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此小说"
            )

        # 2. 创建章节记录
        chapter_service = ChapterService(db)
        latest_chapter_num = await chapter_service.get_latest_chapter_number(novel_id)

        chapter = Chapter(
            novel_id=novel_id,
            chapter_number=latest_chapter_num + 1,
            title="生成中...",
            content="",
            status=ChapterStatus.GENERATING
        )
        db.add(chapter)
        await db.flush()  # 获取chapter.id
        await db.commit()

        logger.info(f"✅ 创建章节记录: {chapter.id}")

        # 3. 启动后台任务（不等待）
        if latest_chapter_num == 0:
            # 第一章
            asyncio.create_task(
                chapter_generator.generate_first_chapter_background(
                    chapter_id=chapter.id,
                    novel_id=novel_id,
                    world_setting=novel.background_setting or "",
                    protagonist_info=novel.character_setting or "",
                    genre=novel.theme or "wuxia"
                )
            )
        else:
            # 后续章节
            asyncio.create_task(
                chapter_generator.generate_next_chapter_background(
                    chapter_id=chapter.id,
                    novel_id=novel_id,
                    genre=novel.theme or "wuxia"
                )
            )

        logger.info(f"🚀 后台任务已启动: {chapter.id}")

        # 4. 立即返回
        return {
            "chapter_id": chapter.id,
            "status": "generating"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 启动章节生成失败: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"启动生成失败: {str(e)}"
        )


# ========== 其他功能接口 ==========


@router.post("/chapters/{chapter_id}/choice", response_model=UserChoiceResponse, summary="保存用户选择")
async def save_user_choice(
    chapter_id: int,
    request: SaveUserChoiceRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    保存用户在特定章节的选择
    """
    try:
        chapter_service = ChapterService(db)

        # 1. 验证章节存在
        chapter = await chapter_service.get_chapter_by_id(chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )

        # 2. 验证用户权限（通过小说验证）
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter.novel_id)
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )

        # 3. 验证选项存在
        option_exists = False
        for option in chapter.options:
            if option.id == request.option_id:
                option_exists = True
                break

        if not option_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="选项不存在"
            )

        # 4. 保存用户选择
        try:
            choice = await chapter_service.save_user_choice(
                user_id=current_user_id,
                chapter_id=chapter_id,
                option_id=request.option_id
            )

            return UserChoiceResponse.from_orm(choice)

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存选择失败: {str(e)}"
        )


@router.get("/novels/{novel_id}/chapters", response_model=list[ChapterResponse], summary="获取小说章节列表")
async def get_novel_chapters(
    novel_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取小说的所有章节列表
    """
    try:
        # 验证小说权限
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(novel_id)

        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )

        if novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此小说"
            )

        # 获取章节列表（包含用户选择）
        chapter_service = ChapterService(db)
        chapters_with_choices = await chapter_service.get_chapters_by_novel_with_user_choices(
            novel_id, current_user_id
        )

        return chapters_with_choices

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节列表失败: {str(e)}"
        )


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse, summary="获取章节详情")
async def get_chapter_detail(
    chapter_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取特定章节的详细信息
    """
    try:
        chapter_service = ChapterService(db)

        # 获取包含用户选择的章节详情
        chapter_data = await chapter_service.get_chapter_by_id_with_user_choice(
            chapter_id, current_user_id
        )

        if not chapter_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )

        # 验证用户权限
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter_data["novel_id"])
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )

        return chapter_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节详情失败: {str(e)}"
        )



@router.get("/chapters/{chapter_id}/stream", summary="获取章节流式数据（统一接口）")
async def stream_chapter(
    chapter_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取章节的流式数据（统一接口，支持新生成和断线重连）

    使用场景：
    1. 新生成：POST /generate 后立即调用
    2. 断线重连：刷新页面后重新连接
    3. 查看已完成：直接返回完整数据

    返回SSE流：
    - event: summary - 章节标题
    - event: content - 内容片段（增量）
    - event: complete - 生成完成
    - event: error - 错误
    """
    try:
        # 验证权限
        chapter_service = ChapterService(db)
        chapter = await chapter_service.get_chapter_by_id(chapter_id)

        if not chapter:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "章节不存在")

        # 验证用户权限
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter.novel_id)

        if not novel or novel.user_id != current_user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问此章节")

        # 使用StreamManager流式推送
        return StreamingResponse(
            StreamGenerationManager.stream_to_client(chapter_id, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用nginx缓冲
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 流式推送失败: {e}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"获取流式数据失败: {str(e)}"
        )