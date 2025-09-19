#!/bin/sh

# 运行时环境变量替换脚本
# 在容器启动时动态替换API地址

# 设置默认值
API_BASE_URL=${VITE_API_BASE_URL:-"http://localhost:8000/api/v1"}

echo "🔧 正在配置API地址: $API_BASE_URL"
echo "📁 当前工作目录: $(pwd)"
echo "📄 目录内容: $(ls -la)"

# 创建运行时配置文件
cat > /app/config.js << EOF
window.__APP_CONFIG__ = {
  API_BASE_URL: '$API_BASE_URL'
};
EOF

echo "✅ API配置完成: $(cat /app/config.js)"
echo "🚀 启动服务..."

# 启动serve
exec serve -s . -l tcp://0.0.0.0:3000