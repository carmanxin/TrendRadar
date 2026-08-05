# TrendRadar Desktop 设计文档

> **状态**：待用户审阅
> **日期**：2026-08-04
> **范围**：trendradar v6.6.0 → 增加桌面应用形态（PyInstaller 打包 + WebUI + 系统托盘）

---

## 1. 背景与目标

### 1.1 现状
TrendRadar 是一个 Python 命令行热点新闻聚合分析系统。当前形态：
- 通过 `python -m trendradar` 运行
- 配置靠 `config/config.yaml` + 环境变量手动管理
- AI KEY 等敏感信息硬编码在 PowerShell 启动脚本里
- 学习/部署门槛高（Python 环境、依赖安装、YAML 语法、cron/任务计划）

### 1.2 目标
提供一个**桌面应用形态**，让小范围用户（5-50 人）可以：
1. 双击即用 — 无需安装 Python
2. 图形化配置 — 通过浏览器 WebUI 调整关键字、信息源、通知渠道
3. 安全使用 AI — 首次输入 KEY 后本地保存，后续直接复用

### 1.3 非目标（本期不做）
- 自动下载升级
- 移动端/响应式 WebUI
- 多用户/账号系统
- 国际化（先中文）
- 插件系统

---

## 2. 架构决策

| 维度 | 决策 | 理由 |
|------|------|------|
| 目标用户 | 小范围分享（5-50 人）| 超过命令行体验，但低于商业产品级 |
| UI 形态 | 浏览器 GUI（本地服务 + WebUI）| 复用现有 HTML 渲染能力，跨平台一致 |
| 打包方式 | PyInstaller 单目录 + 系统托盘 | 启动快、调试方便、托盘 + 浏览器即"桌面软件"体验 |
| 核心约束 | **零侵入现有代码** | desktop 子包只 import 不修改 |

---

