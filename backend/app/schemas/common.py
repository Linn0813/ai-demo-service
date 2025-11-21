# encoding: utf-8
"""Pydantic 请求 / 响应模型。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class BaseLLMOptions(BaseModel):
    model_name: Optional[str] = Field(None, description="自定义模型名称")
    base_url: Optional[HttpUrl | str] = Field(None, description="自定义 LLM 服务地址")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="采样温度")
    max_tokens: Optional[int] = Field(None, gt=0, description="生成最大 token 数")


class RequirementDocPayload(BaseLLMOptions):
    requirement_doc: str = Field(..., min_length=10, description="需求文档全文")
    task_id: Optional[str] = Field(None, description="用于跟踪的任务/调试 ID")


class GenerateTestCasesRequest(RequirementDocPayload):
    limit: Optional[int] = Field(None, ge=1, le=50, description="限制功能点数量")
    max_workers: int = Field(4, ge=1, le=8, description="并发线程数")
    confirmed_function_points: Optional[List[Dict[str, Any]]] = None


class ExtractModulesRequest(RequirementDocPayload):
    pass


class FunctionModule(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    matched_content: Optional[str] = None
    matched_positions: Optional[List[int]] = None
    match_confidence: Optional[float] = None


class GenerateTestCasesResponse(BaseModel):
    test_cases: List[Dict[str, Any]]
    by_function_point: Dict[str, Any]
    meta: Dict[str, Any]


class ExtractModulesResponse(BaseModel):
    function_points: List[FunctionModule]
    requirement_doc: str


class RematchModuleRequest(RequirementDocPayload):
    module_data: Dict[str, Any] = Field(..., description="包含模块名称、关键词等信息")
    all_modules: Optional[List[Dict[str, Any]]] = Field(None, description="所有模块列表（用于边界检测）")


class RematchModuleResponse(BaseModel):
    matched_content: str
    matched_positions: List[int]
    match_confidence: float


class ModelInfo(BaseModel):
    key: str
    name: str
    model_id: str
    model: str
    description: Optional[str] = None
    recommended: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    name: str
