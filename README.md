# Trae FunASR Watch — 视频理解插件

> 基于 [bradautomates/claude-video](https://github.com/bradautomates/claude-video) 改造的 Trae 视频理解插件，使用阿里达摩院 **FunASR + SenseVoiceSmall** 替代 Whisper API，实现完全本地化的视频转写与内容理解。

## 简介

为 AI Agent 提供原生的视频输入能力。当用户粘贴视频 URL（YouTube、Bilibili、抖音、TikTok、Twitch 等 yt-dlp 支持的平台）或指向本地视频文件时，插件会自动：

1. **下载视频** — 使用 `yt-dlp` 拉取视频流（仅有字幕时优先拉字幕）
2. **抽取帧** — 使用 `ffmpeg` 按场景感知/关键帧/均匀采样策略生成 JPEG 帧
3. **获取字幕** — 优先拉取原生字幕；缺失时回退到 **FunASR 本地转写**（SenseVoiceSmall 模型），无需 API Key，完全离线
4. **输出报告** — 打印帧路径 + 带时间戳的字幕，并保存 `transcript.txt` 到工作目录，方便后续查看和复用

## 核心特性

### 🎯 FunASR 本地转写（替代 Whisper API）

- **零 API Key** — 模型首次下载后完全离线（约 234MB）
- **中文识别最佳** — SenseVoiceSmall CER 7.81%，针对中文优化
- **本地执行** — 音频数据不离开本机，隐私安全
- **GPU 加速** — 自动检测 CUDA，无 GPU 时回退 CPU
- **标签自动过滤** — 自动清理 SenseVoiceSmall 输出中的语言/情绪/事件标签（`<|zh|>`, `<|HAPPY|>`, `<|BGM|>`, `<|woitn|>` 等）

### 🍪 多平台 Cookie 支持

- 动态识别 URL 域名（Bilibili / 抖音 / YouTube）
- 支持 Netscape 格式 `cookies.txt` 和 JSON 格式 `cookies.json`
- 自动选择对应平台的 Cookie 源，解决登录/会员视频下载问题

### 🖼️ 智能帧抽取

- 场景感知（scene-aware）抽帧，捕捉画面变化
- 关键帧快速通道（keyframe-fast），适合长视频
- 帧去重（frame-delta），自动丢弃近似重复帧
- 自适应帧率（最高 2 fps），根据视频时长动态调整

### 💾 字幕持久化

- 转写完成后，字幕同时打印到 stdout 并保存到工作目录的 `transcript.txt`
- 格式：`[MM:SS] 文本内容`，便于检索和复用

## 环境要求

- **Python 3.10+**（Windows 用 `py` 启动器，macOS/Linux 用 `python3`）
- **ffmpeg / ffprobe**（Windows 推荐：`winget install Gyan.FFmpeg`）
- **yt-dlp**（`pip install yt-dlp`）
- **FunASR**（`pip install funasr torch`）
  - GPU 加速（可选）：`pip install torch --index-url https://download.pytorch.org/whl/cu121`

## 安装

### 方式一：Trae 插件市场（推荐）

在 Trae IDE 的插件市场搜索 "Watch Video" 并安装。

### 方式二：手动安装

```bash
git clone https://github.com/JACKWang19559/trae-funasr-watch.git
# 将 watch/0.2.0 目录复制到 Trae 的插件目录
```

### 初始化

首次使用时，插件会自动运行 `setup.py` 检测依赖、创建 `~/.config/watch/.env` 配置文件，并在 Windows 上自动检测含 FunASR 的系统 Python 路径。

## Windows + Trae 环境说明

Trae IDE 自带的 Python 3.10 缺少 FunASR。本插件通过以下机制解决：

1. `setup.py --json` 自动检测系统中含 FunASR 的 Python 路径（如 Python 3.11）
2. 路径写入 `~/.config/watch/.env` 的 `WATCH_PYTHON` 变量
3. AI 从 `setup.py` 返回的 `watch_python` 字段读取路径，后续脚本调用使用该路径代替 `py`

**全程自动，无需手动配置。**

## 使用方法

### 基本用法

```
watch <视频URL或本地路径> [问题]
```

### 示例

```
# 分析 YouTube 视频
watch https://youtu.be/abc 这视频讲的是什么语言？

# 分析 Bilibili 视频
watch https://www.bilibili.com/video/BV1xxxxx 总结视频内容

# 分析抖音视频
watch https://v.douyin.com/xxxxx/

# 分析本地视频，聚焦特定时间段
watch video.mp4 --start 0:45 --end 1:00

# 仅获取字幕，不抽取帧
watch $URL --detail transcript
```

### 抽帧模式

通过 `--detail` 参数控制帧抽取策略：

| 模式 | 帧数上限 | 行为 |
|------|----------|------|
| `transcript` | 0 | 仅字幕，不抽帧（有字幕时跳过视频下载） |
| `efficient` | ≤50 | 快速关键帧通道 |
| `balanced` *(默认)* | ≤100 | 场景感知抽帧 |
| `token-burner` | 无上限 | 场景感知，最高保真度（Token 消耗大） |

也可在 `~/.config/watch/.env` 中设置 `WATCH_DETAIL=balanced`。

### 常用参数

| 参数 | 说明 |
|------|------|
| `--detail <mode>` | 抽帧模式 |
| `--start T` / `--end T` | 聚焦时间段（格式：`SS` / `MM:SS` / `HH:MM:SS`） |
| `--timestamps T1,T2,…` | 在指定时间点强制抽帧（用于捕捉"看这里"等指示性时刻） |
| `--max-frames N` | 覆盖模式默认的帧数上限 |
| `--resolution W` | 帧宽度（默认 512px，需读取屏幕文字时可调到 1024） |
| `--fps F` | 覆盖自动帧率（上限 2 fps） |
| `--out-dir DIR` | 指定工作目录（默认：系统临时目录） |
| `--no-whisper` | 禁用 FunASR 转写回退（无字幕时仅返回帧） |
| `--no-dedup` | 保留近似重复帧 |

## 配置

配置文件位于 `~/.config/watch/.env`（权限 0600）：

```ini
# 抽帧模式
WATCH_DETAIL=balanced

# FunASR 转写设备（auto/cuda/cpu）
WATCH_TRANSCRIBE_DEVICE=auto

# 含 FunASR 的系统 Python 路径（Windows 自动检测）
WATCH_PYTHON=C:\Users\<user>\AppData\Local\Programs\Python\Python311\python.exe

# Cookie 文件路径（用于下载登录/会员视频）
WATCH_COOKIE_FILE=C:\Users\<user>\.config\watch\cookies.txt

# 安装完成标记
SETUP_COMPLETE=true
```

### Cookie 配置（可选）

如需下载 Bilibili 会员视频或抖音私密视频，可导出 Cookie：

1. 安装浏览器插件 [J2Team Cookies](https://junookyo.gitbook.io/j2team-cookies)
2. 导出 Netscape 格式的 `cookies.txt` 到 `~/.config/watch/cookies.txt`
3. 插件会根据 URL 域名自动选择对应的 Cookie 源

## 项目结构

```
watch/0.2.0/
├── .trae-plugin/
│   └── plugin.json              # Trae 插件清单
├── assets/
│   └── watch-small.svg          # 插件图标
├── skills/
│   └── watch/
│       ├── SKILL.md             # 技能契约文档
│       └── scripts/
│           ├── watch.py         # 主入口
│           ├── setup.py         # 环境检测与初始化
│           ├── download.py      # yt-dlp 下载封装
│           ├── frames.py        # ffmpeg 抽帧
│           ├── transcribe.py    # 字幕解析（VTT/SRT）
│           ├── funasr_transcribe.py  # FunASR 本地转写
│           ├── whisper.py       # FunASR 薄封装（向后兼容）
│           ├── ffmpeg_utils.py  # ffmpeg 路径解析
│           ├── config.py        # .env 读取
│           └── build-skill.sh   # 构建脚本
└── README.md                    # 本文档
```

## 与上游的主要差异

本插件基于 [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.2.0 改造，主要变更：

### Whisper API → FunASR 本地转写

| 维度 | 原版（Whisper API） | 本插件（FunASR） |
|------|---------------------|------------------|
| API Key | 需要（Groq/OpenAI） | 不需要 |
| 网络依赖 | 必须联网 | 首次下载模型后离线 |
| 隐私 | 音频上传到云端 | 完全本地 |
| 中文识别 | 一般 | 优秀（CER 7.81%） |
| 成本 | 按 API 调用计费 | 免费 |

### 其他增强

- **`plugin.json`** — Trae 清单格式，包含 `interface`（displayName、capabilities、brandColor `#E11D48`、icon）
- **`SKILL.md`** — 适配 Trae 的 `RunCommand` 工具，Windows 用 `py` 启动器，添加 `WATCH_PYTHON` 环境检测说明
- **`setup.py`** — 新增 `_find_python_with_funasr()` 等函数，自动检测含 FunASR 的系统 Python（绕过 Trae 自带的 Python 3.10），使用 `importlib.util.find_spec` 快速检测
- **`funasr_transcribe.py`** — 新模块，实现 FunASR + SenseVoiceSmall 本地转写，支持 GPU/CPU 自动切换、VAD 分段、时间戳输出、标签过滤
- **`whisper.py`** — 简化为薄封装，委托给 `funasr_transcribe.transcribe_video()`
- **`watch.py`** — 新增 `transcript.txt` 保存功能
- **`ffmpeg_utils.py`** — 新模块，解析 Windows 上完整版 ffmpeg 路径（绕过 Trae 自带的精简版）
- **`download.py`** — 支持 SRT 字幕，基于 URL 域名动态选择 Cookie 源
- **`transcribe.py`** — 支持 SRT 格式解析

## 故障排查

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| `ffmpeg not found` | 运行 `winget install Gyan.FFmpeg`（Windows）或 `brew install ffmpeg`（macOS） |
| `yt-dlp not found` | 运行 `pip install yt-dlp` |
| `No module named 'funasr'` | 在系统 Python 中运行 `pip install funasr torch` |
| 字幕为空 | 检查视频是否有音轨；会员视频需配置 Cookie |
| 下载失败 | yt-dlp 版本过旧，运行 `pip install -U yt-dlp` |
| GPU 未启用 | 安装 CUDA 版 PyTorch：`pip install torch --index-url https://download.pytorch.org/whl/cu121` |

### 日志位置

- 工作目录：`%TEMP%\watch-<random>\`（包含 video.mp4、frames/、audio.wav、transcript.txt）
- 配置文件：`~/.config/watch/.env`

## 技术栈

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — 视频下载
- **[ffmpeg](https://ffmpeg.org/)** — 音视频处理
- **[FunASR](https://github.com/modelscope/FunASR)** — 语音识别框架
- **[SenseVoiceSmall](https://www.modelscope.cn/models/iic/SenseVoiceSmall)** — 多语言语音识别模型
- **[PyTorch](https://pytorch.org/)** — 深度学习框架（GPU 加速）

## 许可证

MIT License — 详见 [上游 LICENSE](https://github.com/bradautomates/claude-video/blob/main/LICENSE)

## 致谢

- 原项目：[bradautomates/claude-video](https://github.com/bradautomates/claude-video)
- FunASR 团队：[modelscope/FunASR](https://github.com/modelscope/FunASR)
- SenseVoice 模型：阿里达摩院 DAMO Academy

## Star History

如果这个项目对你有帮助，欢迎 Star ⭐
