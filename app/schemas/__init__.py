# 第一个流程所需的Schema导入
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserDetail
from app.schemas.novel import NovelCreate, NovelUpdate, NovelResponse, NovelDetail
from app.schemas.novel import WuxiaWorldSetting, SciFiWorldSetting, ProtagonistProfile
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse
from app.schemas.kimi import KimiRequest, KimiResponse, StreamChunk

__all__ = [
    # 基础用户功能
    "UserCreate", "UserUpdate", "UserResponse", "UserDetail",
    # 基础小说功能
    "NovelCreate", "NovelUpdate", "NovelResponse", "NovelDetail",
    # 第一流程AI生成相关
    "WuxiaWorldSetting", "SciFiWorldSetting", "ProtagonistProfile",
    # 认证相关
    "UserRegisterRequest", "UserLoginRequest", "TokenResponse",
    # Kimi API相关
    "KimiRequest", "KimiResponse", "StreamChunk",
]