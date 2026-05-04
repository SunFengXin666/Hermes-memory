#!/bin/bash
# IM+云盘 启动脚本 (Linux/Mac)
echo "📦 安装依赖..."
pip3 install -r "$(dirname "$0")/requirements.txt" -q 2>/dev/null
echo "🚀 启动 IM+云盘..."
echo "   打开浏览器访问 http://localhost:5000"
cd "$(dirname "$0")" && python3 app.py --port 5000
