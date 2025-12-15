# encoding: utf-8
"""FastAPI 应用入口。"""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router
from shared.config import settings
from models import HealthResponse
from domain.task.manager import get_task_manager
from shared.logger import log


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="独立可部署的 AI 测试用例生成演示服务。",
    )

    # CORS 配置：支持前后端分离部署
    # 开发环境：默认允许所有来源（可通过 AI_DEMO_CORS_ORIGINS 覆盖）
    # 生产环境：应通过环境变量设置具体的前端域名，例如：http://localhost:3000,https://yourdomain.com
    cors_origins_env = os.getenv("AI_DEMO_CORS_ORIGINS", "")
    if cors_origins_env:
        # 如果设置了环境变量，使用指定的来源列表
        cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    else:
        # 默认允许所有来源（开发环境）
        cors_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/healthz", response_model=HealthResponse, tags=["health"])
    def root_health() -> HealthResponse:  # pragma: no cover - 简单路由
        return HealthResponse(status="ok", version=settings.app_version, name=settings.app_name)

    app.include_router(router)
    
    # 初始化任务管理器
    @app.on_event("startup")
    def startup_event():
        """应用启动时初始化任务管理器。"""
        task_manager = get_task_manager()
        log.info("任务管理器已初始化")
    
    @app.on_event("shutdown")
    def shutdown_event():
        """应用关闭时清理任务管理器。"""
        task_manager = get_task_manager()
        task_manager.shutdown()
        log.info("任务管理器已关闭")
    
    return app


app = create_app()


if __name__ == "__main__":
    # 像 Flask 那样直接运行：python -m ai_demo_service.main
    # 或：python src/ai_demo_service/main.py
    host = os.getenv("AI_DEMO_BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("AI_DEMO_BACKEND_PORT", "8113"))
    reload = os.getenv("AI_DEMO_BACKEND_RELOAD", "true").lower() == "true"
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )
