import json
import uuid
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from app.models.task import GenerationTask, TaskStatus, TaskType
from app.models.user import User
from app.models.novel import Novel
from app.schemas.task import TaskProgressUpdate, StartTaskResponse, TaskProgressResponse
from app.services.chapter_generator import chapter_generator

logger = logging.getLogger(__name__)


class TaskService:
    """任务管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_generation_task(
        self,
        user_id: int,
        novel_id: int,
        task_type: TaskType,
        input_data: Optional[Dict[Any, Any]] = None
    ) -> StartTaskResponse:
        """启动生成任务"""
        try:
            # 生成唯一任务ID
            task_id = str(uuid.uuid4())

            # 创建任务记录
            task = GenerationTask(
                task_id=task_id,
                user_id=user_id,
                novel_id=novel_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                input_data=json.dumps(input_data) if input_data else None,
                progress_percentage=0,
                current_step="正在初始化任务...",
                total_steps=100
            )

            self.db.add(task)
            await self.db.commit()
            await self.db.refresh(task)

            # 异步启动任务执行
            asyncio.create_task(self._execute_task(task_id))

            logger.info(f"✅ 任务创建成功 - 任务ID: {task_id}, 类型: {task_type}")

            return StartTaskResponse(
                task_id=task_id,
                status=TaskStatus.PENDING,
                message="任务已启动，正在准备生成..."
            )

        except Exception as e:
            logger.error(f"❌ 启动任务失败: {str(e)}")
            raise e

    async def get_task_progress(self, task_id: str, user_id: int) -> Optional[TaskProgressResponse]:
        """获取任务进度"""
        try:
            # 查询任务
            stmt = select(GenerationTask).where(
                and_(
                    GenerationTask.task_id == task_id,
                    GenerationTask.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"⚠️ 任务不存在或无权访问 - 任务ID: {task_id}, 用户ID: {user_id}")
                return None

            # 构建响应
            response = TaskProgressResponse(
                task_id=task.task_id,
                status=task.status,
                progress_percentage=task.progress_percentage,
                current_step=task.current_step,
                total_steps=task.total_steps,
                result_data=json.loads(task.result_data) if task.result_data else None,
                error_message=task.error_message,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                updated_at=task.updated_at
            )

            return response

        except Exception as e:
            logger.error(f"❌ 获取任务进度失败: {str(e)}")
            raise e

    async def get_user_tasks(
        self,
        user_id: int,
        novel_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 20
    ) -> List[TaskProgressResponse]:
        """获取用户任务列表"""
        try:
            # 构建查询条件
            conditions = [GenerationTask.user_id == user_id]

            if novel_id:
                conditions.append(GenerationTask.novel_id == novel_id)

            if status:
                conditions.append(GenerationTask.status == status)

            # 查询任务
            stmt = (
                select(GenerationTask)
                .where(and_(*conditions))
                .order_by(desc(GenerationTask.created_at))
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            tasks = result.scalars().all()

            # 转换为响应格式
            task_responses = []
            for task in tasks:
                response = TaskProgressResponse(
                    task_id=task.task_id,
                    status=task.status,
                    progress_percentage=task.progress_percentage,
                    current_step=task.current_step,
                    total_steps=task.total_steps,
                    result_data=json.loads(task.result_data) if task.result_data else None,
                    error_message=task.error_message,
                    created_at=task.created_at,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                    updated_at=task.updated_at
                )
                task_responses.append(response)

            return task_responses

        except Exception as e:
            logger.error(f"❌ 获取用户任务列表失败: {str(e)}")
            raise e

    async def cancel_task(self, task_id: str, user_id: int) -> bool:
        """取消任务"""
        try:
            # 查询任务
            stmt = select(GenerationTask).where(
                and_(
                    GenerationTask.task_id == task_id,
                    GenerationTask.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"⚠️ 任务不存在或无权访问 - 任务ID: {task_id}")
                return False

            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                logger.warning(f"⚠️ 任务已结束，无法取消 - 状态: {task.status}")
                return False

            # 更新任务状态
            task.status = TaskStatus.CANCELLED
            task.current_step = "任务已被用户取消"
            task.completed_at = datetime.utcnow()

            await self.db.commit()
            logger.info(f"✅ 任务已取消 - 任务ID: {task_id}")

            return True

        except Exception as e:
            logger.error(f"❌ 取消任务失败: {str(e)}")
            raise e

    async def update_task_progress(
        self,
        task_id: str,
        progress_update: TaskProgressUpdate
    ) -> bool:
        """更新任务进度（内部方法）"""
        try:
            # 查询任务
            stmt = select(GenerationTask).where(GenerationTask.task_id == task_id)
            result = await self.db.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"⚠️ 任务不存在 - 任务ID: {task_id}")
                return False

            # 更新进度信息
            task.progress_percentage = progress_update.progress_percentage

            if progress_update.current_step:
                task.current_step = progress_update.current_step

            if progress_update.status:
                task.status = progress_update.status

                if progress_update.status == TaskStatus.RUNNING and not task.started_at:
                    task.started_at = datetime.utcnow()

                if progress_update.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.completed_at = datetime.utcnow()

            if progress_update.result_data:
                task.result_data = json.dumps(progress_update.result_data)

            if progress_update.error_message:
                task.error_message = progress_update.error_message

            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"❌ 更新任务进度失败: {str(e)}")
            return False

    async def _execute_task(self, task_id: str):
        """执行任务的内部方法"""
        from app.db.database import async_session_maker

        async with async_session_maker() as session:
            try:
                # 查询任务详情
                stmt = (
                    select(GenerationTask)
                    .options(selectinload(GenerationTask.novel))
                    .where(GenerationTask.task_id == task_id)
                )
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if not task:
                    logger.error(f"❌ 任务不存在 - 任务ID: {task_id}")
                    return

                # 标记任务开始
                task_service = TaskService(session)
                await task_service.update_task_progress(
                    task_id,
                    TaskProgressUpdate(
                        task_id=task_id,
                        progress_percentage=10,
                        current_step="正在准备生成参数...",
                        status=TaskStatus.RUNNING
                    )
                )

                # 根据任务类型执行不同的生成逻辑
                if task.task_type == TaskType.FIRST_CHAPTER_GENERATION:
                    await self._execute_first_chapter_generation(task, session)
                elif task.task_type == TaskType.CHAPTER_GENERATION:
                    await self._execute_chapter_generation(task, session)
                else:
                    raise ValueError(f"不支持的任务类型: {task.task_type}")

            except Exception as e:
                logger.error(f"❌ 任务执行失败 - 任务ID: {task_id}, 错误: {str(e)}")

                # 标记任务失败
                await self.update_task_progress(
                    task_id,
                    TaskProgressUpdate(
                        task_id=task_id,
                        progress_percentage=0,
                        current_step="任务执行失败",
                        status=TaskStatus.FAILED,
                        error_message=str(e)
                    )
                )

    async def _execute_first_chapter_generation(self, task: GenerationTask, session: AsyncSession):
        """执行第一章生成任务"""
        # TODO: 实现第一章生成逻辑
        # 这里需要调用 chapter_generator 并处理进度更新
        pass

    async def _execute_chapter_generation(self, task: GenerationTask, session: AsyncSession):
        """执行章节生成任务"""
        # TODO: 实现章节生成逻辑
        # 这里需要调用 chapter_generator 并处理进度更新
        pass