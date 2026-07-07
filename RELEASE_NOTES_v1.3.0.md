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

**Windows 下载：** [DanbooruDownload-v1.3.0-win-x64.zip](https://github.com/storyAura/DanbooruDownload/releases/download/v1.3.0/DanbooruDownload-v1.3.0-win-x64.zip)

解压后运行 `DanbooruDownload.exe`；运行依赖位于 `win-x64/`，默认下载目录为 `Download/`。
