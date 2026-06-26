# 版本更新说明

本文记录 DanbooruDownload 当前版本相对上一版的主要变化。

## v1.2

### 自动图片转换

- WebP 转换现在支持透明 PNG 背景合成，可选择白色、固定彩色或随机鲜艳色背景。
- 固定彩色背景默认使用 `#ff4fd8`，并支持在设置页通过颜色选择器调整。
- 转换输出目录不再固定为 `jpg_webp`，现在会保存到原下载文件夹同级目录：
  - WebP：`原文件夹名_webp`
  - JPG：`原文件夹名_jpg`
- TXT 标签文件会跟随转换后的图片保存到对应转换目录。

### 设置界面

- 设置页新增 WebP 背景模式选择：白色、彩色、随机。
- 彩色背景旁新增颜色选择按钮，可直接打开系统颜色选择器。
- 优化切换背景模式时的控件刷新，减少闪烁和布局跳动。
- 更新转换格式设置截图，展示新的背景和颜色控件。

### Logo 与窗口图标

- 重新设计应用 Logo：圆角 `D` 加下载箭头，表达 DanbooruDownload 和下载含义。
- 替换窗口标题栏、任务栏、EXE 图标和资源文件中的图标。
- 优化 16/24/32 小尺寸图标，让标题栏显示更清晰。

### Windows EXE 打包

- 新增 PyInstaller onedir 打包流程，输出：
  - `dist\DanbooruDownload\DanbooruDownload.exe`
  - `dist\DanbooruDownload\win-x64`
  - `dist\DanbooruDownload\Download`
- 打包根目录只保留必要的 `Download` 文件夹，运行依赖集中在 `win-x64`。
- `start.bat` 保持快速开发/测试启动方式，`build_exe.bat` 用于正式打包。

### 配置和文档

- YAML 配置新增：
  - `auto_convert_background_mode`
  - `auto_convert_background_color`
- README 更新 v1.2 简要说明、转换路径示例和打包说明。
- `UPDATE.md` 用于记录完整版本变化。

### 验证

本版本已通过以下检查：

```bash
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m compileall danbooru_download config.py danbooru_client.py downloader.py formatter.py gui.py main.py
```

并完成 Windows EXE 打包与启动烟测。
