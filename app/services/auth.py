from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.user import UserService
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token
)
from app.schemas.auth import UserRegisterRequest, UserLoginRequest

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def register_user(self, user_data: UserRegisterRequest) -> User:
        """用户注册"""
        # 检查邮箱是否已存在
        existing_user = await self.user_service.get_by_email(user_data.email)
        if existing_user:
            raise ValueError("Email already registered")

        # 加密密码
        hashed_password = get_password_hash(user_data.password)

        # 创建用户
        user = User(
            name=user_data.name,
            email=user_data.email,
            password=hashed_password
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def authenticate_user(self, login_data: UserLoginRequest) -> Optional[User]:
        """用户认证"""
        user = await self.user_service.get_by_email(login_data.email)
        if not user:
            return None

        if not verify_password(login_data.password, user.password):
            return None

        return user

    def create_user_tokens(self, user: User) -> dict:
        """为用户创建令牌"""
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def refresh_access_token(self, refresh_token: str) -> Optional[dict]:
        """刷新访问令牌"""
        payload = verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        # 验证用户是否存在
        user = await self.user_service.get_by_id(int(user_id))
        if not user:
            return None

        # 创建新的访问令牌
        access_token = create_access_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "token_type": "bearer"
        }

    async def get_current_user(self, user_id: int) -> Optional[User]:
        """获取当前用户"""
        return await self.user_service.get_by_id(user_id)