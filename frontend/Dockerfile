# 前端Dockerfile - 使用简单的静态文件服务
FROM node:20-alpine AS builder

WORKDIR /app

# 设置npm镜像源（避免网络问题）
RUN npm config set registry https://registry.npmmirror.com

# 复制package文件
COPY package*.json ./

# 清理npm缓存并安装依赖
RUN npm cache clean --force && \
    npm install --legacy-peer-deps --no-audit --no-fund

# 复制源代码
COPY . .

# 构建
RUN npm run build

# 生产阶段 - 使用Node.js serve静态文件
FROM node:20-alpine

# 安装serve
RUN npm install -g serve

# 复制构建结果
COPY --from=builder /app/dist /app

# 复制启动脚本
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app

EXPOSE 3000

# 使用启动脚本支持运行时配置
CMD ["/app/entrypoint.sh"]