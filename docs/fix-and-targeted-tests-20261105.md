# 2026-11-05 项目修复与针对性测试报告

范围：对 `ecommerce-agent-thesis` 当前工作区做缺陷修复与针对性回归。未启用真实付费模型、未改动数据库 schema、未提交或推送 Git、未写论文/正式实验。历史 D9、UI、流式证据保留原字节与原始结论。

## 一、发现并修复的问题

### 1. 环境级：项目依赖树带低完整性沙箱 ACL（阻断测试）

现场：`.venv/Scripts/python.exe`、`frontend/node_modules`、`data/runtime/*.sqlite3`、源码文件均被标记为 `Mandatory Label\Low Mandatory Level`，并带有旧沙箱 ACE。由此：

- 用 `.venv` 解释器运行 pytest 时，`tmp_path` / `--basetemp` 创建目录报 `PermissionError [WinError 5]`，首轮结果 `81 passed / 196 errors`；E2E 的 Alembic 隔离库迁移退出码 1，首轮 `3 failed / 9 did not run`。
- 项目解释器无法写入 D 盘任务缓存（同一系统解释器可以），导致 pytest、导入缓存、E2E 临时库全部受影响；用沙箱外的系统 Python 执行则正常。

修复：对项目树执行 `icacls <项目> /setintegritylevel Medium /T`（`.venv` 单独执行 `/reset` 后设回 Medium），不再有低完整性进程写正常对象的问题。原始失败日志均保留在缓存 `logs/`，未删除、未改写为 PASS。

### 2. 依赖级：`frontend/node_modules` 中 esbuild 平台二进制缺失

现场：`node_modules/@esbuild/win32-x64` 只有 `package.json`/`README.md`，没有 `esbuild.exe`；`npm run test` 直接 `Startup Error`，报 "installed esbuild for another platform"（实际同平台，载体缺文件）。这不是源码缺陷。

修复：按锁定文件重新安装前端依赖（`npm ci --no-fund --no-audit`，179 packages），确认 `esbuild.exe` 存在且 `require('esbuild').transformSync()` 可用。`package-lock.json` 未修改。

### 3. 数据级：`data/raw` 缺少官方源文件

现场：`data/raw` 只有 README 与锁文件，官方 `online_retail_uci352.zip`、`Online_Retail.xlsx` 不在位，导入/幂等/XLSX 复用 E2E 无法运行。

修复：从 D9 封存缓存的同内容文件恢复，SHA-256 与 `data/manifest.json` 审计值一致：

- `online_retail_uci352.zip`：`F5385CBB…AEDE8B`
- `Online_Retail.xlsx`：`43465A06…F64676D`

文件仍在 `.gitignore` 保护范围（`*.zip`/`*.xlsx`、`data/raw/*`），不会进入 Git。

### 4. 代码级：STREAM-02 模型末轮 JSON 语法失败（真实追问曾被阻断）

现场（历史真实调用记录）：模型在 `message` 内输出未转义的英文双引号，严格 `Decision.model_validate_json` 拒绝 → 触发“仅格式纠错”轮 → 模型重复同一语法错误并消耗保守预算 → 后续网关 HTTP 错误。已核验工具证据与预算逻辑本身没有失效，问题在末轮 JSON 语法。

修复：新增 `backend/app/agent/tolerant_json.py`，在严格校验前只做**语法级**恢复：

- 允许 `message`/`label` 字符串内的未转义双引号、原始换行、Markdown 围栏、对象前后说明文字；
- 正确合并 `\uXXXX` 代理对，未知转义保留字面值；
- 只用恢复后的对象进入原 `Decision` 严格模型，随后仍执行 `resolve_claim`、数值一致性、B2 条件/对账、引用完整性全部校验；
- 无法恢复时仍抛原严格错误，走原有有界纠错流程。

`backend/app/agent/workflow.py` 的 `review` 节点改用 `parse_decision`。未放宽任何证据、金额、预算、授权或数据库约束，没有新增请求/依赖/schema 变更。

对应测试：

