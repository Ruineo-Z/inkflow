#!/bin/sh

# 运行时环境变量替换
API_URL=${API_BASE_URL:-"http://localhost:8000/api/v1"}

echo "🔧 配置API地址: $API_URL"

# 检查index.html文件是否存在
if [ ! -f "/app/index.html" ]; then
    echo "❌ 错误: /app/index.html 文件不存在"
    exit 1
fi

# 显示替换前的内容用于调试
echo "🔍 替换前的内容:"
grep "__API_BASE_URL__" /app/index.html || echo "未找到 __API_BASE_URL__ 占位符"

# 替换index.html中的API配置
sed -i "s|__API_BASE_URL__|$API_URL|g" /app/index.html

# 显示替换后的内容用于调试
echo "🔍 替换后的内容:"
grep -n "window\.__API_BASE_URL__" /app/index.html || echo "替换后未找到API配置"

echo "✅ 配置完成，启动服务..."

# 启动serve，使用配置文件
exec serve -s . -l tcp://0.0.0.0:3000