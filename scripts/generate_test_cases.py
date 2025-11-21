#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI测试用例生成脚本
功能：根据需求文档自动生成测试用例
作者: yuxiaoling
创建日期: 2025-11-11
"""

import argparse
import difflib
import json
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from colorama import Fore, init

# 初始化colorama（Windows兼容）
init(autoreset=True)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 预定义的模型配置（Ollama 可直接使用）
MODEL_PRESETS = {
    # DeepSeek 系列
    "deepseek-coder": {
        "model": "deepseek-coder:6.7b",
        "description": "DeepSeek Coder 6.7B - 代码能力强，适合测试用例生成",
        "recommended": True
    },
    "deepseek-chat": {
        "model": "deepseek-chat:6.7b",
        "description": "DeepSeek Chat 6.7B - 通用对话模型",
        "recommended": False
    },
    "deepseek-r1": {
        "model": "deepseek-r1:7b",
        "description": "DeepSeek R1 7B - 推理模型，适合复杂任务",
        "recommended": False
    },
    # Qwen 系列（推荐，中文能力强）
    "qwen2.5": {
        "model": "qwen2.5:7b",
        "description": "Qwen 2.5 7B - 中文能力强，通用对话（推荐）",
        "recommended": True
    },
    "qwen2.5-14b": {
        "model": "qwen2.5:14b",
        "description": "Qwen 2.5 14B - 更大参数版本，质量更高",
        "recommended": False
    },
    "qwen2.5-coder": {
        "model": "qwen2.5-coder:7b",
        "description": "Qwen 2.5 Coder 7B - 代码专用版本",
        "recommended": False
    },
    # ChatGLM 系列
    "chatglm3": {
        "model": "chatglm3:6b",
        "description": "ChatGLM3 6B - 清华对话模型",
        "recommended": False
    },
    # 其他模型（需要手动导入到 Ollama）
    "minimax": {
        "model": "minimax-text-01",  # 需要手动导入
        "description": "MiniMax Text-01 - 需要手动导入到 Ollama",
        "recommended": False
    },
    "kimi": {
        "model": "kimi-k2",  # 需要手动导入
        "description": "Kimi K2 - 需要手动导入到 Ollama",
        "recommended": False
    }
}

# ============================================================
# 配置区域 - 在这里修改设置
# ============================================================

# 模型选择（在代码中直接选择）
# 可选值：
#   - "deepseek-coder" (推荐，代码能力强)
#   - "qwen2.5" (推荐，中文能力强)
#   - "deepseek-chat" (通用对话)
#   - "deepseek-r1" (推理模型)
#   - "qwen2.5-14b" (更大参数版本)
#   - "qwen2.5-coder" (代码专用)
#   - "chatglm3" (清华对话模型)
#   - 或者直接写模型名称，如 "qwen2.5:7b"
SELECTED_MODEL = "qwen2.5"  # 在这里修改要使用的模型

# 默认配置
DEFAULT_CONFIG = {
    "llm_base_url": "http://localhost:11434",  # Ollama默认地址
    "default_model": "deepseek-coder:6.7b",
    "temperature": 0.7,
    "max_tokens": 8000,  # 大幅增加token数以支持生成更多测试用例
    "timeout": 600  # 增加超时时间到10分钟
}

# 默认需求文件路径（相对于脚本目录）
DEFAULT_REQUIREMENT_FILE = "example_requirement.txt"

# 测试模式：限制处理的功能点数量（用于快速测试，设为None或0表示处理所有功能点）
TEST_FUNCTION_POINTS_LIMIT = 4  # 测试时设为1，正式使用时设为None

# 默认输出目录
DEFAULT_OUTPUT_DIR = "generated_test_cases"

# 修复配置
class RepairConfig:
    """修复功能配置类（通用配置，不依赖特定业务）"""
    # 格式修复阈值
    FORMAT_FIX_MIN_LENGTH = 50
    FORMAT_FIX_KEYWORD_COUNT = 3

    # 相似度匹配阈值（降低阈值以提高匹配率）
    SIMILARITY_THRESHOLD = 0.6  # 从0.7降低到0.6，提高匹配率
    KEYWORD_BONUS = 0.15  # 从0.1增加到0.15，提高关键词匹配的权重

    # 候选句子过滤
    MIN_SENTENCE_LENGTH = 10
    MIN_VALID_CHARS = 5

    # 匹配检查
    KEY_PHRASE_COUNT = 3
    MIN_PHRASE_LENGTH = 5

    # preconditions修复
    PRECONDITIONS_DEFAULT = "满足测试前置条件"

# 文档提取配置
class ExtractionConfig:
    """文档提取相关配置"""
    # 回退策略：当找不到匹配时使用的文档片段长度
    FALLBACK_SNIPPET_LENGTH = 2000

    # 最小片段长度
    MIN_SNIPPET_LENGTH = 400

    # 上下文扩展范围
    CONTEXT_BEFORE = 80
    CONTEXT_AFTER = 200
    EXTENDED_CONTEXT_BEFORE = 100
    EXTENDED_CONTEXT_AFTER = 400

    # 章节窗口范围
    SECTION_WINDOW_BEFORE = 20
    SECTION_WINDOW_AFTER = 80

    # 匹配位置限制
    MAX_MATCH_POSITIONS = 10

    # 模糊匹配阈值
    FUZZY_MATCH_THRESHOLD = 0.45

# 预编译常用的正则表达式（性能优化）
RE_NORMALIZE = re.compile(r"[\s`~!@#$%^&*()_\-+=\[\]{}|\\;:'\",.<>/?·！￥…（）—【】、；：" "'’《》？]")
RE_SPLIT_TOKENS = re.compile(r"[、，,;；：:（）()\\-\\s]+")
RE_SPLIT_PHRASES = re.compile(r'[，,。！？!?\n]+')
RE_EXTRACT_KEYWORDS = re.compile(r'[^\w\u4e00-\u9fff]+')
RE_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])")
RE_TITLE_LINE = re.compile(r'^\d+\.\s*[^。！？!?]{0,15}[：:]?\s*$')
RE_JSON_CASE = re.compile(r'\{\s*"case_name"[^}]+\}', re.DOTALL)

# 繁体标点映射表（完整映射，通用）
TRADITIONAL_TO_SIMPLIFIED_PUNCTUATION = {
    "「": "【", "」": "】",
    "『": "【", "』": "】",
    "﹁": "【", "﹂": "】",
    "﹃": "【", "﹄": "】",
    "﹙": "（", "﹚": "）",
    "﹛": "{", "﹜": "}",
    "﹝": "[", "﹞": "]",
    "«": "《", "»": "》",
}


def slugify_function_point(function_point: str) -> str:
    """将功能点名称转换为适合作为文件名的字符串"""
    if not function_point:
        return "function_point"
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", function_point)
    slug = slug.strip("_")
    return slug or "function_point"


class LLMService:
    """LLM模型调用服务"""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        self.base_url = base_url or DEFAULT_CONFIG["llm_base_url"]
        self.model = model or DEFAULT_CONFIG["default_model"]
        self.temperature = temperature or DEFAULT_CONFIG["temperature"]
        self.max_tokens = max_tokens or DEFAULT_CONFIG["max_tokens"]
        self.timeout = DEFAULT_CONFIG["timeout"]

    def generate(self, prompt: str) -> str:
        """
        调用LLM生成内容

        Args:
            prompt: 输入的提示词

        Returns:
            LLM生成的文本内容
        """
        try:
            # 检查服务是否可用
            if not self._check_service_available():
                raise ConnectionError(f"无法连接到LLM服务: {self.base_url}")

            # 构建请求
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens
                }
            }

            print(f"{Fore.CYAN}正在调用模型: {self.model}...")
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "")

        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接到LLM服务，请确保服务运行在: {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"请求超时（{self.timeout}秒），请检查网络或增加超时时间")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LLM服务请求失败: {str(e)}")

    def _check_service_available(self) -> bool:
        """检查LLM服务是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


