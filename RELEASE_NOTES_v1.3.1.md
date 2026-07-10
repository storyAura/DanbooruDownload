## v1.3.1

维护版本，修复 Nozomi.la 下载问题，并调整站点预设。

### Nozomi.la 下载修复

- 修复 Nozomi.la 图片下载失败的问题：CDN 对静态图片只提供 `.webp` 格式，此前程序按帖子元数据里的 `type`（jpg/png）拼接地址会导致 404。
- 现在非视频、非 gif 的静态图统一使用 `.webp` 媒体地址。
- 新增对应回归单元测试。

### 移除 Konachan

- Konachan 已对 API 请求启用 Cloudflare 人机验证，任何纯 HTTP 客户端都无法匿名访问，因此从站点预设中移除。
- 仍保留 `konachan.com` 的 profile 识别，高级用户可在站点地址栏手动输入尝试（能否成功取决于 Cloudflare 是否放行）。

### Gelbooru 凭据提示

- Gelbooru 已关闭匿名 API（返回 `401 Unauthorized`）。在站点预设中选择 Gelbooru 时，界面会在站点下方显示提醒，引导前往 设置 → API 认证 填写 **数字 User ID** 与 **API Key**。

### 站点抓取验证

- 对全部内置站点做了端到端抓取测试：Danbooru、AIBooru、Safebooru、Yande.re、Nozomi.la 均可正常搜索并下载；Gelbooru 需填写凭据；Konachan 因 Cloudflare 拦截已移除。

**Windows 下载：** [DanbooruDownload-v1.3.1-win-x64.zip](https://github.com/storyAura/DanbooruDownload/releases/download/v1.3.1/DanbooruDownload-v1.3.1-win-x64.zip)

解压后运行 `DanbooruDownload.exe`；运行依赖位于 `win-x64/`，默认下载目录为 `Download/`。
