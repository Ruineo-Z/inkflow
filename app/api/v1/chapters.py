import json
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.chapter import ChapterService
from app.services.chapter_generator import chapter_generator
from app.services.novel import NovelService
from app.schemas.chapter import (
    GenerateChapterRequest,
    GenerateChapterResponse,
    ChapterGenerationProgress,
    SaveUserChoiceRequest,
    ChapterResponse,
    UserChoiceResponse
)
from app.services.task import TaskService
from app.models.task import TaskType

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/novels/{novel_id}/chapters/generate", response_model=GenerateChapterResponse, summary="创建章节生成任务")
async def create_chapter_generation_task(
    novel_id: int,
    request: GenerateChapterRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    创建章节生成任务

    - 自动检测是第一章还是后续章节
    - 返回task_id供前端查询进度
    """
    try:
        logger.info(f"🚀 创建章节生成任务 - 小说ID: {novel_id}, 用户ID: {current_user_id}")

        novel_service = NovelService(db)
        chapter_service = ChapterService(db)
        task_service = TaskService(db)

        # 验证小说存在且属于当前用户
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

        # 检查是否第一章生成
        latest_chapter_number = await chapter_service.get_latest_chapter_number(novel_id)

        # 确定任务类型
        task_type = TaskType.FIRST_CHAPTER_GENERATION if latest_chapter_number == 0 else TaskType.CHAPTER_GENERATION

        # 创建任务（生成时再从数据库获取详细信息）
        response = await task_service.start_generation_task(
            user_id=current_user_id,
            novel_id=novel_id,
            task_type=task_type
        )

        logger.info(f"✅ 章节生成任务创建成功 - 任务ID: {response.task_id}")

        return GenerateChapterResponse(
            task_id=response.task_id,
            status=response.status.value,
            message=response.message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 创建章节生成任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
        )


@router.get("/novels/{novel_id}/chapters/generate/{task_id}", response_model=ChapterGenerationProgress, summary="查询章节生成进度")
async def get_chapter_generation_progress(
    novel_id: int,
    task_id: str,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    查询章节生成任务的进度

    - 支持多端同步查询同一task_id
    - 返回实时进度、状态和生成结果
    """
    try:
        task_service = TaskService(db)

        # 查询任务进度
        progress = await task_service.get_task_progress(task_id, current_user_id)

        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )

        # 验证任务是否属于指定小说
        if progress.result_data and "novel_id" in progress.result_data:
            if progress.result_data["novel_id"] != novel_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="任务不属于此小说"
                )

        # 转换为章节生成进度响应格式
        return ChapterGenerationProgress(
            task_id=progress.task_id,
            status=progress.status.value,
            progress_percentage=progress.progress_percentage,
            current_step=progress.current_step,
            chapter_data=progress.result_data,
            error_message=progress.error_message,
            created_at=progress.created_at,
            started_at=progress.started_at,
            completed_at=progress.completed_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查询章节生成进度失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询进度失败: {str(e)}"
        )


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
    获取章节详情，包含用户选择信息
    """
    try:
        chapter_service = ChapterService(db)
        
        # 获取章节详情（包含用户选择）
        chapter_with_choice = await chapter_service.get_chapter_with_user_choice(
            chapter_id, current_user_id
        )
        
        if not chapter_with_choice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )
        
        # 验证用户权限（通过小说验证）
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter_with_choice.novel_id)
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )
        
        return chapter_with_choice
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节详情失败: {str(e)}"
        )