from typing import Optional, Dict, Any
from pydantic import BaseModel

# Kimi API 请求结构
class KimiRequest(BaseModel):
    prompt: str  # 提示词
    context: Optional[Dict[str, Any]] = None  # 上下文信息
    output_format: str = "json"  # 输出格式
    stream: bool = False  # 是否流式输出

# Kimi API 响应结构
class KimiResponse(BaseModel):
    success: bool
    data: Dict[str, Any]  # 结构化数据
    message: Optional[str] = None
    tokens_used: Optional[int] = None

# 流式输出的数据块
class StreamChunk(BaseModel):
    chunk_id: int
    chunk_type: str  # "content", "option", "character", etc.
    data: Dict[str, Any]
    is_complete: bool = False