"""AI调试信息记录工具（共享）"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from shared.logger import log


_BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "debug" / "ai_runs"


def _ensure_dir() -> Path:
    try:
        _BASE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("创建AI调试目录失败: %s", exc)
    return _BASE_DIR


def _build_filename(run_type: str, run_id: Optional[str] = None) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    suffix = run_id or f"{os.getpid()}"
    return f"{timestamp}_{run_type}_{suffix}.json"


def record_ai_debug(run_type: str, payload: Dict[str, Any], run_id: Optional[str] = None) -> None:
    """
    将AI运行调试信息落盘，便于后续分析。

    Args:
        run_type: 运行类型（如 "extract_modules", "generate_test_cases", "knowledge_base_qa"）
        payload: 需要记录的数据
        run_id: 可选的运行ID，用于串联同一次流程
    """
    try:
        directory = _ensure_dir()
        filename = _build_filename(run_type, run_id)
        file_path = directory / filename

        payload_to_dump = {
            "run_type": run_type,
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": payload,
        }

        with open(file_path, "w", encoding="utf-8") as fp:
            json.dump(payload_to_dump, fp, ensure_ascii=False, indent=2)
        log.info("AI调试信息已保存: %s", file_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("AI调试信息保存失败: %s", exc)

