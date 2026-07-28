#!/usr/bin/env python3
"""Download a video via yt-dlp, or resolve a local file path.

Also fetches subtitles (manual first, then auto-generated) in VTT format so
transcribe.py can parse them without needing Whisper.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}

# 浏览器 cookie 来源（用于拉取需要登录才能访问的字幕，如 B 站）。
# 可通过环境变量 WATCH_BROWSER 覆盖。支持 chrome/edge/firefox/brave/chromium/opera/safari/vivaldi。
# 设为空字符串则禁用 cookie 读取。
#
# 如果浏览器 cookie 解密失败（如 Edge 120+ 的 App-Bound Encryption），
# 可用浏览器扩展导出 cookies.txt 文件，然后设置环境变量 WATCH_COOKIE_FILE 指向它。
# 优先级：WATCH_COOKIE_FILE > WATCH_BROWSER
#
# 注意：这些值也可以写在 ~/.config/watch/.env 文件里（由 config.py 管理）。
# _cookie_args() 会动态读取 .env，所以这里只用环境变量作为初始默认值。
DEFAULT_BROWSER = "edge"


def is_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def resolve_local(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    if p.suffix.lower() not in VIDEO_EXTS:
        print(
            f"[watch] warning: {p.suffix} is not a known video extension, proceeding anyway",
            file=sys.stderr,
        )
    return {
        "video_path": str(p),
        "subtitle_path": None,
        "info": {"title": p.name, "url": str(p)},
        "downloaded": False,
    }


def _cookie_args(source: str = "") -> list[str]:
    """构造 yt-dlp 的 cookie 参数，根据 URL 域名智能选择 cookie 来源。

    优先级：
    1. 如果 WATCH_COOKIE_FILE 指向的 cookie 文件包含目标域名的 cookie，用它
    2. 否则回退到 WATCH_BROWSER 指定的浏览器 cookie

    这样同一个 cookies.txt 可以放多个网站的 cookie（yt-dlp 会按域名过滤），
    而未在 cookie 文件中的网站（如抖音）会自动回退到浏览器 cookie。

    Args:
        source: 视频 URL 或本地路径。为空或本地路径时，保持原有行为（用 cookie 文件）

    Returns:
        参数列表（如 ["--cookies", "C:/path/to/cookies.txt"]），
        或 ["--cookies-from-browser", "edge"]，或空列表（禁用时）
    """
    # 动态读取 .env 文件（覆盖模块加载时的环境变量）
    from config import read_env_file
    env = read_env_file()

    def _get(key: str, default: str = "") -> str:
        """优先环境变量，其次 .env 文件，最后默认值。"""
        return os.environ.get(key) or env.get(key) or default

    cookie_file = _get("WATCH_COOKIE_FILE", "")
    browser = _get("WATCH_BROWSER", DEFAULT_BROWSER)

    # 提取 source 的域名用于匹配 cookie 文件
    source_domain = ""
    if source and is_url(source):
        source_domain = urlparse(source).netloc.lower()

    # 1. 检查 cookie 文件是否包含目标域名的 cookie
    if cookie_file:
        cookie_path = Path(cookie_file).expanduser()
        if cookie_path.exists():
            # 如果无法识别域名（本地文件或空 URL），直接用 cookie 文件
            if not source_domain:
                return ["--cookies", str(cookie_path)]
            # 读取 cookie 文件，检查是否包含目标域名
            # Netscape cookie 格式：每行用 tab 分隔，第 1 列是域名
            try:
                content = cookie_path.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        cookie_domain = parts[0].lower().lstrip(".")
                        # 双向匹配：cookie 域名是 URL 域名的后缀，或反之
                        if cookie_domain and (
                            source_domain.endswith(cookie_domain)
                            or cookie_domain.endswith(source_domain)
                        ):
                            return ["--cookies", str(cookie_path)]
                # cookie 文件不包含目标域名，回退到浏览器 cookie
                print(
                    f"[watch] cookie file has no cookies for {source_domain}, "
                    f"falling back to browser cookies",
                    file=sys.stderr,
                )
            except OSError:
                # 读取失败，回退到浏览器 cookie
                print(
                    f"[watch] failed to read cookie file, "
                    f"falling back to browser cookies",
                    file=sys.stderr,
                )
        else:
            print(
                f"[watch] warning: WATCH_COOKIE_FILE={cookie_file} not found, "
                f"falling back to browser cookies",
                file=sys.stderr,
            )
    # 2. 用浏览器 cookie
    if browser:
        return ["--cookies-from-browser", browser]
    return []


def _pick_subtitle(out_dir: Path) -> Path | None:
    """选择最佳字幕文件，优先中文，其次英文，最后任意可用字幕。

    支持 VTT 和 SRT 两种格式（Bilibili 提供 SRT，YouTube 提供 VTT）。

    Args:
        out_dir: 字幕文件所在目录

    Returns:
        字幕文件路径，或 None 如果没有字幕
    """
    # 同时收集 VTT 和 SRT 文件
    candidates = sorted(
        list(out_dir.glob("video*.vtt")) + list(out_dir.glob("video*.srt"))
    )
    if not candidates:
        return None
    # 优先中文字幕（zh., zh-CN., zh-Hans. 等）
    preferred = [
        c for c in candidates
        if any(marker in c.name for marker in (".zh.", ".zh-CN.", ".zh-Hans.", ".zh-Hant.", ".zh-orig."))
    ]
    if preferred:
        return preferred[0]
    # 其次英文字幕
    preferred = [
        c for c in candidates
        if any(marker in c.name for marker in (".en.", ".en-US.", ".en-GB.", ".en-orig."))
    ]
    return preferred[0] if preferred else candidates[0]


def _pick_video(out_dir: Path) -> Path | None:
    for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus"):
        for candidate in out_dir.glob(f"video*{ext}"):
            return candidate
    for candidate in out_dir.glob("video.*"):
        if candidate.suffix.lower() in VIDEO_EXTS:
            return candidate
    return None


def fetch_captions(url: str, out_dir: Path) -> dict:
    """Fetch metadata and best available VTT captions without downloading video."""
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        # 优先中文字幕，其次英文，最后任意语言
        # sub-format 按 srt/vtt/best 顺序尝试，避免 Bilibili SRT 转 VTT 失败
        # 不强制 convert-subs，保留原始格式（transcribe.py 同时支持 VTT 和 SRT）
        "--sub-langs", "zh.*,en.*,all",
        "--sub-format", "srt/vtt/best",
        "--no-playlist",
        "--ignore-errors",
    ]
    # 按 URL 域名选择 cookie 来源（B 站用 cookie 文件，其他网站用浏览器 cookie）
    cmd += _cookie_args(url)
    cmd += [
        "-o", output_template,
        "--",
        url,
    ]
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)
    return {
        "video_path": None,
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": False,
    }


def _read_info(info_path: Path, url: str) -> dict:
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
                "url": raw.get("webpage_url") or url,
            }
        except Exception as exc:
            print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
            info = {"url": url}
    return info


def download_url(
    url: str,
    out_dir: Path,
    audio_only: bool = False,
) -> dict:
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    # audio_only 时优先纯音频流，回退到最佳音视频合并流（部分平台如抖音
    # 不提供独立音频流，需要下载完整视频再由 ffmpeg 提取音频）
    fmt = "ba/b" if audio_only else "bv*[height<=720]+ba/b[height<=720]/bv+ba/b"
    cmd = [
        "yt-dlp",
        "-N", "8",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        # 优先中文字幕，其次英文，最后任意语言
        # sub-format 按 srt/vtt/best 顺序尝试，避免 Bilibili SRT 转 VTT 失败
        # 不强制 convert-subs，保留原始格式（transcribe.py 同时支持 VTT 和 SRT）
        "--sub-langs", "zh.*,en.*,all",
        "--sub-format", "srt/vtt/best",
        "--no-playlist",
        "--ignore-errors",
    ]
    # 按 URL 域名选择 cookie 来源（B 站用 cookie 文件，其他网站用浏览器 cookie）
    cmd += _cookie_args(url)
    cmd += [
        "-o", output_template,
        "--",
        url,
    ]

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    video = _pick_video(out_dir)
    if video is None:
        raise SystemExit(
            f"yt-dlp did not produce a video file in {out_dir} (exit {result.returncode})"
        )

    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)

    return {
        "video_path": str(video),
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": True,
    }


def download(
    source: str,
    out_dir: Path,
    audio_only: bool = False,
) -> dict:
    if is_url(source):
        return download_url(source, out_dir, audio_only=audio_only)
    return resolve_local(source)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: download.py <url-or-path> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    result = download(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