class TestCaseGenerator:
    """测试用例生成器"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self._cached_requirement_doc: Optional[str] = None
        self._cached_doc_lines: List[str] = []
        self._cached_normalized_lines: List[str] = []
        self._cached_sections: List[Tuple[int, str]] = []

    @staticmethod
    def _normalize_text(text: str) -> str:
        """标准化文本用于匹配"""
        cleaned = re.sub(r"[\s`~!@#$%^&*()_\-+=\[\]{}|\\;:'\",.<>/?·！￥…（）—【】、；：“”‘’《》？]", "", text or "")
        return cleaned.lower()

    @staticmethod
    def _fix_traditional_punctuation(text: str) -> str:
        """修复所有繁体标点为简体标点（通用方法）"""
        if not text:
            return text
        result = text
        for trad, simp in TRADITIONAL_TO_SIMPLIFIED_PUNCTUATION.items():
            result = result.replace(trad, simp)
        return result

    @staticmethod
    def _infer_preconditions_from_steps(steps: List[str]) -> str:
        """
        从测试步骤推断前置条件（通用方法）

        策略：
        1. 提取第一步的关键信息
        2. 如果第一步包含状态描述，直接使用
        3. 否则使用第一步作为前置条件
        """
        if not steps or not isinstance(steps, list) or len(steps) == 0:
            return RepairConfig.PRECONDITIONS_DEFAULT

        first_step = steps[0].strip() if steps[0] else ""
        if not first_step:
            return RepairConfig.PRECONDITIONS_DEFAULT

        # 提取第一步的关键部分（去除逗号分隔的后续部分）
        preconditions = first_step.split("，")[0] if "，" in first_step else first_step
        preconditions = preconditions.split(",")[0] if "," in preconditions else preconditions

        # 如果第一步太短（少于5个字符），使用默认值
        if len(preconditions.strip()) < 5:
            return RepairConfig.PRECONDITIONS_DEFAULT

        return preconditions.strip()

    def _prepare_requirement_cache(self, requirement_doc: str):
        """缓存需求文档的分行、归一化和章节信息，避免重复计算"""
        if self._cached_requirement_doc == requirement_doc:
            return

        self._cached_requirement_doc = requirement_doc
        self._cached_doc_lines = requirement_doc.splitlines()
        self._cached_normalized_lines = [self._normalize_text(line) for line in self._cached_doc_lines]
        self._cached_sections = self._detect_sections(self._cached_doc_lines)

    @staticmethod
    def _detect_sections(lines: List[str]) -> List[Tuple[int, str]]:
        """
        检测文档中的章节标题，用于后续截取上下文

        规则：
        - 行内容长度较短（< 80）
        - 不以项目符号/数字序号开头
        - 包含中文或大写字母，或者形如“模块NPS”这样的标题
        """
        sections: List[Tuple[int, str]] = []
        heading_pattern = re.compile(r"^(?:[A-Za-z\u4e00-\u9fff【].*)$")
        bullet_prefix = re.compile(r"^\s*(?:[-*•●◦·①②③④⑤⑥⑦⑧⑨⑩\d]+\s)")

        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue
            if len(line) > 80:
                continue
            if bullet_prefix.match(line):
                continue
            if heading_pattern.match(line):
                sections.append((idx, line))

        if not sections or sections[0][0] != 0:
            sections.insert(0, (0, "__document_start__"))
        return sections

    def _locate_section_window(self, line_index: int, extra_before: int = 20, extra_after: int = 80) -> Tuple[int, int]:
        """
        根据章节信息和额外上下文，计算需要截取的起止行号
        """
        if not self._cached_sections:
            start = max(0, line_index - extra_before)
            end = min(len(self._cached_doc_lines), line_index + extra_after)
            return start, end

        start = 0
        end = len(self._cached_doc_lines)

        for idx, (section_line, _) in enumerate(self._cached_sections):
            if section_line <= line_index:
                start = section_line
                # 下一个章节开始前结束
                if idx + 1 < len(self._cached_sections):
                    end = self._cached_sections[idx + 1][0]
                else:
                    end = len(self._cached_doc_lines)
            else:
                break

        start = max(0, start - extra_before)
        end = min(len(self._cached_doc_lines), end + extra_after)
        return start, end

    def build_prompt(self, requirement_doc: str) -> str:
        """
        构建生成测试用例的Prompt

        Args:
            requirement_doc: 需求文档内容

        Returns:
            完整的Prompt字符串
        """
        prompt = f"""你是一位有着10年测试经验的资深测试工程师。请仔细阅读以下需求文档，并严格按照文档内容生成全面的测试用例。

【任务要求】
根据以下需求文档，生成测试用例。必须严格按照需求文档中的实际功能点生成。

【需求文档】
{requirement_doc}

【生成要求】
1. 仔细分析需求文档，识别所有功能模块和功能点
2. 为每个功能模块生成测试用例，覆盖：
   - UI元素测试（按钮、字段、显示等）
   - 交互逻辑测试（按钮状态、弹窗逻辑、流程跳转等）
   - 业务规则测试（不同条件对应不同行为等）
   - 边界条件测试（字符限制、数值范围等）
3. 对于需求文档中提到的每个具体功能、按钮、字段、流程、规则、限制，都要有对应的测试用例
4. 根据需求文档的复杂程度，生成足够全面的测试用例，确保不遗漏任何功能点
5. **所有输出必须使用简体中文，不得出现繁体字或「」等繁体标点**
6. **禁止臆造需求文档中未出现的功能、文案或页面位置**

【输出格式要求】
**重要：只输出JSON格式，不要包含任何其他文字说明！**

每个测试用例必须包含以下字段：
- case_name: 测试用例名称（必须与需求文档中的功能点对应）
- description: 用例描述（详细说明测试目的，引用需求文档中的具体内容）
- preconditions: 前置条件（基于需求文档中的前置要求）
- steps: 测试步骤（数组格式，每个步骤一行，必须与需求文档中的操作流程一致）
- expected_result: 预期结果（必须与需求文档中的预期行为一致）
- priority: 优先级（high/medium/low）

【输出格式示例】
{{
  "test_cases": [
    {{
      "case_name": "用例名称",
      "description": "用例描述",
      "preconditions": "前置条件",
      "steps": ["步骤1", "步骤2", "步骤3"],
      "expected_result": "预期结果",
      "priority": "high"
    }}
  ]
}}

【重要提醒】
1. 只生成需求文档中明确提到的功能
2. 必须生成足够多的测试用例，覆盖所有功能点
3. **只输出JSON，不要包含任何其他文字说明**
4. **确保JSON格式正确，可以直接解析**"""

        return prompt

    def extract_function_points(self, requirement_doc: str) -> List[Dict]:
        """
        第一步：提取需求文档中的所有功能点（带定位线索）

        Args:
            requirement_doc: 需求文档内容

        Returns:
            功能点列表，每个包含name和定位线索
        """
        print(f"{Fore.CYAN}第一步：提取需求文档中的功能点（带定位线索）...")

        extract_prompt = f"""请仔细阅读以下需求文档，提取所有功能点。

需求文档：
{requirement_doc}

请详细列出需求文档中提到的所有功能点，包括：
- 所有功能模块（如全局NPS、模块NPS等）
- 所有按钮（如"去评分"、"关闭"、"下一步"等）
- 所有字段（如主标题、副标题、答案选项等）
- 所有流程步骤（如弹窗展示、用户操作、数据记录等）
- 所有规则和限制（如字符限制、时间限制、人群选择等）
- 所有异常场景（如超出字符限制、未登录等）

**重要要求：**
- 使用简体中文描述功能点，不要使用繁体字或「」等繁体标点
- 不要遗漏需求文档中出现的任意功能点
- 不要臆造需求文档中没有的内容
- 每个功能点必须提供定位线索，帮助程序找到相关原文

**重要：必须提取所有功能点，不能遗漏。如果需求文档很长，应该提取至少20-30个功能点。**

**关键词提取要求：**
- keywords：提供2-4个核心关键词，这些关键词必须是文档中真实存在的短语，用于精确定位原文
- 避免过于泛化的词语（如"关闭"、"操作"、"显示"等），优先选择具体的描述性词语
- exact_phrases：提供1个文档中的确切短语或句子，这个短语必须逐字来自文档原文
- section_hint：简短的章节名称或上下文线索（可选）

**重要格式要求：**
- 必须使用双引号，不要使用单引号
- 字符串中的特殊字符要正确转义
- 确保JSON格式完全正确

输出格式：
{{
  "function_points": [
    {{
      "name": "数据记录流程",
      "keywords": ["用户ID", "填写内容", "跟踪", "访谈"],
      "section_hint": "注意事项",
      "exact_phrases": ["需记录填写用户的ID和填写的内容"]
    }}
  ]
}}

