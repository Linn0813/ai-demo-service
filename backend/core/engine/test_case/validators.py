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
    required_fields = {"case_name", "description", "preconditions", "steps", "expected_result", "priority"}
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

        for field in required_fields - {"steps"}:
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                if field == "preconditions":
                    inferred_preconditions = infer_preconditions_from_steps(case.get("steps", []))
                    case["preconditions"] = inferred_preconditions
                    warnings.append(f"[{function_point}] 第{idx}条用例字段'{field}'已自动修复")
                else:
                    warnings.append(f"[{function_point}] 第{idx}条用例字段'{field}'为空或类型错误")

        steps = case.get("steps")
        if not isinstance(steps, list) or not steps or not all(isinstance(step, str) and step.strip() for step in steps):
            warnings.append(f"[{function_point}] 第{idx}条用例步骤列表为空或格式错误")

        combined_text = "".join([
            str(case.get("case_name", "")),
            case.get("description", ""),
            case.get("expected_result", ""),
            "".join(steps or []),
        ])
        if any(char in traditional_punctuation for char in combined_text):
            for field in ["case_name", "description", "expected_result"]:
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
        if expected_normalized in snippet_normalized:
            continue

        if skip_already_fixed:
            if case.get("_format_fixed", False):
                case.pop("_format_fixed", None)
                continue
            if expected_normalized in snippet_normalized or expected_normalized.replace(" ", "") in snippet_normalized.replace(" ", ""):
                continue

        expected_normalized_for_match = normalize_text(expected.replace(" ", ""))
        matched_line: Optional[str] = None

        expected_keywords = [kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2]

        for candidate in unique_candidates:
            candidate_normalized = normalize_text(candidate.replace(" ", ""))
            if expected_normalized_for_match == candidate_normalized:
                matched_line = candidate
                break

        if not matched_line:
            best_ratio = 0.0
            best_candidate = None

            for candidate in unique_candidates:
                candidate_normalized = normalize_text(candidate)
                ratio = difflib.SequenceMatcher(None, expected_normalized, candidate_normalized).ratio()

                keyword_bonus = 0.0
                if expected_keywords:
                    matched_keywords = sum(1 for kw in expected_keywords if kw in candidate_normalized)
                    keyword_bonus = (matched_keywords / len(expected_keywords)) * RepairConfig.KEYWORD_BONUS

                length_ratio = min(len(candidate), len(expected)) / max(len(candidate), len(expected)) if max(len(candidate), len(expected)) > 0 else 0
                length_bonus = length_ratio * 0.05

                core_keyword_bonus = 0.0
                if expected_keywords and len(expected_keywords) >= 2:
                    core_keywords = expected_keywords[:3]
                    matched_core = sum(1 for kw in core_keywords if kw in candidate_normalized)
                    if matched_core >= 2:
                        core_keyword_bonus = RepairConfig.CORE_KEYWORD_BONUS

                final_ratio = ratio + keyword_bonus + length_bonus + core_keyword_bonus

                if final_ratio > best_ratio:
                    best_ratio = final_ratio
                    best_candidate = candidate

            if best_candidate and best_ratio >= RepairConfig.SIMILARITY_THRESHOLD:
                matched_line = best_candidate

        if matched_line and matched_line != expected:
            already_logged = any(
                f"第{idx}条" in log_text and ("已自动替换" in log_text or "已修复格式" in log_text)
                for log_text in repair_logs
            )
            if not already_logged:
                case["expected_result"] = matched_line
                display_text = matched_line if len(matched_line) <= 100 else matched_line[:97] + "..."
                repair_logs.append(f"[{function_point}] 第{idx}条预期结果已自动替换为原文: {display_text}")
            continue

        if not matched_line and expected_keywords:
            for candidate in unique_candidates:
                candidate_normalized = normalize_text(candidate)
                matched_count = sum(1 for kw in expected_keywords if kw in candidate_normalized)
                if matched_count >= max(2, len(expected_keywords) // 2):
                    core_words = [kw for kw in expected_keywords if len(kw) >= 2]
                    matched_core = sum(1 for word in core_words if word in candidate_normalized)
                    if matched_core >= len(core_words) * 0.5:
                        matched_line = candidate
                        break

            if matched_line and matched_line != expected:
                already_logged = any(
                    f"第{idx}条" in log_text and ("已自动替换" in log_text or "已修复格式" in log_text)
                    for log_text in repair_logs
                )
                if not already_logged:
                    case["expected_result"] = matched_line
                    display_text = matched_line if len(matched_line) <= 100 else matched_line[:97] + "..."
                    repair_logs.append(
                        f"[{function_point}] 第{idx}条预期结果已自动替换为原文（部分匹配）: {display_text}"
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
