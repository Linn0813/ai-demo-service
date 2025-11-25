"""生成结果校验与修复工具"""
from __future__ import annotations

import difflib
from typing import Callable, Dict, List, Optional

from core.engine.base.config import RepairConfig
from core.logger import log

# 复用正则
from core.engine.base.config import (
    RE_EXTRACT_KEYWORDS,
    RE_SPLIT_PHRASES,
    RE_SENTENCE_SPLIT,
    RE_TITLE_LINE,
)


def infer_preconditions_from_steps(steps: List[str]) -> str:
    """从测试步骤推断前置条件。"""

    if not steps or not isinstance(steps, list) or len(steps) == 0:
        return RepairConfig.PRECONDITIONS_DEFAULT

    first_step = steps[0].strip() if steps[0] else ""
    if not first_step:
        return RepairConfig.PRECONDITIONS_DEFAULT

    preconditions = first_step.split("，")[0] if "，" in first_step else first_step
    preconditions = preconditions.split(",")[0] if "," in preconditions else preconditions

    if len(preconditions.strip()) < 5:
        return RepairConfig.PRECONDITIONS_DEFAULT

    return preconditions.strip()


def run_static_validation(
    function_point: str,
    test_cases: List[Dict],
    doc_snippet: str,
    normalize_text: Callable[[str], str],
    fix_traditional_punctuation: Callable[[str], str],
) -> List[str]:
    """对生成的测试用例进行静态校验，返回告警列表。"""

    warnings: List[str] = []
    required_fields = {"module_name", "case_name", "preconditions", "steps", "expected_result"}
    optional_fields = {"sub_module"}  # 可选字段
    traditional_punctuation = set("「」『』﹁﹂﹃﹄﹙﹚﹛﹜﹝﹞﹃﹫﹬﹭«»")

    if not isinstance(test_cases, list):
        warnings.append(f"[{function_point}] 测试用例数据格式异常，非列表")
        return warnings

    for idx, case in enumerate(test_cases, 1):
        if not isinstance(case, Dict):
            warnings.append(f"[{function_point}] 第{idx}条用例不是字典类型")
            continue

        missing = required_fields - set(case.keys())
        if missing:
            warnings.append(f"[{function_point}] 第{idx}条用例缺少字段: {', '.join(sorted(missing))}")

        # 确保sub_module字段存在（如果不存在，设置为空字符串）
        if "sub_module" not in case:
            case["sub_module"] = ""

        for field in required_fields - {"steps", "preconditions"}:
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                warnings.append(f"[{function_point}] 第{idx}条用例字段'{field}'为空或类型错误")
        
        # 处理preconditions字段（可以为空字符串）
        preconditions = case.get("preconditions")
        if preconditions is None:
            # 如果preconditions不存在，尝试从steps推断
            inferred_preconditions = infer_preconditions_from_steps(case.get("steps", []))
            case["preconditions"] = inferred_preconditions
            warnings.append(f"[{function_point}] 第{idx}条用例字段'preconditions'已自动修复")
        elif not isinstance(preconditions, str):
            case["preconditions"] = ""
            warnings.append(f"[{function_point}] 第{idx}条用例字段'preconditions'已自动修复为空字符串")

        steps = case.get("steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(step, str) and step.strip() for step in steps):
            warnings.append(f"[{function_point}] 第{idx}条用例步骤列表为空或格式错误")

        combined_text = "".join([
            str(case.get("module_name", "")),
            str(case.get("case_name", "")),
            case.get("expected_result", ""),
            "".join(steps or []),
        ])
        if any(char in traditional_punctuation for char in combined_text):
            for field in ["module_name", "case_name", "expected_result"]:
                if field in case and isinstance(case[field], str):
                    case[field] = fix_traditional_punctuation(case[field])
            if steps and isinstance(steps, list):
                for i, step in enumerate(steps):
                    if isinstance(step, str):
                        steps[i] = fix_traditional_punctuation(step)
            warnings.append(f"[{function_point}] 第{idx}条用例已自动修复繁体标点")

        if doc_snippet:
            expected = case.get("expected_result", "")
            if expected:
                if len(expected) > RepairConfig.FORMAT_FIX_MIN_LENGTH and not any(p in expected for p in ["。", "！", "？", ".", "!", "?", "\n"]):
                    expected_keywords = [kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2][:RepairConfig.FORMAT_FIX_KEYWORD_COUNT + 2]
                    if expected_keywords:
                        snippet_lines = [line.strip() for line in doc_snippet.splitlines() if line.strip()]
                        matched_sentences = []
                        for line in snippet_lines:
                            matched_count = sum(1 for kw in expected_keywords[:RepairConfig.FORMAT_FIX_KEYWORD_COUNT] if kw in line)
                            if matched_count >= max(1, RepairConfig.FORMAT_FIX_KEYWORD_COUNT - 1):
                                matched_sentences.append(line)
                        if matched_sentences:
                            original_length = len(case["expected_result"])
                            best_match = min(matched_sentences, key=lambda s: abs(len(s) - original_length))
                            case["expected_result"] = best_match
                            case["_format_fixed"] = True
                            warnings.append(f"[{function_point}] 第{idx}条预期结果已自动修复格式问题")

                expected_normalized = normalize_text(expected.replace("\n", " ").strip())
                snippet_normalized = normalize_text(doc_snippet.replace("\n", " "))

                if expected_normalized not in snippet_normalized:
                    expected_no_space = expected_normalized.replace(" ", "")
                    snippet_no_space = snippet_normalized.replace(" ", "")

                    if expected_no_space not in snippet_no_space:
                        key_phrases = [phrase for phrase in RE_SPLIT_PHRASES.split(expected) if len(phrase.strip()) >= RepairConfig.MIN_PHRASE_LENGTH]
                        found_any = False
                        for phrase in key_phrases[:RepairConfig.KEY_PHRASE_COUNT]:
                            phrase_normalized = normalize_text(phrase.strip())
                            if (
                                phrase_normalized in snippet_normalized
                                or phrase_normalized.replace(" ", "") in snippet_no_space
                                or any(phrase_normalized in normalize_text(line) for line in doc_snippet.splitlines())
                            ):
                                found_any = True
                                break

                        if not found_any:
                            expected_keywords = [kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2]
                            if expected_keywords:
                                matched_keywords = sum(1 for kw in expected_keywords[:5] if normalize_text(kw) in snippet_normalized)
                                if matched_keywords >= max(1, len(expected_keywords[:5]) // 2):
                                    found_any = True

                        if not found_any:
                            warnings.append(f"[{function_point}] 第{idx}条预期结果未在原文中找到，需人工确认")

    return warnings


def _detect_generic_expected_result(expected: str) -> bool:
    """
    检测是否为通用预期结果（通用化检测，不包含特定需求）。
    
    Args:
        expected: 预期结果文本
        
    Returns:
        如果是通用预期结果，返回True；否则返回False
    """
    expected_normalized = expected.strip().lower()
    
    # 检查是否匹配通用模式
    for pattern in RepairConfig.GENERIC_EXPECTED_PATTERNS:
        if pattern in expected_normalized:
            return True
    
    # 检查是否为过于简短的描述（可能是通用结果）
    if len(expected_normalized) <= 8 and any(kw in expected_normalized for kw in ['正确', '正常', '成功', '通过', '符合']):
        return True
    
    return False


def _find_best_match_from_doc(
    expected: str,
    doc_snippet: str,
    normalize_text: Callable[[str], str],
    case_name: str = "",
    steps: List[str] = None,
) -> Optional[str]:
    """
    从需求文档中查找最佳匹配的预期结果（通用化算法）。
    
    Args:
        expected: 当前预期结果
        doc_snippet: 需求文档片段
        normalize_text: 文本标准化函数
        case_name: 用例名称（用于提取关键词）
        steps: 测试步骤（用于提取关键词）
        
    Returns:
        找到的最佳匹配文本，如果未找到则返回None
    """
    if not doc_snippet or not expected:
        return None
    
    normalized_snippet = doc_snippet.replace("\n", "")
    snippet_lines = [line.strip() for line in doc_snippet.splitlines() if line.strip()]

    snippet_sentences: List[str] = []
    for line in snippet_lines:
        parts = [part.strip() for part in RE_SENTENCE_SPLIT.split(line) if part.strip()]
        snippet_sentences.extend(parts if parts else [line])

    seen = set()
    unique_candidates: List[str] = []
    for candidate in snippet_lines + snippet_sentences:
        if (
            len(candidate) >= RepairConfig.MIN_SENTENCE_LENGTH
            and candidate not in seen
            and not RE_TITLE_LINE.match(candidate)
            and len(RE_EXTRACT_KEYWORDS.sub('', candidate)) >= RepairConfig.MIN_VALID_CHARS
        ):
            seen.add(candidate)
            unique_candidates.append(candidate)
    
    if not unique_candidates:
        return None
    
    expected_normalized = normalize_text(expected.replace("\n", " "))
    snippet_normalized = normalize_text(normalized_snippet)
    
    # 提取关键词（从预期结果、用例名称、测试步骤中提取）
    all_keywords = []
    if expected:
        all_keywords.extend([kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2])
    if case_name:
        all_keywords.extend([kw for kw in RE_EXTRACT_KEYWORDS.split(case_name) if len(kw) >= 2])
    if steps:
        for step in steps:
            all_keywords.extend([kw for kw in RE_EXTRACT_KEYWORDS.split(step) if len(kw) >= 2])
    
    # 去重并保留核心关键词
    unique_keywords = list(dict.fromkeys(all_keywords))[:10]  # 保留前10个关键词
    
    best_match = None
    best_score = 0.0
    
    for candidate in unique_candidates:
        candidate_normalized = normalize_text(candidate)
        
        # 计算相似度
        ratio = difflib.SequenceMatcher(None, expected_normalized, candidate_normalized).ratio()
        
        # 关键词匹配加分
        keyword_bonus = 0.0
        if unique_keywords:
            matched_keywords = sum(1 for kw in unique_keywords if kw in candidate_normalized)
            keyword_bonus = (matched_keywords / len(unique_keywords)) * RepairConfig.KEYWORD_BONUS
        
        # 核心关键词匹配加分
        core_keyword_bonus = 0.0
        if unique_keywords and len(unique_keywords) >= 2:
            core_keywords = unique_keywords[:3]
            matched_core = sum(1 for kw in core_keywords if kw in candidate_normalized)
            if matched_core >= 2:
                core_keyword_bonus = RepairConfig.CORE_KEYWORD_BONUS
        
        # 长度相似度加分
        length_ratio = min(len(candidate), len(expected)) / max(len(candidate), len(expected)) if max(len(candidate), len(expected)) > 0 else 0
        length_bonus = length_ratio * 0.05
        
        # 最终得分
        final_score = ratio + keyword_bonus + length_bonus + core_keyword_bonus
        
        if final_score > best_score:
            best_score = final_score
            best_match = candidate
    
    # 如果得分达到阈值，返回最佳匹配
    if best_match and best_score >= RepairConfig.SIMILARITY_THRESHOLD:
        return best_match
    
    # 如果相似度不够，尝试基于关键词的部分匹配
    if unique_keywords:
        for candidate in unique_candidates:
            candidate_normalized = normalize_text(candidate)
            matched_count = sum(1 for kw in unique_keywords if kw in candidate_normalized)
            if matched_count >= max(2, len(unique_keywords) // 2):
                core_words = [kw for kw in unique_keywords if len(kw) >= 2]
                matched_core = sum(1 for word in core_words if word in candidate_normalized)
                if matched_core >= len(core_words) * 0.5:
                    return candidate
    
    return None


def repair_expected_results(
    function_point: str,
    test_cases: List[Dict],
    doc_snippet: str,
    normalize_text: Callable[[str], str],
    fix_traditional_punctuation: Callable[[str], str],
    skip_already_fixed: bool = False,
) -> List[str]:
    """当expected_result与原文不完全匹配时，尝试自动纠正为文档原句。"""

    repair_logs: List[str] = []

    if not doc_snippet or not isinstance(test_cases, list):
        return repair_logs

    normalized_snippet = doc_snippet.replace("\n", "")
    snippet_lines = [line.strip() for line in doc_snippet.splitlines() if line.strip()]

    snippet_sentences: List[str] = []
    for line in snippet_lines:
        parts = [part.strip() for part in RE_SENTENCE_SPLIT.split(line) if part.strip()]
        snippet_sentences.extend(parts if parts else [line])

    seen = set()
    unique_candidates: List[str] = []
    for candidate in snippet_lines + snippet_sentences:
        if (
            len(candidate) >= RepairConfig.MIN_SENTENCE_LENGTH
            and candidate not in seen
            and not RE_TITLE_LINE.match(candidate)
            and len(RE_EXTRACT_KEYWORDS.sub('', candidate)) >= RepairConfig.MIN_VALID_CHARS
        ):
            seen.add(candidate)
            unique_candidates.append(candidate)

    for idx, case in enumerate(test_cases, 1):
        if not isinstance(case, Dict):
            continue
        expected = case.get("expected_result")
        if not isinstance(expected, str) or not expected.strip():
            continue

        original_expected = expected
        expected = fix_traditional_punctuation(expected)
        if expected != original_expected:
            case["expected_result"] = expected
            repair_logs.append(f"[{function_point}] 第{idx}条预期结果已修复繁体标点")

        expected_normalized = normalize_text(expected.replace("\n", " "))
        snippet_normalized = normalize_text(normalized_snippet)
        
        # 检查是否已经在原文中
        if expected_normalized in snippet_normalized:
            continue

        if skip_already_fixed:
            if case.get("_format_fixed", False):
                case.pop("_format_fixed", None)
                continue
            if expected_normalized in snippet_normalized or expected_normalized.replace(" ", "") in snippet_normalized.replace(" ", ""):
                continue

        # 检测是否为通用预期结果
        is_generic = _detect_generic_expected_result(expected)
        
        # 提取用例信息用于匹配
        case_name = case.get("case_name", "")
        steps = case.get("steps", [])
        
        # 使用改进的匹配算法查找最佳匹配
        matched_line = _find_best_match_from_doc(
            expected, doc_snippet, normalize_text, case_name, steps
        )
        
        # 如果是通用预期结果，强制要求找到匹配
        if is_generic and not matched_line:
            # 尝试基于用例名称和步骤查找匹配
            if case_name or steps:
                # 使用用例名称和步骤中的关键词重新查找
                matched_line = _find_best_match_from_doc(
                    case_name + " " + " ".join(steps) if steps else case_name,
                    doc_snippet,
                    normalize_text,
                    case_name,
                    steps
                )
        
        # 如果找到匹配，替换预期结果
        if matched_line and matched_line != expected:
            already_logged = any(
                f"第{idx}条" in log_text and ("已自动替换" in log_text or "已修复格式" in log_text)
                for log_text in repair_logs
            )
            if not already_logged:
                case["expected_result"] = matched_line
                display_text = matched_line if len(matched_line) <= 100 else matched_line[:97] + "..."
                if is_generic:
                    repair_logs.append(f"[{function_point}] 第{idx}条通用预期结果已自动替换为原文: {display_text}")
                else:
                    repair_logs.append(f"[{function_point}] 第{idx}条预期结果已自动替换为原文: {display_text}")
            continue
        
        # 如果未找到匹配且是通用预期结果，记录警告
        if is_generic and not matched_line:
            repair_logs.append(
                f"[{function_point}] 第{idx}条用例使用了通用预期结果但未在原文中找到匹配，需人工确认"
            )

    return repair_logs


def clean_test_cases(test_cases: List[Dict]) -> List[Dict]:
    """清理测试用例中的临时标记字段。"""

    cleaned = []
    for case in test_cases:
        if isinstance(case, dict):
            cleaned_case = {k: v for k, v in case.items() if not k.startswith("_")}
            cleaned.append(cleaned_case)
        else:
            cleaned.append(case)
    return cleaned
