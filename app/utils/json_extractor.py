"""
JSON片段提取工具

用途：从Kimi流式返回的不完整JSON片段中提取content字段
设计：使用正则表达式提取，支持中文引号和转义字符
"""
import re
import logging

logger = logging.getLogger(__name__)


def extract_content_from_json_fragment(json_fragment: str) -> str:
    """
    从不完整JSON片段中提取content字段的纯文本内容

    原理：
    - Kimi返回的JSON格式：{"content": "文本内容...", "options": [...]}
    - 对话使用中文引号："他说："你好""
    - 不需要处理英文引号转义（因为Kimi使用中文引号）

    Args:
        json_fragment: 累积的JSON片段，可能不完整

    Returns:
        提取到的纯文本content，如果未找到返回空字符串

    Examples:
        >>> extract_content_from_json_fragment('{"content": "夜色')
        '夜色'
        >>> extract_content_from_json_fragment('{"content": "他说："你好""}')
        '他说："你好"'
    """
    try:
        # 正则模式：匹配 "content": "..." 中的内容
        # 由于Kimi使用中文引号，不会与JSON的英文引号冲突
        # 所以可以使用简单的正则：匹配到第一个未转义的英文引号为止
        pattern = r'"content"\s*:\s*"((?:[^"\\]|\\.)*)'

        match = re.search(pattern, json_fragment)
        if match:
            # 提取到的内容（可能包含转义字符）
            raw_content = match.group(1)

            # 处理JSON转义字符
            # 注意：这里提取的是JSON字符串内部的内容，需要反转义
            content = raw_content.replace('\\n', '\n')  # 换行
            content = content.replace('\\t', '\t')      # 制表符
            content = content.replace('\\"', '"')       # 引号（如果有）
            content = content.replace('\\\\', '\\')     # 反斜杠

            logger.debug(f"成功提取content: {len(content)}字符")
            return content
        else:
            logger.debug("未找到content字段")
            return ""

    except Exception as e:
        logger.warning(f"提取content时出错: {e}")
        return ""


def extract_options_from_json(json_str: str) -> list:
    """
    从完整JSON中提取options数组

    注意：Options需要完整JSON才能解析

    Args:
        json_str: 完整的JSON字符串

    Returns:
        options列表，解析失败返回空列表
    """
    try:
        import json
        data = json.loads(json_str)
        options = data.get('options', [])
        logger.debug(f"成功提取options: {len(options)}个")
        return options
    except Exception as e:
        logger.debug(f"提取options失败（可能JSON不完整）: {e}")
        return []
