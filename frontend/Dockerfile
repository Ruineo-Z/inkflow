# 简化版前端Dockerfile
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

# 生产阶段
FROM nginx:alpine

# 复制构建结果
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]