# InkFlow

AI-powered writing assistant

## 数据库设置

### 使用Docker Compose启动PostgreSQL

1. **启动数据库**:
   ```bash
   # 启动PostgreSQL容器
   docker-compose up -d postgres

   # 或者使用脚本（Windows）
   ./scripts/start-db.bat
   ```

2. **验证数据库连接**:
   ```bash
   # 连接到数据库
   docker exec -it inkflow-postgres psql -U inkflow -d inkflow
   ```

3. **停止数据库**:
   ```bash
   # 停止容器
   docker-compose down

   # 或者使用脚本（Windows）
   ./scripts/stop-db.bat
   ```

### 数据库信息

- **主机**: localhost
- **端口**: 5432
- **数据库名**: inkflow
- **用户名**: inkflow
- **密码**: inkflow123
- **连接URL**: `postgresql+asyncpg://inkflow:inkflow123@localhost:5432/inkflow`

## 运行项目

1. **启动数据库**:
   ```bash
   docker-compose up -d postgres
   ```

2. **运行迁移**:
   ```bash
   uv run alembic upgrade head
   ```

3. **启动API服务**:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

4. **访问API文档**:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API端点

### 认证相关
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/refresh` - 刷新令牌
- `POST /api/v1/auth/logout` - 用户登出
- `GET /api/v1/auth/me` - 获取用户信息