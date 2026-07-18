# 版本更新说明

本文记录 BooruDownload(原名 DanbooruDownload)当前版本相对上一版的主要变化。

## v1.4.0

### 项目更名为 BooruDownload

- 支持站点早已不限于 Danbooru（Gelbooru、Yande.re、Nozomi.la 等），项目正式更名为 **BooruDownload**。
- Python 包由 `danbooru_download` 更名为 `booru_download`；打包产物为 `dist\BooruDownload\BooruDownload.exe`。
- 窗口标题、CLI 横幅、User-Agent、打包配置与文档同步更新；GitHub 仓库地址更新为 `storyAura/BooruDownload`（旧地址自动跳转）。
- 站点相关标识（如 Danbooru 站点预设、`DanbooruClient`）保持原名，因为它们指的是站点本身。

### 下载与落盘可靠性

- 下载改为「唯一随机临时文件 → 流式 MD5 校验 → `os.replace` 原子替换」：帖子携带 MD5 时逐块校验，不匹配会重试并最终计为失败，不再只检查文件头魔数。
- 校验 `Content-Length`，截断的下载不再被计为成功。
- Windows 上损坏的旧文件可自动修复，`--no-skip` 重新下载可正常覆盖（原先 `rename` 遇到已存在目标必定失败）。
- 输出路径强制约束在保存根目录内：远端返回的扩展名走白名单净化，队列「文件夹名称」拒绝 `..`、盘符、保留设备名等路径逃逸写法。
- 同名目标并发下载按路径加锁，多个任务不再争抢同一个临时文件；TXT 与图片转换的临时文件同样改为唯一随机名。
- 取消下载时先关闭文件句柄再清理临时文件，不再留下 `.tmp` 残骸，取消也不再计为失败。
- 无 MD5 的已存在文件与转换输出必须通过结构校验才会被跳过，零字节或损坏文件会自动重新下载。
- 修复 webm/zip 等视频附件被误判为「无效图片」导致下载失败的问题。

### 配置与凭据安全

- 配置、队列与 API 凭据全部改为原子写入（先写同目录临时文件再替换），磁盘满或断电不再损坏原文件。
- 损坏的 `api_credentials.yaml` 在启动时自动隔离为 `.corrupt-时间戳` 备份并以空凭据继续启动，不再阻断 GUI。
- CLI `--save-config` 不再把用户名与 API Key 写入任务配置文件（与 GUI 导出行为一致）。

### 稳定性与退出语义

- 队列后台线程不再读取界面控件：配置在主线程一次性生成快照后传入，消除跨线程访问 Tk 的崩溃隐患。
- 并发数、超时、最大数量增加统一范围校验；并发数为 0/负数不再导致永久等待或异常（CLI 直接报参数错误）。
- 任一文件失败时 CLI 返回非零退出码（Ctrl+C 为 130）；GUI 显示「部分文件下载失败」；队列项相应标记为失败而非完成。
- 关闭窗口时先通知下载线程停止并等待其退出（最多 15 秒）再销毁界面，不再直接截断写盘。
- 修复 `start.bat` 在括号块内读取过期 `%ERRORLEVEL%` 的问题。

### 测试

- 新增 34 项回归测试：路径逃逸、MD5 校验、Windows 覆盖自愈、同名并发、原子写入、损坏凭据恢复、参数钳制、配置脱敏等。
- 全量 101 项单元测试通过。

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
