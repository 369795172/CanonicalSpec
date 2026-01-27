#!/bin/bash
# Restart Canonical Frontend Dev Server

cd "$(dirname "$0")"

# 停止可能正在运行的前端服务
echo "Checking for running frontend service..."
if lsof -ti :5173 > /dev/null 2>&1; then
    echo "Stopping existing frontend service on port 5173..."
    kill $(lsof -ti :5173) 2>/dev/null
    sleep 2
fi

# 启动前端开发服务器
echo "Starting frontend dev server..."
npm run dev
