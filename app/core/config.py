from typing import List, Optional
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # 项目基础配置
    PROJECT_NAME: str = "InkFlow"
    PROJECT_DESCRIPTION: str = "AI-powered writing assistant"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"

    # CORS配置
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://inkflow:inkflow123@localhost:5432/inkflow"
    DATABASE_ECHO: bool = False

    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Redis配置
    REDIS_HOST: str = "localhost"  # 开发环境使用localhost，生产环境通过.env配置
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None  # None表示无密码，生产环境必须配置
    REDIS_STREAM_CACHE_TTL: int = 3600  # 流式内容缓存1小时

    # 开发/生产环境
    DEBUG: bool = True
    TESTING: bool = False

    # Kimi大模型配置
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "moonshot-v1-8k"
    KIMI_MAX_TOKENS: int = 2000
    KIMI_TEMPERATURE: float = 0.7
    KIMI_TIMEOUT: int = 30

    @property
    def get_allowed_origins(self) -> List[str]:
        """解析 ALLOWED_ORIGINS 字符串为列表"""
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

    def model_post_init(self, __context):
        """配置验证钩子 - 在模型初始化后执行"""
        # 生产环境检查Redis密码
        if not self.DEBUG and not self.REDIS_PASSWORD:
            logger.warning("⚠️  生产环境Redis未配置密码！这可能导致安全风险。")


settings = Settings()