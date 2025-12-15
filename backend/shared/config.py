# encoding: utf-8
"""
统一配置管理

合并应用配置和引擎配置，统一管理所有配置项。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - 可选依赖
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def _env(key: str, default: str) -> str:
    """从环境变量读取配置"""
    return os.getenv(key, default)


# ==================== 应用配置 ====================

@dataclass(slots=True)
class Settings:
    """应用设置"""
    app_name: str = _env("AI_DEMO_APP_NAME", "AI Demo Service")
    app_version: str = _env("AI_DEMO_APP_VERSION", "0.1.0")
    log_level: str = _env("AI_DEMO_LOG_LEVEL", "INFO")
    
    # LLM 配置（向后兼容）
    llm_provider: str = _env("AI_DEMO_LLM_PROVIDER", "ollama")
    llm_base_url: str = _env("AI_DEMO_LLM_BASE_URL", "http://localhost:11434")
    llm_api_key: str = _env("AI_DEMO_LLM_API_KEY", "")
    llm_default_model: str = _env("AI_DEMO_DEFAULT_MODEL", "qwen2.5:7b")
    llm_max_tokens: int = int(_env("AI_DEMO_MAX_TOKENS", "8000"))
    llm_temperature: float = float(_env("AI_DEMO_LLM_TEMPERATURE", "0.7"))
    azure_deployment: str = _env("AI_DEMO_AZURE_DEPLOYMENT", "")
    azure_api_version: str = _env("AI_DEMO_AZURE_API_VERSION", "2024-12-01-preview")
    
    # 后端服务配置
    backend_host: str = _env("AI_DEMO_BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(_env("AI_DEMO_BACKEND_PORT", "8113"))
    backend_reload: bool = _env("AI_DEMO_BACKEND_RELOAD", "true").lower() == "true"
    cors_origins: str = _env("AI_DEMO_CORS_ORIGINS", "*")
    
    # 飞书应用配置
    feishu_app_id: str = _env("FEISHU_APP_ID", "")
    feishu_app_secret: str = _env("FEISHU_APP_SECRET", "")
    feishu_api_base_url: str = _env("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
    feishu_token_cache_ttl: int = int(_env("FEISHU_TOKEN_CACHE_TTL", "7200"))
    feishu_use_user_token: bool = _env("FEISHU_USE_USER_TOKEN", "false").lower() == "true"
    feishu_redirect_uri: str = _env("FEISHU_REDIRECT_URI", "http://localhost:8113/api/v1/feishu/oauth/callback")
    
    # 前端地址配置
    frontend_url: str = _env("FRONTEND_URL", "http://localhost:3000")


settings = Settings()


# ==================== LLM 配置 ====================

# 预定义的模型配置
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
    # GPT-5.2 系列（OpenAI兼容API）
    "gpt-5.2": {
        "model": "gpt-5.2",
        "description": "GPT-5.2 - OpenAI兼容API模型",
        "recommended": True
    },
}

# LLM 默认配置
LLM_CONFIG = {
    "provider": _env("AI_DEMO_LLM_PROVIDER", "ollama"),  # ollama 或 openai
    "llm_base_url": _env("AI_DEMO_LLM_BASE_URL", "http://localhost:11434"),
    "api_key": _env("AI_DEMO_LLM_API_KEY", ""),
    "default_model": _env("AI_DEMO_DEFAULT_MODEL", "qwen2.5:7b"),
    "azure_deployment": _env("AI_DEMO_AZURE_DEPLOYMENT", ""),
    "azure_api_version": _env("AI_DEMO_AZURE_API_VERSION", "2024-12-01-preview"),
    "temperature": float(_env("AI_DEMO_LLM_TEMPERATURE", "0.7")),
    "max_tokens": int(_env("AI_DEMO_MAX_TOKENS", "8000")),
    "timeout": int(_env("AI_DEMO_LLM_TIMEOUT", "600"))
}

# 向后兼容
DEFAULT_CONFIG = LLM_CONFIG


# ==================== Embedding 配置 ====================

EMBEDDING_CONFIG = {
    "provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:7b",
    "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "device": "cpu",
    "batch_size": 32,
}


# ==================== 测试用例生成配置 ====================

class RepairConfig:
    """修复功能配置类"""
    FORMAT_FIX_MIN_LENGTH = 50
    FORMAT_FIX_KEYWORD_COUNT = 3
    SIMILARITY_THRESHOLD = 0.50
    KEYWORD_BONUS = 0.25
    CORE_KEYWORD_BONUS = 0.20
    MIN_SENTENCE_LENGTH = 10
    MIN_VALID_CHARS = 5
    KEY_PHRASE_COUNT = 3
    MIN_PHRASE_LENGTH = 5
    PRECONDITIONS_DEFAULT = "满足测试前置条件"
    GENERIC_EXPECTED_PATTERNS = [
        "点击关闭直接消失",
        "正确显示",
        "正常显示",
        "验证通过",
        "符合预期",
        "满足要求",
        "操作成功",
        "显示正确",
        "功能正常",
    ]
    GENERIC_DETECTION_THRESHOLD = 0.8


class ExtractionConfig:
    """文档提取相关配置"""
    FALLBACK_SNIPPET_LENGTH = 2000
    MIN_SNIPPET_LENGTH = 400
    TARGET_SNIPPET_LENGTH = 800
    MAX_SNIPPET_LENGTH = 1200
    CONTEXT_BEFORE = 80
    CONTEXT_AFTER = 200
    EXTENDED_CONTEXT_BEFORE = 100
    EXTENDED_CONTEXT_AFTER = 400
    SECTION_WINDOW_BEFORE = 20
    SECTION_WINDOW_AFTER = 80
    MAX_MATCH_POSITIONS = 10
    FUZZY_MATCH_THRESHOLD = 0.45
    AUTO_DETECT_HEADER_LINES = True
    MAX_HEADER_LINES = 15
    MIN_HEADER_LINES = 3
    MIN_TERM_LENGTH = 3
    MIN_PARTIAL_MATCH_LENGTH = 5
    ENABLE_FUNCTION_POINT_EXTRACTION = True
    COMPLEX_MODULE_THRESHOLD = 500
    MIN_FUNCTION_POINTS_FOR_EXTRACTION = 2
    MAX_BACKWARD_SEARCH_LINES = 10
    MIN_BACKWARD_SEARCH_LINES = 3
    SUB_MODULE_MAX_DISTANCE = 100
    MODULE_SEARCH_EXTEND_RANGE = 50
    MAIN_MODULE_SEARCH_EXTEND_RANGE = 200
    CONTENT_EXTEND_RANGE = 50
    MODULE_POSITION_TOLERANCE = 5
    SHORT_MODULE_NAME_LENGTH = 6
    MODULE_TITLE_REMAINING_LENGTH = 3
    SUB_MODULE_KEYWORDS = [
        "弹窗", "半弹窗", "对话框", "设置", "配置",
        "规则", "定义", "算法", "说明", "解释",
        "详情", "信息", "卡片", "列表", "表单"
    ]
    SHORT_SUB_MODULE_KEYWORDS = ["弹窗", "设置", "规则", "定义", "解释", "详情"]
    METADATA_SECTION_KEYWORDS = [
        "上线后", "数据准备", "准备策略",
        "多语言文档", "多语言", "语言文档",
        "设计稿", "设计", "交互稿",
        "逻辑补充", "补充说明",
        "审批", "签名", "审批与签名",
        "参考设计稿", "参考设计",
    ]


# ==================== 预编译正则表达式 ====================

RE_NORMALIZE = re.compile(r"[\s`~!@#$%^&*()_\-+=\[\]{}|\\;:'\",.<>/?·！￥…（）—【】、；：" "''《》？]")
RE_SPLIT_TOKENS = re.compile(r"[、，,;；：:（）()\\-\\s]+")
RE_SPLIT_PHRASES = re.compile(r'[，,。！？!?\n]+')
RE_EXTRACT_KEYWORDS = re.compile(r'[^\w\u4e00-\u9fff]+')
RE_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])")
RE_TITLE_LINE = re.compile(r'^\d+\.\s*[^。！？!?]{0,15}[：:]?\s*$')
RE_JSON_CASE = re.compile(r'\{\s*"case_name"[^}]+\}', re.DOTALL)

# 繁体标点映射表
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


__all__ = [
    "settings",
    "Settings",
    "MODEL_PRESETS",
    "LLM_CONFIG",
    "DEFAULT_CONFIG",
    "EMBEDDING_CONFIG",
    "RepairConfig",
    "ExtractionConfig",
    "RE_NORMALIZE",
    "RE_SPLIT_TOKENS",
    "RE_SPLIT_PHRASES",
    "RE_EXTRACT_KEYWORDS",
    "RE_SENTENCE_SPLIT",
    "RE_TITLE_LINE",
    "RE_JSON_CASE",
    "TRADITIONAL_TO_SIMPLIFIED_PUNCTUATION",
]

