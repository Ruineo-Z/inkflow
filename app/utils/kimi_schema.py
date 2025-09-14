"""
Kimi API Schema工具类
用于将Pydantic模型转换为Kimi API所需的JSON Schema描述格式
"""
import json
from typing import Type, Dict, Any
from pydantic import BaseModel

class KimiSchemaConverter:
    """Kimi Schema转换器"""

    @staticmethod
    def get_json_schema(model_class: Type[BaseModel]) -> Dict[str, Any]:
        """
        获取Pydantic模型的JSON Schema

        Args:
            model_class: Pydantic模型类

        Returns:
            JSON Schema字典
        """
        return model_class.model_json_schema()

    @staticmethod
    def get_json_schema_string(model_class: Type[BaseModel], indent: int = 2) -> str:
        """
        获取Pydantic模型的JSON Schema字符串（格式化）

        Args:
            model_class: Pydantic模型类
            indent: 缩进空格数

        Returns:
            格式化的JSON Schema字符串
        """
        schema = model_class.model_json_schema()
        return json.dumps(schema, indent=indent, ensure_ascii=False)

    @staticmethod
    def create_kimi_prompt_schema(model_class: Type[BaseModel],
                                description: str = None) -> str:
        """
        为Kimi API创建结构化输出提示词中的JSON Schema部分

        Args:
            model_class: Pydantic模型类
            description: 额外的描述信息

        Returns:
            适合在Kimi提示词中使用的JSON Schema描述
        """
        schema = model_class.model_json_schema()

        prompt_parts = []

        if description:
            prompt_parts.append(f"请按照以下JSON格式输出：{description}\n")
        else:
            prompt_parts.append("请严格按照以下JSON格式输出：\n")

        # 构建Kimi风格的简化Schema描述
        prompt_parts.append("```json")
        prompt_parts.append("{")

        # 获取属性并生成简化格式
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])

        field_items = []
        for field_name, field_info in properties.items():
            # 获取中文描述
            chinese_desc = field_info.get('description', field_name)
            field_items.append(f'    "{field_name}": "{chinese_desc}"')

        prompt_parts.append(",\n".join(field_items))
        prompt_parts.append("}")
        prompt_parts.append("```")

        return "\n".join(prompt_parts)

    @staticmethod
    def create_kimi_system_message(model_class: Type[BaseModel],
                                 task_description: str = None) -> str:
        """
        为Kimi API创建系统消息，包含JSON Schema约束

        Args:
            model_class: Pydantic模型类
            task_description: 任务描述

        Returns:
            适合作为Kimi API system message的内容
        """
        schema = model_class.model_json_schema()

        message_parts = [
            "你是一个专业的AI写作助手。",
            f"任务：{task_description}" if task_description else "请根据用户需求完成写作任务。",
            "",
            "重要：你必须严格按照以下JSON格式输出，不要添加任何额外的文本或格式：",
            "",
            "```json",
            json.dumps(schema, indent=2, ensure_ascii=False),
            "```",
            "",
            "确保输出的JSON：",
            "1. 格式完全正确，可以被JSON解析",
            "2. 包含所有必需字段",
            "3. 数据类型符合要求",
            "4. 不包含任何注释或额外内容"
        ]

        return "\n".join(message_parts)

    @staticmethod
    def validate_kimi_response(response_data: Dict[str, Any],
                             model_class: Type[BaseModel]) -> bool:
        """
        验证Kimi API响应是否符合指定的Pydantic模型

        Args:
            response_data: Kimi API返回的数据
            model_class: 期望的Pydantic模型类

        Returns:
            验证是否通过
        """
        try:
            model_class(**response_data)
            return True
        except Exception:
            return False

    @staticmethod
    def parse_kimi_response(response_data: Dict[str, Any],
                          model_class: Type[BaseModel]) -> BaseModel:
        """
        将Kimi API响应解析为指定的Pydantic模型

        Args:
            response_data: Kimi API返回的数据
            model_class: 目标Pydantic模型类

        Returns:
            解析后的模型实例

        Raises:
            ValidationError: 数据验证失败时
        """
        return model_class(**response_data)