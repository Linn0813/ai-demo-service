#!/bin/bash

# AI Demo Service 启动脚本
# 同时启动后端（FastAPI）和前端（Vite）

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI Demo Service 启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}错误: 未找到 python3${NC}"
    exit 1
fi

# 检查Node.js环境
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}错误: 未找到 node${NC}"
    exit 1
fi

# 检查是否在虚拟环境中
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}提示: 建议在虚拟环境中运行${NC}"
    echo -e "${YELLOW}可以运行: python3 -m venv .venv && source .venv/bin/activate${NC}"
fi

# 启动后端服务
echo -e "${GREEN}启动后端服务 (FastAPI)...${NC}"
cd "$(dirname "$0")"
uvicorn ai_demo_service.main:app --reload --port 8113 &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 启动前端服务
echo -e "${GREEN}启动前端服务 (Vite)...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}服务已启动！${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "后端服务: ${GREEN}http://localhost:8113${NC}"
echo -e "前端服务: ${GREEN}http://localhost:3000${NC}"
echo -e "API文档: ${GREEN}http://localhost:8113/docs${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "按 Ctrl+C 停止所有服务"
echo -e "${BLUE}========================================${NC}"

# 等待用户中断
trap "echo -e '\n${YELLOW}正在停止服务...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait

