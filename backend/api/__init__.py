# encoding: utf-8
"""API 路由模块"""

from fastapi import APIRouter

from .v1 import router as v1_router

# 聚合所有路由
router = APIRouter()
router.include_router(v1_router, prefix="/api/v1")

__all__ = ["router"]

