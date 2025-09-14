from pydantic import BaseModel, EmailStr

# 用户注册请求
class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

# 用户登录请求
class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

# 令牌响应
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# 刷新令牌请求
class RefreshTokenRequest(BaseModel):
    refresh_token: str

# 用户信息响应
class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True