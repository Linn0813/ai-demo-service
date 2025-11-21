# encoding: utf-8
"""基础共享服务模块"""

from .config import (
    DEFAULT_CONFIG,
    EMBEDDING_CONFIG,
    LLM_CONFIG,
    MODEL_PRESETS,
    ExtractionConfig,
    RepairConfig,
)
from .debug_recorder import record_ai_debug
from .llm_service import LLMService

__all__ = [
    "LLMService",
    "LLM_CONFIG",
    "EMBEDDING_CONFIG",
    "DEFAULT_CONFIG",
    "MODEL_PRESETS",
    "ExtractionConfig",
    "RepairConfig",
    "record_ai_debug",
]

