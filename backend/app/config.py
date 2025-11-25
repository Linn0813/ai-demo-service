# encoding: utf-8
"""
服务运行配置。

为避免额外依赖，简单地从环境变量读取，提供默认值即可。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - 可选依赖
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


@dataclass(slots=True)
class Settings:
    app_name: str = _env("AI_DEMO_APP_NAME", "AI Demo Service")
    app_version: str = _env("AI_DEMO_APP_VERSION", "0.1.0")
    log_level: str = _env("AI_DEMO_LOG_LEVEL", "INFO")
    llm_base_url: str = _env("AI_DEMO_LLM_BASE_URL", "http://localhost:11434")
    llm_default_model: str = _env("AI_DEMO_DEFAULT_MODEL", "qwen2.5:7b")
    llm_max_tokens: int = int(_env("AI_DEMO_MAX_TOKENS", "8000"))
    
    # 飞书应用配置
    feishu_app_id: str = _env("FEISHU_APP_ID", "")
    feishu_app_secret: str = _env("FEISHU_APP_SECRET", "")
    feishu_api_base_url: str = _env("FEISHU_API_BASE_URL", "https://open.feishu.cn/open-apis")
    feishu_token_cache_ttl: int = int(_env("FEISHU_TOKEN_CACHE_TTL", "7200"))
    # 用户身份权限配置
    feishu_use_user_token: bool = _env("FEISHU_USE_USER_TOKEN", "false").lower() == "true"
    feishu_redirect_uri: str = _env("FEISHU_REDIRECT_URI", "http://localhost:8113/api/v1/feishu/oauth/callback")
    # 前端地址配置（用于OAuth回调后的重定向）
    frontend_url: str = _env("FRONTEND_URL", "http://localhost:3000")


settings = Settings()

__all__ = ["settings", "Settings"]
