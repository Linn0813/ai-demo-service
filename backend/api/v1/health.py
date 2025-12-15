# encoding: utf-8
"""健康检查和模型列表路由"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from shared.config import settings
from shared.logger import log
from models import HealthResponse, ModelInfo

from domain.test_case.service import AIDemoTestCaseService

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """健康检查"""
    return HealthResponse(status="ok", version=settings.app_version, name=settings.app_name)


@router.get("/models", response_model=List[ModelInfo])
def list_models() -> List[ModelInfo]:
    """获取可用模型列表"""
    service = AIDemoTestCaseService()
    models = service.get_available_models()
    return [ModelInfo(**model) for model in models]

