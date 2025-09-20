# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

InkFlow 是一个AI驱动的互动小说创作助手，支持多章节智能生成、用户选择分支和协作创作。采用前后端分离架构：
- **后端**: FastAPI + PostgreSQL + Alembic + Kimi大模型 (moonshot-v1-8k)
- **前端**: React 19 + Vite + Antd Mobile + React Router

## 核心架构

### 后端架构 (FastAPI)
```
app/
├── api/v1/           # API路由层
│   ├── auth.py       # 用户认证API
│   ├── novels.py     # 小说管理API
│   ├── chapters.py   # 章节生成API (支持流式输出)
│   ├── themes.py     # 主题管理API
│   ├── admin.py      # 管理后台API
│   └── health.py     # 健康检查API
├── core/             # 核心配置
│   ├── config.py     # 应用配置(基于pydantic-settings)
│   └── security.py   # JWT认证与安全
├── db/              # 数据库层
│   ├── database.py   # AsyncPG数据库连接
│   ├── migration.py  # 自动迁移逻辑
│   └── init_db.py    # 数据库初始化
├── models/          # SQLAlchemy 2.0 模型
│   ├── user.py       # 用户模型
│   ├── novel.py      # 小说模型(包含背景和角色设定)
│   ├── chapter.py    # 章节模型
│   └── option.py     # 用户选择分支模型
├── schemas/         # Pydantic 数据结构
│   ├── auth.py       # 认证相关Schema
│   ├── novel.py      # 小说相关Schema
│   ├── chapter.py    # 章节相关Schema
│   └── kimi.py       # Kimi API Schema
├── services/        # 业务逻辑层
│   ├── auth.py       # 认证服务
│   ├── user.py       # 用户服务
│   ├── novel.py      # 小说服务
│   ├── chapter.py    # 章节服务
│   ├── novel_generator.py    # AI小说大纲生成
│   └── chapter_generator.py  # AI章节内容生成(支持流式)
├── utils/           # 工具模块
│   └── kimi_schema.py # Kimi API Schema定义
└── main.py          # FastAPI应用入口
```

### 前端架构 (React)
```
frontend/src/
├── pages/           # 页面组件
│   ├── Login/       # 登录注册页面
│   ├── NovelList/   # 小说列表页面
│   ├── CreateNovel/ # 创建小说页面
│   └── Reading/     # 阅读互动页面
├── contexts/        # React Context状态管理
│   └── AuthContext.jsx  # 用户认证状态
├── services/        # API服务层
│   └── api.js       # 统一API调用封装
├── styles/          # CSS样式文件
└── router.jsx       # React Router配置
```

## 开发命令

### 容器化部署
```bash
# 启动完整服务 (生产环境)
docker-compose up -d

# 启动后端服务
docker-compose up -d inkflow_backend

# 启动前端服务
docker-compose up -d inkflow_frontend

# 查看服务日志
docker-compose logs -f inkflow_backend
docker-compose logs -f inkflow_frontend

# 停止所有服务
docker-compose down
```

### 本地开发环境

#### 后端开发
```bash
# 安装开发依赖
uv sync --dev

# 启动API服务 (自动重载，默认端口8000)
uv run uvicorn app.main:app --reload --host 0.0.0.0

# 数据库迁移
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "描述"

# 代码质量检查
uv run black app/           # 代码格式化
uv run isort app/           # import排序
uv run mypy app/            # 类型检查
uv run flake8 app/          # 代码风格检查

# 测试
uv run pytest              # 运行所有测试
uv run pytest tests/unit/  # 单元测试
uv run pytest tests/integration/ # 集成测试
uv run pytest --cov=app    # 测试覆盖率
```

#### 前端开发
```bash
cd frontend

# 安装依赖
npm install

# 开发服务器 (默认端口5173)
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint

# 预览构建结果
npm run preview
```

## 核心功能模块

