"""需求文档提取相关工具"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.engine.base.config import ExtractionConfig
from .content_extractor import ContentExtractor
from core.engine.base.debug_recorder import record_ai_debug
from .heuristic_extractor import HeuristicExtractor
from .json_parser import get_project_root, parse_json_with_fallback
from core.engine.base.llm_service import LLMService
from .module_hierarchy import ModuleHierarchyDetector
from .module_hierarchy_builder import ModuleHierarchyBuilder
from .module_matcher import EXPECTED_MODULE_CANONICALS, ModuleMatcher
from .module_validator import ModuleValidator
from .prompts import build_module_extraction_prompt
from .text_normalizer import RequirementCache
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
        self._hierarchy_builder = ModuleHierarchyBuilder(normalize_func=self._cache.normalize_text)
        self._validator = ModuleValidator()

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
            validated_modules = self._validator.validate_modules(function_modules_data, requirement_doc)

            # 基于规则的后处理：过滤掉明显是子功能的模块
            filtered_modules = self._validator.filter_sub_function_modules(validated_modules, requirement_doc)

            processed_modules = self._post_process_modules(filtered_modules, requirement_doc)
            log.info("提取到 %s 个功能模块（规范化后）", len(processed_modules))
            return processed_modules
        except Exception as exc:  # noqa: BLE001
            log.error("提取功能模块失败: %s", exc)
            log.debug("异常类型: %s", type(exc).__name__)
            fallback = HeuristicExtractor.extract_modules(requirement_doc)
            if fallback:
                log.info("使用启发式提取功能模块，得到 %s 个模块", len(fallback))
                return self._post_process_modules(fallback, requirement_doc)
            raise


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
        # 优先使用AI输出的层次关系，如果AI没有提供或提供不完整，则使用代码规则补充
        main_modules: List[str] = []
        module_hierarchy: Dict[str, str] = {}

        # 获取所有模块名称集合，用于验证父模块是否存在
        all_module_names = {m.get("name", "") for m in sorted_modules if m.get("name")}
        
        # 第一步：从AI输出中提取层次关系
        ai_provided_hierarchy = {}  # 记录AI提供的层次关系
        log.info("=== 开始提取AI输出的层次关系 ===")
        for module in sorted_modules:
            module_name = module.get("name", "")
            if not module_name:
                continue

            # 检查AI是否输出了层次关系
            ai_is_main = module.get("is_main_module")
            ai_parent = module.get("parent_module")
            
            log.info("模块 '%s': AI输出 is_main_module=%s, parent_module=%s", module_name, ai_is_main, ai_parent)
            
            if ai_is_main is True:
                # AI明确标记为主模块
                main_modules.append(module_name)
                log.info("✓ AI标记为主模块: %s", module_name)
            elif ai_is_main is False and ai_parent:
                # AI明确标记为子模块，且有父模块
                # 验证父模块是否存在
                if ai_parent in all_module_names:
                    module_hierarchy[module_name] = ai_parent
                    ai_provided_hierarchy[module_name] = ai_parent
                    log.info("✓ AI标记为子模块: %s -> %s", module_name, ai_parent)
                else:
                    log.warning("✗ AI输出的父模块 '%s' 不存在，忽略该层次关系: %s -> %s", ai_parent, module_name, ai_parent)
            elif ai_is_main is False and ai_parent is None:
                log.info("? AI标记为子模块但无父模块: %s (将使用代码规则判断)", module_name)
            # 如果 ai_is_main 是 None，则使用代码规则判断
        
        log.info("=== AI层次关系提取完成: 主模块 %s 个, 子模块 %s 个 ===", len(main_modules), len(module_hierarchy))
        log.info("AI提取的主模块列表: %s", main_modules)
        log.info("AI提取的子模块层次关系: %s", module_hierarchy)
        
        # 第二步：对于AI没有明确判断的模块，使用代码规则补充
        # 检查哪些模块AI没有提供层次关系（包括 is_main_module 为 None 或 False 但 parent_module 为 None 的情况）
        modules_without_ai_hierarchy = []
        for m in sorted_modules:
            module_name = m.get("name", "")
            if not module_name:
                continue
            ai_is_main = m.get("is_main_module")
            ai_parent = m.get("parent_module")
            
            # 如果AI已经提供了明确的层次关系（is_main_module=True 或 (is_main_module=False and parent_module存在)），跳过
            if ai_is_main is True:
                log.info("AI已提供层次关系（主模块）: %s，跳过代码规则判断", module_name)
                continue
            elif ai_is_main is False and ai_parent:
                log.info("AI已提供层次关系（子模块）: %s -> %s，跳过代码规则判断", module_name, ai_parent)
                continue

            # 如果AI没有明确判断（is_main_module 为 None），或者AI标记为子模块但没有父模块
            if ai_is_main is None:
                modules_without_ai_hierarchy.append(m)
                log.info("AI未提供层次关系: %s (is_main_module=None)", module_name)
            elif ai_is_main is False and ai_parent is None:
                # AI标记为子模块但没有父模块，可能是独立的子模块，也使用代码规则判断
                modules_without_ai_hierarchy.append(m)
                log.info("AI标记为子模块但无父模块，使用代码规则判断: %s", module_name)
        
        if modules_without_ai_hierarchy:
            log.info("AI未提供层次关系的模块数量: %s，使用代码规则补充", len(modules_without_ai_hierarchy))
            log.info("需要代码规则补充的模块: %s", [m.get("name") for m in modules_without_ai_hierarchy])
            # 只对这些模块使用代码规则判断
            # 注意：build_hierarchy 需要所有模块的信息来判断层次关系，所以传入所有模块
            # 但只对 modules_without_ai_hierarchy 中的模块使用代码规则的结果
            code_main_modules, code_hierarchy = self._hierarchy_builder.build_hierarchy(
                sorted_modules, module_positions, doc_lines
            )
            # 合并AI和代码的结果（AI的结果优先）
            # 只对AI未提供层次关系的模块使用代码规则的结果
            modules_without_names = {m.get("name") for m in modules_without_ai_hierarchy if m.get("name")}
            log.info("AI已提供层次关系的模块: %s", [name for name in all_module_names if name not in modules_without_names])
            log.info("代码规则返回的主模块: %s", code_main_modules)
            log.info("代码规则返回的层次关系: %s", code_hierarchy)
            # 记录AI已提供的层次关系，防止被代码规则覆盖
            ai_provided_main_modules = set(main_modules)
            ai_provided_hierarchy_set = set(module_hierarchy.keys())
            
            for module_name in code_main_modules:
                if module_name in modules_without_names and module_name not in main_modules:
                    # 确保不在AI已提供的层次关系中
                    if module_name not in ai_provided_hierarchy_set:
                        main_modules.append(module_name)
                        log.info("代码规则补充主模块: %s", module_name)
                    else:
                        log.warning("跳过代码规则的主模块判断 '%s'（AI已将其标记为子模块）", module_name)
                elif module_name not in modules_without_names:
                    log.debug("跳过代码规则的主模块判断 '%s'（AI已提供层次关系）", module_name)
                elif module_name in ai_provided_hierarchy_set:
                    log.warning("跳过代码规则的主模块判断 '%s'（AI已将其标记为子模块）", module_name)
            
            for module_name, parent_name in code_hierarchy.items():
                if module_name in modules_without_names and module_name not in module_hierarchy:
                    # 确保不在AI已提供的主模块列表中
                    if module_name not in ai_provided_main_modules:
                        module_hierarchy[module_name] = parent_name
                        log.info("代码规则补充子模块: %s -> %s", module_name, parent_name)
                    else:
                        log.warning("跳过代码规则的子模块判断 '%s -> %s'（AI已将其标记为主模块）", module_name, parent_name)
                elif module_name not in modules_without_names:
                    log.debug("跳过代码规则的层次关系判断 '%s -> %s'（AI已提供层次关系）", module_name, parent_name)
                elif module_name in ai_provided_main_modules:
                    log.warning("跳过代码规则的子模块判断 '%s -> %s'（AI已将其标记为主模块）", module_name, parent_name)
            else:
                # AI已经提供了完整的层次关系，使用AI的结果
                log.info("=== 使用AI输出的模块层次关系: 主模块 %s 个, 子模块 %s 个 ===", len(main_modules), len(module_hierarchy))
                log.info("主模块列表: %s", main_modules)
                log.info("子模块层次关系: %s", module_hierarchy)

        result = []
        for idx, module in enumerate(sorted_modules, start=1):
            module_name = module.get("name", "")
            if not module_name:
                continue
            anchor_index = module_positions[module_name]
            matched_content = self.extract_relevant_section(requirement_doc, module_name, module)
            
            # 准备模块信息，包含层次关系
            module_with_hierarchy = module.copy()
            module_with_hierarchy["parent_module"] = module_hierarchy.get(module_name)
            module_with_hierarchy["is_main_module"] = module_name in main_modules
            
            refined_content, matched_positions = self._content_extractor.refine_matched_content(
                requirement_doc,
                module_name,
                module_with_hierarchy,
                anchor_index,
                matched_content,
                all_modules=sorted_modules,  # 传递所有模块信息
                module_hierarchy=module_hierarchy,  # 传递层次关系
            )

            match_confidence = "low"
            if module.get("exact_phrases"):
                match_confidence = "high"
            elif module.get("keywords"):
                match_confidence = "medium"

            # 判断是否是主模块（使用最终的层次关系）
            is_main = module_name in main_modules
            parent_module = module_hierarchy.get(module_name)
            
            # 记录最终结果，用于调试
            log.debug("模块 '%s' 最终结果: is_main_module=%s, parent_module=%s", module_name, is_main, parent_module)

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
        
        log.info("=== 最终结果构建完成: 共 %s 个模块 ===", len(result))
        log.info("最终主模块列表: %s", main_modules)
        log.info("最终子模块层次关系: %s", module_hierarchy)

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
                    # 保留AI输出的层次关系字段
                    "is_main_module": module.get("is_main_module"),
                    "parent_module": module.get("parent_module"),
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
                    # 保留AI输出的层次关系字段（如果entry中没有，则使用module中的）
                    if entry.get("is_main_module") is None:
                        entry["is_main_module"] = module.get("is_main_module")
                    if entry.get("parent_module") is None:
                        entry["parent_module"] = module.get("parent_module")
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
                            # 保留AI输出的层次关系字段
                            "is_main_module": module.get("is_main_module"),
                            "parent_module": module.get("parent_module"),
                        }
                        grouped[position_key] = entry
                    else:
                        # 如果位置key也存在，合并
                        entry = grouped[position_key]
                        new_desc = module.get("description", "").strip()
                        if new_desc and len(new_desc) > len(entry.get("description", "")):
                            entry["description"] = new_desc
                        entry["__position"] = min(entry["__position"], module_position)
                        # 保留AI输出的层次关系字段（如果entry中没有，则使用module中的）
                        if entry.get("is_main_module") is None:
                            entry["is_main_module"] = module.get("is_main_module")
                        if entry.get("parent_module") is None:
                            entry["parent_module"] = module.get("parent_module")

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

