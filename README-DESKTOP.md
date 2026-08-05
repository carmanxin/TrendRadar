# TrendRadar Desktop

TrendRadar 的桌面应用形态 — 双击即用，无需 Python 环境。

## 用户使用

1. 下载与你系统对应的压缩包（Windows / macOS / Linux），来自 GitHub Actions 的 `build-desktop` 工作流产物。
2. 解压，双击 `TrendRadar`（或 `TrendRadar.exe`）。
3. 首次启动会打开浏览器到 <http://127.0.0.1:8765>，按向导填入 AI API 信息（Base URL / API Key / 模型 / 时区）。
4. 在"主页"点击"立即运行"，日志实时显示，跑完后可查看生成的 HTML 报告。
5. 系统托盘菜单：打开 WebUI / 立即运行 / 开机自启 / 退出。
6. "设置"页可修改 AI Key、关键词、AI 兴趣、信息源（平台 + RSS）开关。

## 安全说明

- AI API Key 保存在操作系统用户目录（Windows: `%APPDATA%\TrendRadar\user_config.yaml`），仅本机可读。
- 日志与 WebUI 返回的配置都会对 Key / Token / 密码做脱敏（显示 `sk-abc****yz` 或 `***`）。
- 本地服务仅绑定 `127.0.0.1`，不会暴露到公网。

## 开发者

见 [docs/desktop.md](docs/desktop.md)。
