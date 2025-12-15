# encoding: utf-8
"""启发式模块提取相关功能"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from shared.logger import log


class HeuristicExtractor:
    """启发式提取器，在LLM失败时基于规则提取模块"""

    @staticmethod
    def extract_modules(requirement_doc: str) -> List[Dict[str, Any]]:
        """
        在LLM失败时，基于标题和关键词的启发式提取

        Args:
            requirement_doc: 需求文档内容

        Returns:
            提取的模块列表
        """
        lines = requirement_doc.splitlines()
        candidates: List[Tuple[int, str]] = []
        seen: set[str] = set()

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # 使用更严格的过滤规则
            if HeuristicExtractor._looks_like_module_heading(stripped, idx, lines) and stripped not in seen:
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
                if HeuristicExtractor._looks_like_module_heading(desc_line, idx + offset, lines):
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
                "keywords": HeuristicExtractor._extract_keywords_from_heading(heading),
                "exact_phrases": [heading],
                "section_hint": heading[:10] if len(heading) > 10 else heading,
            })

        log.info("启发式提取识别到 %s 个候选模块，过滤后保留 %s 个", len(candidates), len(modules))
        return modules

    @staticmethod
    def _looks_like_module_heading(text: str, line_idx: int, all_lines: List[str]) -> bool:
        """
        判断文本是否像功能模块标题（更严格的规则）

        Args:
            text: 待判断的文本
            line_idx: 行索引
            all_lines: 所有行的列表

        Returns:
            如果像模块标题返回True，否则返回False
        """
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
        """
        从标题中提取关键词

        Args:
            heading: 标题文本

        Returns:
            关键词列表
        """
        tokens = [token for token in re.split(r"[^A-Za-z0-9\u4e00-\u9fa5]+", heading) if token]
        keywords = [token for token in tokens if len(token) >= 2]

        if not keywords:
            keywords.append(heading)

        return keywords[:5]

