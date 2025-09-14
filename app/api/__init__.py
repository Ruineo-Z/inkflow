from fastapi import APIRouter

from app.api.v1 import api_router as v1_router

router = APIRouter()

# 注册v1版本的API路由
router.include_router(v1_router, prefix="/v1")