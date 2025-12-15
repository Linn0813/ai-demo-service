# encoding: utf-8
"""API v1 路由"""

from fastapi import APIRouter

from .health import router as health_router
from .test_cases import router as test_cases_router
from .modules import router as modules_router
from .tasks import router as tasks_router
from .knowledge_base import router as knowledge_base_router
from .upload import router as upload_router

# 聚合所有 v1 路由
router = APIRouter(tags=["ai-demo"])

router.include_router(health_router)
router.include_router(test_cases_router)
router.include_router(modules_router)
router.include_router(tasks_router)
router.include_router(knowledge_base_router)
router.include_router(upload_router)

__all__ = ["router"]

