"""内容提取和边界检测相关功能"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from shared.config import ExtractionConfig
from domain.test_case.text_normalizer import MARKDOWN_HEADING_PATTERN, MARKDOWN_HEADING_PATTERN_1_2, RequirementCache
from shared.logger import log


class ContentExtractor:
    """内容提取器，负责精确提取模块对应的原文内容"""

    def __init__(
        self,
        normalize_func: Callable[[str], str],
        is_module_title_line_func: Callable[[str, List[str]], bool],
        cache: Optional[RequirementCache] = None,
        module_matcher: Optional[Any] = None,
    ):
        """
        初始化内容提取器

        Args:
            normalize_func: 文本标准化函数
            is_module_title_line_func: 判断是否是模块标题行的函数
            cache: RequirementCache 实例（可选，用于访问缓存数据）
            module_matcher: ModuleMatcher 实例（可选，用于模块匹配）
        """
        self._normalize_identifier = normalize_func
        self._is_module_title_line = is_module_title_line_func
        self._cache = cache
        self._module_matcher = module_matcher

    def find_module_boundary(
        self,
        doc_lines: List[str],
        anchor_index: int,
        initial_end_idx: int,
        other_module_tokens: List[str],
        sections: Optional[List[Tuple[int, str]]] = None,
        main_module_tokens: Optional[List[str]] = None,
    ) -> Tuple[int, bool]:
        """
        查找模块边界（结束位置）

        Args:
            doc_lines: 文档行列表
            anchor_index: 模块锚点位置
            initial_end_idx: 初始结束位置（章节边界）
            other_module_tokens: 其他模块的标识符列表
            sections: 章节列表（可选）
            main_module_tokens: 主模块标识符列表（可选，如果提供则只检测主模块作为边界）

        Returns:
            (module_end_idx, found_next_module)
        """
        module_end_idx = initial_end_idx
        found_next_module = False

        # 扩大搜索范围，确保能找到下一个模块（即使它在 initial_end_idx 之后）
        search_end = min(len(doc_lines), initial_end_idx + ExtractionConfig.MODULE_SEARCH_EXTEND_RANGE)

        # 如果提供了主模块标识符，优先使用主模块标识符；否则使用所有模块标识符
        tokens_to_check = main_module_tokens if main_module_tokens else other_module_tokens

        for idx in range(anchor_index + 1, search_end):
            line = doc_lines[idx].strip()
            if not line:
                continue

            normalized_line = self._normalize_identifier(line)

            # 优先检查Markdown格式的标题（如 ## 标题）
            markdown_match = MARKDOWN_HEADING_PATTERN.match(line)
            if markdown_match:
                heading_text = markdown_match.group(1).strip()
                normalized_heading = self._normalize_identifier(heading_text)
                
                # 检查标题级别：二级标题（##）通常是主模块，三级标题（###）通常是子模块
                title_level = 2 if line.startswith("## ") and not line.startswith("### ") else 3
                
                # 如果提供了主模块标识符，只检测二级标题作为边界
                if main_module_tokens and title_level != 2:
                    continue
                
                # 检查是否是其他模块的标题
                for token in tokens_to_check:
                    if normalized_heading == token:
                        module_end_idx = idx
                        found_next_module = True
                        log.debug(
                            "找到下一个模块边界（Markdown格式）: anchor_index=%s, next_module_at=%s, module_end_idx=%s, heading=%s, level=%s",
                            anchor_index, idx, module_end_idx, heading_text, title_level
                        )
                        break
                if found_next_module:
                    break

            # 检测其他模块标题（普通格式）
            # 如果提供了主模块标识符，只检测主模块
            if self._is_module_title_line(normalized_line, tokens_to_check):
                # 对于普通格式，如果提供了主模块标识符，需要额外检查是否是主模块
                # 这里假设普通格式的标题如果匹配主模块标识符，就是主模块
                module_end_idx = idx
                found_next_module = True
                log.debug(
                    "找到下一个模块边界: anchor_index=%s, next_module_at=%s, module_end_idx=%s",
                    anchor_index, idx, module_end_idx
                )
                break

            # 如果遇到明显的章节标题（在sections中），也在这里结束
            if sections:
                for section_line, _ in sections:
                    if section_line == idx and idx > anchor_index:
                        module_end_idx = idx
                        found_next_module = True
                        log.debug(
                            "找到章节边界: anchor_index=%s, section_at=%s, module_end_idx=%s",
                            anchor_index, idx, module_end_idx
                        )
                        break
                if found_next_module:
                    break

        if not found_next_module:
            log.debug(
                "未找到下一个模块边界: anchor_index=%s, search_end=%s, tokens_checked=%s",
                anchor_index, search_end, len(tokens_to_check)
            )

        return module_end_idx, found_next_module

    def _get_title_level(self, doc_lines: List[str], line_index: int) -> int:
        """
        获取指定行的标题级别
        
        Args:
            doc_lines: 文档行列表
            line_index: 行索引
            
        Returns:
            标题级别：2表示##，3表示###，0表示不是标题
        """
        if line_index >= len(doc_lines):
            return 0
        line = doc_lines[line_index].strip()
        if line.startswith("## ") and not line.startswith("### "):
            return 2
        elif line.startswith("### "):
            return 3
        return 0

    def _find_parent_module_end(
        self,
        doc_lines: List[str],
        parent_anchor: int,
        other_tokens: List[str],
        main_module_tokens: Optional[List[str]] = None,
    ) -> int:
        """
        查找父模块的结束位置（下一个主模块的开始位置）
        
        Args:
            doc_lines: 文档行列表
            parent_anchor: 父模块的锚点位置
            other_tokens: 其他模块的标识符列表
            main_module_tokens: 主模块标识符列表（可选，如果提供则只检测主模块）
            
        Returns:
            父模块的结束位置（行索引）
        """
        search_end = min(len(doc_lines), parent_anchor + ExtractionConfig.MAIN_MODULE_SEARCH_EXTEND_RANGE)
        tokens_to_check = main_module_tokens if main_module_tokens else other_tokens
        
        for idx in range(parent_anchor + 1, search_end):
            line = doc_lines[idx].strip()
            if not line:
                continue
            # 检查是否是二级标题（##），二级标题通常是主模块
            markdown_match = MARKDOWN_HEADING_PATTERN_1_2.match(line)
            if markdown_match:
                heading_text = markdown_match.group(1).strip()
                normalized_heading = self._normalize_identifier(heading_text)
                # 检查是否是其他主模块的标题
                if normalized_heading in tokens_to_check:
                    return idx
        # 没有找到下一个主模块，返回文档结束位置
        return len(doc_lines)

    def trim_content_at_module_boundary(
        self,
        snippet_lines: List[str],
        other_tokens: List[str],
        min_content_length: int,
    ) -> List[str]:
        """
        在内容中裁剪到模块边界

        从后往前查找，确保包含所有非空行，直到遇到下一个模块标题

        Args:
            snippet_lines: 内容行列表
            other_tokens: 其他模块的标识符列表
            min_content_length: 最小内容长度

        Returns:
            裁剪后的行列表
        """
        if not snippet_lines:
            return snippet_lines

        # 从后往前查找下一个模块标题
        cut_idx = len(snippet_lines)

        for rel_idx in range(len(snippet_lines) - 1, -1, -1):
            line = snippet_lines[rel_idx].strip()
            if not line:
                continue
            normalized_line = self._normalize_identifier(line)

            # 优先检查Markdown格式的标题（如 ## 标题、### 标题）
            markdown_match = MARKDOWN_HEADING_PATTERN.match(line)
            if markdown_match:
                heading_text = markdown_match.group(1).strip()
                normalized_heading = self._normalize_identifier(heading_text)
                # 检查是否是其他模块的标题
                if normalized_heading in other_tokens:
                    log.debug(
                        "模块边界检测: 在第 %s 行发现其他模块标题（Markdown格式） '%s'",
                        rel_idx, line
                    )
                    # 确保截断位置之前的内容满足最小长度要求
                    current_content = "\n".join(snippet_lines[:rel_idx]).strip()
                    if len(current_content) >= min_content_length:
                        cut_idx = rel_idx
                        log.debug(
                            "模块边界检测: 截断到第 %s 行，截断后内容长度=%s (>= %s)",
                            rel_idx, len(current_content), min_content_length
                        )
                        break
                    # 如果截断后内容太短，不截断，保留原内容
                    else:
                        log.debug(
                            "模块边界检测: 发现其他模块标题但截断后内容太短 (%s < %s)，保留原内容",
                            len(current_content), min_content_length
                        )
                        # 不截断，保留原内容
                        cut_idx = len(snippet_lines)
                        break

            # 检查是否是其他模块的标题行（普通格式）
            if self._is_module_title_line(normalized_line, other_tokens):
                log.debug(
                    "模块边界检测: 在第 %s 行发现其他模块标题 '%s'，other_tokens=%s",
                    rel_idx, line, other_tokens
                )
                # 确保截断位置之前的内容满足最小长度要求
                current_content = "\n".join(snippet_lines[:rel_idx]).strip()
                if len(current_content) >= min_content_length:
                    cut_idx = rel_idx
                    log.debug(
                        "模块边界检测: 截断到第 %s 行，截断后内容长度=%s (>= %s)",
                        rel_idx, len(current_content), min_content_length
                    )
                    break
                # 如果截断后内容太短，不截断，保留原内容
                else:
                    log.debug(
                        "模块边界检测: 发现其他模块标题但截断后内容太短 (%s < %s)，保留原内容",
                        len(current_content), min_content_length
                    )
                    # 不截断，保留原内容
                    cut_idx = len(snippet_lines)
                    break

        if cut_idx < len(snippet_lines):
            log.debug(
                "模块边界检测: 裁剪了 %s 行，从 %s 行到 %s 行",
                len(snippet_lines) - cut_idx, cut_idx, len(snippet_lines) - 1
            )
        return snippet_lines[:cut_idx]

    def shrink_lines_to_limit(self, lines: List[str]) -> List[str]:
        """
        裁剪行列表到最大长度限制

        注意：这个方法只是为了控制文本长度，不应该改变行号范围
        因此，即使某些行被移除，matched_positions 也应该基于原始的行范围
        """
        if not lines:
            return lines

        joined = "\n".join(lines).strip()
        if len(joined) <= ExtractionConfig.MAX_SNIPPET_LENGTH:
            # 如果内容在限制内，保留所有行（包括空行，以保持行号一致性）
            return lines

        # 如果内容超过限制，从后往前移除行
        trimmed = list(lines)
        while trimmed and len("\n".join(trimmed).strip()) > ExtractionConfig.MAX_SNIPPET_LENGTH:
            trimmed.pop()

        if trimmed:
            # 保留所有行，包括空行，以保持行号一致性
            return trimmed

        # 如果所有行都被移除了，至少保留第一行
        return [lines[0].strip()] if lines else []

    def refine_matched_content(
        self,
        requirement_doc: str,
        module_name: str,
        module_data: Dict[str, Any],
        anchor_index: int,
        fallback_section: str,
        all_modules: Optional[List[Dict[str, Any]]] = None,
        module_hierarchy: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, List[int]]:
        """
        精确提取模块对应的原文内容

        Args:
            requirement_doc: 需求文档
            module_name: 模块名称
            module_data: 模块数据（包含 keywords, exact_phrases 等）
            anchor_index: 模块在文档中的锚点位置
            fallback_section: 回退内容（如果无法提取）
            all_modules: 所有模块列表（用于边界检测）

        Returns:
            (refined_content, matched_positions)
            - refined_content: 精炼后的内容
            - matched_positions: [start_line, end_line] 行号范围（从1开始）
        """
        if not self._cache or not self._module_matcher:
            raise ValueError("ContentExtractor 需要 cache 和 module_matcher 才能使用 refine_matched_content")

        doc_lines = self._cache._cached_doc_lines or requirement_doc.splitlines()
        if anchor_index >= len(doc_lines):
            cleaned = fallback_section.strip()
            if len(cleaned) > ExtractionConfig.MAX_SNIPPET_LENGTH:
                cleaned = cleaned[:ExtractionConfig.MAX_SNIPPET_LENGTH]
            return cleaned, [0, 0]

        # 确保 anchor_index 是有效的模块起始位置（不是文档开头的通用描述）
        # 自动检测文档头部结束位置
        header_end = RequirementCache._detect_header_end(doc_lines)
        if anchor_index < header_end:
            # 使用统一方法获取模块标识符
            _, normalized_current, _, _ = self._module_matcher.get_module_tokens(module_name)
            # 从文档头部结束后开始查找模块标题
            for idx in range(header_end, len(doc_lines)):
                normalized_line = self._normalize_identifier(doc_lines[idx].strip())
                if normalized_line == normalized_current or normalized_line.startswith(normalized_current):
                    anchor_index = idx
                    break

        sections = self._cache._cached_sections

        # 先获取模块标识符，因为后面可能会用到
        canonical, normalized_current, anchor_tokens, other_tokens = self._module_matcher.get_module_tokens(module_name)

        # 检查是否是第一个模块（位置最靠前的模块）
        is_first_module = True
        if all_modules:
            for other_module in all_modules:
                other_name = other_module.get("name", "")
                if other_name and other_name != module_name:
                    # 检查其他模块的位置
                    other_anchor = self._module_matcher.find_first_occurrence_line(
                        other_name,
                        other_module,
                        doc_lines,
                    )
                    if other_anchor < anchor_index:
                        is_first_module = False
                        break

        start_idx = max(0, anchor_index)
        end_idx = len(doc_lines)

        # 向上查找更合适的起始位置（如"状态"、"判断条件"等标题）
        # 提取公共逻辑，避免重复代码
        search_up_limit = min(ExtractionConfig.MAX_BACKWARD_SEARCH_LINES, anchor_index)
        best_start = anchor_index
        for idx in range(anchor_index - 1, max(0, anchor_index - search_up_limit) - 1, -1):
            line = doc_lines[idx].strip()
            if not line:
                continue
            # 检查是否是模块相关的标题行（包含keywords中的关键词）
            normalized_line = self._normalize_identifier(line)
            for keyword in module_data.get("keywords", []):
                normalized_keyword = self._normalize_identifier(keyword)
                if normalized_keyword and normalized_keyword == normalized_line:
                    # 找到了更靠前的标题行，使用它作为起始位置
                    best_start = idx
                    log.debug(
                        "模块 %s: 找到更靠前的标题行 '%s' 在第 %s 行，使用它作为起始位置",
                        module_name, line, idx + 1
                    )
                    break
            if best_start < anchor_index:
                break
        start_idx = best_start
        if is_first_module:
            log.debug("模块 %s 是第一个模块，从第 %s 行开始匹配（anchor_index=%s）", module_name, start_idx + 1, anchor_index + 1)
        else:
            log.debug("模块 %s: 使用起始位置 %s (anchor_index=%s)", module_name, start_idx, anchor_index)
            # 确定初始的章节边界（但不要覆盖anchor_index）
            # 注意：这里只用于确定初始的end_idx，不要覆盖start_idx（因为start_idx已经通过向上查找确定了）
            if sections:
                # 找到anchor_index所在的section，使用下一个section作为初始end_idx
                for idx, (line_no, _) in enumerate(sections):
                    if line_no <= anchor_index:
                        # 找到下一个section作为初始end_idx（但不要覆盖start_idx）
                        if idx + 1 < len(sections):
                            potential_end = sections[idx + 1][0]
                            # 只有当potential_end在anchor_index之后时，才使用它作为初始end_idx
                            if potential_end > anchor_index:
                                end_idx = potential_end
                    else:
                        break

            # 向上查找空行或章节边界，但不要超过 anchor_index 之前太多
            # 使用配置的最大向后搜索行数
            max_backward = ExtractionConfig.MAX_BACKWARD_SEARCH_LINES
            search_start = max(0, start_idx - max_backward)
            for idx in range(start_idx - 1, search_start - 1, -1):
                line = doc_lines[idx].strip()
                # 如果遇到空行或明显的章节标题，从这里开始
                if not line or len(line) < ExtractionConfig.MIN_TERM_LENGTH:
                    potential_start = idx + 1
                    # 确保不超过anchor_index
                    if potential_start <= anchor_index:
                        start_idx = potential_start
                    break
                # 如果遇到其他模块标题（Markdown格式），从这里开始
                markdown_match = MARKDOWN_HEADING_PATTERN.match(line)
                if markdown_match:
                    # 遇到Markdown标题，检查是否是其他模块
                    heading_text = markdown_match.group(1).strip()
                    normalized_heading = self._normalize_identifier(heading_text)
                    # 如果这是其他模块的标题，从这里开始
                    if normalized_heading in other_tokens:
                        potential_start = idx + 1
                        if potential_start <= anchor_index:
                            start_idx = potential_start
                        break
                # 如果遇到其他模块标题，从这里开始（使用章节检测结果）
                if sections:
                    for section_line, section_title in sections:
                        if section_line == idx:
                            potential_start = idx
                            if potential_start <= anchor_index:
                                start_idx = potential_start
                            break
                    if start_idx < anchor_index:
                        break

        # 模块标识符已经在上面获取了，这里不需要重复获取

        # 如果提供了所有模块信息，从中获取其他模块的标识符（更准确）
        if all_modules:
            other_module_tokens = []
            for other_module in all_modules:
                other_name = other_module.get("name", "")
                if other_name and other_name != module_name:
                    normalized_other = self._normalize_identifier(other_name)
                    if normalized_other and normalized_other != normalized_current:
                        other_module_tokens.append(normalized_other)
                    # 也添加关键词和exact_phrases作为标识符
                    for keyword in other_module.get("keywords", []):
                        normalized_keyword = self._normalize_identifier(keyword)
                        if normalized_keyword and normalized_keyword not in other_module_tokens:
                            other_module_tokens.append(normalized_keyword)
                    # 处理exact_phrases，特别是Markdown格式的标题
                    for phrase in other_module.get("exact_phrases", []):
                        # 如果是Markdown格式的标题（如 "## 标题"），提取标题文本
                        markdown_match = MARKDOWN_HEADING_PATTERN.match(phrase.strip())
                        if markdown_match:
                            heading_text = markdown_match.group(1).strip()
                            normalized_heading = self._normalize_identifier(heading_text)
                            if normalized_heading and normalized_heading not in other_module_tokens:
                                other_module_tokens.append(normalized_heading)
                        else:
                            # 普通短语
                            normalized_phrase = self._normalize_identifier(phrase)
                            if normalized_phrase and normalized_phrase not in other_module_tokens:
                                other_module_tokens.append(normalized_phrase)
            # 合并预定义的标识符和实际提取的模块标识符
            other_tokens = list(set(other_tokens + other_module_tokens))

        # 准备主模块标识符列表（用于边界检测，只检测主模块作为边界）
        main_module_tokens = None
        if all_modules:
            main_module_names = []
            for other_module in all_modules:
                other_name = other_module.get("name", "")
                if other_name and other_name != module_name:
                    # 检查是否是主模块（通过 is_main_module 字段或 parent_module 字段）
                    is_main = other_module.get("is_main_module", False)
                    has_parent = other_module.get("parent_module") or (module_hierarchy.get(other_name) if module_hierarchy else None)
                    if is_main or not has_parent:
                        main_module_names.append(other_name)
            
            if main_module_names:
                main_module_tokens = []
                for main_name in main_module_names:
                    normalized_main = self._normalize_identifier(main_name)
                    if normalized_main and normalized_main not in main_module_tokens:
                        main_module_tokens.append(normalized_main)

        # 检查当前模块是否是子模块（通过检查是否有父模块）
        is_current_sub_module = False
        parent_module_end = None
        parent_module_name = module_data.get("parent_module") or (module_hierarchy.get(module_name) if module_hierarchy else None)
        
        if parent_module_name and all_modules:
            # 当前模块是子模块，需要找到父模块的结束位置
            for other_module in all_modules:
                other_name = other_module.get("name", "")
                if other_name == parent_module_name:
                    # 找到父模块的锚点位置
                    parent_anchor = self._module_matcher.find_first_occurrence_line(
                        parent_module_name,
                        other_module,
                        doc_lines,
                    )
                    if parent_anchor >= 0:
                        # 找到父模块的结束位置（下一个主模块的开始位置）
                        parent_module_end = self._find_parent_module_end(
                            doc_lines, parent_anchor, other_tokens, main_module_tokens=main_module_tokens
                        )
                        is_current_sub_module = True
                        log.debug(
                            "模块 %s: 识别为子模块（父模块: %s），父模块结束位置在第 %s 行",
                            module_name, parent_module_name, parent_module_end + 1 if parent_module_end else "未知"
                        )
                    break

        # 查找模块边界（结束位置）
        initial_end_idx = end_idx  # 保存初始的章节边界
        module_end_idx, found_next_module = self.find_module_boundary(
            doc_lines,
            anchor_index,
            initial_end_idx,
            other_tokens,
            sections,
            main_module_tokens=main_module_tokens,  # 传入主模块标识符，只检测主模块作为边界
        )

        # 使用更精确的模块结束位置
        start_idx = max(0, start_idx)

        # 关键修复：如果检测到了下一个模块标题，确保包含当前模块的所有内容
        # 包括下一个模块标题之前的所有行（包括空行）
        # 但是，如果下一个模块是子模块（三级标题###），不应该截断主模块的内容
        # 需要检查下一个模块是否是子模块
        is_next_module_sub = False
        if found_next_module and module_end_idx < len(doc_lines):
            next_line = doc_lines[module_end_idx].strip()
            # 检查下一个模块是否是三级标题（###），如果是，说明是子模块，不应该截断主模块
            if next_line.startswith("### "):
                is_next_module_sub = True
                log.debug(
                    "模块 %s: 下一个模块是子模块（三级标题），不截断主模块内容",
                    module_name
                )

        # 如果是子模块，限制内容范围在父模块内
        if is_current_sub_module and parent_module_end is not None:
            # 子模块的内容不能超过父模块的结束位置
            end_idx = min(end_idx, parent_module_end)
            log.debug(
                "模块 %s: 子模块内容限制在父模块范围内，结束位置: %s",
                module_name, end_idx + 1
            )
        elif found_next_module and not is_next_module_sub:
            # 找到了下一个模块，且不是子模块，module_end_idx 是下一个模块的开始位置（行号）
            # Python 切片是左闭右开的，所以 doc_lines[start_idx:module_end_idx]
            # 会包含索引 start_idx 到 module_end_idx-1 的行
            # 这正好是我们想要的：包含当前模块的所有内容，不包括下一个模块标题
            end_idx = module_end_idx
        else:
            # 没有检测到下一个模块，或者下一个模块是子模块，需要继续查找下一个主模块
            if is_next_module_sub:
                # 下一个模块是子模块，继续查找下一个主模块（二级标题##）
                # 扩大搜索范围，查找下一个二级标题
                search_end = min(len(doc_lines), module_end_idx + ExtractionConfig.MAIN_MODULE_SEARCH_EXTEND_RANGE)
                for idx in range(module_end_idx + 1, search_end):
                    line = doc_lines[idx].strip()
                    if not line:
                        continue
                    # 检查是否是二级标题（##）
                    markdown_match = MARKDOWN_HEADING_PATTERN_1_2.match(line)
                    if markdown_match:
                        heading_text = markdown_match.group(1).strip()
                        normalized_heading = self._normalize_identifier(heading_text)
                        # 检查是否是其他主模块的标题
                        if normalized_heading in other_tokens:
                            end_idx = idx
                            log.debug(
                                "模块 %s: 找到下一个主模块（二级标题）在第 %s 行: %s",
                                module_name, idx + 1, heading_text
                            )
                            break
                else:
                    # 没有找到下一个主模块，检测文档实际内容结束位置（排除元信息）
                    content_end = RequirementCache._detect_content_end(doc_lines)
                    # 确保不超过实际内容结束位置
                    end_idx = min(content_end, module_end_idx + ExtractionConfig.MAIN_MODULE_SEARCH_EXTEND_RANGE)
                    if end_idx < len(doc_lines):
                        log.debug(
                            "模块 %s: 检测到文档内容结束位置（排除元信息）在第 %s 行",
                            module_name, end_idx + 1
                        )
            else:
                # 没有检测到下一个模块，检测文档实际内容结束位置（排除元信息）
                content_end = RequirementCache._detect_content_end(doc_lines)
                # 可以稍微扩展（最多1行，用于包含可能的空行），但不超过实际内容结束位置
                end_idx = min(content_end, module_end_idx + 1)
                if end_idx < len(doc_lines):
                    log.debug(
                        "模块 %s: 检测到文档内容结束位置（排除元信息）在第 %s 行",
                        module_name, end_idx + 1
                    )

        # 确保 start_idx 不超过 anchor_index，以保证包含模块标题行
        # 但不要强制设置为anchor_index，如果start_idx更靠前（在anchor_index之前），应该保留
        start_idx = min(start_idx, anchor_index)

        # 重要：确保start_idx至少从anchor_index开始（对于第一个模块，可能start_idx被设置得太靠前）
        # 但如果anchor_index是模块标题行，start_idx应该等于或小于anchor_index
        # 这里的关键是：如果anchor_index是模块标题行，start_idx应该从anchor_index开始
        # 但如果start_idx在anchor_index之前（比如找到了更靠前的章节标题），应该保留
        if start_idx > anchor_index:
            # 这种情况不应该发生，但如果发生了，使用anchor_index
            log.warning(
                "模块 %s: start_idx (%s) > anchor_index (%s)，使用anchor_index作为start_idx",
                module_name, start_idx, anchor_index
            )
            start_idx = anchor_index

        # 再次检查：确保不包含元信息部分
        content_end = RequirementCache._detect_content_end(doc_lines)
        if end_idx > content_end:
            log.debug(
                "模块 %s: end_idx (%s) 超过内容结束位置 (%s)，调整为内容结束位置",
                module_name, end_idx, content_end
            )
            end_idx = content_end

        snippet_lines = doc_lines[start_idx:end_idx]

        # 调试信息：记录关键变量
        log.debug(
            "模块 %s 内容提取调试:\n"
            "  anchor_index=%s (行%d: %s)\n"
            "  start_idx=%s (行%d: %s)\n"
            "  end_idx=%s (行%d: %s)\n"
            "  module_end_idx=%s\n"
            "  found_next_module=%s\n"
            "  snippet_lines数量=%s",
            module_name,
            anchor_index, anchor_index + 1, doc_lines[anchor_index] if anchor_index < len(doc_lines) else "N/A",
            start_idx, start_idx + 1, doc_lines[start_idx] if start_idx < len(doc_lines) else "N/A",
            end_idx, end_idx, doc_lines[end_idx - 1] if end_idx > 0 and end_idx <= len(doc_lines) else "N/A",
            module_end_idx,
            found_next_module,
            len(snippet_lines)
        )

        # 调试信息：确保我们获取了正确的内容
        if not snippet_lines:
            log.warning(
                "模块边界异常: start_idx=%s, end_idx=%s, anchor_index=%s, module_name=%s, found_next_module=%s",
                start_idx, end_idx, anchor_index, module_name, found_next_module
            )
            # 如果 snippet_lines 为空，返回 fallback
            cleaned = fallback_section.strip()
            if len(cleaned) > ExtractionConfig.MAX_SNIPPET_LENGTH:
                cleaned = cleaned[:ExtractionConfig.MAX_SNIPPET_LENGTH]
            return cleaned, [anchor_index + 1, anchor_index + 1]

        anchor_relative_idx = max(0, anchor_index - start_idx)
        min_content_length = ExtractionConfig.MIN_SNIPPET_LENGTH

        # 第一轮裁剪：如果找到了下一个模块，确保不包含下一个模块的标题行
        # 注意：由于 Python 切片是左闭右开的，如果 end_idx = module_end_idx（下一个模块的开始位置），
        # 那么 snippet_lines 已经正确排除了下一个模块标题
        # 但是为了安全起见，我们还是要检查一下是否意外包含了下一个模块标题
        if found_next_module and snippet_lines:
            # 从后往前查找，确保不包含下一个模块的标题行
            # 正常情况下，由于 end_idx = module_end_idx，snippet_lines 不应该包含下一个模块标题
            # 但为了安全，我们还是要检查
            # 注意：只检查非空行，空行不应该触发截断
            found_other_module_in_snippet = False
            for rel_idx in range(len(snippet_lines) - 1, anchor_relative_idx, -1):
                normalized_line = self._normalize_identifier(snippet_lines[rel_idx].strip())
                if not normalized_line:
                    continue
                # 如果遇到其他模块的标题行，在这里截断（不包括这一行）
                if self._is_module_title_line(normalized_line, other_tokens):
                    trimmed_content = "\n".join(snippet_lines[:rel_idx]).strip()
                    # 确保截断后仍有足够内容
                    if len(trimmed_content) >= min_content_length:
                        snippet_lines = snippet_lines[:rel_idx]
                        found_other_module_in_snippet = True
                        log.debug(
                            "模块 %s: 在第一轮裁剪中发现其他模块标题，截断到第 %s 行 (相对索引 %s)",
                            module_name, start_idx + rel_idx + 1, rel_idx
                        )
                    else:
                        # 如果截断后内容太短，不截断，保留原内容
                        log.warning(
                            "模块 %s: 发现其他模块标题但截断后内容太短 (%s < %s)，保留原内容",
                            module_name, len(trimmed_content), min_content_length
                        )
                    break

            # 如果没有找到其他模块标题，说明边界检测是正确的，不需要截断
            if not found_other_module_in_snippet:
                log.debug(
                    "模块 %s: 第一轮裁剪检查完成，未发现其他模块标题，保留所有 %s 行",
                    module_name, len(snippet_lines)
                )

        current_content = "\n".join(snippet_lines).strip()
        if len(current_content) < min_content_length:
            # 扩展时也要检查是否遇到下一个模块标题
            original_end_idx = end_idx
            extended_end_idx = min(len(doc_lines), start_idx + len(snippet_lines) + ExtractionConfig.CONTENT_EXTEND_RANGE)
            # 在扩展范围内检查是否有其他模块标题
            for idx in range(original_end_idx, extended_end_idx):
                if idx >= len(doc_lines):
                    break
                line = doc_lines[idx].strip()
                if not line:
                    continue
                normalized_line = self._normalize_identifier(line)
                # 检查是否是其他模块标题
                if self._is_module_title_line(normalized_line, other_tokens):
                    extended_end_idx = idx
                    break
            end_idx = extended_end_idx
            snippet_lines = doc_lines[start_idx:end_idx]
            # 重新裁剪，确保不包含下一个模块
            snippet_lines = self.trim_content_at_module_boundary(
                snippet_lines,
                other_tokens,
                min_content_length,
            )

        # 在裁剪到长度限制之前，再次检查是否包含下一个模块标题
        # 确保即使经过扩展和裁剪，也不会包含下一个模块的内容
        # 但是，如果found_next_module=True且end_idx=module_end_idx，说明边界已经正确，不需要再次裁剪
        snippet_lines_before_final_trim = snippet_lines.copy()

        # 重要：即使found_next_module=True，也要检查snippet_lines是否真的不包含下一个模块标题
        # 因为可能存在边界检测错误的情况
        needs_trim = False
        if found_next_module and end_idx == module_end_idx:
            # 检查snippet_lines的最后几行，确保不包含下一个模块标题
            # 如果最后几行包含下一个模块标题，说明边界检测有问题，需要trim
            CHECK_LAST_LINES = 5  # 检查最后N行
            for i in range(len(snippet_lines) - 1, max(0, len(snippet_lines) - CHECK_LAST_LINES), -1):
                line = snippet_lines[i].strip()
                if not line:
                    continue
                normalized_line = self._normalize_identifier(line)
                if self._is_module_title_line(normalized_line, other_tokens):
                    needs_trim = True
                    log.debug(
                        "模块 %s: 虽然found_next_module=True，但snippet_lines中包含下一个模块标题（第%d行），需要trim",
                        module_name, i
                    )
                    break
        else:
            # 边界可能不正确，需要再次检查
            needs_trim = True

        if needs_trim:
            snippet_lines = self.trim_content_at_module_boundary(
                snippet_lines,
                other_tokens,
                min_content_length,
            )
        else:
            log.debug(
                "模块 %s: 边界已正确（found_next_module=%s, end_idx=%s, module_end_idx=%s），跳过final_trim",
                module_name, found_next_module, end_idx, module_end_idx
            )

        # 关键修复：保存最终确定的行范围信息，用于计算 matched_positions
        # 这个信息应该在所有裁剪操作之后、长度限制之前确定
        # 因为 matched_positions 应该反映实际包含在文档中的行范围
        final_snippet_lines_count = len(snippet_lines)
        final_start_idx = start_idx

        # 如果 final_trim 截断了内容，记录截断位置
        trim_cut_idx = len(snippet_lines_before_final_trim)
        if len(snippet_lines) < len(snippet_lines_before_final_trim):
            trim_cut_idx = len(snippet_lines)

        # 裁剪到长度限制（这可能会减少行数，但不应该影响 matched_positions 的计算）
        # _shrink_lines_to_limit 只是为了控制文本长度，不应该改变行号范围
        snippet_lines_before_shrink = snippet_lines.copy()
        snippet_lines = self.shrink_lines_to_limit(snippet_lines)

        snippet_text = "\n".join(snippet_lines).strip()

        if not snippet_text:
            cleaned = fallback_section.strip()
            if len(cleaned) > ExtractionConfig.MAX_SNIPPET_LENGTH:
                cleaned = cleaned[:ExtractionConfig.MAX_SNIPPET_LENGTH]
            return cleaned, [anchor_index + 1, anchor_index + 1]

        # 关键修复：matched_positions 应该基于实际包含在文档中的行范围
        # 而不是基于经过 _shrink_lines_to_limit 裁剪后的行数
        # _shrink_lines_to_limit 只是为了控制文本长度，不应该影响行号范围

        # 计算实际包含的行范围
        # start_line_number 是第一个包含的行号（从1开始，因为行号从1开始）
        start_line_number = final_start_idx + 1

        # end_line_number 是最后一个包含的行号
        # 使用 final_trim 之后的行数，因为这是实际包含在文档中的行范围
        # 注意：final_trim 可能会截断到下一个模块标题之前，这是正确的
        # 但是，如果 final_snippet_lines_count 为0或1，说明可能有问题，需要检查
        if final_snippet_lines_count == 0:
            # 如果被完全截断，至少返回 anchor_index 所在的行
            end_line_number = anchor_index + 1
            log.warning(
                "模块 %s: final_snippet_lines_count 为0，使用 anchor_index=%s 作为 end_line_number",
                module_name, anchor_index
            )
        elif final_snippet_lines_count == 1:
            # 如果只有一行，检查是否是因为过度截断
            # 使用原始的行范围（在 final_trim 之前）
            if len(snippet_lines_before_final_trim) > 1:
                # 如果原始有多行，说明被过度截断了
                # 尝试找到最后一个非空行的位置
                last_non_empty_idx = -1
                for rel_idx in range(len(snippet_lines_before_final_trim) - 1, -1, -1):
                    if snippet_lines_before_final_trim[rel_idx].strip():
                        last_non_empty_idx = rel_idx
                        break
                if last_non_empty_idx >= 0:
                    end_line_number = final_start_idx + last_non_empty_idx + 1
                    log.warning(
                        "模块 %s: final_snippet_lines_count 只有1行，但原始有 %s 行，使用最后一个非空行 %s",
                        module_name, len(snippet_lines_before_final_trim), end_line_number
                    )
                else:
                    end_line_number = final_start_idx + len(snippet_lines_before_final_trim)
            else:
                # 原始也只有一行，这是正常的
                end_line_number = final_start_idx + final_snippet_lines_count
        else:
            # 正常情况
            end_line_number = final_start_idx + final_snippet_lines_count

        # 调试日志：记录整个匹配过程
        log.debug(
            "模块匹配详情 [%s]:\n"
            "  anchor_index=%s (第%d行)\n"
            "  start_idx=%s (第%d行), end_idx=%s (第%d行)\n"
            "  found_next_module=%s\n"
            "  final_snippet_lines_count=%s (在final_trim之后)\n"
            "  final_snippet_lines_after_shrink=%s (在shrink之后)\n"
            "  matched_positions=[%s, %s] (第%d-%d行)\n"
            "  matched_content长度=%s字符",
            module_name,
            anchor_index, anchor_index + 1,
            final_start_idx, final_start_idx + 1,
            end_idx, end_idx + 1,
            found_next_module,
            final_snippet_lines_count,
            len(snippet_lines),
            start_line_number, end_line_number, start_line_number, end_line_number,
            len(snippet_text)
        )

        return snippet_text, [start_line_number, end_line_number]
