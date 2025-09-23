import json
import uuid
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from app.models.task import GenerationTask
from app.models.task import TaskStatus as ModelTaskStatus, TaskType as ModelTaskType
from app.models.user import User
from app.models.novel import Novel
from app.schemas.task import TaskProgressUpdate, StartTaskResponse, TaskProgressResponse, TaskType
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
        task_type: ModelTaskType,
        input_data: Optional[Dict[Any, Any]] = None
    ) -> StartTaskResponse:
        """启动生成任务"""
        try:
            from app.services.redis_queue import get_task_queue

            # 创建任务数据
            task_data = {
                "user_id": user_id,
                "novel_id": novel_id,
                "task_type": task_type.value,
                "input_data": input_data if input_data is not None else {}
            }

            # 提交到Redis队列
            task_queue = get_task_queue()
            task_id = await task_queue.submit_task(task_data)

            # 在数据库中创建记录（只存储核心信息，实时状态在Redis中）
            task = GenerationTask(
                task_id=task_id,
                user_id=user_id,
                novel_id=novel_id,
                task_type=task_type,
                status=ModelTaskStatus.PENDING,
                input_data=json.dumps(input_data) if input_data else ""
            )

            self.db.add(task)
            await self.db.commit()
            await self.db.refresh(task)

            logger.info(f"✅ 任务已提交到Redis队列 - 任务ID: {task_id}, 类型: {task_type}")

            return StartTaskResponse(
                task_id=task_id,
                status=ModelTaskStatus.PENDING.value,
                message="任务已提交到队列，正在等待处理..."
            )

        except Exception as e:
            logger.error(f"❌ 启动任务失败: {str(e)}")
            raise e

    async def get_task_progress(self, task_id: str, user_id: int) -> Optional[TaskProgressResponse]:
        """获取任务进度"""
        try:
            from app.services.redis_queue import get_task_queue

            # 先从Redis获取实时状态
            task_queue = get_task_queue()
            redis_status = await task_queue.get_task_status(task_id)

            # 验证用户权限（从数据库查询）
            stmt = select(GenerationTask).where(
                and_(
                    GenerationTask.task_id == task_id,
                    GenerationTask.user_id == user_id
                )
            )
            result = await self.db.execute(stmt)
            db_task = result.scalar_one_or_none()

            if not db_task:
                logger.warning(f"⚠️ 任务不存在或无权访问 - 任务ID: {task_id}, 用户ID: {user_id}")
                return None

            # 如果Redis中有最新状态，使用Redis数据，否则用数据库数据
            if redis_status:
                # 安全处理result_data字段 - 确保类型正确
                def safe_parse_result_data(data):
                    if data and data.strip():
                        try:
                            return json.loads(data)
                        except json.JSONDecodeError:
                            return None
                    return None

                result_data = None
                redis_result = redis_status.get('result')
                if redis_result and redis_result != "":
                    try:
                        # Redis中的result可能是JSON字符串，需要解析
                        if isinstance(redis_result, str):
                            result_data = json.loads(redis_result) if redis_result.strip() else None
                        elif isinstance(redis_result, dict):
                            result_data = redis_result
                    except json.JSONDecodeError:
                        # 解析失败，回退到数据库数据
                        result_data = safe_parse_result_data(db_task.result_data)
                else:
                    # Redis中没有result或为空字符串，使用数据库数据
                    result_data = safe_parse_result_data(db_task.result_data)

                response = TaskProgressResponse(
                    task_id=task_id,
                    status=redis_status.get('status', db_task.status.value),
                    progress_percentage=int(redis_status.get('progress_percentage', 0)),
                    current_step=redis_status.get('current_step', "任务准备中..."),
                    total_steps=100,  # 固定值
                    result_data=result_data,
                    error_message=redis_status.get('error', db_task.error_message),
                    created_at=db_task.created_at,
                    started_at=None,  # Redis中不存储，可以从Redis时间戳计算
                    completed_at=db_task.completed_at,
                    updated_at=db_task.created_at  # 简化
                )
            else:
                # 回退到数据库数据（任务已完成或Redis数据过期）
                # 安全处理数据库result_data
                def safe_parse_result_data(data):
                    if data and data.strip():
                        try:
                            return json.loads(data)
                        except json.JSONDecodeError:
                            return None
                    return None

                response = TaskProgressResponse(
                    task_id=db_task.task_id,
                    status=db_task.status.value,
                    progress_percentage=100 if db_task.status == ModelTaskStatus.COMPLETED else 0,
                    current_step="任务已完成" if db_task.status == ModelTaskStatus.COMPLETED else "任务处理中...",
                    total_steps=100,
                    result_data=safe_parse_result_data(db_task.result_data),
                    error_message=db_task.error_message,
                    created_at=db_task.created_at,
                    started_at=None,  # 简化
                    completed_at=db_task.completed_at,
                    updated_at=db_task.created_at  # 简化
                )

            return response

        except Exception as e:
            logger.error(f"❌ 获取任务进度失败: {str(e)}")
            raise e

    async def get_user_tasks(
        self,
        user_id: int,
        novel_id: Optional[int] = None,
        status: Optional[ModelTaskStatus] = None,
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
                # 安全处理任务列表result_data
                def safe_parse_result_data(data):
                    if data and data.strip():
                        try:
                            return json.loads(data)
                        except json.JSONDecodeError:
                            return None
                    return None

                response = TaskProgressResponse(
                    task_id=task.task_id,
                    status=task.status.value,
                    progress_percentage=task.progress_percentage,
                    current_step=task.current_step,
                    total_steps=task.total_steps,
                    result_data=safe_parse_result_data(task.result_data),
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

            if task.status in [ModelTaskStatus.COMPLETED, ModelTaskStatus.FAILED, ModelTaskStatus.CANCELLED]:
                logger.warning(f"⚠️ 任务已结束，无法取消 - 状态: {task.status}")
                return False

            # 更新任务状态
            task.status = ModelTaskStatus.CANCELLED
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
                # 将字符串状态转换为模型枚举
                task.status = ModelTaskStatus(progress_update.status)

                if progress_update.status == ModelTaskStatus.RUNNING.value and not task.started_at:
                    task.started_at = datetime.utcnow()

                if progress_update.status in [ModelTaskStatus.COMPLETED.value, ModelTaskStatus.FAILED.value]:
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
                        status=ModelTaskStatus.RUNNING.value
                    )
                )

                # 根据任务类型执行不同的生成逻辑
                if task.task_type == ModelTaskType.FIRST_CHAPTER_GENERATION:
                    await self._execute_first_chapter_generation(task, session)
                elif task.task_type == ModelTaskType.CHAPTER_GENERATION:
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
                        status=ModelTaskStatus.FAILED.value,
                        error_message=str(e)
                    )
                )

    async def _execute_first_chapter_generation(self, task: GenerationTask, session: AsyncSession):
        """执行第一章生成任务"""
        try:
            logger.info(f"🎯 开始执行第一章生成任务 - 任务ID: {task.task_id}")

            # 更新进度：开始生成
            task_service = TaskService(session)
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=20,
                    current_step="正在获取小说信息...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 获取小说信息
            novel = task.novel
            if not novel:
                raise ValueError("未找到关联的小说")

            logger.info(f"📚 小说信息 - 标题: {novel.title}, 类型: {novel.theme}")

            # 更新进度：开始AI生成
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=40,
                    current_step="正在调用AI生成第一章...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 调用章节生成器
            chapter_data = None
            error_occurred = False

            async for sse_event in chapter_generator.generate_first_chapter_stream(
                world_setting=novel.background_setting or "",
                protagonist_info=novel.character_setting or "",
                genre=novel.theme or "wuxia"
            ):
                # 解析SSE事件
                if "event: status" in sse_event:
                    # 更新状态信息
                    await task_service.update_task_progress(
                        task.task_id,
                        TaskProgressUpdate(
                            task_id=task.task_id,
                            progress_percentage=60,
                            current_step="AI正在生成章节内容...",
                            status=ModelTaskStatus.RUNNING.value
                        )
                    )
                elif "event: summary" in sse_event:
                    # 摘要生成完成
                    await task_service.update_task_progress(
                        task.task_id,
                        TaskProgressUpdate(
                            task_id=task.task_id,
                            progress_percentage=70,
                            current_step="摘要生成完成，正在生成正文...",
                            status=ModelTaskStatus.RUNNING.value
                        )
                    )
                elif "event: complete" in sse_event:
                    # 提取完成数据
                    import re
                    data_match = re.search(r'data: (.+)', sse_event)
                    if data_match:
                        import json
                        chapter_data = json.loads(data_match.group(1))
                        logger.info(f"✅ 第一章生成完成 - 标题: {chapter_data.get('title', '未知')}")
                    break
                elif "event: error" in sse_event:
                    # 处理错误
                    error_occurred = True
                    data_match = re.search(r'data: (.+)', sse_event)
                    if data_match:
                        import json
                        error_data = json.loads(data_match.group(1))
                        raise ValueError(f"AI生成失败: {error_data.get('error', '未知错误')}")

            if error_occurred or not chapter_data:
                raise ValueError("章节生成失败，未获取到有效数据")

            # 更新进度：保存章节到数据库
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=90,
                    current_step="正在保存章节到数据库...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 保存章节到数据库
            from app.services.chapter import ChapterService
            chapter_service = ChapterService(session)

            created_chapter = await chapter_service.create_chapter_with_options(
                novel_id=task.novel_id,
                title=chapter_data['title'],
                summary=chapter_data['summary']['summary'],
                content=chapter_data['content'],
                options_data=chapter_data['options']
            )

            # 更新任务为完成状态
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=100,
                    current_step="第一章生成完成！",
                    status=ModelTaskStatus.COMPLETED.value,
                    result_data={
                        "chapter_id": created_chapter.id,
                        "chapter_number": created_chapter.chapter_number,
                        "title": created_chapter.title,
                        "novel_id": task.novel_id
                    }
                )
            )

            logger.info(f"🎉 第一章生成任务完成 - 任务ID: {task.task_id}, 章节ID: {created_chapter.id}")

        except Exception as e:
            logger.error(f"❌ 第一章生成任务失败 - 任务ID: {task.task_id}, 错误: {str(e)}")
            # 标记任务失败
            task_service = TaskService(session)
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=0,
                    current_step="第一章生成失败",
                    status=ModelTaskStatus.FAILED.value,
                    error_message=str(e)
                )
            )
            raise e

    async def _execute_chapter_generation(self, task: GenerationTask, session: AsyncSession):
        """执行章节生成任务"""
        try:
            logger.info(f"🎯 开始执行后续章节生成任务 - 任务ID: {task.task_id}")

            # 更新进度：开始生成
            task_service = TaskService(session)
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=20,
                    current_step="正在获取章节上下文...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 获取小说和章节信息
            novel = task.novel
            if not novel:
                raise ValueError("未找到关联的小说")

            # 获取章节服务来构建上下文
            from app.services.chapter import ChapterService
            chapter_service = ChapterService(session)

            # 获取用户最新选择和章节上下文
            latest_choice = await chapter_service.get_latest_user_choice(task.user_id, task.novel_id)
            if not latest_choice:
                raise ValueError("未找到用户的选择记录")

            logger.info(f"📚 获取到用户选择 - 选项ID: {latest_choice.option_id}")

            # 更新进度：构建上下文
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=30,
                    current_step="正在构建章节上下文...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 构建章节上下文
            from app.schemas.chapter import ChapterContext
            context = await chapter_service.build_chapter_context(
                novel_id=task.novel_id,
                user_id=task.user_id,
                selected_option_id=latest_choice.option_id
            )

            logger.info(f"📋 章节上下文构建完成 - 历史章节数: {len(context.recent_chapters)}")

            # 更新进度：开始AI生成
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=40,
                    current_step="正在调用AI生成新章节...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 调用章节生成器
            chapter_data = None
            error_occurred = False

            async for sse_event in chapter_generator.generate_next_chapter_stream(
                novel_id=task.novel_id,
                selected_option_id=latest_choice.option_id,
                context=context
            ):
                # 解析SSE事件
                if "event: status" in sse_event:
                    # 更新状态信息
                    await task_service.update_task_progress(
                        task.task_id,
                        TaskProgressUpdate(
                            task_id=task.task_id,
                            progress_percentage=60,
                            current_step="AI正在生成章节内容...",
                            status=ModelTaskStatus.RUNNING.value
                        )
                    )
                elif "event: summary" in sse_event:
                    # 摘要生成完成
                    await task_service.update_task_progress(
                        task.task_id,
                        TaskProgressUpdate(
                            task_id=task.task_id,
                            progress_percentage=70,
                            current_step="摘要生成完成，正在生成正文...",
                            status=ModelTaskStatus.RUNNING.value
                        )
                    )
                elif "event: complete" in sse_event:
                    # 提取完成数据
                    import re
                    data_match = re.search(r'data: (.+)', sse_event)
                    if data_match:
                        import json
                        chapter_data = json.loads(data_match.group(1))
                        logger.info(f"✅ 后续章节生成完成 - 标题: {chapter_data.get('title', '未知')}")
                    break
                elif "event: error" in sse_event:
                    # 处理错误
                    error_occurred = True
                    data_match = re.search(r'data: (.+)', sse_event)
                    if data_match:
                        import json
                        error_data = json.loads(data_match.group(1))
                        raise ValueError(f"AI生成失败: {error_data.get('error', '未知错误')}")

            if error_occurred or not chapter_data:
                raise ValueError("章节生成失败，未获取到有效数据")

            # 更新进度：保存章节到数据库
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=90,
                    current_step="正在保存章节到数据库...",
                    status=ModelTaskStatus.RUNNING.value
                )
            )

            # 保存章节到数据库
            created_chapter = await chapter_service.create_chapter_with_options(
                novel_id=task.novel_id,
                title=chapter_data['title'],
                summary=chapter_data['summary']['summary'],
                content=chapter_data['content'],
                options_data=chapter_data['options']
            )

            # 更新任务为完成状态
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=100,
                    current_step="新章节生成完成！",
                    status=ModelTaskStatus.COMPLETED.value,
                    result_data={
                        "chapter_id": created_chapter.id,
                        "chapter_number": created_chapter.chapter_number,
                        "title": created_chapter.title,
                        "novel_id": task.novel_id,
                        "based_on_choice": latest_choice.option_id
                    }
                )
            )

            logger.info(f"🎉 后续章节生成任务完成 - 任务ID: {task.task_id}, 章节ID: {created_chapter.id}")

        except Exception as e:
            logger.error(f"❌ 后续章节生成任务失败 - 任务ID: {task.task_id}, 错误: {str(e)}")
            # 标记任务失败
            task_service = TaskService(session)
            await task_service.update_task_progress(
                task.task_id,
                TaskProgressUpdate(
                    task_id=task.task_id,
                    progress_percentage=0,
                    current_step="章节生成失败",
                    status=ModelTaskStatus.FAILED.value,
                    error_message=str(e)
                )
            )
            raise e