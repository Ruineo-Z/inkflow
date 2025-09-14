"""
Kimi AI服务
实现结构化输出和结构化流式输出功能
基于Moonshot API (https://api.moonshot.cn/v1)
使用OpenAI SDK进行API调用
"""
import json
from typing import Dict, Any, Optional, AsyncGenerator, Type
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.kimi import KimiRequest, KimiResponse, StreamChunk
from app.utils.kimi_schema import KimiSchemaConverter


class KimiService:
    """Kimi AI服务类"""

    def __init__(self):
        self.api_key = settings.KIMI_API_KEY
        self.base_url = settings.KIMI_BASE_URL
        self.model = settings.KIMI_MODEL
        self.timeout = settings.KIMI_TIMEOUT

        # 初始化OpenAI客户端，配置为使用Kimi API
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )

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

    async def generate_streaming_output(
        self,
        model_class: Type[BaseModel],
        user_prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        生成结构化流式输出

        Args:
            model_class: Pydantic模型类
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）

        Yields:
            StreamChunk: 流式数据块
        """
        chunk_id = 0
        accumulated_content = ""

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

        except Exception as e:
            yield StreamChunk(
                chunk_id=chunk_id,
                chunk_type="error",
                data={"error": f"流式生成错误: {str(e)}"},
                is_complete=True
            )

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