只输出JSON，不要包含其他说明文字。"""

        try:
            response = self.llm_service.generate(extract_prompt)
            print(f"{Fore.CYAN}  原始响应长度: {len(response)} 字符")

            # 提取JSON
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                print(f"{Fore.CYAN}  提取的JSON长度: {len(json_str)} 字符")
            else:
                print(f"{Fore.RED}✗ 无法找到有效的JSON边界")
                print(f"{Fore.WHITE}原始响应预览:\n{response[:500]}...")
                raise ValueError("无法提取JSON内容")

            # 尝试解析JSON
            result = None
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as json_err:
                print(f"{Fore.RED}✗ JSON解析失败，尝试自动修复: {str(json_err)}")

                # 尝试自动修复常见JSON问题
                fixed_json = json_str
                original_length = len(fixed_json)

                # 修复1: 移除尾部多余的逗号
                fixed_json = re.sub(r',(\s*[}\]])', r'\1', fixed_json)

                # 修复2: 修复单引号为双引号（更精确的正则，避免误修复字符串内容）
                # 只修复对象键和简单字符串值，不修复字符串内容中的单引号
                # 修复键：'key': -> "key":
                fixed_json = re.sub(r"'([^']*)':\s*", r'"\1": ', fixed_json)
                # 修复简单值：: 'value' -> : "value" (但排除包含单引号的值)
                fixed_json = re.sub(r":\s*'([^']*)'(?=\s*[,}\]])", r': "\1"', fixed_json)

                # 修复3: 移除多余的转义
                fixed_json = fixed_json.replace('\\"', '"')

                print(f"{Fore.CYAN}  尝试修复JSON ({original_length} -> {len(fixed_json)} 字符)")

                try:
                    result = json.loads(fixed_json)
                    print(f"{Fore.GREEN}✓ JSON自动修复成功")
                except json.JSONDecodeError as fix_err:
                    print(f"{Fore.RED}✗ 自动修复失败: {str(fix_err)}")
                    print(f"{Fore.YELLOW}问题位置预览 (附近50字符):")
                    error_pos = json_err.pos
                    start_preview = max(0, error_pos - 25)
                    end_preview = min(len(json_str), error_pos + 25)
                    preview = json_str[start_preview:end_preview]
                    print(f"{Fore.WHITE}'{preview}'")
                    print(f"{Fore.RED}{' ' * (error_pos - start_preview)}^ 这里有问题")

                    # 提供修复建议
                    if "Expecting ',' delimiter" in str(json_err):
                        print(f"{Fore.YELLOW}💡 可能是缺少逗号或有多余逗号")
                    elif "Expecting ':' delimiter" in str(json_err):
                        print(f"{Fore.YELLOW}💡 可能是缺少冒号分隔符")
                    elif "Unterminated string" in str(json_err):
                        print(f"{Fore.YELLOW}💡 可能是字符串引号不匹配")

                    raise json_err

            function_points_data = result.get("function_points", [])

            # 兼容旧格式：如果返回的是字符串列表，转换为新格式
            if function_points_data and isinstance(function_points_data[0], str):
                function_points_data = [
                    {
                        "name": fp,
                        "keywords": [fp],
                        "section_hint": "",
                        "exact_phrases": []
                    }
                    for fp in function_points_data
                ]

            print(f"{Fore.GREEN}✓ 提取到 {len(function_points_data)} 个功能点（带定位线索）")
            return function_points_data

        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 功能点提取失败，将直接生成测试用例: {str(e)}")
            return []

    def extract_relevant_section(self, requirement_doc: str, function_point: str, fp_data: Optional[Dict] = None) -> str:
        """
        提取与功能点相关的需求文档片段（使用AI提供的定位线索进行精确匹配）
        """
        print(f"{Fore.CYAN}  正在提取与'{function_point}'相关的需求文档片段...")

        self._prepare_requirement_cache(requirement_doc)

        # 初始化候选索引列表
        candidate_indices: List[int] = []

        # 如果有AI提供的定位线索，优先使用
        if fp_data:

            # 1) 使用exact_phrases进行精确匹配
            exact_phrases = fp_data.get("exact_phrases", [])
            for phrase in exact_phrases:
                if phrase:
                    normalized_phrase = self._normalize_text(phrase)
                    for idx, normalized_line in enumerate(self._cached_normalized_lines):
                        if normalized_phrase and normalized_phrase in normalized_line:
                            candidate_indices.append(idx)
                            break  # 找到一个就够了

            # 2) 使用keywords进行关键词匹配
            if not candidate_indices:
                keywords = fp_data.get("keywords", [])
                if keywords:
                    print(f"{Fore.CYAN}    使用关键词进行匹配: {', '.join(keywords[:5])}...")
                    # 过滤掉过于泛化的关键词
                    filtered_keywords = []
                    for keyword in keywords:
                        # 跳过过于短或过于泛化的关键词
                        if len(keyword.strip()) < 2 or keyword.lower() in ['关闭', '操作', '显示', '点击', '按钮']:
                            continue
                        filtered_keywords.append(keyword)

                    if filtered_keywords:
                        # 改进：至少匹配一半的关键词（更宽松的匹配）
                        min_match_count = max(1, len(filtered_keywords) // 2)
                        for idx, normalized_line in enumerate(self._cached_normalized_lines):
                            line_text = normalized_line.lower()
                            matched_count = sum(1 for keyword in filtered_keywords if keyword.lower() in line_text)
                            if matched_count >= min_match_count:
                                candidate_indices.append(idx)
                        if candidate_indices:
                            print(f"{Fore.CYAN}  ✓ 使用关键词匹配找到 {len(candidate_indices)} 个位置")

            # 3) 使用section_hint缩小范围
            section_hint = fp_data.get("section_hint", "")
            if section_hint and candidate_indices:
                # 查找章节标题
                section_indices = []
                for idx, line in enumerate(self._cached_doc_lines):
                    if section_hint.lower() in line.lower():
                        section_indices.append(idx)

                # 只保留在相关章节内的匹配
                if section_indices:
                    filtered_indices = []
                    for candidate_idx in candidate_indices:
                        # 检查是否在章节范围内
                        for section_idx in section_indices:
                            if section_idx <= candidate_idx < section_idx + 50:  # 章节范围大约50行
                                filtered_indices.append(candidate_idx)
                                break
                    if filtered_indices:
                        candidate_indices = filtered_indices

            if candidate_indices:
                print(f"{Fore.CYAN}  ✓ 使用AI定位线索找到 {len(candidate_indices)} 个匹配位置")

        # 如果没有fp_data，或者虽然有fp_data但没找到匹配，回退到原有的匹配策略
        if not candidate_indices:
            # 回退到原有的匹配策略
            normalized_target = self._normalize_text(function_point)
            if not normalized_target:
                print(f"{Fore.YELLOW}  ⚠ 功能点'{function_point}'无法归一化，使用原始文档片段")
                return requirement_doc[:ExtractionConfig.FALLBACK_SNIPPET_LENGTH] if len(requirement_doc) > ExtractionConfig.FALLBACK_SNIPPET_LENGTH else requirement_doc

            candidate_indices = []

            # 1) 精确包含匹配
            for idx, normalized_line in enumerate(self._cached_normalized_lines):
                if normalized_target and normalized_target in normalized_line:
                    candidate_indices.append(idx)

            # 2) 词粒度匹配
            if not candidate_indices:
                tokens = [
                    self._normalize_text(token)
                    for token in RE_SPLIT_TOKENS.split(function_point)
                    if token.strip()
                ]
                strong_tokens = [token for token in tokens if len(token) >= 2]
                if strong_tokens:
                    for idx, normalized_line in enumerate(self._cached_normalized_lines):
                        if all(token in normalized_line for token in strong_tokens):
                            candidate_indices.append(idx)

            # 3) 模糊匹配
            if not candidate_indices and self._cached_normalized_lines:
                ratios = [
                    (difflib.SequenceMatcher(None, normalized_target, normalized_line).ratio(), idx)
                    for idx, normalized_line in enumerate(self._cached_normalized_lines)
                    if normalized_line
                ]
                if ratios:
                    best_ratio, best_idx = max(ratios, key=lambda item: item[0])
                    if best_ratio >= ExtractionConfig.FUZZY_MATCH_THRESHOLD:
                        candidate_indices.append(best_idx)

        if not candidate_indices:
            # 尝试更宽松的匹配策略：使用功能点名称的单个关键词
            print(f"{Fore.YELLOW}  ⚠ 未找到精确匹配，尝试使用关键词匹配...")
            tokens = [
                self._normalize_text(token)
                for token in RE_SPLIT_TOKENS.split(function_point)
                if token.strip() and len(token.strip()) >= 2
            ]
            # 尝试匹配单个关键词
            for token in tokens[:3]:  # 最多尝试前3个关键词
                if token:
                    for idx, normalized_line in enumerate(self._cached_normalized_lines):
                        if token in normalized_line:
                            candidate_indices.append(idx)
                    if candidate_indices:
                        print(f"{Fore.GREEN}  ✓ 使用关键词'{token}'找到 {len(candidate_indices)} 个匹配位置")
                        break

            # 如果仍然没有找到，使用原文档前N字符（使用配置常量）
            if not candidate_indices:
                print(f"{Fore.YELLOW}  ⚠ 未找到包含'{function_point}'的内容，使用原文档前{ExtractionConfig.FALLBACK_SNIPPET_LENGTH}字符")
                return requirement_doc[:ExtractionConfig.FALLBACK_SNIPPET_LENGTH] if len(requirement_doc) > ExtractionConfig.FALLBACK_SNIPPET_LENGTH else requirement_doc

        # 如果匹配位置太多，进行额外筛选（使用配置常量）
        if len(candidate_indices) > ExtractionConfig.MAX_MATCH_POSITIONS:
            print(f"{Fore.YELLOW}  ⚠ 找到 {len(candidate_indices)} 个匹配位置，尝试优化筛选...")
            # 使用章节信息进一步筛选
            if fp_data and fp_data.get("section_hint"):
                section_hint = fp_data.get("section_hint", "").lower()
                filtered_indices = []
                for idx in candidate_indices:
                    # 检查周围内容是否包含章节线索
                    start_check = max(0, idx - 5)
                    end_check = min(len(self._cached_doc_lines), idx + 5)
                    context = "\n".join(self._cached_doc_lines[start_check:end_check]).lower()
                    if section_hint in context:
                        filtered_indices.append(idx)
                if filtered_indices:
                    print(f"{Fore.GREEN}  ✓ 章节筛选后剩余 {len(filtered_indices)} 个位置")
                    candidate_indices = filtered_indices[:ExtractionConfig.MAX_MATCH_POSITIONS]  # 限制最多N个

            # 如果仍然太多，只保留前N个（使用配置常量）
            if len(candidate_indices) > ExtractionConfig.MAX_MATCH_POSITIONS:
                candidate_indices = candidate_indices[:ExtractionConfig.MAX_MATCH_POSITIONS]
                print(f"{Fore.YELLOW}  ⚠ 限制匹配位置数量为{ExtractionConfig.MAX_MATCH_POSITIONS}个")

        collected_indices: set[int] = set()
        for idx in candidate_indices:
            start, end = self._locate_section_window(idx)
            collected_indices.update(range(start, end))

        if not collected_indices:
            print(f"{Fore.YELLOW}  ⚠ 未能确定章节范围，使用匹配行附近内容")
            idx = candidate_indices[0]
            start = max(0, idx - ExtractionConfig.CONTEXT_BEFORE)
            end = min(len(self._cached_doc_lines), idx + ExtractionConfig.CONTEXT_AFTER)
            collected_indices.update(range(start, end))

        relevant_lines = [self._cached_doc_lines[i] for i in sorted(collected_indices)]
        relevant_section = "\n".join(relevant_lines).strip()

        if len(relevant_section) < ExtractionConfig.MIN_SNIPPET_LENGTH:
            print(f"{Fore.YELLOW}  ⚠ 提取片段不足{ExtractionConfig.MIN_SNIPPET_LENGTH}字符，自动扩展上下文")
            idx = candidate_indices[0]
            start = max(0, idx - ExtractionConfig.EXTENDED_CONTEXT_BEFORE)
            end = min(len(self._cached_doc_lines), idx + ExtractionConfig.EXTENDED_CONTEXT_AFTER)
            relevant_section = "\n".join(self._cached_doc_lines[start:end]).strip()

        print(f"{Fore.GREEN}  ✓ 提取到 {len(relevant_section)} 字符的相关内容（原文）")
        return relevant_section

    def generate_test_cases_for_point(self, requirement_doc: str, function_point: str, fp_data: Optional[Dict] = None) -> Tuple[List[Dict], List[str], str]:
        """
        为单个功能点生成测试用例

        Args:
            requirement_doc: 需求文档内容
            function_point: 功能点名称
            fp_data: 功能点数据（包含定位线索）

        Returns:
            测试用例列表
        """
        # 提取与功能点相关的需求文档片段
        doc_snippet = self.extract_relevant_section(requirement_doc, function_point, fp_data)

        prompt = f"""你是一位测试工程师。请根据需求文档为功能点"{function_point}"生成测试用例。

