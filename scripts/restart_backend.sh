#!/bin/bash
# Restart Canonical Backend API Server

cd "$(dirname "$0")/.."

# 停止可能正在运行的后端服务
echo "Checking for running backend service..."
if lsof -ti :8000 > /dev/null 2>&1; then
    echo "Stopping existing backend service on port 8000..."
    kill $(lsof -ti :8000) 2>/dev/null
    sleep 2
fi

# 激活虚拟环境并启动后端
echo "Starting backend API server..."
source venv/bin/activate
uvicorn canonical.api:app --host 0.0.0.0 --port 8000 --reload
