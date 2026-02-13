<p align="center">
  <h1 align="center">🎨 DanbooruDownload</h1>
  <p align="center">
    快速、强大、易用的 Danbooru 图片批量下载工具<br>
    <em>A fast, powerful, and user-friendly batch image downloader for Danbooru</em>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/platform-Windows-0078d4?logo=windows" alt="Windows">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
    <img src="https://img.shields.io/badge/GUI-CustomTkinter-purple" alt="CustomTkinter">
  </p>
  <p align="center">
    <a href="#-中文文档">中文</a> · <a href="#-english-documentation">English</a>
  </p>
</p>

---

# � 中文文档

## 简介

**DanbooruDownload** 是一款专为 [Danbooru](https://danbooru.donmai.us) 及其兼容镜像站（如 Safebooru）设计的图片批量下载工具。无论你是需要收集特定画师的作品、某个角色的同人图，还是批量下载高质量壁纸素材，DanbooruDownload 都可以帮你高效完成。

本工具提供 **精美的 GUI 图形界面** 和 **强大的命令行 CLI** 两种使用方式，适合不同习惯的用户。GUI 基于 CustomTkinter 构建，拥有现代化暗色主题界面，告别传统爬虫工具的命令行恐惧。

## 为什么选择 DanbooruDownload？

| 🏆 优势 | 说明 |
|---------|------|
| **零门槛上手** | 双击 `start.bat` 即可运行，自动配置环境、安装依赖，无需手动折腾 |
| **精美 GUI** | 基于 CustomTkinter 的现代深色界面，中英双语切换，操作直观 |
| **极速下载** | 异步并发引擎，支持自定义并发数（默认 8 路），充分利用带宽 |
| **智能续传** | MD5 校验已下载文件，避免重复下载，断点继续不浪费流量 |
| **灵活命名** | 12 种文件名占位符自由组合（画师、角色、ID、评分、日期…） |
| **高级筛选** | 支持评级过滤、最低评分、屏蔽标签，精准获取目标内容 |
| **多站兼容** | 支持 Danbooru 及所有兼容 API 的镜像站 |
| **视频控制** | 可选择下载或跳过视频/动图文件（mp4, webm, zip） |
| **配置管理** | YAML 配置文件导入/导出，方便复用和分享下载参数 |
| **完全开源** | MIT 许可证，自由使用和修改 |

## 📦 安装

### 环境要求

- **Python 3.10 或更高版本** — [点击下载](https://www.python.org/downloads/)
  > ⚠️ 安装 Python 时请务必勾选 **"Add Python to PATH"**
- **Windows** 操作系统

### 下载项目

```bash
git clone https://github.com/storyAura/DanbooruDownload.git
cd DanbooruDownload
```

或者直接在 GitHub 页面点击 **Code → Download ZIP**，解压后进入文件夹。

### 安装依赖

**方式一（推荐）**：直接双击 `start.bat`，脚本会自动完成以下步骤：
1. 创建 Python 虚拟环境
2. 安装全部依赖
3. 启动 GUI 界面

**方式二（手动安装）**：

```bash
pip install -r requirements.txt
```

## 🚀 使用方法

### GUI 图形界面（推荐）

双击 `start.bat` 即可启动 GUI 界面。在界面中可以：

- 配置站点地址和 API 认证信息
- 输入搜索标签，设置评级和评分筛选
- 自定义保存路径和文件命名格式
- 控制并发数、超时时间等下载参数
- 实时查看下载进度和日志
- 随时停止下载任务

### 命令行 CLI

```bash
# 基本用法 — 下载风景图
python main.py -t "landscape rating:g" -l 20

# 指定画师 + 高评分筛选
python main.py -t "1girl solo" --rating s --min-score 100

# 使用镜像站下载
python main.py -u "https://safebooru.donmai.us" -t "scenery" -l 50

# 自定义保存格式和路径
python main.py -t "touhou" -o ./touhou -f "{artist}_{id}.{ext}" -c 12

# 使用 YAML 配置文件
python main.py --config my_config.yaml

# 保存当前参数为配置文件
python main.py -t "landscape" -l 50 --save-config my_config.yaml
```

### CLI 完整参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-t`, `--tags` | 搜索标签（支持 metatag） | — |
| `--rating` | 评级筛选：`g` / `s` / `q` / `e` | 不限 |
| `--min-score` | 最低评分 | 不限 |
| `-o`, `--output` | 保存目录 | `./downloads` |
| `-f`, `--format` | 文件名格式模板 | `{id}_{artist}_{md5}.{ext}` |
| `-l`, `--limit` | 最大下载数量 | `100` |
| `-c`, `--concurrent` | 并发下载数 | `8` |
| `-u`, `--url` | Danbooru 站点地址 | `https://danbooru.donmai.us` |
| `--username` | API 用户名 | — |
| `--api-key` | API 密钥 | — |
| `--config` | 读取 YAML 配置文件 | — |
| `--save-config` | 保存配置到文件 | — |
| `--no-skip` | 不跳过已存在文件 | 关闭 |
| `--timeout` | 请求超时（秒） | `30` |

## 📝 文件名格式占位符

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `{id}` | 帖子 ID | `12345` |
| `{md5}` | 文件 MD5 哈希 | `a1b2c3d4...` |
| `{artist}` | 画师名 | `artist_name` |
| `{character}` | 角色名 | `hatsune_miku` |
| `{copyright}` | 作品/系列 | `vocaloid` |
| `{rating}` | 评级 | `g` / `s` / `q` / `e` |
| `{score}` | 评分 | `150` |
| `{date}` | 上传日期 | `2025-01-15` |
| `{width}` / `{height}` | 图片尺寸 | `1920` / `1080` |
| `{ext}` | 文件扩展名 | `png` |
| `{tags}` | 所有标签（前 10 个） | `tag1+tag2+...` |

**默认格式：** `{artist}_{id}.{ext}`

## 📂 项目结构

```
DanbooruDownload/
├── gui.py              # GUI 图形界面（CustomTkinter）
├── main.py             # CLI 命令行入口
├── config.py           # 配置管理（YAML 导入/导出）
├── danbooru_client.py  # Danbooru API 客户端
├── downloader.py       # 异步批量下载引擎
├── formatter.py        # 文件名格式化引擎
├── locales/            # 国际化语言包
│   ├── zh_cn.py        #   中文
│   └── en.py           #   English
├── start.bat           # Windows 一键启动脚本
└── requirements.txt    # Python 依赖列表
```

---

# � English Documentation

## Introduction

**DanbooruDownload** is a powerful batch image downloader built specifically for [Danbooru](https://danbooru.donmai.us) and compatible mirror sites (e.g., Safebooru). Whether you need to collect works from a specific artist, fan art of a character, or batch download high-quality wallpapers, DanbooruDownload can handle it efficiently.

The tool offers both a **beautiful GUI** and a **powerful CLI**, catering to different user preferences. The GUI is built with CustomTkinter, featuring a modern dark-themed interface — no more intimidating terminal windows.

## Why DanbooruDownload?

| 🏆 Advantage | Description |
|--------------|-------------|
| **Zero Setup** | Double-click `start.bat` to run — auto-configures environment and installs dependencies |
| **Beautiful GUI** | Modern dark-themed interface with Chinese/English toggle, intuitive and clean |
| **Blazing Fast** | Async concurrent download engine with adjustable concurrency (default: 8) |
| **Smart Resume** | MD5 checksum verification skips already-downloaded files, saving bandwidth |
| **Flexible Naming** | 12 filename placeholders for complete customization (artist, character, ID, score, date…) |
| **Advanced Filtering** | Rating filter, minimum score, blocked tags — precisely target the content you want |
| **Multi-Site** | Works with Danbooru and all API-compatible mirror sites |
| **Video Control** | Optionally download or skip video/animation files (mp4, webm, zip) |
| **Config Management** | Import/export YAML configs for easy reuse and sharing |
| **Fully Open Source** | MIT License — free to use and modify |

## 📦 Installation

### Requirements

- **Python 3.10+** — [Download here](https://www.python.org/downloads/)
  > ⚠️ Make sure to check **"Add Python to PATH"** during installation
- **Windows** OS

### Download

```bash
git clone https://github.com/storyAura/DanbooruDownload.git
cd DanbooruDownload
```

Or click **Code → Download ZIP** on the GitHub page and extract.

### Install Dependencies

**Option A (Recommended)**: Double-click `start.bat`. It will automatically:
1. Create a Python virtual environment
2. Install all dependencies
3. Launch the GUI

**Option B (Manual)**:

```bash
pip install -r requirements.txt
```

## 🚀 Usage

### GUI (Recommended)

Double-click `start.bat` to launch the GUI. From the interface you can:

- Configure site URL and API authentication
- Enter search tags with rating and score filters
- Customize save path and filename format
- Adjust concurrency, timeout, and other download settings
- Monitor real-time download progress and logs
- Stop downloads at any time

### CLI

```bash
# Basic usage — download landscape images
python main.py -t "landscape rating:g" -l 20

# Filter by rating and score
python main.py -t "1girl solo" --rating s --min-score 100

# Use a mirror site
python main.py -u "https://safebooru.donmai.us" -t "scenery" -l 50

# Custom save format and path
python main.py -t "touhou" -o ./touhou -f "{artist}_{id}.{ext}" -c 12

# Use a YAML config file
python main.py --config my_config.yaml

# Save current settings to config
python main.py -t "landscape" -l 50 --save-config my_config.yaml
```

### CLI Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-t`, `--tags` | Search tags (supports metatags) | — |
| `--rating` | Rating filter: `g` / `s` / `q` / `e` | Any |
| `--min-score` | Minimum post score | Any |
| `-o`, `--output` | Save directory | `./downloads` |
| `-f`, `--format` | Filename format template | `{id}_{artist}_{md5}.{ext}` |
| `-l`, `--limit` | Maximum number of downloads | `100` |
| `-c`, `--concurrent` | Concurrent downloads | `8` |
| `-u`, `--url` | Danbooru site URL | `https://danbooru.donmai.us` |
| `--username` | API username | — |
| `--api-key` | API key | — |
| `--config` | Load YAML config file | — |
| `--save-config` | Save settings to file | — |
| `--no-skip` | Re-download existing files | Off |
| `--timeout` | Request timeout (seconds) | `30` |

## 📝 Filename Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{id}` | Post ID | `12345` |
| `{md5}` | File MD5 hash | `a1b2c3d4...` |
| `{artist}` | Artist name(s) | `artist_name` |
| `{character}` | Character name(s) | `hatsune_miku` |
| `{copyright}` | Copyright/series | `vocaloid` |
| `{rating}` | Rating | `g` / `s` / `q` / `e` |
| `{score}` | Post score | `150` |
| `{date}` | Upload date | `2025-01-15` |
| `{width}` / `{height}` | Image dimensions | `1920` / `1080` |
| `{ext}` | File extension | `png` |
| `{tags}` | All tags (first 10) | `tag1+tag2+...` |

**Default format:** `{artist}_{id}.{ext}`

---

## ⚙️ Dependencies

| Package | Purpose |
|---------|---------|
| [httpx](https://www.python-httpx.org/) | HTTP client (sync + async) |
| [tqdm](https://github.com/tqdm/tqdm) | CLI progress bar |
| [pyyaml](https://pyyaml.org/) | YAML config file I/O |
| [customtkinter](https://github.com/TomSchimansky/CustomTkinter) | Modern GUI framework |

## 📄 License

[MIT License](LICENSE) — Free to use, modify, and distribute.