**重要：只输出JSON格式，不要任何其他文字！**

【需求文档】
{doc_snippet}

【功能点】
{function_point}

【要求】
1. 只生成与"{function_point}"相关的测试用例
2. 必须严格按照需求文档中的内容生成，不能编造
3. **测试用例中的expected_result字段必须逐字引用需求文档中的原句，不能改写、总结或意译**
4. 不能添加需求文档中没有的功能、按钮、操作
5. **输出必须全部使用简体中文，禁止出现繁体字或「」等繁体标点**
6. **用例中涉及的页面/模块名称必须与需求文档保持一致，不得自行更换页面位置**

【生成规则】
- 仔细阅读需求文档中关于"{function_point}"的所有描述
- 为每个UI元素、交互逻辑、业务规则、限制条件生成测试用例
- **expected_result必须从需求文档中直接复制完整的句子，不能修改任何文字**
- 如果需求文档写"点击关闭直接消失"，expected_result必须写"点击关闭直接消失"（不能写成"点击关闭按钮后弹窗消失"）
- 直接引用需求文档中的按钮名称、字段名称、标题文字
- 输出结构化且详尽，确保覆盖正常流程、边界场景与约束条件

【示例】
如果需求文档写"主标题：喜欢RingConn吗？来评分吧！"，测试用例应该写：
{{
  "case_name": "验证Banner主标题显示",
  "description": "验证Banner主标题显示",
  "preconditions": "用户已登录，在'今天'页面",
  "steps": ["打开app，进入'今天'页面", "查看Banner主标题"],
  "expected_result": "主标题：喜欢RingConn吗？来评分吧！",
  "priority": "high"
}}

**注意**：expected_result必须直接复制需求文档中的原句，不能添加"Banner主标题显示为"这样的描述性文字。

【输出格式】
只输出JSON，格式如下：

{{
  "test_cases": [
    {{
      "case_name": "用例名称",
      "description": "用例描述",
      "preconditions": "前置条件",
      "steps": ["步骤1", "步骤2"],
      "expected_result": "预期结果（必须逐字复制需求文档中的原句，不能改写）",
      "priority": "high"
    }}
  ]
}}

**关键要求**：
- expected_result字段必须从需求文档中直接复制完整的原句
- 不能添加任何描述性文字（如"显示为"、"应该"等）
- 不能改写、总结或意译原文

