# encoding: utf-8
"""
AI Demo 测试用例服务层
---------------------

复用 `ai_demo_core.engine` 封装 HTTP 层所需的方法。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from infrastructure.llm.service import LLMService
from shared.config import MODEL_PRESETS
from domain.test_case.test_case_generator import TestCaseGenerator
from domain.test_case.document_understanding import DocumentUnderstandingService
from domain.test_case.validators import assess_test_case_quality, infer_priority
from models.schemas import DocumentUnderstanding
from shared.logger import log

from shared.config import settings


class AIDemoTestCaseService:
    """面向 API 层的轻量包装。"""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        # 从配置中读取 Azure 相关参数
        from shared.config import LLM_CONFIG
        azure_deployment = LLM_CONFIG.get("azure_deployment", "")
        azure_api_version = LLM_CONFIG.get("azure_api_version", "2024-12-01-preview")
        
        self.llm_service = LLMService(
            base_url=base_url or settings.llm_base_url,
            model=model or settings.llm_default_model,
            temperature=temperature,
            max_tokens=max_tokens or settings.llm_max_tokens,
            api_key=api_key or settings.llm_api_key,
            provider=provider or settings.llm_provider,
            azure_deployment=azure_deployment,
            azure_api_version=azure_api_version,
        )
        self.generator = TestCaseGenerator(self.llm_service)
        self.understanding_service = DocumentUnderstandingService(self.llm_service)
        log.debug(
            "AIDemoTestCaseService 初始化完成 base_url=%s model=%s",
            self.llm_service.base_url,
            self.llm_service.model,
        )

    def extract_function_modules_with_content(
        self,
        requirement_doc: str,
        trace_id: Optional[str] = None,
        enable_understanding: bool = True,
    ) -> tuple[List[Dict[str, Any]], Optional[DocumentUnderstanding]]:
        """
        提取功能模块并匹配原文内容
        
        Returns:
            (modules, understanding): 模块列表和理解结果
        """
        log.info("开始提取功能模块并匹配原文 (trace_id=%s, enable_understanding=%s)", trace_id, enable_understanding)
        
        understanding = None
        if enable_understanding:
            try:
                # 创建进度回调（如果提供了）
                progress_callback = None
                if hasattr(self, '_current_progress_callback'):
                    progress_callback = self._current_progress_callback
                
                understanding = self.understanding_service.understand_document(
                    requirement_doc,
                    run_id=trace_id,
                    progress_callback=progress_callback
                )
                log.info("文档理解完成 quality_score=%.2f", understanding.quality_score)
            except Exception as e:
                log.warning("文档理解失败，降级到无理解模式: %s", e)
                understanding = None
        
        modules = self.generator.extract_function_modules_with_content(
            requirement_doc,
            run_id=trace_id,
            understanding=understanding
        )
        log.info("提取完成 count=%s", len(modules))
        return modules, understanding

    def generate_test_cases(
        self,
        *,
        requirement_doc: str,
        limit: Optional[int] = None,
        max_workers: int = 4,
        model_name: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        confirmed_function_points: Optional[List[Dict[str, Any]]] = None,
        trace_id: Optional[str] = None,
        enable_understanding: bool = True,
        document_understanding: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成测试用例"""
        if model_name:
            if model_name in MODEL_PRESETS:
                preset = MODEL_PRESETS[model_name]
                actual_model = preset.get("model", model_name)
                self.llm_service.model = actual_model
                log.info("使用模型预设 %s -> %s", model_name, actual_model)
            else:
                self.llm_service.model = model_name
                log.info("使用自定义模型 %s", model_name)

        # 处理理解结果
        understanding = None
        if enable_understanding:
            if document_understanding:
                # 使用前端提供的理解结果
                try:
                    understanding = DocumentUnderstanding(**document_understanding)
                    log.info("使用前端提供的理解结果 quality_score=%.2f", understanding.quality_score)
                except Exception as e:
                    log.warning("解析前端提供的理解结果失败: %s", e)
                    understanding = None
            else:
                # 调用理解服务
                try:
                    understanding = self.understanding_service.understand_document(
                        requirement_doc,
                        run_id=trace_id,
                        progress_callback=progress_callback
                    )
                    log.info("文档理解完成 quality_score=%.2f", understanding.quality_score)
                except Exception as e:
                    log.warning("文档理解失败，降级到无理解模式: %s", e)
                    understanding = None

        log.info(
            "开始生成测试用例 limit=%s max_workers=%s trace_id=%s",
            limit,
            max_workers,
            trace_id,
        )
        result = self.generator.generate_test_cases(
            requirement_doc=requirement_doc,
            limit=limit,
            max_workers=max_workers,
            progress_callback=progress_callback,
            confirmed_function_points=confirmed_function_points,
            trace_id=trace_id,
            understanding=understanding,
        )
        
        # 对生成的测试用例进行质量评估和优先级推断
        all_test_cases = result.get("test_cases", [])
        total_quality_score = 0
        issues_count = 0
        
        for case in all_test_cases:
            # 质量评估
            quality_score, quality_issues = assess_test_case_quality(case, requirement_doc)
            case["quality_score"] = quality_score
            case["quality_issues"] = quality_issues
            
            # 优先级推断（如果用例没有优先级字段或为空）
            if not case.get("priority"):
                case["priority"] = infer_priority(case)
            
            total_quality_score += quality_score
            if quality_issues:
                issues_count += 1
        
        # 计算平均质量评分
        avg_quality_score = (total_quality_score / len(all_test_cases)) if all_test_cases else 0
        
        # 更新meta信息
        if "meta" not in result:
            result["meta"] = {}
        result["meta"]["average_quality_score"] = avg_quality_score
        result["meta"]["test_cases_with_issues"] = issues_count
        
        # 将理解结果添加到返回结果中
        if understanding:
            result["document_understanding"] = understanding.to_dict()
        
        log.info(
            "测试用例生成完成 cases=%s, 平均质量评分=%.2f, 有问题的用例=%s",
            len(all_test_cases),
            avg_quality_score,
            issues_count,
        )
        return result

    def get_available_models(self) -> List[Dict[str, Any]]:
        models: List[Dict[str, Any]] = []
        for key, preset in MODEL_PRESETS.items():
            model_id = preset.get("model") or key
            models.append(
                {
                    "key": key,
                    "name": preset.get("name", key),
                    "model_id": model_id,
                    "model": model_id,
                    "description": preset.get("description", ""),
                    "recommended": preset.get("recommended", False),
                }
            )
        return models

    def rematch_module_content(
        self,
        *,
        requirement_doc: str,
        module_data: Dict[str, Any],
        all_modules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        log.info("重新匹配模块原文 name=%s", module_data.get("name"))
        return self.generator.extractor.rematch_module_content(
            requirement_doc=requirement_doc,
            module_data=module_data,
            all_modules=all_modules,
        )
