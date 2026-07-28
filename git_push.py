"""初始化 git 仓库并推送到 GitHub。

本脚本在 watch/0.2.0 目录执行以下操作：
1. git init 初始化本地仓库
2. git add 添加所有文件（受 .gitignore 控制）
3. git commit 创建首次提交
4. 关联远程仓库 https://github.com/JACKWang19559/trae-funasr-watch.git
5. git push 推送到 main 分支

执行完毕后本脚本会自删除。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# 远程仓库地址
REMOTE_URL = "https://github.com/JACKWang19559/trae-funasr-watch.git"

# 提交信息
COMMIT_MESSAGE = (
    "feat: 初始提交 - Trae 视频理解插件\n\n"
    "- 基于 bradautomates/claude-video v0.2.0 改造\n"
    "- 使用 FunASR + SenseVoiceSmall 替代 Whisper API\n"
    "- 支持本地转写（GPU/CPU 自动切换）\n"
    "- 多平台 Cookie 支持（Bilibili/抖音）\n"
    "- 字幕保存到 transcript.txt\n"
    "- SenseVoiceSmall 标签自动过滤"
)


def run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """执行 git 命令并返回结果。

    Args:
        args: git 命令参数列表，例如 ["init", "-b", "main"]
        cwd: 工作目录

    Returns:
        元组 (返回码, 标准输出, 标准错误)
    """
    cmd = ["git"] + args
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    """主函数：执行 git 初始化和推送。

    Returns:
        退出码，0 表示成功
    """
    # 工作目录为脚本所在目录
    work_dir = Path(__file__).resolve().parent
    print(f"[git-push] 工作目录: {work_dir}", flush=True)

    # 步骤 1：初始化 git 仓库（使用 main 作为默认分支）
    code, _, _ = run_git(["init", "-b", "main"], work_dir)
    if code != 0:
        print("[git-push] git init 失败", file=sys.stderr, flush=True)
        return 1

    # 步骤 2：添加所有文件（受 .gitignore 控制）
    code, _, _ = run_git(["add", "."], work_dir)
    if code != 0:
        print("[git-push] git add 失败", file=sys.stderr, flush=True)
        return 1

    # 检查暂存区是否有文件
    code, out, _ = run_git(["diff", "--cached", "--name-only"], work_dir)
    if code != 0:
        print("[git-push] 检查暂存区失败", file=sys.stderr, flush=True)
        return 1

    staged_files = [f for f in out.strip().split("\n") if f]
    print(f"[git-push] 暂存文件数: {len(staged_files)}", flush=True)
    if not staged_files:
        print("[git-push] 警告：暂存区为空，请检查 .gitignore", file=sys.stderr, flush=True)
        return 1

    # 打印暂存文件列表
    print("[git-push] 暂存文件:", flush=True)
    for f in staged_files:
        print(f"  - {f}", flush=True)

    # 步骤 3：创建首次提交
    code, _, _ = run_git(["commit", "-m", COMMIT_MESSAGE], work_dir)
    if code != 0:
        print("[git-push] git commit 失败", file=sys.stderr, flush=True)
        return 1

    # 步骤 4：关联远程仓库
    code, _, _ = run_git(["remote", "add", "origin", REMOTE_URL], work_dir)
    if code != 0:
        # 远程可能已存在，尝试更新
        code, _, _ = run_git(["remote", "set-url", "origin", REMOTE_URL], work_dir)
        if code != 0:
            print("[git-push] 配置远程仓库失败", file=sys.stderr, flush=True)
            return 1

    # 步骤 5：推送到 GitHub
    code, _, _ = run_git(["push", "-u", "origin", "main"], work_dir)
    if code != 0:
        print("[git-push] git push 失败", file=sys.stderr, flush=True)
        return 1

    print("[git-push] 推送成功！", flush=True)
    print(f"[git-push] 仓库地址: https://github.com/JACKWang19559/trae-funasr-watch", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
