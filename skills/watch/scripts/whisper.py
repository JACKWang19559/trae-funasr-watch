#!/usr/bin/env python3
"""视频音频转写模块，使用 FunASR 本地转写。

已从 Whisper API 迁移到 FunASR + SenseVoiceSmall 本地转写，
无需 API key，完全离线运行（首次运行需下载模型）。

返回 segments 格式与 transcribe.parse_vtt 一致：
    [{"start": float, "end": float, "text": str}, ...]

本模块作为 funasr_transcribe 的薄包装层保留，向后兼容 watch.py
的 import whisper 调用。实际转写逻辑在 funasr_transcribe.py 中。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 实际转写逻辑委托给 funasr_transcribe
from funasr_transcribe import transcribe_video


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "usage: whisper.py <video-path> [<audio-out.wav>]",
            file=sys.stderr,
        )
        raise SystemExit(2)

    video = sys.argv[1]
    audio_out = (
        Path(sys.argv[2])
        if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
        else Path("audio.wav")
    )

    segments, backend = transcribe_video(video, audio_out)
    print(json.dumps({"backend": backend, "segments": segments}, indent=2))
