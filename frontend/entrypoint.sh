#!/bin/sh

# 运行时环境变量替换
API_URL=${API_BASE_URL:-"http://localhost:8000/api/v1"}

echo "🔧 配置API地址: $API_URL"

# 替换index.html中的API配置
sed -i "s|__API_BASE_URL__|$API_URL|g" /app/index.html

echo "✅ 配置完成，启动服务..."

# 启动serve
exec serve -s . -l tcp://0.0.0.0:3000