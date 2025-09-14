from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 项目基础配置
    PROJECT_NAME: str = "InkFlow"
    PROJECT_DESCRIPTION: str = "AI-powered writing assistant"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"

    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://inkflow:inkflow123@localhost:5432/inkflow"
    DATABASE_ECHO: bool = False

    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

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

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://localhost:8080"]

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()