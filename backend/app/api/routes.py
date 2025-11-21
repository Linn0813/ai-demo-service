# encoding: utf-8
"""FastAPI 路由定义。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from core.logger import log
from app.config import settings
from app.schemas.common import (
    ExtractModulesRequest,
    ExtractModulesResponse,
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
    HealthResponse,
    ModelInfo,
    RematchModuleRequest,
    RematchModuleResponse,
)
from app.services import AIDemoTestCaseService

router = APIRouter(prefix="/api/v1", tags=["ai-demo"])


def _build_service(payload: GenerateTestCasesRequest | ExtractModulesRequest | RematchModuleRequest) -> AIDemoTestCaseService:
    return AIDemoTestCaseService(
        base_url=str(payload.base_url) if payload.base_url else None,
        model=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version, name=settings.app_name)


@router.get("/models", response_model=List[ModelInfo])
def list_models() -> List[ModelInfo]:
    service = AIDemoTestCaseService()
    models = service.get_available_models()
    return [ModelInfo(**model) for model in models]


@router.post("/function-modules/extract", response_model=ExtractModulesResponse)
def extract_function_modules(payload: ExtractModulesRequest) -> ExtractModulesResponse:
    try:
        service = _build_service(payload)
        modules = service.extract_function_modules_with_content(payload.requirement_doc, trace_id=payload.task_id)
        return ExtractModulesResponse(function_points=modules, requirement_doc=payload.requirement_doc)
    except Exception as exc:  # noqa: BLE001
        log.exception("提取功能模块失败")
        raise HTTPException(status_code=500, detail=f"提取功能模块失败: {exc}") from exc


@router.post("/test-cases/generate", response_model=GenerateTestCasesResponse)
def generate_test_cases(payload: GenerateTestCasesRequest) -> GenerateTestCasesResponse:
    try:
        service = _build_service(payload)
        result = service.generate_test_cases(
            requirement_doc=payload.requirement_doc,
            limit=payload.limit,
            max_workers=payload.max_workers,
            model_name=payload.model_name,
            confirmed_function_points=payload.confirmed_function_points,
            trace_id=payload.task_id,
        )
        return GenerateTestCasesResponse(**result)
    except Exception as exc:  # noqa: BLE001
        log.exception("生成测试用例失败")
        raise HTTPException(status_code=500, detail=f"生成测试用例失败: {exc}") from exc


@router.post("/modules/rematch", response_model=RematchModuleResponse)
def rematch_module_content(payload: RematchModuleRequest) -> RematchModuleResponse:
    try:
        service = _build_service(payload)
        result = service.rematch_module_content(
            requirement_doc=payload.requirement_doc,
            module_data=payload.module_data,
            all_modules=payload.all_modules,
        )
        return RematchModuleResponse(**result)
    except Exception as exc:  # noqa: BLE001
        log.exception("模块重匹配失败")
        raise HTTPException(status_code=500, detail=f"模块重匹配失败: {exc}") from exc
