"""
数据库Base定义模块
将Base定义与引擎创建分离，避免在Alembic迁移时触发异步引擎初始化
"""
from sqlalchemy.orm import declarative_base

# 创建SQLAlchemy Base类
Base = declarative_base()