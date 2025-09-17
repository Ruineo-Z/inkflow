# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

InkFlow 是一个AI驱动的小说创作助手，支持多章节智能生成和用户协作。采用前后端分离架构：
- **后端**: FastAPI + PostgreSQL + Alembic + Kimi大模型
- **前端**: React + Vite + Antd Mobile

## 核心架构

### 后端架构 (FastAPI)
```
app/
├── api/v1/           # API路由层
│   ├── auth.py       # 认证相关API
│   ├── novels.py     # 小说管理API
│   ├── chapters.py   # 章节生成API
│   └── themes.py     # 主题管理API
├── core/             # 核心配置
│   ├── config.py     # 应用配置
│   └── security.py   # 安全认证
├── db/              # 数据库层
│   ├── database.py   # 数据库连接
│   └── migration.py  # 自动迁移逻辑
├── models/          # SQLAlchemy模型
│   ├── user.py       # 用户模型
│   ├── novel.py      # 小说模型
│   ├── chapter.py    # 章节模型
│   └── option.py     # 选项模型
├── schemas/         # Pydantic数据结构
├── services/        # 业务逻辑层
│   ├── auth.py       # 认证服务
│   ├── novel_generator.py    # AI小说生成
│   ├── chapter_generator.py  # AI章节生成
│   └── kimi.py       # Kimi大模型接口
└── main.py          # 应用入口
```

### 前端架构 (React)
```
frontend/src/
├── pages/           # 页面组件
│   ├── Login/       # 登录页面
│   ├── NovelList/   # 小说列表
│   ├── CreateNovel/ # 创建小说
│   └── Reading/     # 阅读页面
├── contexts/        # React Context
│   └── AuthContext.jsx  # 认证状态管理
├── services/        # API服务
│   └── api.js       # API调用封装
├── styles/          # CSS样式文件
└── router.jsx       # 路由配置
```

## 开发命令

### 数据库管理
```bash
# 启动PostgreSQL容器
docker-compose up -d postgres

# 停止数据库
docker-compose down

# 运行数据库迁移
uv run alembic upgrade head

# 创建新迁移
uv run alembic revision --autogenerate -m "描述"
```

### 后端开发
```bash
# 启动API服务 (自动重载)
uv run uvicorn app.main:app --reload

# 运行测试
uv run pytest

# 代码格式化
uv run black app/
uv run isort app/

# 类型检查
uv run mypy app/

# 代码检查
uv run flake8 app/
```

### 前端开发
```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

## 核心功能模块

### AI集成架构
- **Kimi模型服务**: `app/services/kimi.py` - 封装Kimi API调用
- **小说生成器**: `app/services/novel_generator.py` - AI创作小说大纲
- **章节生成器**: `app/services/chapter_generator.py` - AI续写章节内容
- **结构化响应**: 使用Pydantic Schema确保AI输出格式一致性

### 认证与授权
- JWT token认证，配置在 `app/core/security.py`
- 前端通过 `AuthContext` 管理登录状态
- API路由支持Bearer token验证

### 数据库设计
- **用户模型**: 支持用户注册、登录、个人信息
- **小说模型**: 小说元信息、背景设定、角色设定
- **章节模型**: 章节内容、生成选项、用户选择
- **选项模型**: AI生成的多个剧情分支选择

### 前端状态管理
- 使用React Context进行全局状态管理
- AuthContext管理用户认证状态
- API调用统一封装在 `services/api.js`

## 配置要点

### 环境变量配置
在项目根目录创建 `.env` 文件：
```
DATABASE_URL=postgresql+asyncpg://inkflow:inkflow123@localhost:5432/inkflow
SECRET_KEY=your-production-secret-key
KIMI_API_KEY=your-kimi-api-key
DEBUG=False
```

### 数据库连接
- 默认连接: `postgresql+asyncpg://inkflow:inkflow123@localhost:5432/inkflow`
- 使用docker-compose启动PostgreSQL
- 支持自动迁移，应用启动时检查并执行

### AI模型配置
- 默认使用Kimi `moonshot-v1-8k`模型
- 可通过环境变量调整 `KIMI_MODEL`、`KIMI_MAX_TOKENS`等参数

## API访问
- API文档: http://localhost:8000/docs (Swagger UI)
- ReDoc文档: http://localhost:8000/redoc
- 前端开发服务器: http://localhost:5173 (Vite默认端口)

## 开发注意事项

1. **数据库迁移**: 修改模型后必须生成并应用迁移
2. **AI响应解析**: AI生成内容需要通过Schema验证，确保JSON格式正确
3. **错误处理**: 前后端都要处理AI服务异常和网络错误
4. **认证流程**: API调用需要携带有效JWT token
5. **开发环境**: 确保PostgreSQL容器运行后再启动API服务