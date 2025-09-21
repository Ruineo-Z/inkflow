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
        logger.info(f"🎯 开始Kimi API调用 - 模型类: {model_class.__name__}")
        logger.info(f"📝 用户提示词长度: {len(user_prompt)} 字符")
        logger.info(f"🔧 系统提示词长度: {len(system_prompt) if system_prompt else 0} 字符")
        
        try:
            # 生成JSON Schema约束
            logger.info("📋 开始生成JSON Schema约束")
            converter = KimiSchemaConverter()
            schema_prompt = converter.create_kimi_system_message(
                model_class,
                system_prompt or "请根据要求生成结构化内容"
            )
            logger.info(f"✅ Schema生成完成，最终系统提示词长度: {len(schema_prompt)} 字符")

            # 构建消息
            messages = [
                {"role": "system", "content": schema_prompt},
                {"role": "user", "content": user_prompt}
            ]
            logger.info(f"📨 消息构建完成，总消息数: {len(messages)}")

            # 记录API调用参数
            logger.info(f"🚀 准备调用Kimi API")
            logger.info(f"📊 API配置: model={self.model}, temperature={settings.KIMI_TEMPERATURE}, max_tokens={settings.KIMI_MAX_TOKENS}")
            logger.info(f"🌐 API地址: {self.base_url}")
            
            # 调用OpenAI兼容API
            logger.info("⏳ 正在调用Kimi API...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=settings.KIMI_TEMPERATURE,
                max_tokens=settings.KIMI_MAX_TOKENS,
                response_format={"type": "json_object"}  # 启用JSON模式
            )
            logger.info("✅ Kimi API调用成功，开始处理响应")

            # 解析响应
            content = response.choices[0].message.content
            logger.info(f"📄 API响应内容长度: {len(content) if content else 0} 字符")
            
            if not content:
                logger.error("❌ API返回空内容")
                return {
                    "success": False,
                    "error": "API返回空内容",
                    "data": None
                }
            
            logger.info("🔍 开始解析JSON响应")
            json_data = json.loads(content)
            logger.info(f"✅ JSON解析成功，数据键: {list(json_data.keys()) if isinstance(json_data, dict) else 'non-dict'}")

            # 验证数据是否符合模型
            logger.info(f"🔧 开始验证数据模型: {model_class.__name__}")
            validated_data = model_class(**json_data)
            logger.info("✅ 数据模型验证成功")

            # 记录token使用情况
            tokens_used = response.usage.total_tokens if response.usage else 0
            logger.info(f"📊 Token使用情况: {tokens_used} tokens")

            return {
                "success": True,
                "data": validated_data.model_dump(),
                "tokens_used": tokens_used
            }

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON解析错误: {str(e)}")
            logger.error(f"📄 原始响应内容: {content if 'content' in locals() else 'N/A'}")
            return {
                "success": False,
                "error": f"JSON解析错误: {str(e)}",
                "data": None
            }
        except Exception as e:
            logger.error(f"💥 Kimi API调用异常: {str(e)}", exc_info=True)
            logger.error(f"🔧 异常类型: {type(e).__name__}")
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
        logger.info(f"🎯 开始Kimi流式API调用 - 模型类: {model_class.__name__}")
        chunk_id = 0
        accumulated_content = ""

        # 生成JSON Schema约束
        logger.info("📋 开始生成流式JSON Schema约束")
        converter = KimiSchemaConverter()
        schema_prompt = converter.create_kimi_system_message(
            model_class,
            system_prompt or "请根据要求生成结构化内容"
        )
        logger.info(f"✅ 流式Schema生成完成，系统提示词长度: {len(schema_prompt)} 字符")

        # 构建消息
        messages = [
            {"role": "system", "content": schema_prompt},
            {"role": "user", "content": user_prompt}
        ]
        logger.info(f"📨 流式消息构建完成，总消息数: {len(messages)}")

        # 调用OpenAI兼容流式API
        logger.info("🚀 准备调用Kimi流式API")
        logger.info(f"📊 流式API配置: model={self.model}, stream=True")
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.KIMI_TEMPERATURE,
            max_tokens=settings.KIMI_MAX_TOKENS,
            stream=True,  # 启用流式输出
            response_format={"type": "json_object"}  # 启用JSON模式
        )
        logger.info("✅ Kimi流式API调用成功，开始处理流式响应")

        # 处理流式响应
        logger.info("📡 开始处理流式响应数据")
        chunk_count = 0
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                accumulated_content += content_chunk
                chunk_count += 1

                # 每100个chunk记录一次进度
                if chunk_count % 100 == 0:
                    logger.info(f"📊 已处理 {chunk_count} 个流式数据块，累计内容长度: {len(accumulated_content)} 字符")

                # 发送流式数据块
                yield StreamChunk(
                    chunk_id=chunk_id,
                    chunk_type="content",
                    data={
                        "chunk": content_chunk,
                        "accumulated": accumulated_content
                    },
                    is_complete=False
                )
                chunk_id += 1

        logger.info(f"✅ 流式响应处理完成，总共处理 {chunk_count} 个数据块，累计内容长度: {len(accumulated_content)} 字符")

        # 流式输出完成，解析完整JSON
        if accumulated_content:
            try:
                logger.info("🔍 开始解析流式输出的完整JSON")
                json_data = json.loads(accumulated_content)
                logger.info(f"✅ 流式JSON解析成功，数据键: {list(json_data.keys()) if isinstance(json_data, dict) else 'non-dict'}")
                
                logger.info(f"🔧 开始验证流式数据模型: {model_class.__name__}")
                validated_data = model_class(**json_data)
                logger.info("✅ 流式数据模型验证成功")

                yield StreamChunk(
                    chunk_id=chunk_id,
                    chunk_type="complete",
                    data={"result": validated_data.model_dump()},
                    is_complete=True
                )
            except Exception as e:
                logger.error(f"❌ 流式输出最终解析失败: {str(e)}", exc_info=True)
                logger.error(f"📄 累计内容: {accumulated_content[:500]}..." if len(accumulated_content) > 500 else f"📄 累计内容: {accumulated_content}")
                yield StreamChunk(
                    chunk_id=chunk_id,
                    chunk_type="error",
                    data={"error": f"最终解析失败: {str(e)}"},
                    is_complete=True
                )
        else:
            logger.error("❌ 流式输出没有收到任何内容")
            yield StreamChunk(
                chunk_id=chunk_id,
                chunk_type="error",
                data={"error": "流式输出没有收到任何内容"},
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