# encoding: utf-8
"""功能模块提取和重匹配路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shared.logger import log
from models import (
    ExtractModulesRequest,
    ExtractModulesResponse,
    RematchModuleRequest,
    RematchModuleResponse,
    TaskSubmitResponse,
)

from domain.test_case.service import AIDemoTestCaseService
from domain.task.manager import get_task_manager

router = APIRouter(tags=["modules"])


def _build_service(payload: ExtractModulesRequest | RematchModuleRequest) -> AIDemoTestCaseService:
    """构建服务实例"""
    return AIDemoTestCaseService(
        base_url=str(payload.base_url) if payload.base_url else None,
        model=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )


@router.post("/function-modules/extract", response_model=ExtractModulesResponse)
def extract_function_modules(payload: ExtractModulesRequest) -> ExtractModulesResponse:
    """
    提取功能模块（同步接口，保持向后兼容）。
    
    注意：此接口可能会超时，建议使用异步接口 /function-modules/extract-async
    """
    try:
        service = _build_service(payload)
        modules = service.extract_function_modules_with_content(
            payload.requirement_doc,
            trace_id=payload.task_id
        )
        return ExtractModulesResponse(
            function_points=modules,
            requirement_doc=payload.requirement_doc
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("提取功能模块失败")
        raise HTTPException(status_code=500, detail=f"提取功能模块失败: {exc}") from exc


@router.post("/function-modules/extract-async", response_model=TaskSubmitResponse)
def extract_function_modules_async(payload: ExtractModulesRequest) -> TaskSubmitResponse:
    """
    异步提取功能模块。
    
    提交任务后立即返回任务ID，客户端需要通过轮询 /tasks/{task_id} 接口获取结果。
    """
    try:
        task_manager = get_task_manager()
        service = _build_service(payload)
        
        # 创建任务函数
        def task_func():
            modules = service.extract_function_modules_with_content(
                payload.requirement_doc,
                trace_id=payload.task_id
            )
            return {
                "function_points": modules,
                "requirement_doc": payload.requirement_doc
            }
        
        # 提交任务
        task_id = task_manager.submit_task(
            task_func,
            task_type="extract_function_modules"
        )
        
        return TaskSubmitResponse(
            task_id=task_id,
            status="pending",
            message="任务已提交，请通过 /tasks/{task_id} 接口查询状态"
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("提交提取功能模块任务失败")
        raise HTTPException(status_code=500, detail=f"提交任务失败: {exc}") from exc


@router.post("/modules/rematch", response_model=RematchModuleResponse)
def rematch_module_content(payload: RematchModuleRequest) -> RematchModuleResponse:
    """模块内容重匹配"""
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

