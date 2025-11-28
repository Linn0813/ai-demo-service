# encoding: utf-8
"""Pydantic 请求 / 响应模型。"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

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
    match_confidence: Optional[Literal["low", "medium", "high"]] = Field(None, description="匹配置信度：low/medium/high")


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
    match_confidence: Literal["low", "medium", "high"]


# ==================== 知识库相关Schema ====================

class SyncDocumentsRequest(BaseModel):
    space_id: Optional[str] = Field(None, description="知识库空间ID，如果不提供则同步所有空间")
    incremental: bool = Field(True, description="是否使用增量同步（默认True，只同步新增或更新的文档）")


class SyncDocumentsResponse(BaseModel):
    success: bool
    message: str = ""
    document_count: int = 0
    indexed_count: int = 0
    new_count: int = 0  # 新增文档数
    updated_count: int = 0  # 更新文档数
    skipped_count: int = 0  # 跳过文档数（未更新）
    deleted_count: int = 0  # 删除文档数
    total_spaces: Optional[int] = None
    success_count: Optional[int] = None
    failed_count: Optional[int] = None
    failed_spaces: Optional[List[Dict[str, Any]]] = None


class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    space_id: Optional[str] = Field(None, description="指定搜索的知识库空间ID，如果不提供则搜索所有空间")
    use_web_search: bool = Field(False, description="是否启用网络搜索（默认False）。当知识库结果不理想时，会使用网络搜索补充")


class SourceInfo(BaseModel):
    title: str
    url: str
    similarity: float = Field(..., ge=0, le=1, description="相似度分数")


class AskQuestionResponse(BaseModel):
    success: bool
    answer: str
    sources: List[SourceInfo] = Field(default_factory=list)
    has_web_search: Optional[bool] = Field(None, description="是否使用了网络搜索")
    suggest_web_search: Optional[bool] = Field(None, description="是否建议使用网络搜索（当知识库结果不理想时）")
    max_similarity: Optional[float] = Field(None, description="最高相似度（用于判断是否需要网络搜索）")


class CollectionInfoResponse(BaseModel):
    success: bool
    info: Dict[str, Any] = Field(default_factory=dict)


class WikiSpaceInfo(BaseModel):
    space_id: str
    name: str
    description: Optional[str] = None


class WikiSpacesResponse(BaseModel):
    success: bool
    spaces: List[WikiSpaceInfo] = Field(default_factory=list)
    message: Optional[str] = None


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


class WordUploadResponse(BaseModel):
    """Word 文档上传解析响应。"""
    text: str = Field(..., description="提取的文本内容")
    total_paragraphs: int = Field(..., description="段落总数")
    total_headings: int = Field(..., description="标题数量")
    structure: Optional[Dict[str, Any]] = Field(None, description="文档结构信息（包含标题列表）")
