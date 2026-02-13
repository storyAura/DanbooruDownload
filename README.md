<p align="center">
  <h1 align="center">🎨 DanbooruDownload</h1>
  <p align="center">
    快速、易用的 Danbooru 图片批量下载工具<br>
    <em>Fast and easy batch image downloader for Danbooru</em>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/platform-Windows-0078d4?logo=windows" alt="Windows">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  </p>
</p>

---

## ✨ 功能特性

- 🖥️ **双模式** — 精美的 GUI 界面 + 强大的命令行工具
- 🌐 **多站点** — 支持 Danbooru 及兼容镜像站（Safebooru 等）
- 🔍 **高级搜索** — 标签搜索、评级筛选、评分过滤、屏蔽标签
- 📝 **自定义命名** — 灵活的文件名格式模板（画师、角色、ID、MD5…）
- ⚡ **高速下载** — 异步并发下载，可调节并发数
- 🔄 **断点续传** — MD5 校验跳过已有文件，支持重试机制
- 🎬 **视频筛选** — 可选择是否下载视频/动图文件
- 🌏 **中英双语** — GUI 支持中文/English 切换
- 🎨 **暗色主题** — 基于 CustomTkinter 的现代 UI

## 🚀 快速开始

### 方式一：GUI 图形界面（推荐）

**双击 `start.bat` 即可运行**，脚本会自动创建虚拟环境并安装依赖。

> 前提条件：已安装 [Python 3.10+](https://www.python.org/downloads/)

### 方式二：命令行 CLI

```bash
# 安装依赖
pip install -r requirements.txt

# 基本用法
python main.py -t "landscape rating:g" -l 20

# 指定画师 + 高评分
python main.py -t "1girl solo" --rating s --min-score 100

# 使用镜像站
python main.py -u "https://safebooru.donmai.us" -t "scenery" -l 50

# 自定义保存格式和路径
python main.py -t "touhou" -o ./touhou -f "{artist}_{id}.{ext}" -c 12

# 使用配置文件
python main.py --config config.yaml
```

## 📝 文件名格式

通过 `-f` 参数或 GUI 中的自定义文件名功能，可使用以下占位符：

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `{id}` | 帖子 ID | `12345` |
| `{md5}` | 文件 MD5 | `a1b2c3d4...` |
| `{artist}` | 画师名 | `artist_name` |
| `{character}` | 角色名 | `hatsune_miku` |
| `{copyright}` | 作品/系列 | `vocaloid` |
| `{rating}` | 评级 | `g` / `s` / `q` / `e` |
| `{score}` | 评分 | `150` |
| `{date}` | 上传日期 | `2025-01-15` |
| `{width}` / `{height}` | 图片尺寸 | `1920` / `1080` |
| `{ext}` | 扩展名 | `png` |
| `{tags}` | 所有标签（前 10） | `tag1+tag2+...` |

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
└── requirements.txt    # Python 依赖
```

## 📋 CLI 完整参数

```
用法: main.py [选项]

搜索:
  -t, --tags TEXT         搜索标签（支持 metatag，如 score:>100）
  --rating {g,s,q,e}     评级筛选
  --min-score N           最低评分

输出:
  -o, --output PATH       保存目录（默认: ./downloads）
  -f, --format TEXT       文件名格式模板

限制:
  -l, --limit N           最大下载数量（默认: 100）
  -c, --concurrent N      并发下载数（默认: 8）

站点:
  -u, --url URL           Danbooru 站点地址
  --username TEXT         用户名（API 认证）
  --api-key TEXT          API 密钥

其他:
  --config FILE           YAML 配置文件
  --save-config FILE      保存当前配置到文件
  --no-skip               不跳过已存在文件
  --timeout SECONDS       请求超时（默认: 30）
```

## ⚙️ 依赖

| 包 | 用途 |
|---|---|
| [httpx](https://www.python-httpx.org/) | HTTP 客户端（同步 + 异步） |
| [tqdm](https://github.com/tqdm/tqdm) | CLI 进度条 |
| [pyyaml](https://pyyaml.org/) | 配置文件读写 |
| [customtkinter](https://github.com/TomSchimansky/CustomTkinter) | 现代 GUI 框架 |

## 📄 License

[MIT License](LICENSE) — 自由使用、修改和分发。
