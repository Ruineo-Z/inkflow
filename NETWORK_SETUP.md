# Docker网络配置说明

## 🌐 网络架构

为了让不同的Docker Compose服务能够相互通信，我们使用了一个共享的外部网络 `inkflow-network`。

## 🚀 部署步骤

### 1. 创建共享网络
```bash
# 创建外部网络（只需执行一次）
docker network create inkflow-network
```

### 2. 启动PostgreSQL数据库
```bash
# 启动PostgreSQL开发服务
docker-compose -f docker-compose.dev.yml up -d

# 查看服务状态
docker-compose -f docker-compose.dev.yml ps
```

### 3. 配置数据库
```bash
# 连接到PostgreSQL
docker exec -it postgres-dev psql -U admin -d postgres

# 创建inkflow用户和数据库
CREATE USER inkflow WITH PASSWORD 'your-password';
CREATE DATABASE inkflow OWNER inkflow;
GRANT ALL PRIVILEGES ON DATABASE inkflow TO inkflow;
\q
```

### 4. 配置应用环境变量
```bash
# 编辑.env文件，设置数据库连接
# DATABASE_URL=postgresql+asyncpg://inkflow:your-password@postgres-dev:5432/inkflow
vim .env
```

### 5. 启动应用服务
```bash
# 启动前后端服务
docker-compose up -d

# 查看所有服务状态
docker ps
```

## 🔍 验证连接

### 检查网络连接
```bash
# 查看网络中的容器
docker network inspect inkflow-network

# 测试网络连通性
docker exec -it inkflow-backend-container ping postgres-dev
```

### 访问服务
- 前端：http://localhost:3030
- 后端：http://localhost:8000
- PostgreSQL：localhost:5432

## 🛠️ 管理命令

```bash
# 停止所有服务
docker-compose down
docker-compose -f docker-compose.dev.yml down

# 重启服务
docker-compose restart
docker-compose -f docker-compose.dev.yml restart

# 查看日志
docker-compose logs -f inkflow_backend
docker-compose -f docker-compose.dev.yml logs -f postgres

# 清理（谨慎使用）
docker-compose down -v
docker network rm inkflow-network
```

## 📝 注意事项

1. **外部网络**：`inkflow-network` 是外部网络，需要手动创建
2. **容器名称**：在.env中使用容器名 `postgres-dev` 而不是 `localhost`
3. **端口映射**：PostgreSQL既可以通过容器名访问，也可以通过localhost:5432访问
4. **数据持久化**：PostgreSQL数据存储在Docker卷中，删除容器不会丢失数据