# DanbooruDownload

快速、易用的 Danbooru 及兼容站点批量下载工具，提供图形界面和命令行两种使用方式。

A fast Windows-friendly batch downloader for [Danbooru](https://danbooru.donmai.us) and compatible booru sites, with both a CustomTkinter GUI and a CLI.

## 中文说明

### 主要功能

| 功能 | 说明 |
| --- | --- |
| GUI 和 CLI | 双击 `start.bat` 使用图形界面，也可以用 `python main.py` 批量下载。 |
| 站点预设 | GUI 内置 Danbooru、AIBooru、Gelbooru、Safebooru，也支持自定义站点地址。 |
| 下载队列 | 可以把多个标签搜索加入队列，按顺序下载、查看单项进度，并对失败任务重爬。 |
| 并发下载 | 异步下载引擎，支持自定义并发数和请求超时。 |
| 智能跳过 | 已存在文件会进行 MD5 校验，避免重复下载。 |
| 流式写入 | 大文件分块写入磁盘，降低内存占用。 |
| 速度显示 | GUI 下载时显示实时速度。 |
| 同名 TXT 标签 | 可为每张图片生成同名 `.txt` 标签文件，适合数据集和 LoRA 工作流。 |
| YAML 配置 | 支持导入、导出下载设置、队列任务和 TXT 标签选项。 |
| 视频控制 | 可选择下载或跳过 `mp4`、`webm`、`zip` 动图/视频文件。 |

### 环境要求

- Windows
- Python 3.10 或更高版本
- 能访问目标 booru 站点

手动安装依赖：

```bash
pip install -r requirements.txt
```

依赖包括 `httpx`、`httpcore[asyncio]`、`typing_extensions`、`tqdm`、`pyyaml`、`customtkinter`。

### 快速开始

```bash
git clone https://github.com/storyAura/DanbooruDownload.git
cd DanbooruDownload
```

启动 GUI：

```bat
start.bat
```

`start.bat` 会创建或修复 `.venv`，安装缺失依赖，然后用 `pythonw` 启动 `gui.py`。

GUI 默认保存到项目内的 `Download` 文件夹。该目录只用于存放下载内容，已被 `.gitignore` 忽略，不会提交到仓库。

### GUI 使用

1. 选择站点预设，或输入自定义站点地址。
2. 输入搜索标签、评级、最低评分和屏蔽标签。
3. 设置保存目录和文件名格式。
4. 设置并发数、超时、跳过已存在文件、视频下载等选项。
5. 可选开启同名 TXT 标签导出。
6. 点击 `开始下载` 执行单次任务，或把多个任务加入队列后点击 `全部开始`。

### 下载队列

GUI 队列任务会保存：

- 搜索标签
- 文件夹名
- 最大下载数量

队列开始前可以移除任务。失败或取消的任务可以点击 `重爬` 重新加入下载流程。导出 YAML 配置时，队列任务也会一起保存。

### 同名 TXT 标签

开启 `保存同名 TXT 标签` 后，每张图片旁边会生成同名 `.txt` 文件：

```text
image_name.png
image_name.txt
```

标签按 Danbooru 侧栏顺序写入：

```text
artist, copyright, character, general, meta
```

GUI 默认选择 `character` 和 `general`。可选将下划线转为空格，并转义括号等特殊字符。

CLI 如需生成 TXT，可通过 YAML 配置开启：

```yaml
save_tag_txt: true
tag_txt_categories:
  - character
  - general
tag_txt_underscore_to_space: true
tag_txt_escape_special_chars: true
```

然后运行：

```bash
python main.py --config my_config.yaml
```

### CLI 用法

```bash
# 基础搜索
python main.py -t "landscape rating:g" -l 20

# 评级和评分过滤
python main.py -t "1girl solo" --rating s --min-score 100

# 使用兼容镜像站
python main.py -u "https://safebooru.donmai.us" -t "scenery" -l 50

# 自定义保存目录和文件名
python main.py -t "touhou" -o ./touhou -f "{artist}_{id}.{ext}" -c 12

# 从 YAML 读取配置
python main.py --config my_config.yaml

# 保存当前 CLI 参数到 YAML
python main.py -t "landscape" -l 50 --save-config my_config.yaml
```

### CLI 参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `-t`, `--tags` | 搜索标签，支持 Danbooru metatag | 空 |
| `--rating` | 评级过滤：`g`、`s`、`q`、`e` | 不限 |
| `--min-score` | 最低评分 | 不限 |
| `-o`, `--output` | 保存目录 | `./downloads` |
| `-f`, `--format` | 文件名模板 | `{id}_{artist}_{md5}.{ext}` |
| `-l`, `--limit` | 最大下载数量 | `100` |
| `-c`, `--concurrent` | 并发下载数 | `8` |
| `-u`, `--url` | Danbooru 兼容站点地址 | `https://danbooru.donmai.us` |
| `--username` | API 用户名 | 空 |
| `--api-key` | API 密钥 | 空 |
| `--config` | 读取 YAML 配置 | 空 |
| `--save-config` | 保存配置到 YAML 后退出 | 空 |
| `--no-skip` | 重新下载已存在文件 | 关闭 |
| `--timeout` | HTTP 超时秒数 | `30` |

### 文件名占位符

| 占位符 | 说明 | 示例 |
| --- | --- | --- |
| `{id}` | 帖子 ID | `12345` |
| `{md5}` | 文件 MD5 | `a1b2c3d4...` |
| `{artist}` | 画师标签 | `artist_name` |
| `{character}` | 角色标签 | `hatsune_miku` |
| `{copyright}` | 版权/作品标签 | `vocaloid` |
| `{rating}` | 评级 | `g` |
| `{score}` | 评分 | `150` |
| `{date}` | 上传日期 | `2025-01-15` |
| `{width}` | 图片宽度 | `1920` |
| `{height}` | 图片高度 | `1080` |
| `{ext}` | 文件扩展名 | `png` |
| `{tags}` | 前 10 个通用标签 | `tag1+tag2+...` |

GUI 默认文件名格式：

```text
{artist}_{id}.{ext}
```

CLI 默认文件名格式：

```text
{id}_{artist}_{md5}.{ext}
```

## English

### Highlights

| Feature | Description |
| --- | --- |
| GUI and CLI | Use the graphical app from `start.bat`, or automate downloads with `python main.py`. |
| Site presets | GUI presets for Danbooru, AIBooru, Gelbooru, and Safebooru, plus custom URLs. |
| Download queue | Add multiple tag searches to the GUI queue, run them in order, retry tasks, and track per-task progress. |
| Concurrent downloads | Async downloader with configurable concurrency and request timeouts. |
| Smart skipping | Existing files are checked by MD5 so repeated runs do not waste bandwidth. |
| Streaming downloads | Large files are written in chunks instead of being loaded fully into memory. |
| Speed display | GUI downloads report live transfer speed. |
| TXT tag export | Optionally save a same-name `.txt` file for each image, useful for dataset and LoRA workflows. |
| YAML configs | Import/export settings, including queued tasks and TXT tag options. |
| Video control | Choose whether to download or skip `mp4`, `webm`, and `zip` animation files. |

### Quick Start

```bash
git clone https://github.com/storyAura/DanbooruDownload.git
cd DanbooruDownload
```

```bat
start.bat
```

`start.bat` creates or repairs `.venv`, installs missing dependencies, and launches `gui.py` with `pythonw`.

The GUI saves downloads to the local `Download` folder by default. This folder is ignored by Git and is only for downloaded files.

### CLI Usage

```bash
python main.py -t "landscape rating:g" -l 20
python main.py -t "1girl solo" --rating s --min-score 100
python main.py -u "https://safebooru.donmai.us" -t "scenery" -l 50
python main.py -t "touhou" -o ./touhou -f "{artist}_{id}.{ext}" -c 12
python main.py --config my_config.yaml
python main.py -t "landscape" -l 50 --save-config my_config.yaml
```

### YAML Queue Example

```yaml
queue_tasks:
  - tags: "1girl solo"
    folder_name: "solo"
    max_posts: 100
```

Queue tasks are currently used by the GUI. The CLI loads common download settings and TXT tag settings.

## Project Structure

```text
DanbooruDownload/
|-- gui.py              # CustomTkinter GUI
|-- main.py             # CLI entry point
|-- config.py           # YAML config model and loader
|-- danbooru_client.py  # Danbooru API client
|-- downloader.py       # Async streaming downloader
|-- formatter.py        # Filename and TXT tag formatters
|-- locales/            # Chinese and English UI text
|-- start.bat           # Windows launcher
|-- requirements.txt    # Python dependencies
`-- Download/           # Local download storage, ignored by Git
```

## License

Released under the [MIT License](LICENSE).
