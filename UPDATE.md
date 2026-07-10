# 版本更新说明

本文记录 DanbooruDownload 当前版本相对上一版的主要变化。

## v1.3.1

### Nozomi.la 下载修复

- 修复 Nozomi.la 图片下载失败的问题：CDN 对静态图片只提供 `.webp` 格式，此前程序按帖子元数据里的 `type`（jpg/png）拼接地址会导致 404。
- 现在非视频、非 gif 的静态图统一使用 `.webp` 媒体地址。
- 新增对应回归单元测试。

### 移除 Konachan

- Konachan 已对 API 请求启用 Cloudflare 人机验证，任何纯 HTTP 客户端都无法匿名访问，因此从站点预设中移除。
- 仍保留 `konachan.com` 的 profile 识别，高级用户可在站点地址栏手动输入尝试。

### Gelbooru 凭据提示

- Gelbooru 已关闭匿名 API（返回 `401`）。在站点预设中选择 Gelbooru 时，界面会在站点下方显示提醒，引导前往 设置 → API 认证 填写数字 User ID 与 API Key。

## v1.3

### Nozomi.la 站点

- 新增 Nozomi.la 站点预设，使用独立的 `.nozomi` 标签索引 API。
- 支持普通标签搜索、多标签交集和屏蔽标签差集。
- 不支持 `rating:`、`score:` 等 metatag；若任务中包含这些条件，程序会在日志中提示已忽略。
- 无需 API 认证。

### 全局 API 认证

- 设置 → API 认证中按站点预设保存凭据到 `api_credentials.yaml`。
- Gelbooru 需填写账户 Options 页中的 **数字 User ID** 和 **API Key**，不是登录用户名。
- 支持快速粘贴 Gelbooru 凭据字符串（`&api_key=...&user_id=...`）并自动解析。

### 暗色主题

- 设置页新增浅色/深色主题切换。
- 主题偏好保存在 `default_config.yaml` 的 `ui_theme` 字段。

### 自动图片转换

- 新增 `auto_convert_keep_original` 配置项（默认 `true`）。
- 关闭「保留原始文件」后，转换成功时会删除原图，仅保留 `原文件夹名_webp` 或 `原文件夹名_jpg` 中的文件。

### 下载修复

- 修复 Gelbooru 等站点的协议相对 URL 和目录/image 字段拼接问题。
- 下载后校验文件大小和 magic bytes，避免 0 KB 损坏文件被误判为已存在。
- 下载媒体文件时发送站点 Referer 头。

### 测试

- 新增 Nozomi 客户端单元测试。
- 新增内置站点 smoke 测试（需 `RUN_SITE_SMOKE=1` 和网络）。

### 验证

本版本已通过以下检查：

```bash
python -m unittest discover -s tests -v
```

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
