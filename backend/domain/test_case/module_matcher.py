"""模块匹配和去重相关功能"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from shared.config import ExtractionConfig
from domain.test_case.text_normalizer import MARKDOWN_HEADING_PATTERN, RequirementCache

# 模块名称规范化映射（可选配置）
# 用途：将同一模块的不同名称变体映射到标准名称，用于去重和规范化
# 注意：这不会强制添加模块，只用于帮助识别同一模块的不同写法
# 如果需要特定业务场景的模块名称规范化，可以在这里配置
# 默认为空，保持系统的通用性
EXPECTED_MODULE_CANONICALS: Dict[str, List[str]] = {
    # 示例配置（已注释，可根据实际需求启用）：
    # "全局NPS": ["全局nps", "global nps"],
    # "功能NPS": ["功能nps", "模块nps"],
    # "生理期NPS": ["生理期nps", "生理期 功能评分"],
    # "OSA NPS": ["osa nps", "睡眠呼吸暂停风险监测"],
    # "计划NPS": ["计划nps"],
    # "健康NPS": ["健康nps", "健康 功能评分", "健康功能nps"],
    # "血压洞察NPS": ["血压洞察nps"],
    # "AI Partner": ["ai partner", "ringconn partner"],
    # "模块NPS提交弹窗": ["模块nps提交弹窗", "完成弹窗", "感谢您的反馈"],
    # "超出字符限制弹窗": ["超出字符限制"],
}
EXPECTED_MODULE_SEQUENCE: List[str] = list(EXPECTED_MODULE_CANONICALS.keys())


class ModuleMatcher:
    """模块匹配器，负责模块名称规范化、去重和位置查找"""

    def __init__(self, normalize_func: callable):
        """
        初始化模块匹配器

        Args:
            normalize_func: 文本标准化函数
        """
        self._normalize_identifier = normalize_func
        # 缓存其他模块的标识符，避免重复计算
        self._cached_other_module_tokens: Optional[Dict[str, List[str]]] = None

    def _ensure_other_module_tokens_cache(self) -> None:
        """
        确保其他模块标识符缓存已初始化

        注意：如果 EXPECTED_MODULE_CANONICALS 为空，此缓存也会为空
        这是正常的，系统会完全依赖 LLM 提取的模块进行边界检测
        """
        if self._cached_other_module_tokens is None:
            self._cached_other_module_tokens = {}
            # 只有当配置了 EXPECTED_MODULE_CANONICALS 时才初始化缓存
            if EXPECTED_MODULE_CANONICALS:
                for name in EXPECTED_MODULE_SEQUENCE:
                    normalized_name = self._normalize_identifier(name)
                    tokens = [normalized_name]
                    # 添加别名
                    aliases = EXPECTED_MODULE_CANONICALS.get(name, [])
                    for alias in aliases:
                        normalized_alias = self._normalize_identifier(alias)
                        if normalized_alias and normalized_alias not in tokens:
                            tokens.append(normalized_alias)
                    self._cached_other_module_tokens[normalized_name] = tokens

    def get_module_tokens(self, module_name: str) -> tuple[str, str, List[str], List[str]]:
        """
        获取模块的规范化标识符和令牌

        Returns:
            (canonical, normalized_current, anchor_tokens, other_tokens)
        """
        canonical = self.map_to_canonical(module_name) or module_name
        normalized_current = self._normalize_identifier(canonical)
        normalized_aliases = [
            self._normalize_identifier(alias) for alias in EXPECTED_MODULE_CANONICALS.get(canonical, [])
        ]
        anchor_tokens = [token for token in [normalized_current, *normalized_aliases] if token]

        # 确保缓存已初始化
        self._ensure_other_module_tokens_cache()
        assert self._cached_other_module_tokens is not None  # 类型检查辅助

        # 获取所有其他模块的标识符
        other_tokens = []
        for name in EXPECTED_MODULE_SEQUENCE:
            normalized_name = self._normalize_identifier(name)
            tokens = self._cached_other_module_tokens.get(normalized_name, [])
            for token in tokens:
                if token != normalized_current:
                    other_tokens.append(token)

        return canonical, normalized_current, anchor_tokens, other_tokens

    @staticmethod
    def is_strong_keyword(keyword: Optional[str]) -> bool:
        """判断关键词是否足够强（不是通用词）"""
        if not keyword:
            return False
        stripped = keyword.strip()
        if len(stripped) < 3:
            return False
        generic_tokens = {"功能", "模块", "系统", "页面", "按钮", "评分", "提交", "关闭"}
        return stripped not in generic_tokens

    def map_to_canonical(self, name: str) -> Optional[str]:
        """
        将模块名称映射到规范名称。

        修复：避免误匹配，例如 "模块NPS提交弹窗" 不应该匹配到 "功能NPS" 的别名 "模块nps"
        """
        normalized_name = self._normalize_identifier(name)
        if not normalized_name:
            return None

        # 第一轮：完全匹配（最精确）
        for canonical, aliases in EXPECTED_MODULE_CANONICALS.items():
            normalized_canonical = self._normalize_identifier(canonical)
            if normalized_canonical == normalized_name:
                return canonical

            for alias in aliases:
                normalized_alias = self._normalize_identifier(alias)
                if normalized_alias == normalized_name:
                    return canonical

        # 第二轮：检查规范化后的名称是否以规范名称开头（作为前缀匹配）
        # 但需要确保剩余部分很短，避免误匹配
        # 例如 "功能nps" 应该匹配 "功能NPS"，但 "模块nps提交弹窗" 不应该匹配 "功能NPS"
        for canonical, aliases in EXPECTED_MODULE_CANONICALS.items():
            normalized_canonical = self._normalize_identifier(canonical)

            # 如果规范名称是输入名称的开头
            if normalized_canonical and normalized_name.startswith(normalized_canonical):
                remaining = normalized_name[len(normalized_canonical):]
                # 如果剩余部分很短（<=2个字符），可能是匹配
                # 例如 "功能nps" 匹配 "功能NPS"（剩余为空）
                if len(remaining) <= 2:
                    return canonical

            # 检查别名（同样的逻辑）
            for alias in aliases:
                normalized_alias = self._normalize_identifier(alias)
                if normalized_alias and normalized_name.startswith(normalized_alias):
                    remaining = normalized_name[len(normalized_alias):]
                    if len(remaining) <= 2:
                        return canonical

        # 第三轮：如果名称包含规范名称，但需要确保是独立词（前后有足够边界）
        # 只在规范名称足够长（>=5字符）时才使用，避免短词误匹配
        for canonical, aliases in EXPECTED_MODULE_CANONICALS.items():
            normalized_canonical = self._normalize_identifier(canonical)
            if normalized_canonical and len(normalized_canonical) >= 5:
                if normalized_canonical in normalized_name:
                    idx = normalized_name.find(normalized_canonical)
                    if idx >= 0:
                        before = normalized_name[:idx]
                        after = normalized_name[idx + len(normalized_canonical):]
                        # 如果前后都是边界或很短（<=1个字符），可能是匹配
                        if (not before or len(before) <= 1) and (not after or len(after) <= 1):
                            return canonical

        return None

    def find_first_occurrence_line(
        self,
        module_name: str,
        module_data: Dict[str, Any],
        doc_lines: List[str],
    ) -> int:
        """
        查找模块在文档中第一次出现的位置

        Returns:
            行号（0-based）
        """
        canonical = self.map_to_canonical(module_name)
        candidate_terms: List[str] = []

        if canonical:
            candidate_terms.append(canonical)
            candidate_terms.extend(EXPECTED_MODULE_CANONICALS.get(canonical, []))
        else:
            candidate_terms.append(module_name)

        # 优先级：模块名称 > keywords > exact_phrases
        # 模块名称已经在candidate_terms的开头，现在添加其他候选词
        # 注意：exact_phrases可能不够精确（如"Key TakeAwayMessage"在多个模块中都存在），所以优先级较低
        candidate_terms.extend(
            kw for kw in module_data.get("keywords", []) or [] if self.is_strong_keyword(kw)
        )
        # exact_phrases放在最后，因为它们可能不够精确
        candidate_terms.extend(module_data.get("exact_phrases", []) or [])

        # 自动检测文档头部结束位置
        header_end = RequirementCache._detect_header_end(doc_lines)

        # 第一轮：优先匹配作为独立标题出现的完整模块名称（单独一行或前后有空行）
        # 关键修复：优先匹配模块名称本身，而不是keywords或exact_phrases
        # 因为exact_phrases（如"Key TakeAwayMessage"）可能在多个模块中都存在，不够精确
        first_round_matches = []  # 存储所有找到的位置 (idx, term, priority)

        # 首先尝试匹配模块名称本身（优先级最高）
        normalized_module_name = self._normalize_identifier(module_name)
        for idx, line in enumerate(doc_lines):
            line_stripped = line.strip()
            normalized_line = self._normalize_identifier(line_stripped)

            # 优先检查Markdown格式的标题（如 ## 社交时差）
            markdown_match = MARKDOWN_HEADING_PATTERN.match(line_stripped)
            if markdown_match:
                heading_text = markdown_match.group(1).strip()
                normalized_heading = self._normalize_identifier(heading_text)
                # 如果Markdown标题文本匹配模块名称
                if normalized_heading == normalized_module_name:
                    first_round_matches.append((idx, module_name, 0))  # 优先级0（最高）
                    continue

            # 检查是否作为独立标题出现（整行完全匹配）
            if normalized_module_name == normalized_line:
                first_round_matches.append((idx, module_name, 0))  # 优先级0（最高）
            # 检查是否在行首作为标题出现（后面可能跟Banner、问卷等）
            elif normalized_line.startswith(normalized_module_name) and (
                idx == 0 or not doc_lines[idx - 1].strip() or
                idx + 1 >= len(doc_lines) or not doc_lines[idx + 1].strip()
            ):
                first_round_matches.append((idx, module_name, 0))  # 优先级0（最高）

        # 如果找到了模块名称的匹配，直接返回（不再尝试其他候选词）
        if first_round_matches:
            first_round_matches.sort(key=lambda x: (x[2], x[0]))  # 先按优先级，再按位置
            return first_round_matches[0][0]

        # 如果没有找到模块名称的匹配，尝试其他候选词（keywords和exact_phrases）
        sorted_terms = sorted(candidate_terms, key=lambda x: len(x or ""), reverse=True)
        for term in sorted_terms:
            if not term or term == module_name:  # 跳过模块名称（已经尝试过了）
                continue
            stripped_term = term.strip()
            if len(stripped_term) < ExtractionConfig.MIN_TERM_LENGTH:
                continue
            normalized_term = self._normalize_identifier(stripped_term)

            for idx, line in enumerate(doc_lines):
                line_stripped = line.strip()
                normalized_line = self._normalize_identifier(line_stripped)

                # 优先检查Markdown格式的标题（如 ## 标题）
                markdown_match = MARKDOWN_HEADING_PATTERN.match(line_stripped)
                if markdown_match:
                    heading_text = markdown_match.group(1).strip()
                    normalized_heading = self._normalize_identifier(heading_text)
                    # 如果Markdown标题文本匹配候选词
                    if normalized_heading == normalized_term:
                        first_round_matches.append((idx, term, 1))  # 优先级1（较低）
                        continue

                # 检查是否作为独立标题出现（整行完全匹配）
                if normalized_term == normalized_line:
                    first_round_matches.append((idx, term, 1))  # 优先级1（较低）
                # 检查是否在行首作为标题出现
                elif normalized_line.startswith(normalized_term) and (
                    idx == 0 or not doc_lines[idx - 1].strip() or
                    idx + 1 >= len(doc_lines) or not doc_lines[idx + 1].strip()
                ):
                    first_round_matches.append((idx, term, 1))  # 优先级1（较低）

        # 如果有找到的位置，选择优先级最高且最靠前的
        if first_round_matches:
            first_round_matches.sort(key=lambda x: (x[2], x[0]))  # 先按优先级，再按位置
            return first_round_matches[0][0]

        # 第二轮：匹配包含完整关键词的行，但跳过文档头部的通用描述
        # 按位置优先：优先匹配更靠前的关键词（按文档顺序）
        # 收集所有匹配位置，选择最靠前的
        found_positions = []  # 存储所有找到的位置 (idx, term, is_exact_match)
        for term in sorted_terms:
            if not term:
                continue
            stripped_term = term.strip()
            if len(stripped_term) < ExtractionConfig.MIN_TERM_LENGTH:
                continue
            normalized_term = self._normalize_identifier(stripped_term)

            for idx, line in enumerate(doc_lines):
                # 跳过文档头部的通用描述
                if idx < header_end:
                    continue
                line_stripped = line.strip()
                normalized_line = self._normalize_identifier(line_stripped)

                # 优先检查Markdown格式的标题（如 ## 标题）
                markdown_match = MARKDOWN_HEADING_PATTERN.match(line_stripped)
                if markdown_match:
                    heading_text = markdown_match.group(1).strip()
                    normalized_heading = self._normalize_identifier(heading_text)
                    # 如果Markdown标题文本匹配模块名称
                    if normalized_heading == normalized_term:
                        found_positions.append((idx, term, True))  # Markdown格式匹配，优先级最高
                        continue

                # 优先完整匹配，避免部分匹配（如"模块NPS"匹配到"功能NPS"）
                if normalized_term == normalized_line.strip():
                    found_positions.append((idx, term, True))  # 完全匹配，优先级最高
                # 如果包含完整关键词，也匹配（但要确保不是部分匹配）
                elif normalized_term in normalized_line and len(normalized_term) >= ExtractionConfig.MIN_PARTIAL_MATCH_LENGTH:
                    found_positions.append((idx, term, False))  # 部分匹配，优先级较低

        # 如果有找到的位置，优先选择最靠前的完全匹配，否则选择最靠前的部分匹配
        if found_positions:
            # 先按位置排序，再按匹配类型排序（完全匹配优先）
            found_positions.sort(key=lambda x: (x[0], not x[2]))
            return found_positions[0][0]

        # 第三轮：fallback到全文匹配（包括文档开头）
        normalized_anchors = [self._normalize_identifier(term) for term in candidate_terms if term]
        for idx, line in enumerate(doc_lines):
            normalized_line = self._normalize_identifier(line)
            if any(anchor and anchor in normalized_line for anchor in normalized_anchors):
                return idx
        return len(doc_lines) + 999  # 放在文档结尾之后

    def collect_phrase_from_doc(self, anchors: List[str], doc_lines: List[str]) -> str:
        """从文档中收集包含锚点的短语"""
        primary_terms = [anchor for anchor in anchors if anchor]
        for term in primary_terms:
            stripped = term.strip()
            if not stripped or len(stripped) < 3:
                continue
            for line in doc_lines:
                if stripped in line:
                    cleaned = line.strip()
                    cleaned = re.sub(r"^[\d一二三四五六七八九十]+\s*[\.、]\s*", "", cleaned)
                    return cleaned or line.strip()

        normalized_anchors = [self._normalize_identifier(anchor) for anchor in anchors if anchor]
        for line in doc_lines:
            normalized_line = self._normalize_identifier(line)
            if any(anchor and anchor in normalized_line for anchor in normalized_anchors):
                cleaned = line.strip()
                cleaned = re.sub(r"^[\d一二三四五六七八九十]+\s*[\.、]\s*", "", cleaned)
                return cleaned or line.strip()
        return ""
