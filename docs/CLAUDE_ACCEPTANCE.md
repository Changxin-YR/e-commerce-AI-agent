# Claude Code 独立验收

本仓库实现基于 FastAPI、SQLite、Vue 3 与 LangGraph 的电商历史交易分析应用。D0—D9 离线工程基线是 `6526e81674649068eac1a1a69a6a63d63a8fc8f2`；当前提交在其基础上增加验收入口。先读根目录 `CLAUDE.md`、`AGENTS.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md`，再读 `D9_ACCEPTANCE.md`、`D9_OPERATIONS.md`、`D9_API.md`、`EVIDENCE_INDEX.md`、`KNOWN_ISSUES.md`。旧 README/STATUS 的“未推送”和旧绝对路径描述记录 D9 封存时刻；用户之后授权提交 GitHub，实际发布状态以当前远端分支为准。

## 当前状态与判断边界

- `READY_FOR_USER_ACCEPTANCE`：离线工程可供验收，用户尚未最终确认。F01—F16 中 12 项 READY，F06—F09 真实模型链仍 `BLOCKED_AUTHORIZATION`。
- D9 历史测试：263 pytest、28 Vitest、9 Edge 与构建通过。验收时重新记录实际命令、退出码和证据；不得直接把这些历史数量称为本轮结果。
- 数据为 UCI Online Retail 541909 行，官方文件哈希与署名见 `data/manifest.json`。金额使用整数千分英镑计算，API 返回三位精度字符串。
- B0 无模型；B1/B2 的 scripted 测试证明工程机制，实际供应商调用仍为 0。默认真实预算 0、付费开关 false。Claude Code 自身可调用模型不等于应用已获付费模型授权。
- npm 历史审计保留 4 项开发依赖 moderate；生产 0，Python 固定依赖当时无已知漏洞。当前漏洞状态须另行查证，不能将历史记录当实时结果。
- 55 份不可变契约保持原字节。旧开工文档中的 NOT_STARTED/D0 是历史，不应据此重启开发。论文、人工 gold、正式学术实验暂未开始。

## 本机接手与另机复现

在用户本机，实际仓库路径为 `C:/Users/27363/Desktop/毕业论文/电商智能体的实现/ecommerce-agent-thesis`。2026-11-03 迁移后，`.env` 指向 `data/runtime/app.sqlite3` 与配套 checkpoint；该工作库有 63 任务、63 报告，含 60 scripted 夹具任务和 3 个 B0。完整封存交付与迁移检查记录在仓库旁的 `../交付物/`，详细路径映射见其中 `项目迁移记录/Claude_Code验收指南.md`。

GitHub 包含源码、Git 历史、锁定依赖清单、文档及已入库工程证据；`.env`、数据库、原始 ZIP/XLSX、依赖目录和本机 2.74 GB 封存交付包不在 Git 中。新克隆请指定文件夹名称，以满足原始交接脚本的项目名检查：

```powershell
git clone https://github.com/Changxin-YR/e-commerce-AI-agent.git ecommerce-agent-thesis
Set-Location ecommerce-agent-thesis
```

按 README 的“首次安装或独立复现”安装锁定依赖、创建本地 `.env`、迁移空库、取得并核对官方源数据、完成导入。不要复制另一台机器的 `.venv`，不要覆盖现有本机 `.env` 或数据库。官方 ZIP/XLSX 已按许可提供下载入口和哈希，源码包不捆绑数据本体。

## 执行检查

在仓库根执行：

```powershell
git status --short
git rev-parse HEAD
python scripts/handoff_check.py
python scripts/manage.py doctor
python scripts/manage.py test --scope all
```

`all` 顺序运行 pytest、Vitest、构建和 Edge 浏览器测试。`handoff_check` 只核验交接资料，不能代替业务验收。测试也可按 `backend`、`frontend`、`smoke`、`e2e` 拆开执行。浏览器测试需要 Microsoft Edge、官方 ZIP/XLSX、已导入源库；使用 `E2E_SOURCE_DATABASE` 指定已审计源库，测试会建立隔离工作库。

按照用户约定，把新增报告放到 `D:/codex产出/电商智能体_Claude验收/交付`，任务缓存放到同任务的 `缓存`；同名任务存在时先检查，使用新时间子目录保留历次结果。使用 `D0_CACHE_DIR`、`IMPORT_CACHE_DIR` 指向本轮缓存。用 `scripts/record_command.py --output <命令证据目录> --label <名称> -- <实际命令>` 保存原始输出与退出码。

执行会新增查询、报告、任务的脚本时，先将业务库和 checkpoint 成对备份到新的验收工作目录，保留封存件。带 WAL/SHM 的数据库使用 SQLite backup API；不要遗漏 WAL。`verify_metrics.py` 会保存查询，`verify_agent.py` 会写入 scripted 夹具。管理器的 `download-data/verify-data/tools/agent/evaluate` 为保留别名，不是已实现入口；具体专用脚本见 README。

前后端分别通过 `python scripts/manage.py backend` 与 `python scripts/manage.py frontend` 启动，默认 8000/5173；按 Ctrl+C 停止。按 D9 手册检查导入与幂等、精确指标、八工具、五视图、B0 报告与导出、历史只读、停服恢复、错误和本地安全边界。真实模型相关项仍标授权阻断。

## 验收报告

先独立审查并报告。每个问题给出严重度、文件行号、复现步骤、实际/预期结果、影响、证据路径和建议。区分缺陷、已知限制、授权阻断与未执行项。列出本轮 Git SHA、实际修改状态、环境、测试命令和退出码，以及 F01—F16/E01—E10 的本轮 PASS/FAIL/BLOCKED/NOT_RUN。需要修复时另行取得授权并留存新复测证据；不得改写封存结果或自授 USER_ACCEPTED。
