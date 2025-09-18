# InkFlow 部署指南

## 🚀 快速部署

### 1. 准备数据库
确保你有一个PostgreSQL数据库实例，并获取连接信息。

### 2. 配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

### 3. 必须配置的环境变量
```bash
# 数据库连接URI
DATABASE_URL=postgresql+asyncpg://username:password@your-postgres-host:5432/inkflow

# JWT密钥（必须修改为随机字符串）
SECRET_KEY=your-super-secret-jwt-key-please-change-this-in-production

# Kimi AI密钥（必须填写真实的API密钥）
KIMI_API_KEY=your-kimi-api-key-here
```

### 4. 启动服务
```bash
# 拉取最新镜像并启动服务
docker-compose pull
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### 5. 验证部署
- 前端访问：http://your-server-ip:3030
- 后端API：http://your-server-ip:8000
- 健康检查：http://your-server-ip/health

## 🔧 环境变量说明

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| POSTGRES_PASSWORD | ✅ | - | 数据库密码 |
| SECRET_KEY | ✅ | - | JWT加密密钥 |
| KIMI_API_KEY | ✅ | - | Kimi AI API密钥 |
| POSTGRES_DB | ❌ | inkflow | 数据库名 |
| POSTGRES_USER | ❌ | inkflow | 数据库用户名 |
| DEBUG | ❌ | false | 调试模式 |
| ALLOWED_ORIGINS | ❌ | * | 跨域设置 |

## 🛠️ 常用命令

```bash
# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新镜像
docker-compose pull && docker-compose up -d

# 查看日志
docker-compose logs backend
docker-compose logs frontend

# 数据库备份
docker-compose exec postgres pg_dump -U inkflow inkflow > backup.sql
```

## 🔒 安全建议

1. 修改默认密码和密钥
2. 设置防火墙规则
3. 使用HTTPS（配置nginx反向代理）
4. 定期备份数据库
5. 定期更新镜像