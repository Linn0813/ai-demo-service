# encoding: utf-8
"""测试用例生成路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shared.logger import log
from models import (
    GenerateTestCasesRequest,
    GenerateTestCasesResponse,
    TaskSubmitResponse,
)

from domain.test_case.service import AIDemoTestCaseService
from domain.task.manager import get_task_manager

router = APIRouter(tags=["test-cases"])


def _build_service(payload: GenerateTestCasesRequest) -> AIDemoTestCaseService:
    """构建测试用例服务"""
    return AIDemoTestCaseService(
        base_url=str(payload.base_url) if payload.base_url else None,
        model=payload.model_name,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )


@router.post("/test-cases/generate", response_model=GenerateTestCasesResponse)
def generate_test_cases(payload: GenerateTestCasesRequest) -> GenerateTestCasesResponse:
    """
    生成测试用例（同步接口，保持向后兼容）。
    
    注意：此接口可能会超时，建议使用异步接口 /test-cases/generate-async
    """
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


@router.post("/test-cases/generate-async", response_model=TaskSubmitResponse)
def generate_test_cases_async(payload: GenerateTestCasesRequest) -> TaskSubmitResponse:
    """
    异步生成测试用例。
    
    提交任务后立即返回任务ID，客户端需要通过轮询 /tasks/{task_id} 接口获取结果。
    """
    try:
        task_manager = get_task_manager()
        service = _build_service(payload)
        
        # 创建任务函数
        def task_func():
            result = service.generate_test_cases(
                requirement_doc=payload.requirement_doc,
                limit=payload.limit,
                max_workers=payload.max_workers,
                model_name=payload.model_name,
                confirmed_function_points=payload.confirmed_function_points,
                trace_id=payload.task_id,
            )
            return result
        
        # 提交任务
        task_id = task_manager.submit_task(
            task_func,
            task_type="generate_test_cases"
        )
        
        return TaskSubmitResponse(
            task_id=task_id,
            status="pending",
            message="任务已提交，请通过 /tasks/{task_id} 接口查询状态"
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("提交生成测试用例任务失败")
        raise HTTPException(status_code=500, detail=f"提交任务失败: {exc}") from exc