**再次强调：只输出JSON，不要任何其他文字！**"""

        try:
            # 打印发送给模型的完整Prompt（用于调试）
            print(f"{Fore.CYAN}  [完整Prompt]")
            print(f"{Fore.WHITE}  {'='*60}")
            print(f"{Fore.WHITE}  {prompt}")
            print(f"{Fore.WHITE}  {'='*60}\n")

            response_text = self.llm_service.generate(prompt)

            # 解析JSON
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]

            # 清理控制字符（JSON不允许的控制字符）
            # 移除除了换行符、制表符、回车符之外的控制字符
            import string
            control_chars = ''.join(chr(i) for i in range(32) if chr(i) not in '\n\r\t')
            for char in control_chars:
                response_text = response_text.replace(char, '')

            # 修复JSON格式问题
            response_text = re.sub(r'"expected[^"]*":', '"expected_result":', response_text)
            response_text = re.sub(r'<\|[^|]+\|>', '', response_text)

            result = json.loads(response_text)
            test_cases = result.get("test_cases", [])
            # 先进行静态校验（包括格式修复）
            warnings = self._run_static_validation(function_point, test_cases, doc_snippet)
            # 然后进行深度修复（替换为原文），避免重复修复
            repair_logs = self._repair_expected_results(function_point, test_cases, doc_snippet, skip_already_fixed=True)
            if repair_logs:
                warnings.extend(repair_logs)
            return test_cases, warnings, doc_snippet
        except json.JSONDecodeError as e:
            print(f"{Fore.YELLOW}  ⚠ 功能点 '{function_point}' JSON解析失败: {str(e)}")
            print(f"{Fore.YELLOW}  原始响应（前1000字符）:")
            print(f"{Fore.WHITE}  {response_text[:1000]}")
            return [], [f"JSON解析失败: {str(e)}"], doc_snippet
        except Exception as e:
            print(f"{Fore.YELLOW}  ⚠ 功能点 '{function_point}' 生成失败: {str(e)}")
            return [], [f"生成失败: {str(e)}"], doc_snippet

    def _run_static_validation(self, function_point: str, test_cases: List[Dict], doc_snippet: str) -> List[str]:
        """对生成的测试用例进行静态校验，返回告警列表"""
        warnings: List[str] = []
        required_fields = {"case_name", "description", "preconditions", "steps", "expected_result", "priority"}
        traditional_punctuation = set("「」『』﹁﹂﹃﹄﹙﹚﹛﹜﹝﹞﹃﹫﹬﹭«»")

        if not isinstance(test_cases, list):
            warnings.append(f"[{function_point}] 测试用例数据格式异常，非列表")
            return warnings

        for idx, case in enumerate(test_cases, 1):
            if not isinstance(case, dict):
                warnings.append(f"[{function_point}] 第{idx}条用例不是字典类型")
                continue

            missing = required_fields - set(case.keys())
            if missing:
                warnings.append(f"[{function_point}] 第{idx}条用例缺少字段: {', '.join(sorted(missing))}")

            # 基础字段校验
            for field in required_fields - {"steps"}:
                value = case.get(field)
                if not isinstance(value, str) or not value.strip():
                    # 尝试自动修复空的preconditions字段（通用方法）
                    if field == "preconditions" and (not value or not value.strip()):
                        steps = case.get("steps", [])
                        inferred_preconditions = self._infer_preconditions_from_steps(steps)
                        case["preconditions"] = inferred_preconditions
                        warnings.append(f"[{function_point}] 第{idx}条用例字段'{field}'已自动修复")
                    else:
                        warnings.append(f"[{function_point}] 第{idx}条用例字段'{field}'为空或类型错误")

            steps = case.get("steps")
            if not isinstance(steps, list) or not steps or not all(isinstance(step, str) and step.strip() for step in steps):
                warnings.append(f"[{function_point}] 第{idx}条用例步骤列表为空或格式错误")

            # 检查并修复繁体标点
            combined_text = "".join(
                [str(case.get("case_name", "")), case.get("description", ""), case.get("expected_result", ""), "".join(steps or [])]
            )
            if any(char in traditional_punctuation for char in combined_text):
                # 自动修复所有字段中的繁体标点
                for field in ["case_name", "description", "expected_result"]:
                    if field in case and isinstance(case[field], str):
                        original = case[field]
                        fixed = self._fix_traditional_punctuation(original)
                        if fixed != original:
                            case[field] = fixed
                # 修复steps中的繁体标点
                if steps and isinstance(steps, list):
                    for i, step in enumerate(steps):
                        if isinstance(step, str):
                            fixed_step = self._fix_traditional_punctuation(step)
                            if fixed_step != step:
                                steps[i] = fixed_step
                warnings.append(f"[{function_point}] 第{idx}条用例已自动修复繁体标点")

            # 关键词引用检查（改进版：更宽松的匹配）
            if doc_snippet:
                expected = case.get("expected_result", "")
                if expected:
                    # 检查expected_result是否包含多个句子连在一起（可能是格式问题）
                    # 如果expected_result很长且没有标点符号分隔，可能是格式问题
                    if len(expected) > RepairConfig.FORMAT_FIX_MIN_LENGTH and not any(p in expected for p in ["。", "！", "？", ".", "!", "?", "\n"]):
                        # 尝试在doc_snippet中查找包含expected_result关键词的句子
                        expected_keywords = [kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2][:RepairConfig.FORMAT_FIX_KEYWORD_COUNT + 2]
                        if expected_keywords:
                            # 在文档片段中查找包含这些关键词的句子（使用部分匹配，更灵活）
                            snippet_lines = [line.strip() for line in doc_snippet.splitlines() if line.strip()]
                            matched_sentences = []
                            for line in snippet_lines:
                                # 至少匹配前N个关键词中的大部分（更灵活）
                                matched_count = sum(1 for kw in expected_keywords[:RepairConfig.FORMAT_FIX_KEYWORD_COUNT] if kw in line)
                                if matched_count >= max(1, RepairConfig.FORMAT_FIX_KEYWORD_COUNT - 1):  # 允许1个关键词不匹配
                                    matched_sentences.append(line)
                            if matched_sentences:
                                # 选择最佳匹配：优先选择长度最接近的句子
                                original_length = len(case["expected_result"])
                                best_match = min(matched_sentences, key=lambda s: abs(len(s) - original_length))
                                case["expected_result"] = best_match
                                # 标记已修复，避免在_repair_expected_results中重复处理
                                case["_format_fixed"] = True
                                warnings.append(f"[{function_point}] 第{idx}条预期结果已自动修复格式问题")

                    # 归一化处理：去除换行、多余空格、繁体标点
                    expected_normalized = self._normalize_text(expected.replace("\n", " ").strip())
                    snippet_normalized = self._normalize_text(doc_snippet.replace("\n", " "))

                    # 检查是否在原文中（使用归一化后的文本）
                    if expected_normalized not in snippet_normalized:
                        # 进一步检查：去除所有空格后是否匹配
                        expected_no_space = expected_normalized.replace(" ", "")
                        snippet_no_space = snippet_normalized.replace(" ", "")
                        if expected_no_space not in snippet_no_space:
                            # 最后尝试：检查是否包含关键短语（更宽松的匹配）
                            key_phrases = [phrase for phrase in RE_SPLIT_PHRASES.split(expected) if len(phrase.strip()) >= RepairConfig.MIN_PHRASE_LENGTH]
                            found_any = False
                            for phrase in key_phrases[:RepairConfig.KEY_PHRASE_COUNT]:  # 使用配置的数量
                                phrase_normalized = self._normalize_text(phrase.strip())
                                # 检查短语是否在文档中（允许部分匹配）
                                if (phrase_normalized in snippet_normalized or
                                    phrase_normalized.replace(" ", "") in snippet_no_space or
                                    any(phrase_normalized in self._normalize_text(line) for line in doc_snippet.splitlines())):
                                    found_any = True
                                    break

                            # 如果仍然没找到，尝试提取关键词进行更宽松的匹配
                            if not found_any:
                                # 提取expected_result中的关键词（至少2个字符）
                                expected_keywords = [kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2]
                                if expected_keywords:
                                    # 检查是否至少有一半的关键词在文档中
                                    matched_keywords = sum(1 for kw in expected_keywords[:5] if self._normalize_text(kw) in snippet_normalized)
                                    if matched_keywords >= max(1, len(expected_keywords[:5]) // 2):
                                        found_any = True

                            if not found_any:
                                warnings.append(f"[{function_point}] 第{idx}条预期结果未在原文中找到，需人工确认")

        return warnings

    def _repair_expected_results(self, function_point: str, test_cases: List[Dict], doc_snippet: str, skip_already_fixed: bool = False) -> List[str]:
        """
        当 expected_result 与原文不完全匹配时，尝试自动纠正为文档原句

        Args:
            function_point: 功能点名称
            test_cases: 测试用例列表
            doc_snippet: 文档片段
            skip_already_fixed: 如果为True，跳过已经在静态校验中修复过的用例（避免重复修复）
        """
        repair_logs: List[str] = []

        if not doc_snippet or not isinstance(test_cases, list):
            return repair_logs

        # 预处理文档片段
        normalized_snippet = doc_snippet.replace("\n", "")
        snippet_lines = [line.strip() for line in doc_snippet.splitlines() if line.strip()]

        # 进一步拆分成句子（基于中文标点）
        snippet_sentences: List[str] = []
        for line in snippet_lines:
            parts = [part.strip() for part in RE_SENTENCE_SPLIT.split(line) if part.strip()]
            snippet_sentences.extend(parts if parts else [line])

        # 去重，保持顺序，并过滤掉不合适的候选
        seen = set()
        unique_candidates: List[str] = []
        for candidate in snippet_lines + snippet_sentences:
            # 过滤条件（使用配置参数）：
            # 1. 长度至少N个字符（避免标题行）
            # 2. 不是纯数字编号行（如"3. 标题："这种标题）
            # 3. 包含实际内容（不是只有标点符号）
            if (len(candidate) >= RepairConfig.MIN_SENTENCE_LENGTH and
                candidate not in seen and
                not RE_TITLE_LINE.match(candidate) and  # 过滤标题行
                len(RE_EXTRACT_KEYWORDS.sub('', candidate)) >= RepairConfig.MIN_VALID_CHARS):  # 至少N个有效字符
                seen.add(candidate)
                unique_candidates.append(candidate)

        for idx, case in enumerate(test_cases, 1):
            if not isinstance(case, dict):
                continue
            expected = case.get("expected_result")
            if not isinstance(expected, str) or not expected.strip():
                continue

            # 修复繁体标点：使用完整的映射表修复所有繁体标点
            original_expected = expected
            expected = self._fix_traditional_punctuation(expected)
            if expected != original_expected:
                case["expected_result"] = expected
                repair_logs.append(
                    f"[{function_point}] 第{idx}条预期结果已修复繁体标点"
                )

            # 若原预期结果已在文档中（使用归一化后的文本），跳过
            expected_normalized = self._normalize_text(expected.replace("\n", " "))
            snippet_normalized = self._normalize_text(normalized_snippet)
            if expected_normalized in snippet_normalized:
                continue

            # 如果skip_already_fixed为True，检查是否已经在静态校验中修复过格式问题
            if skip_already_fixed:
                # 检查是否已经标记为格式修复过
                if case.get("_format_fixed", False):
                    # 清理标记
                    case.pop("_format_fixed", None)
                    continue
                # 或者检查归一化后的文本是否已经在文档中（说明可能已经修复过）
                if expected_normalized in snippet_normalized or expected_normalized.replace(" ", "") in snippet_normalized.replace(" ", ""):
                    continue

            # 策略1：去除空格后精确匹配（使用归一化文本）
            expected_normalized_for_match = self._normalize_text(expected.replace(" ", ""))
            matched_line: Optional[str] = None

            # 预先提取关键词（供后续策略使用）
            expected_normalized = self._normalize_text(expected.replace("\n", " "))
            expected_keywords = [kw for kw in RE_EXTRACT_KEYWORDS.split(expected) if len(kw) >= 2]

            for candidate in unique_candidates:
                candidate_normalized = self._normalize_text(candidate.replace(" ", ""))
                if expected_normalized_for_match == candidate_normalized:
                    matched_line = candidate
                    break

            # 策略2：相似度匹配（提高阈值，优先匹配完整句子）
            if not matched_line:
                best_ratio = 0.0
                best_candidate = None

                for candidate in unique_candidates:
                    # 计算相似度（使用归一化后的文本）
                    candidate_normalized = self._normalize_text(candidate)
                    ratio = difflib.SequenceMatcher(None, expected_normalized, candidate_normalized).ratio()

                    # 如果候选句子包含预期结果中的关键词，给予加分（使用配置参数）
                    keyword_bonus = 0.0
                    if expected_keywords:
                        matched_keywords = sum(1 for kw in expected_keywords if kw in candidate_normalized)
                        keyword_bonus = (matched_keywords / len(expected_keywords)) * RepairConfig.KEYWORD_BONUS

                    # 长度相似度加分（长度越接近，加分越多）
                    length_ratio = min(len(candidate), len(expected)) / max(len(candidate), len(expected)) if max(len(candidate), len(expected)) > 0 else 0
                    length_bonus = length_ratio * 0.05  # 最多加0.05

                    # 如果候选句子包含expected_result中的核心关键词（至少2个），额外加分
                    core_keyword_bonus = 0.0
                    if expected_keywords and len(expected_keywords) >= 2:
                        # 提取前3个最重要的关键词
                        core_keywords = expected_keywords[:3]
                        matched_core = sum(1 for kw in core_keywords if kw in candidate_normalized)
                        if matched_core >= 2:  # 至少匹配2个核心关键词
                            core_keyword_bonus = 0.1  # 额外加0.1

                    final_ratio = ratio + keyword_bonus + length_bonus + core_keyword_bonus

                    if final_ratio > best_ratio:
                        best_ratio = final_ratio
                        best_candidate = candidate

                # 使用配置的相似度阈值
                if best_candidate and best_ratio >= RepairConfig.SIMILARITY_THRESHOLD:
                    matched_line = best_candidate

            # 如果找到匹配，替换 expected_result（避免重复记录）
            if matched_line and matched_line != expected:
                # 检查是否已经记录过修复日志（避免重复）
                already_logged = any(
                    f"第{idx}条" in log and ("已自动替换" in log or "已修复格式" in log)
                    for log in repair_logs
                )
                if not already_logged:
                    case["expected_result"] = matched_line
                    # 如果替换后的文本较长，截断显示（避免日志过长）
                    display_text = matched_line if len(matched_line) <= 100 else matched_line[:97] + "..."
                    repair_logs.append(
                        f"[{function_point}] 第{idx}条预期结果已自动替换为原文: {display_text}"
                    )

            # 策略3：如果仍然没有找到匹配，尝试部分匹配（更宽松的策略）
            # 检查expected_result是否包含文档中的关键短语
            if not matched_line and expected_keywords:
                # 尝试在文档中查找包含大部分关键词的句子
                for candidate in unique_candidates:
                    candidate_normalized = self._normalize_text(candidate)
                    # 检查是否包含至少一半的关键词
                    matched_count = sum(1 for kw in expected_keywords if kw in candidate_normalized)
                    if matched_count >= max(2, len(expected_keywords) // 2):  # 至少匹配2个或一半的关键词
                        # 进一步检查：候选句子是否包含expected_result中的核心概念
                        # 提取expected_result中的核心词汇（去除常见词）
                        common_words = {"的", "是", "在", "有", "和", "与", "或", "及", "为", "会", "可以", "能够"}
                        core_words = [kw for kw in expected_keywords if kw not in common_words and len(kw) >= 2]
                        if core_words:
                            matched_core = sum(1 for word in core_words if word in candidate_normalized)
                            if matched_core >= len(core_words) * 0.5:  # 至少匹配一半的核心词
                                matched_line = candidate
                                break

                # 如果找到部分匹配，替换
                if matched_line and matched_line != expected:
                    already_logged = any(
                        f"第{idx}条" in log and ("已自动替换" in log or "已修复格式" in log)
                        for log in repair_logs
                    )
                    if not already_logged:
                        case["expected_result"] = matched_line
                        display_text = matched_line if len(matched_line) <= 100 else matched_line[:97] + "..."
                        repair_logs.append(
                            f"[{function_point}] 第{idx}条预期结果已自动替换为原文（部分匹配）: {display_text}"
                        )

        return repair_logs

    def _generate_single_point_wrapper(self, requirement_doc: str, fp_data: Dict, idx: int, total: int) -> Tuple[str, List[Dict], List[str], str]:
        """
        包装方法，用于并发处理单个功能点

        Args:
            requirement_doc: 需求文档内容
            fp_data: 功能点数据
            idx: 当前索引
            total: 总数量

        Returns:
            (function_point_name, test_cases, warnings, doc_snippet)
        """
        function_point_name = fp_data.get("name", "")
        try:
            print(f"{Fore.CYAN}[{idx}/{total}] 正在为功能点生成用例: {function_point_name}")
            test_cases, warnings, doc_snippet = self.generate_test_cases_for_point(
                requirement_doc, function_point_name, fp_data
            )
            if test_cases:
                print(f"{Fore.GREEN}[{idx}/{total}] ✓ {function_point_name}: 生成 {len(test_cases)} 个测试用例")
            else:
                print(f"{Fore.YELLOW}[{idx}/{total}] ⚠ {function_point_name}: 未生成测试用例")
            if warnings:
                for warn in warnings:
                    print(f"{Fore.YELLOW}    • {function_point_name}: {warn}")
            return function_point_name, test_cases, warnings, doc_snippet
        except Exception as e:
            print(f"{Fore.RED}[{idx}/{total}] ✗ {function_point_name}: 处理失败 - {str(e)}")
            return function_point_name, [], [f"处理失败: {str(e)}"], ""

    def generate_test_cases(self, requirement_doc: str, limit: Optional[int] = None, max_workers: int = 4) -> Dict:
        """
        生成测试用例 - 为每个功能点分别生成

        Args:
            requirement_doc: 需求文档内容

        Returns:
            包含测试用例的字典
        """
        print(f"{Fore.YELLOW}正在生成测试用例...")

        # 缓存文档，避免重复拆分
        self._prepare_requirement_cache(requirement_doc)

        # 第一步：提取功能点（带定位线索）
        function_points_data = self.extract_function_points(requirement_doc)

        if not function_points_data:
            print(f"{Fore.YELLOW}⚠ 未能提取功能点，使用传统方式生成...")
            # 如果没有提取到功能点，使用原来的方式
            prompt = self.build_prompt(requirement_doc)
            # 打印发送给模型的完整Prompt（用于调试）
            print(f"{Fore.CYAN}[完整Prompt]")
            print(f"{Fore.WHITE}{'='*60}")
            print(f"{Fore.WHITE}{prompt}")
            print(f"{Fore.WHITE}{'='*60}\n")
            response_text = self.llm_service.generate(prompt)
            # 继续原有的解析逻辑
            return self._parse_response(response_text)

        # 第二步：为每个功能点分别生成测试用例
        all_test_cases = []
        per_point_cases: Dict[str, Dict[str, Any]] = {}
        total_points = len(function_points_data)

        # 测试模式：随机选择N个功能点（用于快速测试）
        effective_limit = limit if limit is not None else TEST_FUNCTION_POINTS_LIMIT
        if effective_limit and effective_limit > 0:
            if len(function_points_data) > effective_limit:
                # 随机选择N个功能点
                selected_points = random.sample(function_points_data, effective_limit)
                function_points_data = selected_points
                print(f"{Fore.YELLOW}⚠ 限制功能点数量：随机选择 {effective_limit} 个功能点进行生成\n")
            else:
                print(f"{Fore.YELLOW}⚠ 功能点总数({len(function_points_data)})少于限制数({effective_limit})，处理所有功能点\n")

        actual_points = len(function_points_data)
        print(f"\n{Fore.CYAN}第二步：为 {actual_points} 个功能点分别生成测试用例（并发处理，最大并发数: {max_workers}）...\n")

        # 使用线程池并发处理功能点
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_fp = {
                executor.submit(self._generate_single_point_wrapper, requirement_doc, fp_data, idx, actual_points): fp_data
                for idx, fp_data in enumerate(function_points_data, 1)
            }

            # 收集结果（按完成顺序）
            completed = 0
            for future in as_completed(future_to_fp):
                completed += 1
                try:
                    function_point_name, test_cases, warnings, doc_snippet = future.result()
                    per_point_cases[function_point_name] = {
                        "test_cases": test_cases,
                        "warnings": warnings,
                        "source": doc_snippet
                    }
                    if test_cases:
                        all_test_cases.extend(test_cases)
                    print(f"{Fore.CYAN}  [{completed}/{actual_points}] 已完成: {function_point_name}\n")
                except Exception as e:
                    fp_data = future_to_fp[future]
                    function_point_name = fp_data.get("name", "")
                    print(f"{Fore.RED}  [{completed}/{actual_points}] ✗ {function_point_name}: 发生异常 - {str(e)}\n")
                    per_point_cases[function_point_name] = {
                        "test_cases": [],
                        "warnings": [f"处理异常: {str(e)}"],
                        "source": ""
                    }

        result = {
            "test_cases": all_test_cases,
            "by_function_point": per_point_cases,
            "meta": {
                "total_function_points": total_points,
                "processed_function_points": actual_points,
                "limit": effective_limit or 0,
                "total_warnings": sum(len(data.get("warnings", []) or []) for data in per_point_cases.values())
            }
        }
        print(f"{Fore.GREEN}✓ 总共生成 {len(all_test_cases)} 个测试用例")
        return result

    def _parse_response(self, response_text: str) -> Dict:
        """
        解析模型响应（原有逻辑）

        Args:
            response_text: 模型响应文本

        Returns:
            包含测试用例的字典
        """

        # 解析JSON响应
        try:
            # 尝试提取JSON部分（去除可能的markdown代码块标记）
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # 移除markdown代码块标记
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            # 尝试找到JSON对象
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]

            # 清理控制字符（JSON不允许的控制字符）
            import string
            control_chars = ''.join(chr(i) for i in range(32) if chr(i) not in '\n\r\t')
            for char in control_chars:
                response_text = response_text.replace(char, '')

            # 修复常见的JSON格式问题
            # 1. 修复被截断的字段名（如 expected<|redacted...|> 应该修复为 expected_result）
            response_text = re.sub(r'"expected[^"]*":', '"expected_result":', response_text)
            # 2. 修复其他可能的截断标记
            response_text = re.sub(r'<\|[^|]+\|>', '', response_text)
            # 3. 移除末尾不完整的字段
            lines = response_text.split('\n')
            cleaned_lines = []
            for line in lines:
                # 如果行包含不完整的字段（有引号开始但没有冒号），跳过
                if '":' in line or line.strip() in ['{', '}', '[', ']', ','] or not line.strip():
                    cleaned_lines.append(line)
                elif line.strip().startswith('"') and ':' not in line:
                    # 可能是被截断的字段，尝试修复或跳过
                    if 'expected' in line.lower():
                        cleaned_lines.append('            "expected_result": "",')
                    # 否则跳过这行
                else:
                    cleaned_lines.append(line)
            response_text = '\n'.join(cleaned_lines)

            # 尝试找到最后一个完整的JSON对象
            # 如果JSON不完整，尝试修复
            brace_count = response_text.count('{') - response_text.count('}')
            if brace_count > 0:
                # 缺少右括号，补充
                response_text += '\n' + '}' * brace_count
            elif brace_count < 0:
                # 多余的右括号，移除最后一个
                for _ in range(-brace_count):
                    last_brace = response_text.rfind('}')
                    if last_brace != -1:
                        response_text = response_text[:last_brace] + response_text[last_brace+1:]

            result = json.loads(response_text)

            # 验证结果格式
            if "test_cases" not in result:
                raise ValueError("响应中缺少'test_cases'字段")

            print(f"{Fore.GREEN}✓ 成功生成 {len(result.get('test_cases', []))} 个测试用例")
            return result

        except json.JSONDecodeError as e:
            print(f"{Fore.YELLOW}⚠ JSON解析遇到问题，尝试修复...")
            # 尝试更激进的修复：提取所有完整的测试用例
            try:
                # 使用预编译的正则表达式提取所有测试用例
                matches = RE_JSON_CASE.findall(response_text)
                if matches:
                    fixed_cases = []
                    for match in matches:
                        try:
                            case = json.loads(match)
                            # 确保必要字段存在
                            if 'case_name' in case:
                                if 'expected_result' not in case:
                                    case['expected_result'] = ''
                                fixed_cases.append(case)
                        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                            continue
                    if fixed_cases:
                        result = {"test_cases": fixed_cases}
                        print(f"{Fore.GREEN}✓ 成功修复并生成 {len(fixed_cases)} 个测试用例")
                        return result
            except (json.JSONDecodeError, re.error, ValueError):
                pass

            print(f"{Fore.RED}✗ JSON解析失败: {str(e)}")
            print(f"{Fore.YELLOW}原始响应内容（前500字符）:")
            print(response_text[:500])
            raise ValueError(f"无法解析LLM返回的JSON格式: {str(e)}")
        except Exception as e:
            print(f"{Fore.RED}✗ 生成测试用例失败: {str(e)}")
            raise


def read_requirement_file(file_path: str) -> str:
    """读取需求文档文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {file_path}")
    except Exception as e:
        raise IOError(f"读取文件失败: {str(e)}")


