from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel, EmailStr

if TYPE_CHECKING:
    from app.schemas.novel import NovelResponse

# 用户基础模式
class UserBase(BaseModel):
    name: str
    email: EmailStr

# 创建用户请求模式
class UserCreate(UserBase):
    password: str

# 更新用户请求模式
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None

# 用户响应模式
class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 用户详情响应模式（包含小说列表）
class UserDetail(UserResponse):
    novels: List["NovelResponse"] = []