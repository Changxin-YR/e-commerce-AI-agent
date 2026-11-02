# 当前进度：D3 精确指标、只读工具与查询历史已完成

最新状态见 `docs/STATUS.json`，本轮交付见 `docs/D3_DELIVERY.md`，指标使用见 `docs/D3_METRICS.md`，导入/恢复操作见 `docs/D2_IMPORT.md`。官方541909行已入库，158 pytest / 8 Vitest / 2 Edge、87项真实核对及真实历史JSON的Edge刷新通过；完成后等待验收，不进入D4。原始文件只在本地 `data/raw/`。

# 电商经营数据分析智能体 · 启动说明

已实现可运行的 FastAPI + SQLite/Alembic 后端、Vue 3 + TypeScript + Vite 健康连接页及管理命令。D0—D3已完成，确定性指标API和3项受限工具可用；业务页面、Agent和完整报告属于D4—D9，尚未实现。论文与正式学术实验继续延期。

本机项目根目录是 `C:\Users\27363\Desktop\毕业论文\电商智能体的实现\ecommerce-agent-thesis`，请在该目录执行以下命令。源文件保留在工作区，额外交付位于 `D:\codex产出\电商智能体_D3精确指标API\交付`，日志、测试数据库和构建位于同任务的 `缓存` 目录。

## 本机环境与安装

2026-11-02 实测：Windows 11 build 26200、Python 3.12.15、Node.js 24.22.0、npm 11.19.1、Git 2.56.0.windows.3、Python 内置 SQLite 3.53.1。Python 要求 3.11+，Node 要求 22.12+；实际锁定环境为上述版本。浏览器测试使用本机 Microsoft Edge，不下载浏览器，不调用模型。

`D:\codex产出` 由用户事先创建。首次安装或重新安装：

```powershell
Set-Location 'C:\Users\27363\Desktop\毕业论文\电商智能体的实现\ecommerce-agent-thesis'
$env:D0_CACHE_DIR = 'D:\codex产出\电商智能体_D3精确指标API\缓存'
New-Item -ItemType Directory -Force -Path $env:D0_CACHE_DIR | Out-Null
$env:PIP_CACHE_DIR = Join-Path $env:D0_CACHE_DIR 'pip'
$env:npm_config_cache = Join-Path $env:D0_CACHE_DIR 'npm'
$env:TEMP = $env:D0_CACHE_DIR
$env:TMP = $env:D0_CACHE_DIR
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
npm --prefix frontend ci --no-fund
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python scripts/manage.py doctor
python scripts/manage.py migrate
```

本次已创建 `.venv`、安装依赖并生成 `.env`，不必重复初始化。管理脚本自动使用项目 `.venv`，无需激活脚本或修改 PowerShell 执行策略。Python 全量实际依赖固定于 `requirements.lock`；npm 完整依赖及 integrity 固定于 `frontend/package-lock.json`，直接依赖也固定精确版本。`requirements.in` 仅用于解释依赖来源，重建请使用锁文件，不自行升级。

`.env` 不入 Git；模板关闭付费模型且总预算为 0。当前没有模型SDK或调用入口。数据库路径指向D3任务缓存/runtime，已真实导入；交付目录另有备份。可修改 `APP_PORT`/`FRONTEND_PORT`，后端与开发代理读取同一配置；端口冲突时报错退出，不悄悄换端口。

## 启动、检查与停止

在两个 PowerShell 窗口进入同一个项目根目录后分别运行：

```powershell
# 窗口 A：后端
python scripts/manage.py backend
```

```powershell
# 窗口 B：前端
python scripts/manage.py frontend
```

浏览器打开 `http://127.0.0.1:5173`，应显示“本地服务已连接”以及真实 SQLite/迁移版本。后端默认 `http://127.0.0.1:8000`，OpenAPI 交互文档在 `/docs`。两服务均只监听本机。

```powershell
# 第三个窗口：真实 API 响应
Invoke-RestMethod 'http://127.0.0.1:8000/healthz' | ConvertTo-Json -Depth 4
```

停止时在各自窗口按 `Ctrl+C`。需要开发自动重载可用 `python scripts/manage.py backend --reload`；该可选模式未作为 D0 验收命令。自动浏览器测试会清理自己创建的服务，不停止用户已有进程。

`GET /healthz` 检查真实连接、`alembic_version`、`app_metadata` 与项目标记。成功为 HTTP 200：

```json
{"status":"ok","service":"ecommerce-agent","version":"0.3.0","stage":"D3","database":{"status":"ok","engine":"sqlite","sqlite_version":"3.53.1","schema_revision":"0003_query_history"}}
```

