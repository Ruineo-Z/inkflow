import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from app.api import router as api_router
from app.core.config import settings
from app.db.database import engine
from app.db.migration import run_auto_migration
from app.db.redis import RedisClient

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("应用正在启动...")

    # 执行数据库迁移
    try:
        logger.info("检查并执行数据库迁移...")
        migration_success = await run_auto_migration(engine)

        if migration_success:
            logger.info("🎉 数据库已准备就绪")
        else:
            logger.error("❌ 数据库迁移失败")
            raise RuntimeError("数据库迁移失败，应用无法启动")
    except Exception as e:
        logger.error(f"❌ 数据库迁移错误: {e}")
        raise

    # 初始化Redis连接
    try:
        logger.info("正在连接Redis...")
        redis_client = await RedisClient.get_client()
        await redis_client.ping()
        logger.info("✅ Redis连接成功")
    except redis.RedisError as e:
        logger.error(f"❌ Redis连接失败: {e}")
        raise RuntimeError(f"Redis连接失败，应用无法启动: {e}")
    except Exception as e:
        logger.error(f"❌ Redis初始化错误: {e}")
        raise

    logger.info("应用启动完成")

    yield  # 应用运行期间

    # 关闭时执行
    logger.info("应用正在关闭...")
    await RedisClient.close()
    logger.info("Redis连接已关闭")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 根路径路由
    @app.get("/")
    async def root():
        return {
            "message": "Welcome to InkFlow API",
            "version": settings.VERSION,
            "docs": "/docs",
            "redoc": "/redoc"
        }

    # 注册API路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)