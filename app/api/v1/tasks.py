import json
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.task import TaskService
from app.services.redis_queue import get_task_queue
from app.schemas.task import TaskStatusResponse, TaskContentResponse, ContentChunk

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, summary="查询任务状态")
async def get_task_status(
    task_id: str,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    查询任务状态和基本信息

    - 返回任务当前状态、进度、步骤等信息
    - 不包含具体生成内容，适用于快速状态检查
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

        return TaskStatusResponse(
            task_id=progress.task_id,
            status=progress.status,
            progress_percentage=progress.progress_percentage,
            current_step=progress.current_step,
            created_at=progress.created_at,
            started_at=progress.started_at,
            completed_at=progress.completed_at,
            error_message=progress.error_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查询任务状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务状态失败: {str(e)}"
        )


@router.get("/tasks/{task_id}/content", response_model=TaskContentResponse, summary="查询任务内容")
async def get_task_content(
    task_id: str,
    from_position: int = Query(0, ge=0, description="起始位置，支持断点续读"),
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    查询任务生成的内容

    - 支持断点续读，通过from_position参数指定起始位置
    - 返回内容块列表和当前总块数
    - 适用于用户重新进入页面时恢复内容显示
    """
    try:
        task_service = TaskService(db)

        # 验证任务权限
        progress = await task_service.get_task_progress(task_id, current_user_id)

        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权访问"
            )

        # 获取Redis中的流式内容
        task_queue = get_task_queue()
        content_chunks = await task_queue.get_task_content_stream(task_id)

        # 根据from_position返回指定范围的内容
        if from_position >= len(content_chunks):
            # 如果起始位置超出范围，返回空内容
            chunks_to_return = []
        else:
            chunks_to_return = content_chunks[from_position:]

        # 构造内容块响应
        content_blocks = []
        for i, chunk_text in enumerate(chunks_to_return):
            content_blocks.append(ContentChunk(
                position=from_position + i,
                text=chunk_text,
                timestamp=None  # Redis中暂时没有存储时间戳
            ))

        return TaskContentResponse(
            task_id=task_id,
            total_chunks=len(content_chunks),
            from_position=from_position,
            chunks=content_blocks,
            is_complete=progress.status == "COMPLETED",
            final_result=progress.result_data if progress.status == "COMPLETED" else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查询任务内容失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务内容失败: {str(e)}"
        )