SQLite 版本以实际运行环境为准。缺库/未迁移/损坏返回 503；健康请求只读，不创建数据库、不自动执行迁移。异常统一为 `{"error":{"code":"...","message":"...","details":{}},"request_id":"..."}`，不返回内部路径或堆栈。不存在的业务路由返回 404，不返回假业务结果。

## 验证命令

```powershell
python scripts/handoff_check.py
python scripts/manage.py test --scope smoke
python scripts/manage.py test --scope e2e
```

`smoke` 顺序执行 pytest、Vitest、TypeScript 检查及 Vite 构建，首个失败立即返回真实退出码。已通过158项Python测试、8项前端测试及构建。`e2e` 通过真实 Edge、隔离数据库与随机本机端口自动启动管理命令，2 项测试覆盖真实健康响应/刷新，以及实际停后端→页面报错→重启恢复，并保存桌面、移动宽度与失败恢复截图。浏览器回归仅验证健康页；另有真实经营数据HTTP/SQL导入验证，全部属于工程验证，无学术实验。

`python scripts/manage.py verify-metrics --database <现有导入库> --output <新的证据目录> --browser` 可执行D3真实验证；会重复上传既有源验证幂等，并显式保存一份查询历史。具体参数见 docs/D3_METRICS.md。

其他已实现命令：

| 命令 | 行为 |
|---|---|
| `python scripts/manage.py doctor` | 实际版本、依赖、端口及数据库文件存在性；环境检查不等于业务验收 |
| `python scripts/manage.py migrate` | Alembic upgrade head；可以重复执行 |
| `python scripts/manage.py test --scope backend` | 后端与管理脚本测试 |
| `python scripts/manage.py test --scope frontend` | Vitest 测试 |
| `python scripts/manage.py build` | 前端类型检查与生产构建 |
| `python scripts/manage.py test --scope all` | smoke 后再执行 e2e |
| `python scripts/manage.py --help` | 所有入口说明 |

`python scripts/manage.py import-data <官方ZIP/XLSX>` 已实现。`download-data/verify-data/tools/agent/evaluate` 管理入口仍预留，返回NOT_IMPLEMENTED和退出码2；真实数据下载/审计使用已实现的专用scripts脚本。

`D0_CACHE_DIR` 从根 `.env` 或环境读取。构建输出为其下 `frontend-dist`；另有 `npm --prefix frontend run preview` 预览入口，仍需启动后端，该可选入口未纳入 D0 验证。仅构建了前端静态文件，不代表实现生产部署。

保存单次命令证据可使用：

```powershell
python scripts/record_command.py --output 'D:\codex产出\电商智能体_D3精确指标API\缓存\commands' --label smoke -- python scripts/manage.py test --scope smoke
```

记录包含完整 argv、工作目录、UTC 起止时间、耗时、退出码和原始 stdout/stderr；不要在参数中放密钥。浏览器证据保存到 `缓存\playwright\<每次独立目录>`，包含真实进程启动/停止记录、截图与 trace。

## 故障排查与当前限制

- `DATABASE_NOT_INITIALIZED` / `DATABASE_MIGRATION_REQUIRED`：检查本地 `.env` 路径，再执行 `python scripts/manage.py migrate`。不要删除已有数据库。
- 页面显示暂不可用：检查后端窗口、配置端口和 `GET /healthz`；服务恢复后点击“重新检查”。
- 缺少依赖：用锁文件安装到 `.venv` 并运行 `npm --prefix frontend ci --no-fund`；不要混用系统 Python 包。
- Edge 不可用：浏览器测试会失败并保留日志，不会冒充通过；安装浏览器或在明确环境变更后调整 Playwright channel。
- 已知依赖告警及真实失败修复见 `docs/KNOWN_ISSUES.md`，完整运行证据见 `docs/EVIDENCE_INDEX.md`。

仓库已有D0—D3本地提交，最终SHA见当前交付目录的git-receipt.json；未推送。源码ZIP和文件哈希清单可核对。`PACKAGE_MANIFEST.json` 是原始 V1.5 交接包的不可变资料描述，其 `NOT_STARTED` 不用于表示当前开发进度。当前进度以 `docs/STATUS.json` 为准。

本轮停止在 D3，用户验收并授权后才进入 D4 真实Vue业务页面。继续开发必须先读项目 `AGENTS.md`、`DEV_FIRST.md` 和 `docs/NEXT_SESSION.md`。
