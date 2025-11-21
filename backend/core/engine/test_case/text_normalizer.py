"""文本标准化和需求文档缓存工具"""
from __future__ import annotations

import difflib
import re
from typing import Dict, List, Optional, Tuple

from core.engine.base.config import TRADITIONAL_TO_SIMPLIFIED_PUNCTUATION, ExtractionConfig
from core.logger import log

# 预编译的正则表达式（性能优化）
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$")
MARKDOWN_HEADING_PATTERN_1_2 = re.compile(r"^#{1,2}\s+(.+)$")


class RequirementCache:
    """需求文档缓存与辅助方法"""

    def __init__(self) -> None:
        self._cached_requirement_doc: Optional[str] = None
        self._cached_doc_lines: List[str] = []
        self._cached_normalized_lines: List[str] = []
        self._cached_sections: List[Tuple[int, str]] = []

    def prepare(self, requirement_doc: str) -> None:
        """缓存需求文档，避免重复计算。"""

        if self._cached_requirement_doc == requirement_doc:
            return

        self._cached_requirement_doc = requirement_doc
        self._cached_doc_lines = requirement_doc.splitlines()
        self._cached_normalized_lines = [self.normalize_text(line) for line in self._cached_doc_lines]
        self._cached_sections = self._detect_sections(self._cached_doc_lines)

    @staticmethod
    def normalize_text(text: str) -> str:
        """标准化文本用于匹配。"""
        # 统一使用相同的正则表达式模式
        return re.sub(r'[\s`~!@#$%^&*()_\-+=\[\]{}|\\;:\'",.<>/?·！￥…（）—【】、；：" "''《》？]', "", text or "").lower()

    @staticmethod
    def fix_traditional_punctuation(text: str) -> str:
        """修复所有繁体标点为简体标点。"""

        if not text:
            return text
        result = text
        for trad, simp in TRADITIONAL_TO_SIMPLIFIED_PUNCTUATION.items():
            result = result.replace(trad, simp)
        return result

    def _detect_sections(self, lines: List[str]) -> List[Tuple[int, str]]:
        """检测文档中的章节标题，用于后续截取上下文。"""

        sections: List[Tuple[int, str]] = []
        heading_pattern = re.compile(r"^(?:[A-Za-z\u4e00-\u9fff【].*)$")
        bullet_prefix = re.compile(r"^\s*(?:[-*•●◦·①②③④⑤⑥⑦⑧⑨⑩\d]+\s)")

        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line or len(line) > 80:
                continue
            if bullet_prefix.match(line):
                continue

            # 优先检查Markdown格式的标题
            markdown_match = MARKDOWN_HEADING_PATTERN.match(line)
            if markdown_match:
                # 提取标题文本（去掉#标记）
                heading_text = markdown_match.group(1).strip()
                sections.append((idx, heading_text))
                continue

            # 检查普通标题
            if heading_pattern.match(line):
                sections.append((idx, line))

        if not sections or sections[0][0] != 0:
            sections.insert(0, (0, "__document_start__"))
        return sections

    @staticmethod
    def _detect_content_end(lines: List[str]) -> int:
        """
        检测文档实际内容结束位置，排除元信息部分

        通过识别常见的元信息标记（如"上线后"、"多语言文档"、"设计稿"、"审批"等）
        来确定文档实际内容的结束位置。

        Returns:
            实际内容结束的行号（不包含元信息部分）
        """
        if not lines:
            return 0

        # 从后往前查找，找到第一个元信息标记
        for idx in range(len(lines) - 1, max(0, len(lines) - 50), -1):  # 只检查最后50行
            line = lines[idx].strip()
            if not line:
                continue

            # 检查是否是元信息标记（一级或二级标题，且包含元信息关键词）
            is_metadata = False
            if line.startswith("# "):  # 一级标题
                for keyword in ExtractionConfig.METADATA_SECTION_KEYWORDS:
                    if keyword in line:
                        is_metadata = True
                        log.debug("检测到元信息部分: 第%d行 '%s'", idx + 1, line)
                        break
            elif line.startswith("## "):  # 二级标题
                for keyword in ExtractionConfig.METADATA_SECTION_KEYWORDS:
                    if keyword in line:
                        is_metadata = True
                        log.debug("检测到元信息部分: 第%d行 '%s'", idx + 1, line)
                        break

            if is_metadata:
                # 找到元信息开始位置，返回之前的位置
                return idx

        # 没有找到元信息标记，返回文档末尾
        return len(lines)

    @staticmethod
    def _detect_header_end(lines: List[str]) -> int:
        """自动检测文档头部结束位置（通用描述部分）。

        通过分析文档结构特征（如第一个主要章节标题、第一个列表项等）
        来确定文档头部的结束位置。
        """
        if not ExtractionConfig.AUTO_DETECT_HEADER_LINES:
            return ExtractionConfig.MIN_HEADER_LINES

        # 查找第一个明显的章节标题（通常是独立一行，前后有空行）
        heading_pattern = re.compile(r"^[A-Za-z\u4e00-\u9fff【].*$")
        bullet_pattern = re.compile(r"^\s*(?:[-*•●◦·①②③④⑤⑥⑦⑧⑨⑩\d]+\s)")

        max_check = min(ExtractionConfig.MAX_HEADER_LINES, len(lines))
        for idx in range(ExtractionConfig.MIN_HEADER_LINES, max_check):
            line = lines[idx].strip()
            if not line:
                continue

            # 如果找到明显的章节标题（独立一行，前后有空行或文档开始）
            if heading_pattern.match(line) and not bullet_pattern.match(line):
                # 检查前后是否有空行或是否是文档开始
                prev_empty = idx == 0 or not lines[idx - 1].strip()
                next_empty = idx + 1 >= len(lines) or not lines[idx + 1].strip()

                if prev_empty or next_empty:
                    return idx

        # 如果没找到明显的章节标题，返回配置的最大值
        return min(ExtractionConfig.MAX_HEADER_LINES, len(lines))

    def _locate_section_window(self, line_index: int, extra_before: int = 20, extra_after: int = 80) -> Tuple[int, int]:
        """根据章节信息和额外上下文，计算需要截取的起止行号。"""

        if not self._cached_sections:
            start = max(0, line_index - extra_before)
            end = min(len(self._cached_doc_lines), line_index + extra_after)
            return start, end

        start = 0
        end = len(self._cached_doc_lines)

        for idx, (section_line, _) in enumerate(self._cached_sections):
            if section_line <= line_index:
                start = section_line
                if idx + 1 < len(self._cached_sections):
                    end = self._cached_sections[idx + 1][0]
                else:
                    end = len(self._cached_doc_lines)
            else:
                break

        start = max(0, start - extra_before)
        end = min(len(self._cached_doc_lines), end + extra_after)
        return start, end

    def extract_relevant_section(self, requirement_doc: str, target: str, fp_data: Optional[Dict] = None) -> str:
        """提取与目标文本相关的需求文档片段。"""

        self.prepare(requirement_doc)
        candidate_indices: List[int] = []

        # 如果有定位线索，优先使用
        if fp_data:
            exact_phrases = fp_data.get("exact_phrases", [])
            for phrase in exact_phrases:
                if not phrase:
                    continue
                normalized_phrase = self.normalize_text(phrase)
                for idx, normalized_line in enumerate(self._cached_normalized_lines):
                    if normalized_phrase and normalized_phrase in normalized_line:
                        candidate_indices.append(idx)
                        break

            if not candidate_indices:
                keywords = fp_data.get("keywords", [])
                if keywords:
                    filtered_keywords = []
                    for keyword in keywords:
                        if len(keyword.strip()) < 2 or keyword.lower() in ['关闭', '操作', '显示', '点击', '按钮']:
                            continue
                        filtered_keywords.append(keyword)

                    if filtered_keywords:
                        min_match_count = max(1, len(filtered_keywords) // 2)
                        for idx, normalized_line in enumerate(self._cached_normalized_lines):
                            line_text = normalized_line.lower()
                            matched_count = sum(1 for keyword in filtered_keywords if keyword.lower() in line_text)
                            if matched_count >= min_match_count:
                                candidate_indices.append(idx)
                        if candidate_indices:
                            log.info("  ✓ 使用关键词匹配找到 %s 个位置", len(candidate_indices))

            if candidate_indices and fp_data.get("section_hint"):
                section_hint = fp_data.get("section_hint", "").lower()
                section_indices = [idx for idx, line in enumerate(self._cached_doc_lines) if section_hint in line.lower()]
                if section_indices:
                    filtered_indices = []
                    for candidate_idx in candidate_indices:
                        for section_idx in section_indices:
                            if section_idx <= candidate_idx < section_idx + 50:
                                filtered_indices.append(candidate_idx)
                                break
                    if filtered_indices:
                        candidate_indices = filtered_indices

            if candidate_indices:
                log.info("  ✓ 使用AI定位线索找到 %s 个匹配位置", len(candidate_indices))

        # 回退策略
        if not candidate_indices:
            normalized_target = self.normalize_text(target)
            if not normalized_target:
                log.warning("  ⚠ 目标'%s'无法归一化，使用原始文档片段", target)
                return requirement_doc[:ExtractionConfig.FALLBACK_SNIPPET_LENGTH] if len(requirement_doc) > ExtractionConfig.FALLBACK_SNIPPET_LENGTH else requirement_doc

            for idx, normalized_line in enumerate(self._cached_normalized_lines):
                if normalized_target and normalized_target in normalized_line:
                    candidate_indices.append(idx)

            if not candidate_indices:
                tokens = [self.normalize_text(token) for token in re.split(r"[、，,;；：:（）()\s-]+", target) if token.strip()]
                strong_tokens = [token for token in tokens if len(token) >= 2]
                if strong_tokens:
                    for idx, normalized_line in enumerate(self._cached_normalized_lines):
                        if all(token in normalized_line for token in strong_tokens):
                            candidate_indices.append(idx)

            if not candidate_indices and self._cached_normalized_lines:
                ratios = [
                    (
                        difflib.SequenceMatcher(
                            None,
                            normalized_target,
                            normalized_line,
                        ).ratio(),
                        idx,
                    )
                    for idx, normalized_line in enumerate(self._cached_normalized_lines)
                    if normalized_line
                ]
                if ratios:
                    best_ratio, best_idx = max(ratios, key=lambda item: item[0])
                    if best_ratio >= ExtractionConfig.FUZZY_MATCH_THRESHOLD:
                        candidate_indices.append(best_idx)

        if not candidate_indices:
            log.info("  ⚠ 未找到包含'%s'的内容，使用原文档前%s字符", target, ExtractionConfig.FALLBACK_SNIPPET_LENGTH)
            return requirement_doc[:ExtractionConfig.FALLBACK_SNIPPET_LENGTH] if len(requirement_doc) > ExtractionConfig.FALLBACK_SNIPPET_LENGTH else requirement_doc

        if len(candidate_indices) > ExtractionConfig.MAX_MATCH_POSITIONS:
            log.info("  ⚠ 找到 %s 个匹配位置，尝试优化筛选...", len(candidate_indices))
            candidate_indices = candidate_indices[:ExtractionConfig.MAX_MATCH_POSITIONS]

        collected_indices: set[int] = set()
        for idx in candidate_indices:
            start, end = self._locate_section_window(idx)
            collected_indices.update(range(start, end))

        if not collected_indices:
            log.warning("  ⚠ 未能确定章节范围，使用匹配行附近内容")
            idx = candidate_indices[0]
            start = max(0, idx - ExtractionConfig.CONTEXT_BEFORE)
            end = min(len(self._cached_doc_lines), idx + ExtractionConfig.CONTEXT_AFTER)
            collected_indices.update(range(start, end))

        relevant_lines = [self._cached_doc_lines[i] for i in sorted(collected_indices)]
        relevant_section = "\n".join(relevant_lines).strip()

        if len(relevant_section) < ExtractionConfig.MIN_SNIPPET_LENGTH and candidate_indices:
            log.warning("  ⚠ 提取片段不足%s字符，自动扩展上下文", ExtractionConfig.MIN_SNIPPET_LENGTH)
            idx = candidate_indices[0]
            start = max(0, idx - ExtractionConfig.EXTENDED_CONTEXT_BEFORE)
            end = min(len(self._cached_doc_lines), idx + ExtractionConfig.EXTENDED_CONTEXT_AFTER)
            relevant_section = "\n".join(self._cached_doc_lines[start:end]).strip()

        log.info("  ✓ 提取到 %s 字符的相关内容（原文）", len(relevant_section))
        return relevant_section
