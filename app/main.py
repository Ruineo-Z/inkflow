import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.core.config import settings
from app.db.database import engine
from app.db.migration import run_auto_migration

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("应用正在启动...")

    try:
        # 执行数据库迁移
        logger.info("检查并执行数据库迁移...")
        migration_success = await run_auto_migration(engine)

        if migration_success:
            logger.info("🎉 数据库已准备就绪")
        else:
            logger.error("⚠️  数据库迁移失败，但应用将继续启动")

    except Exception as e:
        logger.error(f"启动时发生错误: {e}")
        # 可以选择是否要因迁移失败而终止应用启动
        # raise e  # 取消注释以在迁移失败时终止启动

    logger.info("应用启动完成")

    yield  # 应用运行期间

    # 关闭时执行
    logger.info("应用正在关闭...")


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