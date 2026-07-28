"""ffmpeg/ffprobe 路径解析工具。

在 Windows 上，PATH 中的 ffmpeg 可能是某些应用自带的精简版（如 Trae IDE 的
ffmpeg 只用于视频合并，没有 image2 muxer，无法输出 JPEG）。本模块优先返回完整版
ffmpeg 的路径。

判断完整版的方法：尝试运行 `ffmpeg -muxers` 并搜索 `image2` 字符串。完整版应包含
image2 muxer。结果会缓存，避免重复调用。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


# Windows 上 winget 安装的 ffmpeg 可能所在的候选路径（按优先级排序）
# winget 安装路径格式: %LOCALAPPDATA%\Microsoft\WinGet\Packages\<pkg>\ffmpeg-<ver>\bin\
_WIN_CANDIDATES = [
    # winget Gyan.FFmpeg
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft"
    / "WinGet"
    / "Packages",
    # scoop
    Path.home() / "scoop" / "apps" / "ffmpeg" / "current" / "bin",
    # 常见手动安装路径
    Path(r"C:\Program Files\ffmpeg\bin"),
    Path(r"C:\ffmpeg\bin"),
    Path(r"C:\tools\ffmpeg\bin"),
]


def _is_full_ffmpeg(ffmpeg_path: str) -> bool:
    """检查 ffmpeg 是否为完整版（包含 image2 muxer）。

    Args:
        ffmpeg_path: ffmpeg 可执行文件路径

    Returns:
        True 如果 ffmpeg 支持 image2 muxer（可输出 JPEG 序列）
    """
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-muxers"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "image2" in (result.stdout or "")
    except (subprocess.TimeoutExpired, OSError):
        return False


@lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    """查找完整版 ffmpeg 路径。

    优先级：
    1. 环境变量 FFMPEG_PATH（如果设置）
    2. Windows 候选路径（winget/scoop/手动安装）
    3. PATH 中的 ffmpeg（如果通过完整性检查）
    4. PATH 中的 ffmpeg（即使不完整，作为最后兜底）

    Returns:
        ffmpeg 可执行文件路径，或 None 如果完全找不到
    """
    # 1. 环境变量
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. Windows 候选路径（只在 Windows 上检查）
    if sys.platform == "win32":
        for candidate_root in _WIN_CANDIDATES:
            if not candidate_root.exists():
                continue
            # winget 路径需要递归查找
            if "WinGet" in str(candidate_root):
                for exe in candidate_root.rglob("ffmpeg.exe"):
                    if _is_full_ffmpeg(str(exe)):
                        return str(exe)
            else:
                exe = candidate_root / "ffmpeg.exe"
                if exe.exists() and _is_full_ffmpeg(str(exe)):
                    return str(exe)

    # 3. PATH 中的 ffmpeg
    which_path = shutil.which("ffmpeg")
    if which_path:
        if _is_full_ffmpeg(which_path):
            return which_path
        # 4. 兜底：即使不完整也返回（让 ffmpeg 自己报错）
        return which_path

    return None


@lru_cache(maxsize=1)
def find_ffprobe() -> str | None:
    """查找 ffprobe 路径，优先与 ffmpeg 同目录。

    Returns:
        ffprobe 可执行文件路径，或 None 如果找不到
    """
    # 1. 环境变量
    env_path = os.environ.get("FFPROBE_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. 与 ffmpeg 同目录
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        sibling = Path(ffmpeg).parent / "ffprobe.exe"
        if sibling.exists():
            return str(sibling)
        sibling_unix = Path(ffmpeg).parent / "ffprobe"
        if sibling_unix.exists():
            return str(sibling_unix)

    # 3. PATH
    return shutil.which("ffprobe")


def get_ffmpeg_cmd(extra_args: list[str] | None = None) -> list[str]:
    """构造 ffmpeg 命令，自动前置完整版 ffmpeg 路径。

    Args:
        extra_args: ffmpeg 参数列表

    Returns:
        完整命令列表，[ffmpeg_path, *extra_args]
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise SystemExit(
            "ffmpeg is not installed. Install with: winget install Gyan.FFmpeg"
        )
    cmd = [ffmpeg]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def get_ffprobe_cmd(extra_args: list[str] | None = None) -> list[str]:
    """构造 ffprobe 命令，自动前置完整版 ffprobe 路径。

    Args:
        extra_args: ffprobe 参数列表

    Returns:
        完整命令列表，[ffprobe_path, *extra_args]
    """
    ffprobe = find_ffprobe()
    if ffprobe is None:
        raise SystemExit(
            "ffprobe is not installed. Install with: winget install Gyan.FFmpeg"
        )
    cmd = [ffprobe]
    if extra_args:
        cmd.extend(extra_args)
    return cmd