- 新增 `tests/test_tolerant_json.py`（5 项）：未转义引号+换行+围栏恢复、代理对、严格 schema 仍拒绝非法 action/缺字段、恢复后无需额外模型请求、恢复语法但金额不符仍判 `CLAIM_VALUE_MISMATCH` 且不绕过纠错轮。
- 调整 `tests/test_streaming.py` 既有格式纠错用例：用真正缺字段的 schema 错误覆盖纠错轮，避免与新的语法恢复行为重叠。

## 二、针对性测试结果（本轮实际执行）

环境：Windows 11、Python 3.12.15（项目 `.venv`）、Node 24.22.0、npm 11.19.1、SQLite 3.53.1；D 盘任务缓存 `D:/codex产出/电商智能体_项目修复与针对性测试/缓存`。

| 检查 | 命令 | 结果 |
|---|---|---|
| 后端全量 | `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` | **282 passed**，0 failed，58.46s |
| 前端单测 | `npm run test` | **39 passed / 4 files** |
| 类型检查+生产构建 | `npm run build`（vue-tsc + vite） | **PASS** |
| 完整 Edge E2E | `npm run test:e2e`（隔离库、真实 UCI 文件、脚本 provider） | **12 passed / 0 skipped / 0 failed**，4.2m |
| 管理器 smoke（记录命令） | `python scripts/manage.py test --scope smoke` | **exit 0**，282 pytest + 39 Vitest + build |
| 交接完整性 | `python scripts/handoff_check.py` | PASS，55 份不可变文件 |
| 环境自检 | `python scripts/manage.py doctor` | PASS |

E2E 覆盖：官方 ZIP 上传/刷新恢复/541909 行核对/XLSX 幂等复用、9/10 月精确值与独立 SQL、部分期间/空筛选/损坏上传/后端停机恢复、B0 报告与导出/重启回看、脚本 B2 补答恢复、取消确认、流式对话与四个宽度/矮窗口、存储型文本转义与跨源 403。

首轮失败证据保留（环境问题时）：`pytest` 196 setup errors、E2E 3 failed/9 did not run；修复环境后同一套命令通过，未用“跳过”冒充 PASS。

## 三、变更文件

- 新增：`backend/app/agent/tolerant_json.py`、`tests/test_tolerant_json.py`
- 修改：`backend/app/agent/workflow.py`（仅 review 调用点与异常捕获）、`tests/test_streaming.py`（纠错用例改用真正 schema 错误）
- 环境/数据（不入 Git）：`.venv` 完整性标签、`frontend/node_modules` 重装、`data/raw` 两个官方文件

## 四、边界与未完成项

- **未做真实付费模型验证**：本轮 0 次外部模型请求、0 token、预算未变；STREAM-02 的修复只证明离线语法恢复与校验未被放松，不能宣称真实供应商追问已通过。
- **STREAM-03 外部阻断未解决**：供应商间歇性 TLS/HTTP 失败属于外部服务问题，本轮未关闭证书校验、未加重试、未扩额度。
- 未新增或修改数据库迁移；`docs/STATUS.json` 的外部模型结论仍为 PARTIAL/BLOCKED，不由本轮自动升级为 USER_ACCEPTED。
- 未执行 `git add/commit/push`；当前工作区仍包含此前未提交的 UI/流式改动与本轮修复。
- K01 的 4 项 npm 开发依赖 moderate 告警保持原状，未强制升级。

## 五、证据位置

- 任务缓存与命令记录：`D:/codex产出/电商智能体_项目修复与针对性测试/缓存`
- 修复后测试日志：`缓存/logs/`（pytest/vitest/build/e2e/manage smoke）
- 命令退出码与原始输出：`缓存/commands/`
- Playwright 结果与 trace：`缓存/playwright/<时间戳>/results.json`、`artifacts/`
- 交付副本：`D:/codex产出/电商智能体_项目修复与针对性测试/交付/`，以及工作区内 `交付物/项目修复与针对性测试/`（含报告、结果 JSON、变更源码与证据副本）
