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
grep "{{API_BASE_URL_PLACEHOLDER}}" /app/index.html || echo "未找到占位符"

# 替换index.html中的API配置
sed -i "s|{{API_BASE_URL_PLACEHOLDER}}|$API_URL|g" /app/index.html

# 显示替换后的内容用于调试
echo "🔍 替换后的内容:"
if grep -q "{{API_BASE_URL_PLACEHOLDER}}" /app/index.html; then
    echo "❌ 替换失败，仍存在占位符:"
    grep -n "{{API_BASE_URL_PLACEHOLDER}}" /app/index.html
else
    echo "✅ 替换成功，当前API配置:"
    grep -n "window\.__API_BASE_URL__" /app/index.html
fi

echo "✅ 配置完成，启动服务..."

# 启动serve，使用配置文件
exec serve -s . -l tcp://0.0.0.0:3000