"""需求文档提取相关工具"""
from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

from core.engine.base.config import ExtractionConfig
from .content_extractor import ContentExtractor
from core.engine.base.debug_recorder import record_ai_debug
from .json_parser import get_project_root, parse_json_with_fallback
from core.engine.base.llm_service import LLMService
from .module_hierarchy import ModuleHierarchyDetector
from .module_matcher import EXPECTED_MODULE_CANONICALS, EXPECTED_MODULE_SEQUENCE, ModuleMatcher
from .prompts import build_module_extraction_prompt
from .text_normalizer import MARKDOWN_HEADING_PATTERN, MARKDOWN_HEADING_PATTERN_1_2, RequirementCache
from core.logger import log

# 向后兼容：导出 _parse_json_with_fallback
_parse_json_with_fallback = parse_json_with_fallback


# 向后兼容：保留 RequirementCache 类（已迁移到 text_normalizer.py，但保留别名）
# 注意：RequirementCache 的实际实现在 text_normalizer.py 中
# 这里不再重复定义，直接使用导入的类


class FunctionModuleExtractor:
    """功能模块提取器"""

    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service
        self._cache = RequirementCache()
        # 初始化各个功能模块
        self._matcher = ModuleMatcher(normalize_func=self._cache.normalize_text)
        self._content_extractor = ContentExtractor(
            normalize_func=self._cache.normalize_text,
            is_module_title_line_func=self._is_module_title_line,
            cache=self._cache,
            module_matcher=self._matcher,
        )
        self._hierarchy_detector = ModuleHierarchyDetector()

    # 对外提供缓存工具方法，方便复用
    def normalize_text(self, text: str) -> str:
        return self._cache.normalize_text(text)

    def fix_traditional_punctuation(self, text: str) -> str:
        return self._cache.fix_traditional_punctuation(text)

    def extract_relevant_section(self, requirement_doc: str, target: str, fp_data: Optional[Dict] = None) -> str:
        return self._cache.extract_relevant_section(requirement_doc, target, fp_data)

    # === 模块检测辅助方法 ===
    def _normalize_identifier(self, text: str) -> str:
        """标准化标识符（委托给缓存）"""
        return self._cache.normalize_text(text)

    def _get_module_tokens(self, module_name: str) -> Tuple[str, str, List[str], List[str]]:
        """获取模块的规范化标识符和令牌（委托给 ModuleMatcher）"""
        return self._matcher.get_module_tokens(module_name)

    def _get_module_title_level(self, doc_lines: List[str], anchor_index: int) -> int:
        """检查模块在文档中的标题级别（委托给 ModuleHierarchyDetector）"""
        return self._hierarchy_detector.get_module_title_level(doc_lines, anchor_index)

    def _is_module_title_line(self, normalized_line: str, module_tokens: List[str]) -> bool:
        """
        检测一行是否是模块标题行

        Args:
            normalized_line: 规范化后的行内容
            module_tokens: 模块标识符列表

        Returns:
            如果是模块标题行返回True，否则返回False
        """
        if not normalized_line:
            return False

        # 检查是否是Markdown格式的标题（如 ## 标题）
        # 注意：normalized_line 已经是规范化后的，但我们需要检查原始格式
        # 这里我们需要传入原始行内容，但为了保持接口一致性，我们检查规范化后的内容
        # 如果 normalized_line 包含 # 开头，说明可能是 Markdown 标题
        # 但由于 normalized_line 已经规范化（去除了特殊字符），我们需要用其他方式判断
        # 实际上，在调用这个方法之前，应该已经处理了 Markdown 格式

        for token in module_tokens:
            if not token:
                continue
            # 完全匹配（最精确）
            if normalized_line == token:
                return True
            # 作为行首出现（例如 "模块NPS提交弹窗" 匹配 "模块nps提交弹窗"）
            if normalized_line.startswith(token):
                # 检查剩余部分是否很短（<=配置的阈值），确保是模块标题而不是内容中的提及
                remaining = normalized_line[len(token):]
                if len(remaining) <= ExtractionConfig.MODULE_TITLE_REMAINING_LENGTH:
                    return True
        return False

    def _find_module_boundary(
        self,
        doc_lines: List[str],
        anchor_index: int,
        initial_end_idx: int,
        other_module_tokens: List[str],
        sections: Optional[List[Tuple[int, str]]] = None,
    ) -> Tuple[int, bool]:
        """查找模块边界（委托给 ContentExtractor）"""
        return self._content_extractor.find_module_boundary(
            doc_lines, anchor_index, initial_end_idx, other_module_tokens, sections
        )

    def _trim_content_at_module_boundary(
        self,
        snippet_lines: List[str],
        other_tokens: List[str],
        min_content_length: int,
    ) -> List[str]:
        """在内容中裁剪到模块边界（委托给 ContentExtractor）"""
        return self._content_extractor.trim_content_at_module_boundary(
            snippet_lines, other_tokens, min_content_length
        )

    def extract_function_modules(self, requirement_doc: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """调用LLM提取功能模块。"""

        self._cache.prepare(requirement_doc)
        extract_prompt = build_module_extraction_prompt(requirement_doc)

        try:
            response = self.llm_service.generate(extract_prompt)
            log.debug("原始响应长度: %s 字符", len(response))

            # 保存原始响应以便调试（在解析之前保存）
            try:
                project_root = get_project_root()
                debug_dir = project_root / "data" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                raw_response_file = debug_dir / "llm_raw_response.txt"
                with open(raw_response_file, "w", encoding="utf-8") as f:
                    f.write("=== 完整 LLM 响应 ===\n")
                    f.write(response)
                    f.write(f"\n\n=== 响应元信息 ===\n")
                    f.write(f"响应长度: {len(response)} 字符\n")
                    f.write(f"包含 '{{': {response.count('{')} 个\n")
                    f.write(f"包含 '}}': {response.count('}')} 个\n")
            except Exception:  # noqa: BLE001
                pass  # 忽略保存失败

            # 改进的 JSON 边界检测：查找最外层完整的 JSON 对象
            start_idx = response.find("{")
            if start_idx == -1:
                log.error("LLM 响应中未找到 JSON 起始标记 '{'")
                log.debug("响应前200字符: %s", response[:200])
                raise ValueError("无法找到 JSON 起始标记 '{'")

            # 通过括号匹配找到最外层的结束位置
            brace_count = 0
            end_idx = -1
            for i in range(start_idx, len(response)):
                if response[i] == '{':
                    brace_count += 1
                elif response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

            if end_idx == -1 or end_idx <= start_idx:
                log.warning("无法找到完整的 JSON 对象，尝试使用最后一个 '}' 作为边界")
                end_idx = response.rfind("}") + 1
                if end_idx <= start_idx:
                    raise ValueError("无法提取JSON内容：找不到有效的 JSON 边界")

            json_str = response[start_idx:end_idx]
            log.debug("提取的JSON长度: %s 字符", len(json_str))

            # 追加提取的 JSON 片段到调试文件
            try:
                project_root = get_project_root()
                debug_dir = project_root / "data" / "debug"
                debug_file = debug_dir / "llm_raw_response.txt"
                with open(debug_file, "a", encoding="utf-8") as f:
                    f.write("\n\n=== 提取的 JSON 片段 ===\n")
                    f.write(json_str)
            except Exception:  # noqa: BLE001
                pass  # 忽略保存失败

            # 使用增强的 JSON 解析函数
            result = _parse_json_with_fallback(json_str)

            function_modules_data = result.get("function_modules", [])
            if not function_modules_data:
                log.warning("LLM 返回的 JSON 中未找到 'function_modules' 字段")
                log.debug("返回的 JSON 结构: %s", list(result.keys()))

            # 验证模块名称是否在需求文档中存在
            validated_modules = []
            # 明显来自prompt而非需求文档的词汇
            prompt_keywords = ["功能模块定义", "提取要求", "输出格式", "重要要求", "关键词提取"]

            for module in function_modules_data:
                module_name = module.get("name", "").strip()
                if not module_name:
                    continue

                # 如果模块名称明显来自prompt，直接过滤
                if any(pk in module_name for pk in prompt_keywords):
                    log.warning(
                        "过滤掉来自prompt的模块: '%s' (不是需求文档中的内容)",
                        module_name
                    )
                    continue

                # 检查模块名称或其关键词是否在文档中出现
                # 使用部分匹配：如果模块名称中的关键词在文档中，也认为有效
                name_in_doc = module_name in requirement_doc
                # 提取模块名称中的关键词（去除"模块"等通用词）
                # 使用更智能的分割，保留有意义的词组
                # 通用词列表，这些词不应该单独作为验证依据
                generic_words = {"模块", "功能", "系统", "定义", "要求", "格式", "管理器", "管理"}
                name_parts = re.split(r'[模块功能系统定义要求格式管理]', module_name)
                name_keywords = [
                    kw.strip() for kw in name_parts
                    if kw and len(kw.strip()) >= 2 and kw.strip() not in generic_words
                ]
                # 如果模块名称包含多个词，要求至少有一个完整的、非通用的词组在文档中
                # 避免单个字母（如"OS"）或通用词误匹配
                name_keywords_in_doc = any(
                    kw in requirement_doc and len(kw) >= 3 and kw not in generic_words
                    for kw in name_keywords
                ) if name_keywords else False
                keywords_in_doc = any(
                    kw in requirement_doc and len(kw) >= 3
                    for kw in module.get("keywords", [])
                    if kw and len(kw) >= 2
                )
                exact_phrases_in_doc = any(
                    phrase in requirement_doc
                    for phrase in module.get("exact_phrases", [])
                    if phrase and len(phrase) >= 3
                )

                # 验证逻辑：至少满足以下条件之一
                # 1. 模块名称完全匹配
                # 2. 模块名称中的非通用关键词在文档中（且长度>=3）
                # 3. 模块的keywords在文档中（且长度>=3）
                # 4. 模块的exact_phrases在文档中
                # 如果只有通用词匹配，不算有效
                is_valid = (
                    name_in_doc or
                    (name_keywords_in_doc and name_keywords) or  # 确保有非通用关键词
                    keywords_in_doc or
                    exact_phrases_in_doc
                )

                if is_valid:
                    validated_modules.append(module)
                else:
                    log.warning(
                        "过滤掉臆造的模块: '%s' (在需求文档中未找到相关提及)",
                        module_name
                    )

            if len(validated_modules) < len(function_modules_data):
                log.info(
                    "验证后保留 %s/%s 个模块（过滤掉 %s 个臆造模块）",
                    len(validated_modules),
                    len(function_modules_data),
                    len(function_modules_data) - len(validated_modules)
                )

            # 基于规则的后处理：过滤掉明显是子功能的模块
            filtered_modules = self._filter_sub_function_modules(validated_modules, requirement_doc)

            processed_modules = self._post_process_modules(filtered_modules, requirement_doc)
            log.info("提取到 %s 个功能模块（规范化后）", len(processed_modules))
            return processed_modules
        except Exception as exc:  # noqa: BLE001
            log.error("提取功能模块失败: %s", exc)
            log.debug("异常类型: %s", type(exc).__name__)
            fallback = self._heuristic_extract_modules(requirement_doc)
            if fallback:
                log.info("使用启发式提取功能模块，得到 %s 个模块", len(fallback))
                return self._post_process_modules(fallback, requirement_doc)
            raise

    def _filter_sub_function_modules(self, modules: List[Dict[str, Any]], requirement_doc: str) -> List[Dict[str, Any]]:
        """
        基于规则过滤掉明显是子功能的模块

        规则：
        1. 状态类模块（如"存在有效数据"、"无有效数据"）应该归属于"判断条件"或"状态"模块
        2. 数据类模块（如"存在数据"、"无工作日数据"）应该归属于相关模块
        3. 如果模块名称是其他模块的子集，且位置接近，应该合并
        """
        if not modules:
            return []

        # 定义明显是子功能的模式
        sub_function_patterns = [
            r"^(存在|无|有|没有).*数据$",  # "存在有效数据"、"无有效数据"等
            r"^(存在|无|有|没有).*$",  # "存在数据"、"无工作日数据"等（但排除主模块）
        ]

        # 定义主模块关键词（这些模块不应该被过滤）
        main_module_keywords = ["判断条件", "状态", "详情", "设置", "弹窗", "卡片", "信息", "社交时差"]

        filtered = []
        for module in modules:
            module_name = module.get("name", "").strip()
            if not module_name:
                continue

            # 检查是否包含主模块关键词（如果是"判断条件"、"状态"等，不应该过滤）
            if any(keyword in module_name for keyword in main_module_keywords):
                filtered.append(module)
                continue

            # 检查是否是明显子功能
            is_sub_function = False
            for pattern in sub_function_patterns:
                if re.match(pattern, module_name):
                    is_sub_function = True
                    log.info(
                        "过滤掉子功能模块: '%s' (匹配模式: %s)",
                        module_name, pattern
                    )
                    break

            if not is_sub_function:
                filtered.append(module)

        if len(filtered) < len(modules):
            log.info(
                "基于规则过滤: 保留 %s/%s 个模块（过滤掉 %s 个子功能模块）",
                len(filtered), len(modules), len(modules) - len(filtered)
            )

        return filtered

    def extract_function_modules_with_content(self, requirement_doc: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """提取功能模块并匹配原文内容。"""

        self._cache.prepare(requirement_doc)
        modules = self.extract_function_modules(requirement_doc, run_id=run_id)
        if not modules:
            log.warning("未能提取功能模块")
            return []

        # 先收集所有模块的锚点位置，用于边界检测
        doc_lines = self._cache._cached_doc_lines or requirement_doc.splitlines()
        module_positions = {}  # {module_name: anchor_index}
        for module in modules:
            module_name = module.get("name", "")
            if not module_name:
                continue
            anchor_index = self._find_first_occurrence_line(
                module_name,
                module,
                doc_lines,
            )
            module_positions[module_name] = anchor_index

        # 按位置排序，确保处理顺序正确
        sorted_modules = sorted(modules, key=lambda m: module_positions.get(m.get("name", ""), 999999))

        # 识别主模块和子模块的关系
        # 规则：
        # 1. 主模块通常是文档中的二级标题（##），如"## 社交时差"
        # 2. 子模块通常是三级标题（###），且位置在主模块之后，如"### 详情信息半弹窗"
        # 3. 更精确的子模块关键词匹配：必须是独立的子功能单元，而不是主模块名称的一部分
        main_modules = []  # 主模块列表
        module_hierarchy = {}  # {module_name: parent_module_name}

        # 更精确的子模块关键词：必须是独立的子功能单元
        # 注意：避免误判，如"睡眠类型详情区域"中的"详情"不应该触发子模块判断
        sub_module_keywords = ["半弹窗", "弹窗", "设置", "规则定义", "算法规则", "文案解释"]

        # 检查模块在文档中的标题级别（## vs ###）
        def get_module_title_level(module_name: str, anchor_index: int) -> int:
            """检查模块在文档中的标题级别：2表示##，3表示###"""
            if anchor_index >= len(doc_lines):
                return 0
            line = doc_lines[anchor_index].strip()
            if line.startswith("## "):
                return 2
            elif line.startswith("### "):
                return 3
            return 0

        for i, module in enumerate(sorted_modules):
            module_name = module.get("name", "")
            if not module_name:
                continue

            anchor_index = module_positions[module_name]
            title_level = self._get_module_title_level(doc_lines, anchor_index)

            # 如果模块是二级标题（##），一定是主模块
            if title_level == 2:
                main_modules.append(module_name)
                continue

            # 检查是否是子模块（更精确的匹配）
            # 必须是：1) 包含子模块关键词 2) 且是三级标题（###）
            is_sub_module = False
            if title_level == 3:
                # 检查是否包含子模块关键词（精确匹配，避免误判）
                for keyword in sub_module_keywords:
                    if keyword in module_name:
                        is_sub_module = True
                        break
                # 如果模块名称很短（<=配置的阈值）且包含关键词，更可能是子模块
                if not is_sub_module and len(module_name) <= ExtractionConfig.SHORT_MODULE_NAME_LENGTH:
                    short_keywords = ["弹窗", "设置", "规则", "定义", "解释"]
                    if any(kw in module_name for kw in short_keywords):
                        is_sub_module = True

            # 查找可能的主模块（位置在当前模块之前，且是二级标题）
            parent_module = None
            if is_sub_module:
                for j in range(i - 1, -1, -1):
                    prev_module = sorted_modules[j]
                    prev_name = prev_module.get("name", "")
                    if not prev_name:
                        continue
                    prev_anchor = module_positions[prev_name]
                    prev_title_level = self._get_module_title_level(doc_lines, prev_anchor)

                    # 如果前一个模块是二级标题（##），且位置接近（相差不超过配置的最大距离）
                    if prev_title_level == 2 and anchor_index - prev_anchor <= ExtractionConfig.SUB_MODULE_MAX_DISTANCE:
                        parent_module = prev_name
                        break

            if parent_module:
                module_hierarchy[module_name] = parent_module
            else:
                # 没有父模块，是主模块
                main_modules.append(module_name)

        result = []
        for idx, module in enumerate(sorted_modules, start=1):
            module_name = module.get("name", "")
            if not module_name:
                continue
            anchor_index = module_positions[module_name]
            matched_content = self.extract_relevant_section(requirement_doc, module_name, module)
            refined_content, matched_positions = self._content_extractor.refine_matched_content(
                requirement_doc,
                module_name,
                module,
                anchor_index,
                matched_content,
                all_modules=sorted_modules,  # 传递所有模块信息
            )

            match_confidence = "low"
            if module.get("exact_phrases"):
                match_confidence = "high"
            elif module.get("keywords"):
                match_confidence = "medium"

            # 判断是否是主模块
            is_main = module_name in main_modules
            parent_module = module_hierarchy.get(module_name)

            result.append({
                "id": f"module_{idx}",
                "name": module_name,
                "description": module.get("description", ""),
                "keywords": module.get("keywords", []),
                "exact_phrases": module.get("exact_phrases", []),
                "section_hint": module.get("section_hint", ""),
                "matched_content": refined_content,
                "matched_positions": matched_positions,
                "match_confidence": match_confidence,
                "is_main_module": is_main,
                "parent_module": parent_module,
            })

        log.info("提取到 %s 个功能模块并完成原文匹配", len(result))

        try:
            record_ai_debug(
                "extract_modules_with_content",
                {
                    "model": getattr(self.llm_service, "model", None),
                    "base_url": getattr(self.llm_service, "base_url", None),
                    "requirement_doc": requirement_doc,
                    "requirement_doc_length": len(requirement_doc or ""),
                    "module_count": len(modules),
                    "modules": modules,
                    "modules_with_content": result,
                },
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("记录功能模块提取调试信息失败: %s", exc)
        return result

    def rematch_module_content(
        self,
        requirement_doc: str,
        module_data: Dict[str, Any],
        all_modules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        重新匹配单个模块的原文内容

        Args:
            requirement_doc: 需求文档内容
            module_data: 模块数据（包含 name, keywords, exact_phrases 等）
            all_modules: 所有模块列表（用于边界检测，可选）

        Returns:
            包含 matched_content 和 matched_positions 的字典
        """
        try:
            module_name = module_data.get("name", "").strip()
            if not module_name:
                raise ValueError("模块名称不能为空")

            # 准备缓存
            self._cache.prepare(requirement_doc)
            doc_lines = self._cache._cached_doc_lines

            # 查找模块在文档中的位置
            anchor_index = self._find_first_occurrence_line(
                module_name,
                module_data,
                doc_lines,
            )

            # 获取初始匹配内容
            matched_content = self.extract_relevant_section(requirement_doc, module_name, module_data)

            # 如果没有提供所有模块信息，尝试从当前模块数据构建
            if all_modules is None:
                all_modules = [module_data]

            # 精确匹配内容
            refined_content, matched_positions = self._content_extractor.refine_matched_content(
                requirement_doc,
                module_name,
                module_data,
                anchor_index,
                matched_content,
                all_modules=all_modules,
            )

            # 计算匹配置信度
            match_confidence = "low"
            if module_data.get("exact_phrases"):
                match_confidence = "high"
            elif module_data.get("keywords"):
                match_confidence = "medium"

            log.info(
                "模块 '%s' 重新匹配完成: 位置=%s, 置信度=%s",
                module_name,
                matched_positions,
                match_confidence,
            )

            return {
                "matched_content": refined_content,
                "matched_positions": matched_positions,
                "match_confidence": match_confidence,
            }
        except Exception as e:
            log.error(f"重新匹配模块 '{module_data.get('name', '')}' 的原文失败: {str(e)}")
            raise

    # 向后兼容旧接口
    def extract_function_points_with_content(self, requirement_doc: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        log.warning("extract_function_points_with_content 已废弃，使用功能模块概念")
        return self.extract_function_modules_with_content(requirement_doc, run_id=run_id)

    def _post_process_modules(self, modules: List[Dict[str, Any]], requirement_doc: str) -> List[Dict[str, Any]]:
        if not modules:
            return []

        doc_lines = self._cache._cached_doc_lines or requirement_doc.splitlines()
        normalized_doc = self._normalize_identifier(requirement_doc)
        grouped: Dict[str, Dict[str, Any]] = {}
        # 用于记录每个模块的原始名称，用于去重检查
        name_to_positions: Dict[str, List[int]] = {}

        for module in modules:
            raw_name = module.get("name", "").strip()
            if not raw_name:
                continue

            canonical_name = self._map_to_canonical(raw_name)
            key = canonical_name or self._normalize_identifier(raw_name)

            # 计算模块位置，用于去重检查
            module_position = self._find_first_occurrence_line(
                canonical_name or raw_name,
                module,
                doc_lines,
            )

            # 检查是否有相同位置的模块（可能是重复的）
            if raw_name not in name_to_positions:
                name_to_positions[raw_name] = []
            name_to_positions[raw_name].append(module_position)

            entry = grouped.get(key)
            if not entry:
                entry = {
                    "name": canonical_name or raw_name,
                    "description": module.get("description", "").strip(),
                    "keywords": [],
                    "section_hint": module.get("section_hint", "").strip() or (canonical_name or raw_name),
                    "exact_phrases": [],
                    "__position": module_position,
                }
                grouped[key] = entry
            else:
                # 如果已经有相同key的模块，检查是否是重复的
                # 如果位置相同或非常接近（相差不超过配置的容差），可能是重复的
                if abs(entry["__position"] - module_position) <= ExtractionConfig.MODULE_POSITION_TOLERANCE:
                    # 可能是重复模块，保留描述更详细的
                    new_desc = module.get("description", "").strip()
                    if new_desc and len(new_desc) > len(entry.get("description", "")):
                        entry["description"] = new_desc
                    # 更新位置为更早的位置
                    entry["__position"] = min(entry["__position"], module_position)
                    log.debug(
                        "模块去重: %s 和 %s 位置接近 (%s vs %s)，合并为一个模块",
                        entry["name"], raw_name, entry["__position"], module_position
                    )
                else:
                    # 位置不同，可能是不同的模块，但key相同
                    # 这种情况需要特殊处理：使用位置作为额外的区分
                    position_key = f"{key}_{module_position}"
                    if position_key not in grouped:
                        entry = {
                            "name": canonical_name or raw_name,
                            "description": module.get("description", "").strip(),
                            "keywords": [],
                            "section_hint": module.get("section_hint", "").strip() or (canonical_name or raw_name),
                            "exact_phrases": [],
                            "__position": module_position,
                        }
                        grouped[position_key] = entry
                    else:
                        # 如果位置key也存在，合并
                        entry = grouped[position_key]
                        new_desc = module.get("description", "").strip()
                        if new_desc and len(new_desc) > len(entry.get("description", "")):
                            entry["description"] = new_desc
                        entry["__position"] = min(entry["__position"], module_position)

                # 更新canonical名称和section_hint
                if canonical_name:
                    entry["name"] = canonical_name
                if not entry.get("section_hint"):
                    entry["section_hint"] = module.get("section_hint", "").strip() or (canonical_name or raw_name)

            for keyword in module.get("keywords", []) or []:
                clean_keyword = keyword.strip()
                if not ModuleMatcher.is_strong_keyword(clean_keyword):
                    continue
                if self._normalize_identifier(clean_keyword) in normalized_doc:
                    if clean_keyword not in entry["keywords"]:
                        entry["keywords"].append(clean_keyword)

            for phrase in module.get("exact_phrases", []) or []:
                clean_phrase = phrase.strip()
                if clean_phrase and clean_phrase in requirement_doc and clean_phrase not in entry["exact_phrases"]:
                    entry["exact_phrases"].append(clean_phrase)

        # 注意：不再强制添加 EXPECTED_MODULE_CANONICALS 中定义的模块
        # 只依赖 LLM 提取的模块，保持通用性

        processed: List[Dict[str, Any]] = []
        for entry in grouped.values():
            if not entry.get("description"):
                entry["description"] = entry["name"]

            if entry.get("name") in EXPECTED_MODULE_CANONICALS:
                entry["section_hint"] = entry["name"]

            if not entry.get("exact_phrases"):
                anchors = [entry["name"]] + EXPECTED_MODULE_CANONICALS.get(entry["name"], [])
                phrase = self._collect_phrase_from_doc(anchors, doc_lines)
                if phrase:
                    entry["exact_phrases"] = [phrase]

            # 限制关键词数量并保持唯一
            unique_keywords: List[str] = []
            for keyword in entry.get("keywords", []):
                clean_keyword = keyword.strip()
                if not ModuleMatcher.is_strong_keyword(clean_keyword):
                    continue
                if clean_keyword not in unique_keywords and len(unique_keywords) < 4:
                    unique_keywords.append(clean_keyword)
            if not unique_keywords:
                fallback_keywords = EXPECTED_MODULE_CANONICALS.get(entry["name"], [])
                if fallback_keywords:
                    fallback_keyword = next(
                        (kw for kw in fallback_keywords if ModuleMatcher.is_strong_keyword(kw)),
                        fallback_keywords[0],
                    )
                    unique_keywords.append(fallback_keyword)
                else:
                    unique_keywords.append(entry["name"])
            entry["keywords"] = unique_keywords

            entry.pop("__position", None)
            processed.append(entry)

        processed.sort(key=lambda item: self._find_first_occurrence_line(item["name"], item, doc_lines))
        return processed


    def _map_to_canonical(self, name: str) -> Optional[str]:
        """将模块名称映射到规范名称（委托给 ModuleMatcher）"""
        return self._matcher.map_to_canonical(name)

    def _find_first_occurrence_line(
        self,
        module_name: str,
        module_data: Dict[str, Any],
        doc_lines: List[str],
    ) -> int:
        """查找模块在文档中的首次出现位置（委托给 ModuleMatcher）"""
        return self._matcher.find_first_occurrence_line(module_name, module_data, doc_lines)

    def _collect_phrase_from_doc(self, anchors: List[str], doc_lines: List[str]) -> str:
        """从文档中收集短语（委托给 ModuleMatcher）"""
        return self._matcher.collect_phrase_from_doc(anchors, doc_lines)

    def _ensure_expected_modules(
        self,
        grouped: Dict[str, Dict[str, Any]],
        requirement_doc: str,
        doc_lines: List[str],
    ) -> None:
        """
        已废弃：不再强制添加 EXPECTED_MODULE_CANONICALS 中定义的模块

        保留此方法是为了向后兼容，但不再执行任何操作。
        现在完全依赖 LLM 提取的模块，保持系统的通用性。
        """
        # 不再强制添加模块，保持通用性
        pass

    def _shrink_lines_to_limit(self, lines: List[str]) -> List[str]:
        """裁剪行列表到最大长度限制（委托给 ContentExtractor）"""
        return self._content_extractor.shrink_lines_to_limit(lines)

    def _refine_matched_content(
        self,
        requirement_doc: str,
        module_name: str,
        module_data: Dict[str, Any],
        anchor_index: int,
        fallback_section: str,
        all_modules: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[int]]:
        """精确提取模块对应的原文内容（委托给 ContentExtractor）"""
        return self._content_extractor.refine_matched_content(
            requirement_doc, module_name, module_data, anchor_index, fallback_section, all_modules
        )

    # === 启发式提取逻辑 ===
    def _heuristic_extract_modules(self, requirement_doc: str) -> List[Dict[str, Any]]:
        """在LLM失败时，基于标题和关键词的启发式提取。"""

        lines = requirement_doc.splitlines()
        candidates: List[Tuple[int, str]] = []
        seen: set[str] = set()

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # 使用更严格的过滤规则
            if self._looks_like_module_heading(stripped, idx, lines) and stripped not in seen:
                candidates.append((idx, stripped))
                seen.add(stripped)

        # 按位置排序，确保顺序
        candidates.sort(key=lambda x: x[0])

        modules: List[Dict[str, Any]] = []
        for idx, heading in candidates:
            # 收集该模块下的描述内容（直到下一个模块标题）
            description_lines: List[str] = []
            for offset in range(1, min(20, len(lines) - idx)):
                if idx + offset >= len(lines):
                    break
                desc_line = lines[idx + offset].strip()
                if not desc_line:
                    continue
                # 如果遇到下一个模块标题，停止收集
                if self._looks_like_module_heading(desc_line, idx + offset, lines):
                    break
                # 跳过编号行和图片标记
                if desc_line.startswith(('[图片]', '图片')):
                    continue
                if re.match(r'^\d+[\.、]', desc_line):
                    continue
                description_lines.append(desc_line)
                if len(description_lines) >= 5:  # 限制描述长度
                    break

            modules.append({
                "name": heading,
                "description": " ".join(description_lines[:3]) if description_lines else heading,
                "keywords": self._extract_keywords_from_heading(heading),
                "exact_phrases": [heading],
                "section_hint": heading[:10] if len(heading) > 10 else heading,
            })

        log.info("启发式提取识别到 %s 个候选模块，过滤后保留 %s 个", len(candidates), len(modules))
        return modules

    @staticmethod
    def _looks_like_module_heading(text: str, line_idx: int, all_lines: List[str]) -> bool:
        """判断文本是否像功能模块标题（更严格的规则）。"""

        # 过滤规则1: 长度限制（太短或太长都不像模块标题）
        if len(text) < 3 or len(text) > 30:
            return False

        # 过滤规则2: 排除明显的非标题内容
        if text.startswith(('*', '-', '[', '（', '(', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '0.')):
            return False

        # 过滤规则3: 排除看起来像问题的行
        if text.endswith('？') or text.endswith('?'):
            return False
        if '是否' in text or '能否' in text or '如何' in text:
            return False

        # 过滤规则4: 排除单个数字或编号
        if re.match(r'^\d+[\.、]?\s*$', text):
            return False

        # 过滤规则5: 排除看起来像选项的行（如 "A. "、"B. "）
        if re.match(r'^[A-Z][\.、]\s*', text):
            return False

        # 过滤规则6: 排除包含太多标点的行（可能是描述而非标题）
        punctuation_count = sum(1 for c in text if c in '，。、；：！？')
        if punctuation_count > 2:
            return False

        # 过滤规则7: 排除以冒号结尾的标题（通常是描述性内容，如"弹窗调用逻辑："）
        if text.endswith('：') or text.endswith(':'):
            return False

        # 过滤规则8: 排除文档结构性的标题（通过模式识别而非具体词汇）
        # 排除包含"说明"、"范围"、"涉及"、"机制"等结构性词汇的标题
        structural_patterns = ["说明", "范围", "涉及", "机制", "输出", "选择", "时间", "方式"]
        if any(pattern in text and len(text) <= 8 for pattern in structural_patterns):
            return False

        # 过滤规则9: 排除问题性的标题（如"邀请您对...功能评分"）
        if '邀请' in text and ('评分' in text or '评价' in text):
            return False
        if '请根据' in text or '请回答' in text:
            return False

        # 过滤规则10: 排除纯描述性的短句（如"海外版是第二份问卷："）
        if '是' in text and len(text) < 15 and ('是' in text[:5] or text.endswith('：')):
            return False

        # 正向规则1: 包含与功能模块相关的通用关键词，但必须是核心词
        core_indicators = ["模块", "功能", "弹窗", "对话", "中心", "系统", "平台"]
        has_core_indicator = any(indicator in text for indicator in core_indicators)

        # 正向规则2: 包含大写缩写或英文字母组合（常见于模块命名）
        has_uppercase_abbr = bool(re.search(r"[A-Z]{2,}", text))

        # 正向规则3: 独立行且前后有空行（更可能是标题）
        is_isolated = False
        if line_idx > 0 and line_idx < len(all_lines) - 1:
            prev_line = all_lines[line_idx - 1].strip()
            next_line = all_lines[line_idx + 1].strip() if line_idx + 1 < len(all_lines) else ""
            # 如果前后都是空行，或者前一行很短，更可能是标题
            if (not prev_line or len(prev_line) < 5) and (not next_line or not next_line.startswith(('1.', '2.', '3.'))):
                is_isolated = True

        # 必须满足：有核心指示词或大写缩写，且是独立行，且长度适中
        if (has_core_indicator or has_uppercase_abbr) and is_isolated and 4 <= len(text) <= 25:
            return True

        # 特殊情况：如果包含大写缩写且长度很短（2-8字符），可能是模块名
        if has_uppercase_abbr and 2 <= len(text) <= 8:
            return True

        return False

    @staticmethod
    def _extract_keywords_from_heading(heading: str) -> List[str]:
        """从标题中提取关键词。"""
        tokens = [token for token in re.split(r"[^A-Za-z0-9\u4e00-\u9fa5]+", heading) if token]
        keywords = [token for token in tokens if len(token) >= 2]

        if not keywords:
            keywords.append(heading)

        return keywords[:5]