## 3. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│            打包后用户视角 (TrendRadar.exe)                    │
│                                                             │
│   双击 → 启动后台 → 浏览器自动打开 http://localhost:8765   │
│       ┌──────────────────────────────────┐                  │
│       │   系统托盘 (pystray)              │                  │
│   ●─►│   右键菜单:                        │                  │
│       │   • 打开 WebUI                     │                  │
│       │   • 立即运行一次                   │                  │
│       │   • 编辑配置 (打开浏览器)          │                  │
│       │   • 开机自启 (勾选)                │                  │
│       │   • 查看日志                       │                  │
│       │   • 退出                           │                  │
│       └──────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│          trendradar.desktop (新模块)                          │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ FastAPI      │    │ ConfigStore  │    │ RunManager   │ │
│  │ /api/*       │    │ (本地密钥)   │    │ (subprocess) │ │
│  │ /static/*    │    └──────┬───────┘    └──────┬───────┘ │
│  └──────┬───────┘           │                   │         │
│         │                   ▼                   ▼         │
│         │         %APPDATA%\TrendRadar\     python -m     │
│         │         user_config.yaml           trendradar    │
│         │                                              │   │
│  ┌──────▼──────────────────────────────────────────┐   │   │
│  │  静态 WebUI (HTML/JS)                             │   │   │
│  │  - 首次向导 (输入 AI KEY + 选信息源)               │   │   │
│  │  - 配置页 (keyword/AI interest/sources)          │   │   │
│  │  - 运行页 (按钮 + 实时日志 + 历史报告)            │   │   │
│  │  - 设置页 (KEY/通知渠道/调度)                     │   │   │
│  └────────────────────────────────────────────────────┘   │   │
└─────────────────────────────────────────────────────────────┘   │
                          │                                      │
                          ▼ (HTTP/SSE 推日志)                     │
              python -m trendradar (现有)  ◄──────────────────┘
```

### 3.1 关键约束
1. **零侵入**：现有 `trendradar/__main__.py`、`core/`、`ai/`、`crawler/`、`notification/` 等模块**完全不修改**。desktop 层只 import。
2. **配置优先级**（运行时注入，不改现有逻辑）：
   `用户 user_config.yaml` → `config/config.yaml` → `环境变量`
   实现方式：desktop 在启动 subprocess 前把用户配置导出为 `AI_API_KEY` 等环境变量；YAML 编辑走 ConfigStore 直接写 `config/*.yaml`。
3. **打包后单 exe**：PyInstaller `--onefile` 模式 + 静态资源 `--add-data`。
4. **跨平台路径**：用 `platformdirs.user_config_dir("TrendRadar")` 找到标准位置：
   - Windows: `C:\Users\<user>\AppData\Roaming\TrendRadar\`
   - macOS: `~/Library/Application Support/TrendRadar/`
   - Linux: `~/.config/TrendRadar/`

---

## 4. 模块拆分

```
trendradar/
├── desktop/                      # 新增子包（打包入口）
│   ├── __init__.py
│   ├── __main__.py               # 打包后的 entry_point: TrendRadar.exe
│   ├── app.py                    # DesktopApp 总编排：start server + tray + browser
│   ├── server.py                 # FastAPI app factory + lifespan
│   ├── tray.py                   # pystray 托盘图标 + 菜单回调
│   ├── runner.py                 # RunManager: subprocess + 日志流转发
│   ├── config_store.py           # UserConfigStore: user_config.yaml 读写
│   │
│   ├── api/                      # FastAPI 路由
│   │   ├── __init__.py
│   │   ├── deps.py               # 依赖注入（path validator, scheduler guard）
│   │   ├── routes_wizard.py      # 首次向导 (/api/wizard/*)
│   │   ├── routes_config.py      # 配置读写 (/api/config/*)
│   │   ├── routes_keywords.py    # 关键词管理 (/api/keywords/*)
│   │   ├── routes_interests.py   # AI 兴趣 (/api/interests/*)
│   │   ├── routes_sources.py     # 信息源启停 (/api/sources/*)
│   │   ├── routes_keys.py        # AI KEY / 通知密钥 (/api/keys/*)
│   │   ├── routes_run.py         # 立即运行 + 日志 SSE (/api/run/*)
│   │   ├── routes_reports.py     # 历史报告列表 (/api/reports/*)
│   │   └── routes_system.py      # 版本/自启/日志路径 (/api/system/*)
│   │
│   ├── webui/                    # 静态前端 (PyInstaller --add-data)
│   │   ├── index.html            # 单页应用壳
│   │   ├── assets/
│   │   │   ├── app.js            # 主逻辑 (vanilla JS + fetch)
│   │   │   ├── styles.css
│   │   │   └── icons/
│   │   └── partials/             # 各 tab 的 HTML 片段
│   │
│   └── paths.py                  # platformdirs 包装 + 资源定位
│
├── ... 现有代码完全不修改 ...
```

### 4.1 各模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| `app.py` | 启动序列：绑端口 → 启服务 → 启托盘 → 开浏览器 | server, tray, paths |
| `server.py` | FastAPI 工厂，挂路由 + 静态资源 + lifespan 启停 | api/, webui |
| `tray.py` | pystray 图标 + 5 项菜单 + 退出清理 | app 单例 |
| `runner.py` | 启动 `python -m trendradar` 子进程，stdout/stderr 通过 SSE 推给前端 | subprocess, asyncio.Queue |
| `config_store.py` | 读写 `%APPDATA%/TrendRadar/user_config.yaml`，优先级合并 | platformdirs, yaml |
| `api/routes_*.py` | RESTful + 1 个 SSE 端点 | config_store, runner |
| `webui/` | 单页应用，3 个 Tab：向导 / 运行 / 设置 | 后端 API |

### 4.2 边界设计原则
- **desktop 层不知道任何业务逻辑**：它不调 `NewsAnalyzer`，不读新闻数据，所有 trendradar 工作都通过 `python -m trendradar` subprocess 走。
- **配置写入只走 ConfigStore**：不直接读写 `config/config.yaml`，避免与 subprocess 冲突（用文件锁或临时切换路径）。
- **WebUI 静态资源与 API 同源**：单一端口 8765，CORS 不用配。

---

## 5. 数据流与关键交互

### 5.1 首次启动 → 向导

```
双击 TrendRadar.exe
   │
   ▼
DesktopApp.start()
   ├─► paths.init()  检查 %APPDATA%\TrendRadar\user_config.yaml
   │     └─► 不存在 → 标记 NEED_WIZARD
   │
   ├─► FastAPI 启动在 127.0.0.1:8765（仅 loopback，防外网访问）
   │
   ├─► pystray 托盘启动
   │
   └─► webbrowser.open("http://localhost:8765")
         │
         ▼
       WebUI 加载 → GET /api/system/status
         │
         ├─ status=NEED_WIZARD → 自动跳转 /wizard 页面
         │     │
         │     ▼
         │   用户填: AI API Base / AI KEY / 模型名 / 时区
         │     │
         │     ▼
         │   POST /api/wizard/complete
         │     └─► ConfigStore.save_user_config()
         │     └─► 写入 %APPDATA%\TrendRadar\user_config.yaml
         │     └─► 生成 config/config.yaml 模板（如不存在）
         │     └─► 返回 status=READY
         │
         └─ status=READY → 跳转 /home
```

### 5.2 立即运行一次（核心交互）

```
WebUI 点击 [立即运行]
   │
   ▼
POST /api/run/start
   │
   ▼
RunManager.start()
   ├─► 检查：是否已有进程在跑？是 → 返回 409
   ├─► 构造环境变量：
   │     AI_API_KEY    = user_config.ai.api_key
   │     AI_API_BASE   = user_config.ai.api_base
   │     AI_MODEL      = user_config.ai.model
   │     AI_FILTER_…   = (其他 AI 参数)
   │     CONFIG_PATH   = config/config.yaml
   │     PYTHONPATH    = sys._MEIPASS (PyInstaller 临时目录)
   │
   ├─► subprocess.Popen(
   │       [sys.executable, "-m", "trendradar"],
   │       stdout=PIPE, stderr=STDOUT,
   │       env=merged_env,
   │       cwd=app_dir,
   │   )
   │
   └─► 启动 asyncio.Task: _pump_logs()
         ├─► 逐行读 stdout
         ├─► 写入 ring buffer (最近 10000 行)
         ├─► 通过 asyncio.Queue 推给所有 SSE 订阅者
         └─► 进程退出 → 推送 event: end + exit_code
   │
   ▼
前端 GET /api/run/logs/stream  (EventSource)
   ├─► 收到日志 → append 到 <pre id="logs">
   ├─► 收到 event: end → 显示 [运行完成 exit=N]
   └─► 刷新 /api/reports/latest
```

### 5.3 配置编辑（关键词 / 信息源 / 通知渠道）

```
WebUI /settings 页面加载
   │
   ▼
GET /api/config  → 返回完整合并后的配置（脱敏，KEY 显示为 sk-****EY）
   │
   ▼
用户修改后 → PUT /api/config/section/{name}
   │
   ▼
ConfigStore.update_section(name, data)
   ├─► 读取 config/config.yaml（PyYAML，YAGNI 不引入 ruamel.yaml；desktop 编辑走完整重写而非 in-place 合并）
   ├─► 深合并更新
   ├─► 写回（原子写：临时文件 → rename）
   └─► 写 audit log: %APPDATA%\TrendRadar\audit.log
   │
   ▼
返回 { ok: true, config: updated_config }
前端提示 [已保存，下次运行生效]
```

### 5.4 配置优先级链（运行时）

```
subprocess 启动时环境变量构造顺序（高 → 低覆盖）:

1. user_config.yaml       ← ConfigStore 读取，KEY 类敏感字段
2. config/config.yaml     ← 项目自带，可被向导初始化
3. process.env            ← 操作系统继承
4. defaults (代码内)      ← 仅作为兜底

合并实现: runner.py::build_env() 返回 dict，按上述顺序 dict.update()。
```

### 5.5 端口冲突处理

```
DesktopApp.start()
   ├─► 尝试绑定 8765
   │     ├─ 成功 → 记录 port=8765
   │     └─ 失败 (Address in use)
   │         ├─► GET http://127.0.0.1:8765/api/system/status
   │         │     ├─ 200 且返回 TrendRadar 标识 → 复用实例，只打开浏览器
   │         │     └─ 失败或非 TrendRadar → 询问用户:
   │         │           [使用其他端口] [退出]
   │         └─► 选其他端口 → 尝试 8766, 8767... 直到成功
```

---

## 6. 错误处理

### 6.1 错误处理矩阵

| 故障场景 | 检测点 | 用户感知 | 恢复策略 |
|---------|--------|---------|---------|
| 端口被占用 | server.py bind | 托盘气泡 + 弹窗"已有实例运行中" | 检测到 TrendRadar 进程则复用，否则让用户选端口 |
| AI KEY 无效 | subprocess 退出码 ≠ 0 + 日志含 401 | WebUI 红色横幅 `[AI 配置错误]` | 引导跳转到 /settings 重输 KEY（**KEY 不写日志**） |
| 网络不通（爬虫失败） | 日志含 `请求超时/连接错误` | WebUI 黄色提示 + 黄色进度 | 不中断，跑完后报告失败平台列表 |
| 子进程崩溃 | subprocess exit_code ≠ 0 | SSE 推送 `event: error` + 完整 stack | 保留日志到 `%APPDATA%\TrendRadar\crash-<ts>.log`，托盘菜单"查看日志"直达 |
| WebUI 静态资源丢失 | PyInstaller 解包失败 | 浏览器 404 | 启动时校验 `sys._MEIPASS/webui/index.html` 存在，否则报错并打开 GitHub Release 页 |
| 配置文件损坏 | YAML parse 失败 | 向导页提示"配置文件损坏，是否重置？" | 提供"备份旧文件 + 重新初始化"按钮 |
| KEY 泄露到日志 | 任何 print/log | 永远 | runner.py 在 `_pump_logs` 中过滤：`AI_API_KEY=sk-***` 模式替换为 `***` 后再推 SSE |

### 6.2 统一异常基类

```python
# trendradar/desktop/errors.py
class DesktopError(Exception): ...
class ConfigError(DesktopError): ...
class PortInUseError(DesktopError): ...
class RunAlreadyActiveError(DesktopError): ...
class ResourceMissingError(DesktopError): ...  # PyInstaller 资源找不到
```

FastAPI 全局 handler：捕获 `DesktopError` 返回 `{error: code, message: ...}`，HTTP 状态码语义化。

---

## 7. 打包（PyInstaller）

### 7.1 目录结构
```
packaging/
├── trendradar.spec          # PyInstaller spec
├── build.py                 # 一键构建脚本
├── icon.ico                 # Windows 图标
├── icon.icns                # macOS 图标
└── hooks/
    └── hook-feedparser.py   # 处理 feedparser 元数据导入
```

### 7.2 `trendradar.spec` 关键配置

```python
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['../trendradar/desktop/__main__.py'],
    pathex=['..'],
    binaries=[],
    datas=[
        ('../trendradar/desktop/webui', 'trendradar/desktop/webui'),
        ('../config/frequency_words.txt', 'config'),
        ('../config/ai_interests.txt', 'config'),
        ('../config/timeline.yaml', 'config'),
    ],
    hiddenimports=[
        'feedparser', 'pystray', 'PIL', 'fastapi', 'uvicorn',
        'platformdirs',
    ],
    hookspath=['hooks'],
    excludes=['tkinter', 'unittest', 'pytest', 'sphinx'],
    runtime_hooks=['runtime_hook_tray.py'],  # Windows 下隐藏控制台
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    name='TrendRadar',
    icon='icon.ico',
    console=False,              # Windows: 不弹黑色控制台
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name='TrendRadar',
)
```

### 7.3 打包产物
- Windows: `dist/TrendRadar/TrendRadar.exe` + 同目录 DLL（约 60-100 MB）
- macOS/Linux: 同结构，可打成 `.app`/`.AppImage`
- 用户获得：`TrendRadar/` 文件夹，**双击 TrendRadar.exe 即可**，无需安装 Python

### 7.4 为什么不用 `--onefile`
- 启动慢（每次解压 60MB 到临时目录）
- 托盘图标 + 浏览器开窗口有竞争，体验差
- 单目录模式启动 < 1 秒，足够"双击即用"

---

## 8. 开机自启

### 8.1 Windows
```python
# trendradar/desktop/autostart.py
import winreg
KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def set_autostart(enabled: bool, exe_path: str):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, "TrendRadar", 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            winreg.DeleteValue(k, "TrendRadar")
```

### 8.2 macOS / Linux
- macOS：写 `~/Library/LaunchAgents/com.trendradar.desktop.plist`
- Linux：写 `~/.config/autostart/trendradar.desktop`

WebUI 设置页勾选框 → `PUT /api/system/autostart {enabled: true/false}` → autostart 模块自动按平台分发。

---

## 9. 升级策略

不做自动升级，但保留升级检查：
- 启动时 `GET https://api.github.com/repos/<owner>/TrendRadar/releases/latest`（失败静默）
- 若 `tag_name > 当前 version` → 托盘气泡提示"有新版本可用"，WebUI 设置页显示下载按钮
- **不自动下载/覆盖**（避免破坏用户数据），用户手动下载覆盖即可

---

## 10. 测试策略

| 层 | 工具 | 覆盖范围 |
|----|------|---------|
| 单元 | pytest | config_store, paths, runner env 合并, KEY 脱敏 |
| API | httpx + FastAPI TestClient | 所有 `/api/*` 端点 + 错误响应 |
| 集成 | pytest + 临时目录 | 端到端：写 user_config → 启动 mock subprocess → 验证 SSE 收到日志 |
| 打包 | GitHub Actions matrix | win/mac/linux 三平台 .spec 构建 + smoke run（启动 → 8765 端口监听 → curl status） |
| 手工 | checklist | 向导流程 / 修改 KEY / 修改关键词 / 立即运行 / 托盘菜单 5 项 / 重启自启 |

### 10.1 测试里程碑

```
M0 完成 → pytest tests/desktop/test_paths.py ✓
M1 完成 → pytest tests/desktop/test_config_store.py + test_runner.py ✓
M2 完成 → pytest tests/desktop/test_api_*.py ✓ + 手动 smoke (启动 → API)
M3 完成 → 手动 e2e: 向导→运行→看报告（Playwright 可选）
M4 完成 → 手动 checklist 5 项托盘菜单 + 重启自启
M5 完成 → CI 三平台 build + smoke: 启动后 GET /api/system/status 返回 200
M6 完成 → 全量 pytest + 手动 e2e 完整流程
```

---

## 11. 实施计划

### 11.1 工作分解（6 个里程碑）

| M | 名称 | 关键交付 | 估时 |
|---|------|---------|------|
| **M0** | 基础设施 | `trendradar/desktop/` 包骨架 + `paths.py` + `errors.py` + 端口探测工具 | 0.5d |
| **M1** | 配置层 | `config_store.py`（读写/合并/原子写/审计）+ KEY 脱敏工具 | 1d |
| **M2** | 服务框架 | `app.py` + `server.py`（FastAPI + lifespan）+ `runner.py`（subprocess + SSE）+ 5 个核心路由（wizard/config/keys/run/system）| 2d |
| **M3** | WebUI v1 | 单页应用：向导 4 步 + 主页（运行按钮+日志面板+历史报告）+ 设置页（KEY/关键词/兴趣/信息源）| 2d |
| **M4** | 托盘 + 高级 | `tray.py` + 开机自启 + 端口冲突复用 + 升级检查提示 | 1d |
| **M5** | 打包 | PyInstaller spec + build.py + GitHub Actions 三平台 + smoke test | 1.5d |
| **M6** | 收尾 | 文档（README-DESKTOP.md）+ 错误处理打磨 + 完整测试矩阵 + 手动 checklist 验证 | 1d |
| | | **总计** | **~9 人天** |

### 11.2 文件清单（新增 ≈ 35 个）

**Python 后端（23 个）：**
- `trendradar/desktop/__init__.py`、`__main__.py`、`app.py`、`server.py`、`tray.py`、`runner.py`、`config_store.py`、`paths.py`、`errors.py`、`autostart.py`、`version_check.py`（11）
- `trendradar/desktop/api/` 下 10 个：`__init__.py` + 9 个 routes_*.py

**前端（≈ 8 个）：**
- `webui/index.html`、`assets/app.js`、`assets/styles.css`
- `assets/icons/` 4-6 个 SVG
- `partials/` 4 个 tab 片段（wizard / home / settings / sources）

**打包与配置（≈ 6 个）：**
- `packaging/trendradar.spec`、`build.py`、`icon.ico`、`icon.icns`
- `packaging/hooks/runtime_hook_tray.py`、`hook-feedparser.py`

**新增 Python 依赖（写入 requirements.txt）：**
- `fastapi`、`uvicorn[standard]`、`pystray`、`Pillow`、`platformdirs`

**文档与 CI（3 个）：**
- `docs/desktop.md`、`README-DESKTOP.md`（中英）
- `.github/workflows/build-desktop.yml`

**测试（≈ 8 个）：**
- `tests/desktop/test_config_store.py`、`test_runner.py`、`test_paths.py`、`test_api_wizard.py`、`test_api_run.py`、`test_api_config.py`、`test_autostart.py`、`test_smoke.py`

### 11.3 关键风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| PyInstaller 打包后隐藏导入缺失 | 启动崩溃 | M2 就用 PyInstaller dry-run 验证一次，提前收集 hiddenimports |
| pystray 在不同 Windows 版本兼容性 | 托盘菜单乱码/图标丢失 | runtime_hook 强制 UTF-8 + 用 PNG（不是 ICO）+ Windows 10+ 文档标注最低版本 |
| 浏览器被防火墙拦截 | 启动后浏览器空白 | 默认端口仅绑 127.0.0.1，绕过大部分防火墙；启动后用 `socket.create_connection` 自检 |
| AI KEY 误写日志 | 安全事故 | M1 就实现脱敏 filter，所有 print/log 路径都过 runner 转发，单元测试覆盖 |
| subprocess 中文 Windows 编码错乱 | 日志乱码 | `PYTHONIOENCODING=utf-8` 强制注入环境变量 |
| feedparser/xml 在 PyInstaller 中缺元数据 | RSS 抓取失败 | 提供 `hook-feedparser.py` |

---

## 12. 显式不做（YAGNI）

为了控制范围，以下功能**本期不实现**（未来按需添加）：

- ❌ 多用户/账号系统（user_config 已经按用户隔离）
- ❌ 自动升级下载安装
- ❌ 移动端/响应式 WebUI（桌面浏览器专用）
- ❌ 完整的趋势图表/可视化（HTML 报告已经够用）
- ❌ WebUI 国际化（先中文，未来加英文）
- ❌ 插件系统/自定义信息源 GUI（先支持 YAML 文本编辑）
- ❌ 日志全文搜索（够用即可）
- ❌ 远程访问（仅 127.0.0.1，绝不暴露公网）

---

## 13. 参考资料

- [TrendRadar 工作流文档](../TRENDRADAR_WORKFLOW.md)
- [PyInstaller 文档](https://pyinstaller.org/en/stable/)
- [pystray 文档](https://github.com/moses-palmer/pystray)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [platformdirs 文档](https://platformdirs.readthedocs.io/)
