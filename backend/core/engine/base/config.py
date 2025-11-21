# encoding: utf-8
"""
AI 服务通用配置（共享）
"""
import re
from typing import Any, Dict

# 预定义的模型配置（仅包含本地可用的模型）
MODEL_PRESETS: Dict[str, Dict[str, Any]] = {
    # Qwen 系列（推荐，中文能力强）
    "qwen2.5": {
        "model": "qwen2.5:7b",
        "description": "Qwen 2.5 7B - 中文能力强，通用对话（推荐）",
        "recommended": True
    },
    # DeepSeek 系列
    "deepseek-coder": {
        "model": "deepseek-coder:6.7b",
        "description": "DeepSeek Coder 6.7B - 代码能力强，适合测试用例生成",
        "recommended": True
    },
    # LLaMA 系列
    "llama2": {
        "model": "llama2:7b",
        "description": "LLaMA 2 7B - Meta开源模型，通用对话",
        "recommended": False
    },
}

# LLM 默认配置（测试用例生成和知识库问答共用）
LLM_CONFIG = {
    "llm_base_url": "http://localhost:11434",  # Ollama默认地址
    "default_model": "qwen2.5:7b",
    "temperature": 0.7,
    "max_tokens": 8000,  # 大幅增加token数以支持生成更多测试用例
    "timeout": 600  # 增加超时时间到10分钟
}

# Embedding 配置（知识库使用）
EMBEDDING_CONFIG = {
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "device": "cpu",  # cpu, cuda
    "batch_size": 32,
}

# 向后兼容：保持 DEFAULT_CONFIG 别名
DEFAULT_CONFIG = LLM_CONFIG


class RepairConfig:
    """修复功能配置类（通用配置，不依赖特定业务）"""
    # 格式修复阈值
    FORMAT_FIX_MIN_LENGTH = 50
    FORMAT_FIX_KEYWORD_COUNT = 3

    # 相似度匹配阈值（降低阈值以提高匹配率）
    SIMILARITY_THRESHOLD = 0.55  # 进一步降低阈值，提高匹配率
    KEYWORD_BONUS = 0.2  # 增加关键词匹配的权重
    CORE_KEYWORD_BONUS = 0.15  # 核心关键词匹配的额外权重

    # 候选句子过滤
    MIN_SENTENCE_LENGTH = 10
    MIN_VALID_CHARS = 5

    # 匹配检查
    KEY_PHRASE_COUNT = 3
    MIN_PHRASE_LENGTH = 5

    # preconditions修复
    PRECONDITIONS_DEFAULT = "满足测试前置条件"


class ExtractionConfig:
    """文档提取相关配置"""
    # 回退策略：当找不到匹配时使用的文档片段长度
    FALLBACK_SNIPPET_LENGTH = 2000

    # 最小片段长度
    MIN_SNIPPET_LENGTH = 400
    # 目标片段长度（用于裁剪）
    TARGET_SNIPPET_LENGTH = 800
    # 允许的最大片段长度
    MAX_SNIPPET_LENGTH = 1200

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

    # 文档结构检测配置
    # 文档开头可能包含通用描述，自动检测或跳过这些行
    AUTO_DETECT_HEADER_LINES = True  # 是否自动检测文档头部
    MAX_HEADER_LINES = 15  # 如果自动检测失败，最多跳过多少行作为头部
    MIN_HEADER_LINES = 3  # 最少跳过多少行（用于短文档）

    # 匹配策略配置
    MIN_TERM_LENGTH = 3  # 最小关键词长度
    MIN_PARTIAL_MATCH_LENGTH = 5  # 部分匹配的最小长度（避免误匹配）

    # 功能点识别配置（智能两阶段生成）
    ENABLE_FUNCTION_POINT_EXTRACTION = True  # 是否启用功能点识别
    COMPLEX_MODULE_THRESHOLD = 500  # 复杂模块阈值（字符数），超过此值需要识别功能点
    MIN_FUNCTION_POINTS_FOR_EXTRACTION = 2  # 至少需要识别到多少个功能点才进行拆分

    # 边界检测配置
    MAX_BACKWARD_SEARCH_LINES = 10  # 向上查找章节边界的最大行数
    MIN_BACKWARD_SEARCH_LINES = 3  # 最少向上查找的行数

    # 模块层级识别配置
    SUB_MODULE_MAX_DISTANCE = 100  # 子模块与主模块的最大距离（行数）
    MODULE_SEARCH_EXTEND_RANGE = 50  # 模块搜索扩展范围（行数）
    MAIN_MODULE_SEARCH_EXTEND_RANGE = 200  # 主模块搜索扩展范围（行数）
    CONTENT_EXTEND_RANGE = 50  # 内容扩展范围（行数）
    MODULE_POSITION_TOLERANCE = 5  # 模块位置容差（行数），用于去重判断
    SHORT_MODULE_NAME_LENGTH = 6  # 短模块名称长度阈值
    MODULE_TITLE_REMAINING_LENGTH = 3  # 模块标题剩余部分长度阈值

    # 文档元信息识别配置（用于排除文档末尾的元信息部分）
    METADATA_SECTION_KEYWORDS = [
        "上线后", "数据准备", "准备策略",
        "多语言文档", "多语言", "语言文档",
        "设计稿", "设计", "交互稿",
        "逻辑补充", "补充说明",
        "审批", "签名", "审批与签名",
        "参考设计稿", "参考设计",
    ]  # 如果行中包含这些关键词，可能是元信息部分


# 预编译常用的正则表达式（性能优化）
RE_NORMALIZE = re.compile(r"[\s`~!@#$%^&*()_\-+=\[\]{}|\\;:'\",.<>/?·！￥…（）—【】、；：" "''《》？]")
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

