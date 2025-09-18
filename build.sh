#!/bin/bash
set -e

# 读取版本号
BACKEND_VERSION=$(cat VERSION)
FRONTEND_VERSION=$(cat frontend/VERSION)
DOCKER_USERNAME=${DOCKER_USERNAME:-ruinow}

echo "构建并推送 InkFlow Docker 镜像..."
echo "后端版本: $BACKEND_VERSION"
echo "前端版本: $FRONTEND_VERSION"

# 构建并推送后端镜像
echo "构建后端镜像..."
docker buildx build --platform linux/amd64 \
    -t $DOCKER_USERNAME/inkflow-backend:$BACKEND_VERSION \
    -t $DOCKER_USERNAME/inkflow-backend:latest \
    . --push

# 构建并推送前端镜像
echo "构建前端镜像..."
docker buildx build --platform linux/amd64 \
    -t $DOCKER_USERNAME/inkflow-frontend:$FRONTEND_VERSION \
    -t $DOCKER_USERNAME/inkflow-frontend:latest \
    -f frontend/Dockerfile frontend/ --push

echo "✅ 构建完成!"