def _clean_test_cases(test_cases: List[Dict]) -> List[Dict]:
    """清理测试用例中的临时标记字段（通用方法）"""
    cleaned = []
    for case in test_cases:
        if isinstance(case, dict):
            # 创建副本，移除临时标记字段
            cleaned_case = {k: v for k, v in case.items() if not k.startswith("_")}
            cleaned.append(cleaned_case)
        else:
            cleaned.append(case)
    return cleaned

def save_result(result: Dict, output_path: str, split_output: bool = False, output_dir: Optional[str] = None):
    """保存结果到文件"""
    try:
        # 清理测试用例中的临时标记
        if "test_cases" in result:
            result["test_cases"] = _clean_test_cases(result["test_cases"])
        if "by_function_point" in result:
            for fp_data in result["by_function_point"].values():
                if "test_cases" in fp_data:
                    fp_data["test_cases"] = _clean_test_cases(fp_data["test_cases"])

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path_obj, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"{Fore.GREEN}✓ 结果已保存到: {output_path_obj}")
    except Exception as e:
        print(f"{Fore.RED}✗ 保存文件失败: {str(e)}")
        raise

    if split_output:
        by_function_point = result.get("by_function_point", {})
        if not by_function_point:
            print(f"{Fore.YELLOW}⚠ 无功能点明细可拆分，跳过按功能点保存")
            return

        target_dir = Path(output_dir) if output_dir else output_path_obj.parent / DEFAULT_OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        for function_point, data in by_function_point.items():
            slug = slugify_function_point(function_point)
            per_point_path = target_dir / f"{slug}.json"
            payload = {
                "function_point": function_point,
                "test_cases": _clean_test_cases(data.get("test_cases", [])),
                "warnings": data.get("warnings", []),
                "source": data.get("source", "")
            }
            with open(per_point_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"{Fore.GREEN}✓ 已按功能点拆分保存到目录: {target_dir}")


