#!/bin/bash
set -e

# 读取版本号
BACKEND_VERSION=$(cat VERSION)
FRONTEND_VERSION=$(cat frontend/VERSION)
DOCKER_USERNAME=${DOCKER_USERNAME:-ruinow}

echo "构建 InkFlow Docker 镜像..."
echo "后端版本: $BACKEND_VERSION"
echo "前端版本: $FRONTEND_VERSION"
echo "Docker用户名: $DOCKER_USERNAME"

# 检查Docker登录状态
echo "检查Docker登录状态..."
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker未运行或无法连接"
    exit 1
fi

# 检查网络连接
echo "测试网络连接..."
if ! curl -s --connect-timeout 10 https://index.docker.io/v1/ > /dev/null; then
    echo "警告: 网络连接可能有问题，构建可能会失败"
fi

# 创建并使用buildx构建器 (支持多平台)
echo "设置多平台构建器..."
docker buildx create --use --name multiarch-builder 2>/dev/null || docker buildx use multiarch-builder
docker buildx inspect --bootstrap

# 构建并推送后端镜像 (针对Linux/amd64平台)
echo "构建并推送后端镜像..."
docker buildx build --platform linux/amd64 --no-cache -t $DOCKER_USERNAME/inkflow-backend:$BACKEND_VERSION -t $DOCKER_USERNAME/inkflow-backend:latest . --push

# 构建并推送前端镜像 (针对Linux/amd64平台)
echo "构建并推送前端镜像..."
docker buildx build --platform linux/amd64 --no-cache -t $DOCKER_USERNAME/inkflow-frontend:$FRONTEND_VERSION -t $DOCKER_USERNAME/inkflow-frontend:latest -f frontend/Dockerfile frontend/ --push

echo "构建和推送完成!"
echo "后端镜像: $DOCKER_USERNAME/inkflow-backend:$BACKEND_VERSION"
echo "前端镜像: $DOCKER_USERNAME/inkflow-frontend:$FRONTEND_VERSION"