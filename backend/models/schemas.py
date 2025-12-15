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
    enable_understanding: bool = Field(True, description="是否启用文档理解（默认启用）")
    document_understanding: Optional[Dict[str, Any]] = Field(None, description="理解结果（可选，如果前端已缓存）")


class ExtractModulesRequest(RequirementDocPayload):
    enable_understanding: bool = Field(True, description="是否启用文档理解（默认启用）")


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
    document_understanding: Optional[Dict[str, Any]] = Field(None, description="文档理解结果（可选）")


class ExtractModulesResponse(BaseModel):
    function_points: List[FunctionModule]
    requirement_doc: str
    document_understanding: Optional[Dict[str, Any]] = Field(None, description="文档理解结果（可选）")


class TaskSubmitResponse(BaseModel):
    """任务提交响应。"""
    task_id: str
    status: str = "pending"
    message: str = "任务已提交"


class TaskStatusResponse(BaseModel):
    """任务状态响应。"""
    task_id: str
    status: str  # pending, running, completed, failed
    task_type: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    partial_result: Optional[Dict[str, Any]] = Field(None, description="部分结果（用于实时展示）")


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


# ==================== 文档理解相关Schema ====================

class DocumentStructure(BaseModel):
    """文档结构信息"""
    has_sections: bool
    section_count: int
    hierarchy_levels: List[int] = Field(default_factory=list, description="层级列表，如 [1, 2, 3] 表示有3级标题")
    main_sections: List[str] = Field(default_factory=list, description="主要章节列表（层级为1的章节）")
    section_tree: Dict[str, Any] = Field(default_factory=dict, description="章节树结构（树形表示）")


class DocumentUnderstanding(BaseModel):
    """文档理解结果"""
    document_type: str = Field(..., description="文档类型（PRD、需求文档、设计文档、用户故事等）")
    main_topic: str = Field(..., description="核心主题")
    business_goals: List[str] = Field(default_factory=list, description="业务目标列表")
    structure: DocumentStructure = Field(..., description="文档结构信息")
    key_concepts: List[str] = Field(default_factory=list, description="关键业务概念列表")
    key_terms: List[str] = Field(default_factory=list, description="关键术语列表")
    business_rules: List[str] = Field(default_factory=list, description="业务规则列表")
    completeness: str = Field("未知", description="完整性（完整/不完整）")
    clarity: str = Field("未知", description="清晰度（清晰/模糊）")
    quality_score: float = Field(0.5, ge=0, le=1, description="质量评分（0-1）")
    total_sections: int = Field(0, description="章节总数")
    total_lines: int = Field(0, description="文档总行数")
    estimated_complexity: str = Field("中等", description="复杂度评估（简单/中等/复杂）")
    prompt_version: str = Field("v1.0.0", description="Prompt版本")
    model_version: str = Field("", description="模型版本")
    generated_at: Optional[str] = Field(None, description="生成时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return self.model_dump()