def print_result(result: Dict):
    """在控制台打印结果"""
    test_cases = result.get("test_cases", [])
    by_function_point = result.get("by_function_point", {})

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}生成的测试用例 ({len(test_cases)} 个)")
    print(f"{Fore.CYAN}{'='*60}\n")

    # 打印整体告警
    aggregated_warnings = []
    for function_point, data in by_function_point.items():
        for warning in data.get("warnings", []) or []:
            aggregated_warnings.append((function_point, warning))

    if aggregated_warnings:
        print(f"{Fore.YELLOW}警告汇总：")
        for function_point, warning in aggregated_warnings:
            print(f"  {Fore.YELLOW}- [{function_point}] {warning}")
        print()

    for i, case in enumerate(test_cases, 1):
        print(f"{Fore.YELLOW}[用例 {i}] {case.get('case_name', 'N/A')}")
        print(f"{Fore.WHITE}  描述: {case.get('description', 'N/A')}")
        print(f"{Fore.WHITE}  前置条件: {case.get('preconditions', 'N/A')}")
        print(f"{Fore.WHITE}  优先级: {case.get('priority', 'N/A')}")
        print(f"{Fore.WHITE}  测试步骤:")
        for step in case.get('steps', []):
            print(f"{Fore.WHITE}    - {step}")
        print(f"{Fore.WHITE}  预期结果: {case.get('expected_result', 'N/A')}")
        print()


