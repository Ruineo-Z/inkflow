from fastapi import APIRouter

from . import auth, health, novels, themes, chapters, admin

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(novels.router, prefix="/novels", tags=["novels"])
api_router.include_router(themes.router, prefix="/themes", tags=["themes"])
api_router.include_router(chapters.router, prefix="", tags=["chapters"])
# api_router.include_router(admin.router, prefix="/admin", tags=["admin"])