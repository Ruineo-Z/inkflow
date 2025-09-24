"""
基于 Redis 的简单任务队列系统
"""
import json
import time
import uuid
import asyncio
import logging
import re
from typing import Dict, Any, Optional
from enum import Enum

def safe_redis_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """确保Redis数据中没有None值，递归处理所有数据类型"""
    def clean_value(value):
        if value is None:
            return ""
        elif isinstance(value, dict):
            # 递归清理字典中的None值
            cleaned_dict = {}
            for k, v in value.items():
                cleaned_dict[k] = clean_value(v)
            return json.dumps(cleaned_dict)
        elif isinstance(value, list):
            # 清理列表中的None值
            cleaned_list = [clean_value(item) for item in value]
            return json.dumps(cleaned_list)
        elif isinstance(value, (str, int, float, bool)):
            return value
        else:
            # 其他类型转为字符串
            return str(value) if value is not None else ""

    safe_data = {}
    for key, value in data.items():
        safe_data[key] = clean_value(value)
    return safe_data

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class RedisTaskQueue:
    """基于 Redis 的简单任务队列"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.queue_name = "chapter_generation_queue"
        self._running = False

    async def submit_task(self, task_data: Dict[str, Any]) -> str:
        """提交任务到队列"""
        task_id = str(uuid.uuid4())

        task_info = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "progress_percentage": 0,
            "current_step": "任务已创建，等待处理...",
            "data": json.dumps(task_data),
            "result": "",
            "error": "",
            "created_at": time.time(),
            "updated_at": time.time()
        }

        # 存储任务信息（确保无None值）
        self.redis.hset(f"task:{task_id}", mapping=safe_redis_data(task_info))

        # 推送到任务队列
        self.redis.lpush(self.queue_name, task_id)

        logger.info(f"✅ 任务已提交到Redis队列 - 任务ID: {task_id}")
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task_data = self.redis.hgetall(f"task:{task_id}")
        if not task_data:
            return None

        # 安全转换键值对（处理bytes和string两种情况）
        result = {}
        for key, value in task_data.items():
            # 安全处理key
            if isinstance(key, bytes):
                key = key.decode()
            elif not isinstance(key, str):
                key = str(key)

            # 安全处理value
            if isinstance(value, bytes):
                value = value.decode()
            elif not isinstance(value, str):
                value = str(value)

            result[key] = value

        # 解析JSON字段 - 确保空字符串被处理为None（修复验证错误）
        result_field = result.get('result', '')
        if result_field and result_field.strip():
            try:
                result['result'] = json.loads(result_field)
            except:
                # JSON解析失败，保持原始字符串
                pass
        else:
            # 空字符串或None，设置为None确保类型安全
            result['result'] = None

        return result

    async def update_task_progress(
        self,
        task_id: str,
        progress: int = None,
        status: str = None,
        current_step: str = None,
        result: Dict[str, Any] = None,
        error: str = None,
        content_chunk: str = None
    ):
        """更新任务进度"""
        updates = {"updated_at": time.time()}

        if progress is not None:
            updates["progress_percentage"] = progress
        if status is not None:
            updates["status"] = status
        if current_step is not None:
            updates["current_step"] = current_step
        if result is not None:
            updates["result"] = json.dumps(result)
        if error is not None:
            updates["error"] = error

        self.redis.hset(f"task:{task_id}", mapping=safe_redis_data(updates))

        # 如果有内容片段，追加到流式内容中
        if content_chunk is not None:
            self.redis.rpush(f"task:{task_id}:content_stream", content_chunk)
            # 设置流式内容的过期时间（1小时）
            self.redis.expire(f"task:{task_id}:content_stream", 3600)

        logger.info(f"📊 任务进度更新 - ID: {task_id}, 进度: {progress}%, 状态: {status}")

    async def get_task_content_stream(self, task_id: str) -> list:
        """获取任务的流式内容"""
        content_chunks = self.redis.lrange(f"task:{task_id}:content_stream", 0, -1)

        # 转换bytes到string
        result = []
        for chunk in content_chunks:
            if isinstance(chunk, bytes):
                result.append(chunk.decode())
            else:
                result.append(str(chunk))

        return result

    async def add_content_chunk(
        self,
        task_id: str,
        chunk_type: str,
        text: str
    ):
        """添加结构化内容片段"""
        import json

        # 获取当前chunk索引
        chunk_index = self.redis.llen(f"task:{task_id}:structured_chunks")

        # 创建结构化chunk
        chunk_data = {
            "type": chunk_type,
            "text": text,
            "index": chunk_index
        }

        # 存储到Redis
        self.redis.rpush(f"task:{task_id}:structured_chunks", json.dumps(chunk_data))

        # 设置过期时间（1小时）
        self.redis.expire(f"task:{task_id}:structured_chunks", 3600)

        logger.info(f"📝 添加内容片段 - 任务ID: {task_id}, 类型: {chunk_type}, 索引: {chunk_index}")

    async def get_structured_chunks(
        self,
        task_id: str,
        from_chunk: int = 0
    ) -> list:
        """获取结构化内容片段（支持增量获取）"""
        import json

        # 获取从指定索引开始的chunks
        all_chunks = self.redis.lrange(f"task:{task_id}:structured_chunks", from_chunk, -1)

        result = []
        for i, chunk_data in enumerate(all_chunks):
            try:
                if isinstance(chunk_data, bytes):
                    chunk_data = chunk_data.decode()

                chunk = json.loads(chunk_data)
                # 确保index正确
                chunk["index"] = from_chunk + i
                result.append(chunk)
            except json.JSONDecodeError:
                logger.warning(f"⚠️  无法解析chunk数据 - 任务ID: {task_id}, 索引: {from_chunk + i}")
                continue

        return result

    async def get_chunks_count(self, task_id: str) -> int:
        """获取当前chunks总数"""
        return self.redis.llen(f"task:{task_id}:structured_chunks")

    async def start_worker(self):
        """启动任务处理worker"""
        self._running = True
        logger.info("🚀 Redis任务队列Worker启动")

        while self._running:
            try:
                # 非阻塞式从队列取任务
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: self.redis.brpop(self.queue_name, timeout=1)
                )

                if result:
                    queue_name, task_id = result
                    logger.info(f"📋 从队列获取任务 - ID: {task_id}")

                    # 处理任务
                    await self._process_task(task_id)
                else:
                    # 没有任务时短暂休眠
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Worker处理任务时出错: {str(e)}")
                await asyncio.sleep(1)

    async def stop_worker(self):
        """停止worker"""
        self._running = False
        logger.info("🛑 Redis任务队列Worker停止")

    async def _process_task(self, task_id: str):
        """处理单个任务"""
        try:
            # 获取任务信息
            task_info = await self.get_task_status(task_id)
            if not task_info:
                logger.error(f"❌ 任务不存在 - ID: {task_id}")
                return

            # 解析任务数据
            task_data = json.loads(task_info['data'])

            # 更新为运行状态
            await self.update_task_progress(
                task_id,
                progress=10,
                status=TaskStatus.RUNNING.value,
                current_step="正在开始处理任务..."
            )

            # 根据任务类型执行相应逻辑
            if task_data['task_type'] == 'FIRST_CHAPTER_GENERATION':
                await self._execute_first_chapter_generation(task_id, task_data)
            elif task_data['task_type'] == 'CHAPTER_GENERATION':
                await self._execute_chapter_generation(task_id, task_data)
            else:
                raise ValueError(f"不支持的任务类型: {task_data['task_type']}")

        except Exception as e:
            logger.error(f"❌ 任务处理失败 - ID: {task_id}, 错误: {str(e)}")
            await self.update_task_progress(
                task_id,
                progress=0,
                status=TaskStatus.FAILED.value,
                current_step="任务执行失败",
                error=str(e)
            )

            # 同时更新PostgreSQL的失败状态
            await self._update_db_final_status(
                task_id,
                status="FAILED",
                error_message=str(e)
            )

    async def _execute_first_chapter_generation(self, task_id: str, task_data: Dict[str, Any]):
        """执行第一章生成"""
        try:
            from app.services.chapter_generator import chapter_generator
            from app.services.chapter import ChapterService
            from app.services.novel import NovelService
            from app.db.database import async_session_maker

            async with async_session_maker() as session:
                # 获取小说信息
                novel_service = NovelService(session)
                novel = await novel_service.get_by_id(task_data['novel_id'])

                if not novel:
                    raise ValueError("小说不存在")

                await self.update_task_progress(
                    task_id,
                    progress=30,
                    current_step="正在调用AI生成第一章..."
                )

                # 调用AI生成
                chapter_data = None
                async for sse_event in chapter_generator.generate_first_chapter_stream(
                    world_setting=novel.background_setting or "",
                    protagonist_info=novel.character_setting or "",
                    genre=novel.theme or "wuxia",
                    task_id=task_id,
                    task_queue=self
                ):
                    if "event: status" in sse_event:
                        await self.update_task_progress(
                            task_id, progress=50, current_step="AI正在生成章节内容..."
                        )
                    elif "event: summary" in sse_event:
                        # 解析摘要数据并添加结构化chunk
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            summary_data = json.loads(data_match.group(1))
                            await self.add_content_chunk(
                                task_id,
                                chunk_type="title",
                                text=summary_data.get('title', '')
                            )
                        await self.update_task_progress(
                            task_id, progress=70, current_step="摘要生成完成，正在生成正文..."
                        )
                    elif "event: content" in sse_event:
                        # 捕获流式内容片段并保存为结构化chunks
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            content_data = json.loads(data_match.group(1))
                            content_chunk = content_data.get('text', '')
                            if content_chunk:
                                # 存储为结构化content chunk
                                await self.add_content_chunk(
                                    task_id,
                                    chunk_type="content",
                                    text=content_chunk
                                )

                                # 保持旧的进度更新（兼容现有流式接口）
                                await self.update_task_progress(
                                    task_id,
                                    current_step="正在生成章节内容...",
                                    content_chunk=content_chunk
                                )
                    elif "event: complete" in sse_event:
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            chapter_data = json.loads(data_match.group(1))

                            # 添加分隔符和选项chunks
                            await self.add_content_chunk(
                                task_id,
                                chunk_type="separator",
                                text="---"
                            )

                            # 添加选项chunks
                            if 'options' in chapter_data:
                                for i, option in enumerate(chapter_data['options'], 1):
                                    option_text = f"选项{i}: {option.get('text', '')}"
                                    await self.add_content_chunk(
                                        task_id,
                                        chunk_type="option",
                                        text=option_text
                                    )
                        break
                    elif "event: error" in sse_event:
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            error_data = json.loads(data_match.group(1))
                            raise ValueError(f"AI生成失败: {error_data.get('error', '未知错误')}")

                if not chapter_data:
                    raise ValueError("AI生成失败，未获取到章节数据")

                await self.update_task_progress(
                    task_id, progress=90, current_step="正在保存章节到数据库..."
                )

                # 保存章节
                chapter_service = ChapterService(session)
                created_chapter = await chapter_service.create_chapter_with_options(
                    novel_id=task_data['novel_id'],
                    title=chapter_data['title'],
                    summary=chapter_data['summary']['summary'],
                    content=chapter_data['content'],
                    options_data=chapter_data['options']
                )

                # 任务完成 - 更新Redis状态
                result_data = {
                    "chapter_id": created_chapter.id,
                    "chapter_number": created_chapter.chapter_number,
                    "title": created_chapter.title,
                    "novel_id": task_data['novel_id']
                }

                await self.update_task_progress(
                    task_id,
                    progress=100,
                    status=TaskStatus.COMPLETED.value,
                    current_step="第一章生成完成！",
                    result=result_data
                )

                # 同时更新PostgreSQL的最终状态
                await self._update_db_final_status(
                    task_id,
                    status="COMPLETED",
                    result_data=result_data,
                    chapter_id=created_chapter.id
                )

                logger.info(f"🎉 第一章生成任务完成 - 任务ID: {task_id}, 章节ID: {created_chapter.id}")

        except Exception as e:
            raise e

    async def _execute_chapter_generation(self, task_id: str, task_data: Dict[str, Any]):
        """执行后续章节生成"""
        try:
            from app.services.chapter_generator import chapter_generator
            from app.services.chapter import ChapterService
            from app.services.novel import NovelService
            from app.db.database import async_session_maker

            async with async_session_maker() as session:
                # 获取小说信息
                novel_service = NovelService(session)
                novel = await novel_service.get_by_id(task_data['novel_id'])

                if not novel:
                    raise ValueError("小说不存在")

                await self.update_task_progress(
                    task_id,
                    progress=20,
                    current_step="正在获取章节上下文..."
                )

                # 获取章节生成上下文
                chapter_service = ChapterService(session)

                # 获取用户的最后选择（如果有的话）
                selected_option_id = task_data.get('selected_option_id')
                context = await chapter_service.get_generation_context(
                    novel_id=task_data['novel_id'],
                    selected_option_id=selected_option_id
                )

                await self.update_task_progress(
                    task_id,
                    progress=30,
                    current_step="正在调用AI生成后续章节..."
                )

                # 调用AI生成后续章节
                chapter_data = None
                async for sse_event in chapter_generator.generate_next_chapter_stream(
                    novel_id=task_data['novel_id'],
                    selected_option_id=selected_option_id or 0,
                    context=context,
                    task_id=task_id,
                    task_queue=self
                ):
                    if "event: status" in sse_event:
                        await self.update_task_progress(
                            task_id, progress=50, current_step="AI正在生成章节内容..."
                        )
                    elif "event: summary" in sse_event:
                        # 解析摘要数据并添加结构化chunk
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            summary_data = json.loads(data_match.group(1))
                            await self.add_content_chunk(
                                task_id,
                                chunk_type="title",
                                text=summary_data.get('title', '')
                            )
                        await self.update_task_progress(
                            task_id, progress=70, current_step="摘要生成完成，正在生成正文..."
                        )
                    elif "event: content" in sse_event:
                        # 捕获流式内容片段并保存为结构化chunks
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            content_data = json.loads(data_match.group(1))
                            content_chunk = content_data.get('text', '')
                            if content_chunk:
                                # 存储为结构化content chunk
                                await self.add_content_chunk(
                                    task_id,
                                    chunk_type="content",
                                    text=content_chunk
                                )

                                # 保持旧的进度更新（兼容现有流式接口）
                                await self.update_task_progress(
                                    task_id,
                                    current_step="正在生成章节内容...",
                                    content_chunk=content_chunk
                                )
                    elif "event: complete" in sse_event:
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            chapter_data = json.loads(data_match.group(1))

                            # 添加分隔符和选项chunks
                            await self.add_content_chunk(
                                task_id,
                                chunk_type="separator",
                                text="---"
                            )

                            # 添加选项chunks
                            if 'options' in chapter_data:
                                for i, option in enumerate(chapter_data['options'], 1):
                                    option_text = f"选项{i}: {option.get('text', '')}"
                                    await self.add_content_chunk(
                                        task_id,
                                        chunk_type="option",
                                        text=option_text
                                    )
                        break
                    elif "event: error" in sse_event:
                        data_match = re.search(r'data: (.+)', sse_event)
                        if data_match:
                            error_data = json.loads(data_match.group(1))
                            raise ValueError(f"AI生成失败: {error_data.get('error', '未知错误')}")

                if not chapter_data:
                    raise ValueError("AI生成失败，未获取到章节数据")

                await self.update_task_progress(
                    task_id, progress=90, current_step="正在保存章节到数据库..."
                )

                # 保存章节
                created_chapter = await chapter_service.create_chapter_with_options(
                    novel_id=task_data['novel_id'],
                    title=chapter_data['title'],
                    summary=chapter_data['summary']['summary'],
                    content=chapter_data['content'],
                    options_data=chapter_data['options']
                )

                # 任务完成 - 更新Redis状态
                result_data = {
                    "chapter_id": created_chapter.id,
                    "chapter_number": created_chapter.chapter_number,
                    "title": created_chapter.title,
                    "novel_id": task_data['novel_id']
                }

                await self.update_task_progress(
                    task_id,
                    progress=100,
                    status=TaskStatus.COMPLETED.value,
                    current_step="后续章节生成完成！",
                    result=result_data
                )

                # 同时更新PostgreSQL的最终状态
                await self._update_db_final_status(
                    task_id,
                    status="COMPLETED",
                    result_data=result_data,
                    chapter_id=created_chapter.id
                )

                logger.info(f"🎉 后续章节生成任务完成 - 任务ID: {task_id}, 章节ID: {created_chapter.id}")

        except Exception as e:
            raise e

    async def _update_db_final_status(
        self,
        task_id: str,
        status: str,
        result_data: Dict[str, Any] = None,
        error_message: str = None,
        chapter_id: int = None
    ):
        """更新PostgreSQL中的最终任务状态"""
        try:
            from app.db.database import async_session_maker
            from app.models.task import GenerationTask, TaskStatus as ModelTaskStatus
            from sqlalchemy import select
            from datetime import datetime
            import json

            async with async_session_maker() as session:
                # 查询任务
                stmt = select(GenerationTask).where(GenerationTask.task_id == task_id)
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()

                if task:
                    # 更新最终状态
                    task.status = ModelTaskStatus(status)
                    if result_data:
                        task.result_data = json.dumps(result_data)
                    if error_message:
                        task.error_message = error_message
                    if chapter_id:
                        task.chapter_id = chapter_id
                    if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                        task.completed_at = datetime.utcnow()

                    await session.commit()
                    logger.info(f"✅ PostgreSQL任务状态已更新 - 任务ID: {task_id}, 状态: {status}")

        except Exception as e:
            logger.error(f"❌ 更新PostgreSQL任务状态失败 - 任务ID: {task_id}, 错误: {str(e)}")


# 全局任务队列实例（稍后初始化）
task_queue: Optional[RedisTaskQueue] = None

def get_task_queue() -> RedisTaskQueue:
    """获取任务队列实例"""
    global task_queue
    if task_queue is None:
        raise RuntimeError("任务队列尚未初始化")
    return task_queue

def init_task_queue(redis_client):
    """初始化任务队列"""
    global task_queue
    task_queue = RedisTaskQueue(redis_client)
    return task_queue