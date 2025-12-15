# encoding: utf-8
"""文档理解服务"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.llm.service import LLMService
from models.schemas import DocumentUnderstanding, DocumentStructure
from domain.test_case.prompts import build_document_understanding_prompt
from domain.test_case.text_normalizer import RequirementCache, MARKDOWN_HEADING_PATTERN
from shared.debug_recorder import record_ai_debug
from shared.logger import log


class DocumentUnderstandingService:
    """文档理解服务（MVP版本：单一服务）"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self._cache = RequirementCache()
        self._understanding_cache: Dict[str, DocumentUnderstanding] = {}  # 理解结果缓存

    def understand_document(
        self,
        requirement_doc: str,
        run_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> DocumentUnderstanding:
        """
        理解需求文档的整体结构和意图
        
        Args:
            requirement_doc: 需求文档
            run_id: 运行ID（用于调试追踪）
            progress_callback: 进度回调函数
        
        Returns:
            DocumentUnderstanding: 包含文档类型、业务意图、结构等信息
        """
        # 检查缓存
        doc_hash = self._compute_hash(requirement_doc)
        if doc_hash in self._understanding_cache:
            log.debug("使用缓存的理解结果 (hash=%s)", doc_hash[:8])
            return self._understanding_cache[doc_hash]

        # 进度回调：开始理解
        if progress_callback:
            progress_callback({
                "type": "thinking",
                "stage": "understanding_document",
                "step": "start",
                "content": "开始分析文档...",
                "thinking": [
                    "📄 正在读取文档内容",
                    f"文档长度: {len(requirement_doc)} 字符",
                    "开始进行文档理解分析"
                ],
                "progress": 0
            })

        try:
            # 1. 复用现有的结构分析
            self._cache.prepare(requirement_doc)
            flat_sections = self._cache._cached_sections

            if progress_callback:
                progress_callback({
                    "type": "thinking",
                    "stage": "understanding_document",
                    "step": "structure_analysis",
                    "content": "分析文档结构...",
                    "thinking": [
                        "🔍 检测文档章节结构",
                        f"发现 {len(flat_sections)} 个章节标题",
                        "正在提取章节层级关系"
                    ],
                    "progress": 10
                })

            # 2. 增强结构分析：提取层级并构建章节树
            structured_sections = self._build_structured_sections(
                requirement_doc,
                flat_sections
            )

            # 进度回调：结构分析完成
            if progress_callback:
                hierarchy_info = f"层级: {structured_sections['hierarchy_levels']}" if structured_sections['hierarchy_levels'] else "无层级结构"
                main_sections_info = f"主要章节: {', '.join(structured_sections['main_sections'][:3])}" if structured_sections['main_sections'] else "无主要章节"
                
                progress_callback({
                    "type": "thinking",
                    "stage": "understanding_document",
                    "step": "structure_complete",
                    "content": "文档结构分析完成",
                    "thinking": [
                        f"✅ 识别到 {structured_sections['section_count']} 个章节",
                        hierarchy_info,
                        main_sections_info,
                        "📊 结构分析完成，开始语义理解..."
                    ],
                    "result": {
                        "section_count": structured_sections['section_count'],
                        "hierarchy_levels": structured_sections['hierarchy_levels'],
                        "main_sections": structured_sections['main_sections'][:5]
                    },
                    "progress": 30
                })

            # 3. 调用LLM理解业务意图
            if progress_callback:
                progress_callback({
                    "type": "thinking",
                    "stage": "understanding_document",
                    "step": "semantic_understanding",
                    "content": "理解文档语义和业务意图...",
                    "thinking": [
                        "🤖 调用AI模型分析文档",
                        "正在识别文档类型...",
                        "正在提取核心主题和业务目标...",
                        "正在识别关键概念和术语..."
                    ],
                    "progress": 40
                })
            
            llm_understanding = self._understand_with_llm(requirement_doc, run_id)

            # 进度回调：LLM理解完成
            if progress_callback:
                doc_type = llm_understanding.get("document_type", "未知")
                main_topic = llm_understanding.get("main_topic", "")
                goals_count = len(llm_understanding.get("business_goals", []))
                concepts_count = len(llm_understanding.get("key_concepts", []))
                quality_score = llm_understanding.get("quality_score", 0)
                
                progress_callback({
                    "type": "thinking",
                    "stage": "understanding_document",
                    "step": "semantic_complete",
                    "content": "语义理解完成",
                    "thinking": [
                        f"✅ 文档类型: {doc_type}",
                        f"✅ 核心主题: {main_topic[:50]}{'...' if len(main_topic) > 50 else ''}",
                        f"✅ 识别到 {goals_count} 个业务目标",
                        f"✅ 识别到 {concepts_count} 个关键概念",
                        f"📊 质量评分: {quality_score:.2f}",
                        "🔄 正在整合理解结果..."
                    ],
                    "result": {
                        "document_type": doc_type,
                        "main_topic": main_topic,
                        "business_goals_count": goals_count,
                        "key_concepts_count": concepts_count,
                        "quality_score": quality_score
                    },
                    "progress": 80
                })

            # 4. 整合结果
            understanding = self._combine_understanding(
                structured_sections,
                llm_understanding,
                requirement_doc
            )

            # 缓存理解结果
            self._understanding_cache[doc_hash] = understanding

            # 记录调试信息
            record_ai_debug(
                "document_understanding",
                {
                    "model": self.llm_service.model,
                    "base_url": self.llm_service.base_url,
                    "requirement_doc_length": len(requirement_doc),
                    "understanding": understanding.to_dict(),
                },
                run_id=run_id
            )

            # 进度回调：理解完成
            if progress_callback:
                progress_callback({
                    "type": "thinking",
                    "stage": "understanding_document",
                    "step": "complete",
                    "content": "文档理解完成",
                    "thinking": [
                        "✅ 文档结构分析完成",
                        "✅ 语义理解完成",
                        "✅ 理解结果已整合",
                        f"📊 最终质量评分: {understanding.quality_score:.2f}",
                        "🎯 理解结果已准备好，可用于后续处理"
                    ],
                    "result": {
                        "document_type": understanding.document_type,
                        "main_topic": understanding.main_topic,
                        "business_goals": understanding.business_goals[:5],
                        "key_concepts": understanding.key_concepts[:5],
                        "quality_score": understanding.quality_score,
                        "estimated_complexity": understanding.estimated_complexity
                    },
                    "progress": 100
                })

            return understanding

        except Exception as e:
            log.warning("文档理解失败，返回默认理解结果: %s", e)
            # 降级处理：返回默认理解结果
            return self._create_default_understanding(requirement_doc)

    def _build_structured_sections(
        self,
        requirement_doc: str,
        flat_sections: List[Tuple[int, str]]
    ) -> Dict[str, Any]:
        """
        基于扁平章节列表构建结构化章节树
        
        Args:
            requirement_doc: 需求文档
            flat_sections: 扁平章节列表 [(行号, 标题文本), ...]
        
        Returns:
            结构化章节信息，包含：
            - sections_with_level: [(行号, 层级, 标题文本), ...]
            - section_tree: 章节树形结构
            - hierarchy_levels: [1, 2, 3] 表示有3级标题
        """
        doc_lines = requirement_doc.splitlines()
        sections_with_level: List[Tuple[int, int, str]] = []

        # 提取标题层级
        for line_idx, title_text in flat_sections:
            if line_idx >= len(doc_lines):
                continue

            raw_line = doc_lines[line_idx].strip()

            # 检测 Markdown 标题层级
            markdown_match = MARKDOWN_HEADING_PATTERN.match(raw_line)
            if markdown_match:
                # 计算层级（# 的数量）
                level = len(raw_line) - len(raw_line.lstrip('#'))
                sections_with_level.append((line_idx, level, title_text))
            else:
                # 普通标题，默认为层级1
                sections_with_level.append((line_idx, 1, title_text))

        # 构建章节树
        section_tree = self._build_section_tree(sections_with_level)

        # 提取层级列表
        hierarchy_levels = sorted(set(level for _, level, _ in sections_with_level))

        return {
            "sections_with_level": sections_with_level,
            "section_tree": section_tree,
            "hierarchy_levels": hierarchy_levels,
            "main_sections": [title for _, level, title in sections_with_level if level == 1],
            "section_count": len(sections_with_level)  # 添加章节数量
        }

    def _build_section_tree(
        self,
        sections_with_level: List[Tuple[int, int, str]]
    ) -> Dict[str, Any]:
        """
        构建章节树形结构
        
        Args:
            sections_with_level: [(行号, 层级, 标题文本), ...]
        
        Returns:
            章节树形结构，格式：
            {
                "title": "文档",
                "level": 0,
                "line": 0,
                "children": [
                    {
                        "title": "章节1",
                        "level": 1,
                        "line": 5,
                        "children": [...]
                    },
                    ...
                ]
            }
        """
        if not sections_with_level:
            return {"title": "文档", "level": 0, "line": 0, "children": []}

        # 构建树形结构
        root = {"title": "文档", "level": 0, "line": 0, "children": []}
        stack = [root]  # 使用栈来维护当前路径

        for line_idx, level, title in sections_with_level:
            node = {
                "title": title,
                "level": level,
                "line": line_idx,
                "children": []
            }

            # 找到合适的父节点（层级小于当前节点的最后一个节点）
            while len(stack) > 1 and stack[-1]["level"] >= level:
                stack.pop()

            # 添加到父节点的children
            stack[-1]["children"].append(node)
            stack.append(node)

        return root

    def _understand_with_llm(
        self,
        requirement_doc: str,
        run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用LLM理解文档的业务意图和关键信息
        
        Returns:
            LLM理解结果，包含：
            - document_type: 文档类型
            - main_topic: 核心主题
            - business_goals: 业务目标
            - key_concepts: 关键概念
            - key_terms: 关键术语
            - business_rules: 业务规则
            - completeness: 完整性
            - clarity: 清晰度
            - quality_score: 质量评分
        """
        prompt = build_document_understanding_prompt(requirement_doc)
        response_text = self.llm_service.generate(prompt)

        # 解析JSON响应
        try:
            # 尝试提取JSON部分
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                understanding_dict = json.loads(json_str)
            else:
                understanding_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            log.warning("解析理解结果JSON失败: %s", e)
            log.debug("响应内容: %s", response_text[:500])
            # 返回默认值
            return self._get_default_llm_understanding()

        return understanding_dict

    def _combine_understanding(
        self,
        structured_sections: Dict[str, Any],
        llm_understanding: Dict[str, Any],
        requirement_doc: str
    ) -> DocumentUnderstanding:
        """
        整合结构分析和LLM理解结果
        
        Returns:
            完整的文档理解结果
        """
        doc_lines = requirement_doc.splitlines()

        structure = DocumentStructure(
            has_sections=len(structured_sections["sections_with_level"]) > 0,
            section_count=len(structured_sections["sections_with_level"]),
            hierarchy_levels=structured_sections["hierarchy_levels"],
            main_sections=structured_sections["main_sections"],
            section_tree=structured_sections["section_tree"]
        )

        return DocumentUnderstanding(
            document_type=llm_understanding.get("document_type", "未知"),
            main_topic=llm_understanding.get("main_topic", ""),
            business_goals=llm_understanding.get("business_goals", []),
            structure=structure,
            key_concepts=llm_understanding.get("key_concepts", []),
            key_terms=llm_understanding.get("key_terms", []),
            business_rules=llm_understanding.get("business_rules", []),
            completeness=llm_understanding.get("completeness", "未知"),
            clarity=llm_understanding.get("clarity", "未知"),
            quality_score=llm_understanding.get("quality_score", 0.5),
            total_sections=structure.section_count,
            total_lines=len(doc_lines),
            estimated_complexity=self._estimate_complexity(
                len(doc_lines),
                structure.section_count,
                len(structure.hierarchy_levels)
            ),
            prompt_version="v1.0.0",
            model_version=self.llm_service.model or "",
        )

    def _estimate_complexity(
        self,
        total_lines: int,
        section_count: int,
        hierarchy_levels: int
    ) -> str:
        """评估文档复杂度"""
        if total_lines < 100 and section_count < 5:
            return "简单"
        elif total_lines < 500 and section_count < 15:
            return "中等"
        else:
            return "复杂"

    def _create_default_understanding(self, requirement_doc: str) -> DocumentUnderstanding:
        """创建默认的理解结果（降级处理）"""
        doc_lines = requirement_doc.splitlines()
        self._cache.prepare(requirement_doc)
        flat_sections = self._cache._cached_sections

        structure = DocumentStructure(
            has_sections=len(flat_sections) > 0,
            section_count=len(flat_sections),
            hierarchy_levels=[],
            main_sections=[],
            section_tree={}
        )

        return DocumentUnderstanding(
            document_type="未知",
            main_topic="",
            business_goals=[],
            structure=structure,
            key_concepts=[],
            key_terms=[],
            business_rules=[],
            completeness="未知",
            clarity="未知",
            quality_score=0.0,  # 标记为低质量
            total_sections=structure.section_count,
            total_lines=len(doc_lines),
            estimated_complexity=self._estimate_complexity(
                len(doc_lines),
                structure.section_count,
                0
            ),
            prompt_version="v1.0.0",
            model_version=self.llm_service.model or "",
        )

    def _get_default_llm_understanding(self) -> Dict[str, Any]:
        """获取默认的LLM理解结果"""
        return {
            "document_type": "未知",
            "main_topic": "",
            "business_goals": [],
            "key_concepts": [],
            "key_terms": [],
            "business_rules": [],
            "completeness": "未知",
            "clarity": "未知",
            "quality_score": 0.5,
        }

    def _compute_hash(self, doc: str) -> str:
        """计算文档内容的hash"""
        return hashlib.md5(doc.encode('utf-8')).hexdigest()

    def extract_key_information(
        self,
        requirement_doc: str,
        understanding: DocumentUnderstanding
    ) -> Dict[str, Any]:
        """
        基于理解结果提取关键信息
        
        Returns:
            包含关键业务概念、术语、规则等
        """
        return {
            "key_concepts": understanding.key_concepts,
            "key_terms": understanding.key_terms,
            "business_rules": understanding.business_rules,
            "main_sections": understanding.structure.main_sections
        }