### AI集成架构
- **Kimi API封装**: `app/utils/kimi_schema.py` - Kimi API Schema定义和验证
- **小说生成器**: `app/services/novel_generator.py` - AI创作小说大纲和设定
- **章节生成器**: `app/services/chapter_generator.py` - AI续写章节内容，支持流式输出
- **结构化响应**: 使用Pydantic Schema确保AI输出格式一致性，定义在 `app/schemas/kimi.py`

### 互动选择机制
- **选择分支**: 每章节结尾提供多个用户选择选项
- **状态追踪**: 记录用户选择历史，影响后续剧情发展
- **个性化体验**: 基于用户选择偏好调整故事走向

### 认证与授权
- **JWT认证**: 基于 `app/core/security.py` 实现token认证
- **用户管理**: `app/services/auth.py` 处理注册登录逻辑
- **权限控制**: API路由支持Bearer token验证和用户权限检查

### 数据库设计 (SQLAlchemy 2.0)
- **用户模型**: `app/models/user.py` - 用户基本信息和认证
- **小说模型**: `app/models/novel.py` - 小说元信息、背景设定、角色设定
- **章节模型**: `app/models/chapter.py` - 章节内容和生成配置
- **选项模型**: `app/models/option.py` - 用户选择分支和后续影响

### 流式处理架构
- **流式章节生成**: `/api/v1/chapters.py` 中的 `generate_chapter_stream` 端点
- **实时内容推送**: 支持大模型内容的流式输出到前端
- **错误恢复**: 流式处理中的错误处理和重试机制

## 环境配置

### 环境变量设置
参考 `.env.example` 创建本地 `.env` 文件，重要配置项：

```bash
# 数据库配置
DATABASE_URL=postgresql+asyncpg://username:password@host:5432/inkflow

# JWT认证配置
SECRET_KEY=your-super-secret-jwt-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Kimi AI配置
KIMI_API_KEY=your-kimi-api-key
KIMI_MODEL=moonshot-v1-8k
KIMI_MAX_TOKENS=2000
KIMI_TEMPERATURE=0.7

# 前端API地址配置 (Docker模式使用服务名)
API_BASE_URL=http://inkflow_backend:8000/api/v1
```

### 容器化配置
- **生产环境**: 使用 `docker-compose.yml` 启动完整服务栈
- **前端服务**: 端口3030 (容器内3000)
- **后端服务**: 端口8000
- **网络**: 使用external网络 `default-network`

## 开发工作流

### 新功能开发流程
1. **数据模型**: 先在 `app/models/` 中定义数据模型
2. **数据库迁移**: `uv run alembic revision --autogenerate -m "描述"`
3. **Schema定义**: 在 `app/schemas/` 中定义Pydantic模型
4. **服务层**: 在 `app/services/` 中实现业务逻辑
5. **API路由**: 在 `app/api/v1/` 中添加API端点
6. **前端集成**: 更新前端页面和API调用

### AI内容生成调试
- 查看Kimi API请求/响应: 启用DEBUG模式查看日志
- Schema验证错误: 检查 `app/schemas/kimi.py` 中的数据结构
- 流式输出测试: 使用API文档中的WebSocket测试工具

### 数据库迁移最佳实践
```bash
# 检查当前迁移状态
uv run alembic current

# 查看迁移历史
uv run alembic history

# 回滚到指定版本
uv run alembic downgrade <revision>

# 生成空白迁移文件(手动编写迁移逻辑)
uv run alembic revision -m "manual migration"
```

## API访问点
- **API文档**: http://localhost:8000/docs (Swagger UI)
- **ReDoc文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/api/v1/health
- **前端开发服务器**: http://localhost:5173

## 技术约束和限制

### AI生成限制
- Kimi API有速率限制，需要实现请求重试和错误处理
- 大模型响应可能不稳定，必须通过Schema验证
- 流式输出需要正确处理连接断开和重连

### 性能考虑
- 数据库查询使用AsyncPG异步连接池
- AI生成内容较大时使用流式传输
- 前端状态管理避免过度重渲染

### 安全要求
- 所有API端点都需要JWT认证(除了登录注册)
- 用户数据隔离，防止跨用户数据访问
- AI生成内容需要内容安全检查