def list_available_models():
    """列出所有可用的模型预设"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}可用的模型预设")
    print(f"{Fore.CYAN}{'='*60}\n")

    recommended = []
    others = []

    for key, config in MODEL_PRESETS.items():
        if config.get("recommended", False):
            recommended.append((key, config))
        else:
            others.append((key, config))

    if recommended:
        print(f"{Fore.GREEN}推荐模型：")
        for key, config in recommended:
            print(f"  {Fore.YELLOW}{key:20} {Fore.WHITE}- {config['description']}")
        print()

    if others:
        print(f"{Fore.CYAN}其他模型：")
        for key, config in others:
            print(f"  {Fore.YELLOW}{key:20} {Fore.WHITE}- {config['description']}")
        print()

    print(f"{Fore.CYAN}使用方法：")
    print(f"  {Fore.WHITE}python generate_test_cases.py --model qwen2.5")
    print(f"  {Fore.WHITE}python generate_test_cases.py --model deepseek-coder")
    print(f"  {Fore.WHITE}python generate_test_cases.py --model <模型名称>")
    print()


def main():
    """主函数 - 简化版：直接读取需求文件并生成测试用例"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="AI测试用例生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python generate_test_cases.py
  python generate_test_cases.py --model qwen2.5
  python generate_test_cases.py --model deepseek-coder --requirement my_requirement.txt
  python generate_test_cases.py --list-models
  python generate_test_cases.py --debug-extraction  # 调试功能点提取和原文匹配
        """
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="要使用的模型预设名称（使用 --list-models 查看所有可用模型）"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        help="直接指定模型名称（如：qwen2.5:7b）"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help=f"LLM服务地址（默认：{DEFAULT_CONFIG['llm_base_url']}）"
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        help=f"温度参数（默认：{DEFAULT_CONFIG['temperature']}）"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help=f"最大token数（默认：{DEFAULT_CONFIG['max_tokens']}）"
    )
    parser.add_argument(
        "--requirement", "-r",
        type=str,
        help=f"需求文档文件路径（默认：{DEFAULT_REQUIREMENT_FILE}）"
    )
    parser.add_argument(
        "--list-models", "-l",
        action="store_true",
        help="列出所有可用的模型预设"
    )
    parser.add_argument(
        "--test-limit",
        type=int,
        help="限制参与生成的功能点数量（默认使用代码中的 TEST_FUNCTION_POINTS_LIMIT 值）"
    )
    parser.add_argument(
        "--split-output",
        action="store_true",
        help="按功能点拆分保存输出文件"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help=f"拆分输出目录（默认：当前目录/{DEFAULT_OUTPUT_DIR}）"
    )
    parser.add_argument(
        "--debug-extraction",
        action="store_true",
        help="只执行功能点提取和原文匹配调试，不生成测试用例"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="并发处理功能点的最大线程数（默认: 4，建议范围: 2-8）"
    )

    args = parser.parse_args()

    # 如果只是列出模型，则显示后退出
    if args.list_models:
        list_available_models()
        sys.exit(0)

    try:
        # 获取脚本所在目录
        script_dir = Path(__file__).parent
        requirement_file = script_dir / (args.requirement or DEFAULT_REQUIREMENT_FILE)

        # 检查文件是否存在
        if not requirement_file.exists():
            print(f"{Fore.RED}✗ 错误: 需求文档文件不存在: {requirement_file}")
            print(f"{Fore.YELLOW}提示: 请确保文件存在")
            sys.exit(1)

        # 确定使用的模型（优先级：命令行参数 > 代码配置 > 环境变量 > 默认值）
        model_name = None
        if args.model_name:
            # 命令行直接指定模型名称（最高优先级）
            model_name = args.model_name
            print(f"{Fore.CYAN}使用命令行指定的模型: {model_name}")
        elif args.model:
            # 命令行使用预设模型
            if args.model not in MODEL_PRESETS:
                print(f"{Fore.RED}✗ 错误: 未知的模型预设: {args.model}")
                print(f"{Fore.YELLOW}提示: 使用 --list-models 查看所有可用模型")
                sys.exit(1)
            model_name = MODEL_PRESETS[args.model]["model"]
            print(f"{Fore.CYAN}使用命令行模型预设: {args.model} -> {model_name}")
        elif SELECTED_MODEL:
            # 使用代码中配置的模型（在文件顶部修改 SELECTED_MODEL 变量）
            if SELECTED_MODEL in MODEL_PRESETS:
                model_name = MODEL_PRESETS[SELECTED_MODEL]["model"]
                print(f"{Fore.CYAN}使用代码配置的模型预设: {SELECTED_MODEL} -> {model_name}")
            else:
                # 直接使用模型名称
                model_name = SELECTED_MODEL
                print(f"{Fore.CYAN}使用代码配置的模型: {model_name}")
        else:
            # 使用环境变量或默认模型
            model_name = os.getenv("LLM_MODEL", DEFAULT_CONFIG["default_model"])
            print(f"{Fore.CYAN}使用默认模型: {model_name}")

        # 读取需求文档
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}AI测试用例生成工具")
        print(f"{Fore.CYAN}{'='*60}\n")
        print(f"{Fore.CYAN}读取需求文档: {requirement_file}")
        requirement_doc = read_requirement_file(str(requirement_file))

        if not requirement_doc.strip():
            print(f"{Fore.RED}✗ 错误: 需求文档内容为空")
            sys.exit(1)

        print(f"{Fore.GREEN}✓ 需求文档长度: {len(requirement_doc)} 字符\n")

        # 初始化服务
        base_url = args.base_url or os.getenv("LLM_BASE_URL", DEFAULT_CONFIG["llm_base_url"])
        temperature = args.temperature or float(os.getenv("LLM_TEMPERATURE", DEFAULT_CONFIG["temperature"]))
        max_tokens = args.max_tokens or int(os.getenv("LLM_MAX_TOKENS", DEFAULT_CONFIG["max_tokens"]))

        # 功能点数量限制（命令行 > 环境变量 > 默认）
        if args.test_limit is not None:
            test_limit = max(args.test_limit, 0)
        else:
            env_limit = os.getenv("LLM_TEST_LIMIT")
            if env_limit and env_limit.isdigit():
                test_limit = int(env_limit)
            else:
                test_limit = None

        llm_service = LLMService(
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )

        generator = TestCaseGenerator(llm_service)

        # 调试模式：只执行功能点提取和原文匹配
        if args.debug_extraction:
            print(f"\n{Fore.CYAN}{'='*60}")
            print(f"{Fore.CYAN}调试模式：功能点提取和原文匹配")
            print(f"{Fore.CYAN}{'='*60}\n")

            # 提取功能点（带定位线索）
            function_points_data = generator.extract_function_points(requirement_doc)

            if not function_points_data:
                print(f"{Fore.RED}✗ 未能提取到功能点")
                sys.exit(1)

            # 显示功能点和定位线索
            print(f"{Fore.GREEN}✓ 提取到的功能点和定位线索：")
            for i, fp_data in enumerate(function_points_data, 1):
                print(f"\n{Fore.YELLOW}[功能点 {i}] {fp_data.get('name', 'N/A')}")
                print(f"  {Fore.CYAN}关键词: {', '.join(fp_data.get('keywords', []))}")
                print(f"  {Fore.CYAN}章节线索: {fp_data.get('section_hint', '无')}")
                print(f"  {Fore.CYAN}确切短语: {len(fp_data.get('exact_phrases', []))} 个")

                # 尝试提取原文片段
                try:
                    doc_snippet = generator.extract_relevant_section(requirement_doc, fp_data.get('name', ''), fp_data)
                    print(f"  {Fore.GREEN}原文片段: {len(doc_snippet)} 字符")
                    print(f"  {Fore.WHITE}预览: {doc_snippet[:200]}...")
                except Exception as e:
                    print(f"  {Fore.RED}原文提取失败: {str(e)}")

            print(f"\n{Fore.GREEN}✓ 调试完成")
            sys.exit(0)

        # 生成测试用例
        result = generator.generate_test_cases(requirement_doc, limit=test_limit, max_workers=args.max_workers)

        # 打印结果
        print_result(result)

        # 自动保存到文件
        output_file = script_dir / f"test_cases_{requirement_file.stem}.json"
        save_result(
            result,
            str(output_file),
            split_output=args.split_output,
            output_dir=args.output_dir
        )

        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}✓ 完成! 结果已保存到: {output_file}")
        print(f"{Fore.GREEN}{'='*60}\n")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
