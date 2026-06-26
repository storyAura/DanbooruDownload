# 版本更新说明

本文用于快速查看当前版本相对上一版的主要变化。

对比入口：

- 上一版基准：`main` 分支，提交 `7aad79a`
- 当前更新：`codex/booru-sites-ui-clarity` 分支，提交 `ef4ed7f`
- GitHub 对比：[main...codex/booru-sites-ui-clarity](https://github.com/storyAura/DanbooruDownload/compare/main...codex/booru-sites-ui-clarity)

## 主要变化

### 1. 项目结构重组

- 新增 `danbooru_download/` 包，将核心逻辑、GUI、语言文件分层放置。
- 根目录的 `gui.py`、`main.py`、`config.py`、`downloader.py` 等文件保留为兼容入口，避免影响旧的启动方式和已有导入。
- 核心代码现在集中在：
  - `danbooru_download/core/`
  - `danbooru_download/ui/`
  - `danbooru_download/locales/`

### 2. 图片格式自动转换

- 新增下载后自动转换静态图片功能。
- 支持输出 `JPG` 和 `WebP`。
- 支持质量、WebP 无损、压缩程度设置。
- 转换后的图片保存到 `jpg_webp` 文件夹。
- 如果开启 TXT 标签，TXT 会跟随转换后的图片保存。

### 3. 设置窗口调整

- 移除了顶部单独的软件详情按钮。
- 软件详情移动到设置窗口底部的独立区域。
- 设置窗口新增项目说明和 GitHub Star 提示。
- 杂项区域集中放置图片转换和默认配置相关设置。

### 4. 默认配置

- 设置窗口可保存当前配置为默认配置。
- 下次启动时会自动加载默认配置。
- 默认配置包含下载设置、TXT 标签设置、队列任务和图片转换设置。

### 5. 文档和截图

- README 已更新为当前功能和新项目结构。
- 更新了主界面截图和站点预设截图。
- 新增图片转换设置截图。
- README 顶部添加本更新说明入口。

### 6. 测试覆盖

- 新增配置读取和转换选项测试。
- 新增下载器转换行为测试。
- 新增图片转换参数测试。
- 新增包结构和兼容入口测试。

## 验证方式

```bash
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m compileall danbooru_download gui.py main.py locales tests
```

当前版本已通过以上验证。
