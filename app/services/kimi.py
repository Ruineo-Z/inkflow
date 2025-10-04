"""
Kimi AI服务
实现结构化输出和结构化流式输出功能
基于Moonshot API (https://api.moonshot.cn/v1)
使用OpenAI SDK进行API调用
"""
import json
import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator, Type
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.kimi import KimiRequest, KimiResponse, StreamChunk
from app.utils.kimi_schema import KimiSchemaConverter

logger = logging.getLogger(__name__)


class KimiService:
    """Kimi AI服务类"""

    def __init__(self):
        self.api_key = settings.KIMI_API_KEY
        self.base_url = settings.KIMI_BASE_URL
        self.model = settings.KIMI_MODEL
        self.timeout = settings.KIMI_TIMEOUT
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 1  # 重试延迟（秒）

        # 初始化OpenAI客户端，配置为使用Kimi API
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

    async def _retry_on_connection_error(self, func, *args, **kwargs):
        """在连接错误时重试的装饰器方法"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                is_connection_error = any(keyword in error_str for keyword in [
                    'connection', 'timeout', 'peer closed', 'incomplete chunked read',
                    'connection reset', 'connection aborted', 'network'
                ])

                if is_connection_error and attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                    logger.warning(f"Kimi API连接错误 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    last_error = e
                    continue
                else:
                    # 非连接错误或已达到最大重试次数
                    raise e

        # 所有重试都失败了，抛出最后一个错误
        if last_error:
            raise last_error

    async def generate_structured_output(
        self,
        model_class: Type[BaseModel],
        user_prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成结构化输出

        Args:
            model_class: Pydantic模型类
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）

        Returns:
            结构化的JSON数据
        """
        try:
            # 生成JSON Schema约束
            converter = KimiSchemaConverter()
            schema_prompt = converter.create_kimi_system_message(
                model_class,
                system_prompt or "请根据要求生成结构化内容"
            )

            # 构建消息
            messages = [
                {"role": "system", "content": schema_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 调用OpenAI兼容API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=settings.KIMI_TEMPERATURE,
                max_tokens=settings.KIMI_MAX_TOKENS,
                response_format={"type": "json_object"}  # 启用JSON模式
            )

            # 解析响应
            content = response.choices[0].message.content
            json_data = json.loads(content)

            # 验证数据是否符合模型
            validated_data = model_class(**json_data)

            return {
                "success": True,
                "data": validated_data.model_dump(),
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析错误: {str(e)}",
                "data": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"生成错误: {str(e)}",
                "data": None
            }

    async def _do_streaming_output(
        self,
        model_class: Type[BaseModel],
        user_prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """内部流式输出方法（用于重试）"""
        chunk_id = 0
        accumulated_content = ""

        # 生成JSON Schema约束
        converter = KimiSchemaConverter()
        schema_prompt = converter.create_kimi_system_message(
            model_class,
            system_prompt or "请根据要求生成结构化内容"
        )

        # 构建消息
        messages = [
            {"role": "system", "content": schema_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 调用OpenAI兼容流式API
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.KIMI_TEMPERATURE,
            max_tokens=settings.KIMI_MAX_TOKENS,
            stream=True,  # 启用流式输出
            response_format={"type": "json_object"}  # 启用JSON模式
        )

        # 处理流式响应
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                accumulated_content += content_chunk

                # 发送流式数据块（原始JSON片段）
                yield StreamChunk(
                    chunk_id=chunk_id,
                    chunk_type="content",
                    data={
                        "chunk": content_chunk,  # 原始chunk
                        "accumulated": accumulated_content  # 累积的JSON
                    },
                    is_complete=False
                )
                chunk_id += 1

        # 流式输出完成，解析完整JSON
        if accumulated_content:
            try:
                json_data = json.loads(accumulated_content)
                validated_data = model_class(**json_data)

                yield StreamChunk(
                    chunk_id=chunk_id,
                    chunk_type="complete",
                    data={"result": validated_data.model_dump()},
                    is_complete=True
                )
            except Exception as e:
                yield StreamChunk(
                    chunk_id=chunk_id,
                    chunk_type="error",
                    data={"error": f"最终解析失败: {str(e)}"},
                    is_complete=True
                )

    async def generate_streaming_output(
        self,
        model_class: Type[BaseModel],
        user_prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        生成结构化流式输出（带重试机制）

        Args:
            model_class: Pydantic模型类
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）

        Yields:
            StreamChunk: 流式数据块
        """
        for attempt in range(self.max_retries):
            try:
                async for chunk in self._do_streaming_output(model_class, user_prompt, system_prompt):
                    yield chunk
                return  # 成功完成，退出重试循环

            except Exception as e:
                error_str = str(e).lower()
                is_connection_error = any(keyword in error_str for keyword in [
                    'connection', 'timeout', 'peer closed', 'incomplete chunked read',
                    'connection reset', 'connection aborted', 'network'
                ])

                if is_connection_error and attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # 指数退避
                    logger.warning(f"流式输出连接错误 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 非连接错误或已达到最大重试次数
                    logger.error(f"流式输出最终失败: {str(e)}")
                    yield StreamChunk(
                        chunk_id=0,
                        chunk_type="error",
                        data={"error": f"流式生成错误: {str(e)}"},
                        is_complete=True
                    )
                    return

    async def test_connection(self) -> bool:
        """测试Kimi API连接"""
        try:
            # 尝试获取模型列表来测试连接
            models = await self.client.models.list()
            return len(models.data) > 0
        except Exception:
            return False


# 全局Kimi服务实例
kimi_service = KimiService()