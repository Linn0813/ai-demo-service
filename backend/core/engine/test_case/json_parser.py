"""JSON 解析工具，用于处理 LLM 返回的 JSON 响应"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from core.logger import log


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent.parent.parent.parent


def parse_json_with_fallback(json_str: str) -> Dict[str, Any]:
    """尝试多种策略解析 JSON，增强容错能力。"""

    # 策略1: 直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 策略2: 修复常见的 JSON 格式问题
    fixed = json_str

    # 2.1: 移除LLM模型特殊标记并修复被破坏的键名
    # 策略：先移除标记，再修复键名，避免误删

    # 第一步：移除所有标准格式的特殊标记 <|...|>
    fixed = re.sub(r'<\|[^|]*\|>', '', fixed)

    # 第二步：移除其他格式的特殊标记（如 <｜begin▁of▁... 等）
    # 使用更精确的匹配，确保不会移除键名中的有效字符
    # 匹配 <｜ 或 <| 开头的标记，直到遇到引号、冒号、换行或结束
    fixed = re.sub(r'<[｜|][^>":\n]*', '', fixed)

    # 第三步：修复被特殊标记破坏的键名
    # 处理各种可能的情况：
    # 1. "exact<｜...:" -> "exact_phrases":
    # 2. "exact>:" -> "exact_phrases":
    # 3. "exact" (后面没有冒号，需要添加) -> "exact_phrases":

    # 先处理有冒号的情况（匹配 "exact" 后面跟着非引号、非冒号字符直到冒号）
    fixed = re.sub(r'"exact[^":]*":', '"exact_phrases":', fixed)
    # 处理 "exact>:" 这种特殊情况（> 后面直接是冒号）
    # 匹配 "exact" 后面跟着 > 然后跟着 : 的模式
    fixed = re.sub(r'"exact>\s*:', '"exact_phrases":', fixed)
    # 处理 "exact" 后面直接是引号或换行的情况（标记被移除后留下的不完整键名）
    fixed = re.sub(r'"exact"\s*\n\s*:', '"exact_phrases":', fixed)
    fixed = re.sub(r'"exact"\s*:', '"exact_phrases":', fixed)

    # 2.2: 移除末尾多余的逗号
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)

    # 2.3: 单引号转双引号（键名）
    fixed = re.sub(r"'([^']*)':\s*", r'"\1": ', fixed)

    # 2.4: 单引号转双引号（字符串值）
    fixed = re.sub(r":\s*'([^']*)'(?=\s*[,}\]])", r': "\1"', fixed)

    # 2.5: 修复转义的双引号
    fixed = fixed.replace('\\"', '"')

    # 2.6: 修复未转义的控制字符
    fixed = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 策略3: 尝试提取并修复嵌套的 JSON 对象
    # 查找最外层的完整 JSON 对象
    brace_count = 0
    start_pos = -1
    for i, char in enumerate(fixed):
        if char == '{':
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                try:
                    return json.loads(fixed[start_pos:i+1])
                except json.JSONDecodeError:
                    pass

    # 策略4: 尝试修复缺失的引号（键名）
    # 匹配类似 key: value 的模式，如果 key 没有引号，添加引号
    fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 策略5: 尝试补全缺失的闭合括号
    # 统计未闭合的括号
    brace_count = fixed.count('{') - fixed.count('}')
    bracket_count = fixed.count('[') - fixed.count(']')

    # 如果缺少闭合括号，尝试补全
    if brace_count > 0 or bracket_count > 0:
        # 移除末尾可能的空白字符
        fixed_trimmed = fixed.rstrip()

        # 先补全数组的闭合括号
        if bracket_count > 0:
            fixed_trimmed += ']' * bracket_count

        # 再补全对象的闭合括号
        if brace_count > 0:
            fixed_trimmed += '}' * brace_count

        try:
            return json.loads(fixed_trimmed)
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        # 记录详细的错误信息以便调试
        log.error("JSON 解析失败，已尝试多种修复策略")
        log.debug("原始 JSON 片段（前500字符）: %s", json_str[:500])
        log.debug("最后尝试的修复版本（前500字符）: %s", fixed[:500])
        log.debug("JSON 解析错误: %s (位置: %s)", e.msg, e.pos)

        # 保存失败的 JSON 到文件以便调试（仅在开发环境）
        try:
            project_root = get_project_root()
            debug_dir = project_root / "data" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / "failed_json_response.txt"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write("=== 原始 JSON ===\n")
                f.write(json_str)
                f.write("\n\n=== 最后修复版本 ===\n")
                f.write(fixed)
                f.write(f"\n\n=== 错误信息 ===\n")
                f.write(f"错误: {e.msg}\n")
                f.write(f"位置: {e.pos}\n")
            log.debug("失败的 JSON 已保存到: %s", debug_file)
        except Exception:  # noqa: BLE001
            pass  # 忽略保存失败

        raise
