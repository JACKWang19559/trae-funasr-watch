#!/usr/bin/env python3
"""Shared /watch configuration helpers."""
from __future__ import annotations

import os
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"

DEFAULT_DETAIL = "balanced"

DETAILS = {"transcript", "efficient", "balanced", "token-burner"}


def read_env_file(path: Path | None = None) -> dict[str, str]:
    if path is None:
        path = CONFIG_FILE
    values: dict[str, str] = {}
    if not path.exists():
        return values
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, _, value = raw.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        else:
            # Strip an inline comment (a '#' preceded by whitespace) from an
            # unquoted value. Without this, `WATCH_DETAIL=balanced  # note`
            # parses as "balanced  # note", fails validation, and silently
            # falls back to the default. Keeps '#' inside quotes / API keys.
            for i, ch in enumerate(value):
                if ch == "#" and i > 0 and value[i - 1] in " \t":
                    value = value[:i].rstrip()
                    break
        values[key.strip()] = value
    return values


def get_config() -> dict[str, object]:
    file_values = read_env_file()

    detail = (
        os.environ.get("WATCH_DETAIL")
        or file_values.get("WATCH_DETAIL")
        or DEFAULT_DETAIL
    )
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL

    return {
        "detail": detail,
        "config_file": str(CONFIG_FILE),
    }


def get_work_dir() -> str | None:
    """读取用户配置的工作目录（WATCH_WORK_DIR）。

    优先级：
    1. 环境变量 WATCH_WORK_DIR
    2. ~/.config/watch/.env 中的 WATCH_WORK_DIR
    3. 返回 None（由调用方决定默认行为）

    Returns:
        用户配置的工作目录路径，或 None 如果未配置
    """
    file_values = read_env_file()
    work_dir = (
        os.environ.get("WATCH_WORK_DIR")
        or file_values.get("WATCH_WORK_DIR")
        or None
    )
    return work_dir.strip() if work_dir and work_dir.strip() else None


def detect_trae_workspace() -> str | None:
    """自动检测 Trae 用户项目根目录。

    Trae 在启动时设置 SAFE_RM_ALLOWED_PATH 环境变量，其第一个路径
    就是用户的主要工作目录（Primary working directory）。通过读取
    这个环境变量，watch.py 可以自动获取用户项目根目录，无需用户
    手动配置 WATCH_WORK_DIR。

    Returns:
        用户项目根目录路径，或 None 如果无法检测
    """
    safe_rm_path = os.environ.get("SAFE_RM_ALLOWED_PATH", "")
    if not safe_rm_path:
        return None
    # SAFE_RM_ALLOWED_PATH 是分号分隔的路径列表，第一个是用户项目根目录
    first_path = safe_rm_path.split(";")[0].strip()
    if not first_path:
        return None
    # 验证路径存在
    if Path(first_path).exists():
        return first_path
    return None


def frame_cap(detail: str) -> int | None:
    if detail == "efficient":
        return 50
    if detail == "balanced":
        return 100
    if detail == "token-burner":
        return None
    if detail == "transcript":
        return None
    return 100
