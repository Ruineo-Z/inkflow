from datetime import datetime, timedelta
from typing import Any, Union, Optional

from jose import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

# 密码加密配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # 刷新令牌7天有效
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.JWTError:
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)

def create_resume_token(
    chapter_id: int,
    session_id: str,
    novel_id: int,
    user_id: int,
    sent_length: int = 0
) -> str:
    """
    创建章节生成恢复令牌（用于断线重连）

    Args:
        chapter_id: 章节ID
        session_id: 生成会话ID
        novel_id: 小说ID
        user_id: 用户ID
        sent_length: 已发送内容长度

    Returns:
        str: JWT格式的resume_token

    Note:
        - 有效期10分钟（与ChatGPT一致）
        - 包含session_id防止跨会话重放
        - 包含user_id防止跨用户访问
    """
    to_encode = {
        "chapter_id": chapter_id,
        "session_id": session_id,
        "novel_id": novel_id,
        "user_id": user_id,
        "sent_length": sent_length,
        "type": "resume",
        "iat": int(datetime.utcnow().timestamp())
    }
    expire = datetime.utcnow() + timedelta(minutes=10)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_resume_token(token: str) -> Optional[dict]:
    """
    验证章节生成恢复令牌

    Args:
        token: resume_token字符串

    Returns:
        Optional[dict]: 解析后的payload，验证失败返回None

    Payload结构:
        {
            "chapter_id": int,
            "session_id": str,
            "novel_id": int,
            "user_id": int,
            "sent_length": int,
            "type": "resume",
            "iat": int,
            "exp": int
        }
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # 验证token类型
        if payload.get("type") != "resume":
            return None

        # 验证必需字段
        required_fields = ["chapter_id", "session_id", "novel_id", "user_id", "sent_length"]
        if not all(field in payload for field in required_fields):
            return None

        return payload
    except jwt.ExpiredSignatureError:
        # Token过期
        return None
    except jwt.JWTError:
        # 签名无效或其他JWT错误
        return None


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """获取当前用户ID"""
    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id