# D0 历史工程证据索引

验证日期：2026-11-02（Asia/Shanghai）。工程验证 PASS，D0 READY_FOR_USER_ACCEPTANCE；不表示业务或模型完成。`docs/plan/evidence/` 仍是原包历史审计资料，未将其当成本机业务验收。

## 路径与记录格式

- 原始命令记录根：`D:/codex产出/电商智能体_D0工程初始化/缓存/commands`。
- 每个 JSON 包含实际 argv/cwd/UTC起止时间/退出码，配套同名 `.stdout.txt` 和 `.stderr.txt` 为原始输出。
- 最终交付包保留这些记录副本于 `D:/codex产出/电商智能体_D0工程初始化/交付/证据/commands`。
- 源码与逐文件 SHA256 清单位于同一交付目录；源码工作区原位保留。

## 实际命令结果

| 标签 | 退出码 | 结论 | 记录文件（相对 commands） |
|---|---:|---|---|
| handoff-initial | 0 | PASS | `20261102T075105819672Z_handoff-initial.json` |
| venv-create | 0 | PASS | `20261102T075106069007Z_venv-create.json` |
| pip-install | 0 | PASS | `20261102T075131665942Z_pip-install.json` |
| npm-install | 0 | PASS | `20261102T075436640894Z_npm-install.json` |
| backend-tests-first | 1 | FAIL：缓存父目录缺失，已修复；首次记录保留 | `20261102T080025218227Z_backend-tests-first.json` |
| playwright-install | 0 | PASS | `20261102T080148380257Z_playwright-install.json` |
| backend-tests-fixed | 0 | PASS | `20261102T080202046424Z_backend-tests-fixed.json` |
| npm-audit | 1 | KNOWN_ISSUE：首次5个moderate | `20261102T080608112698Z_npm-audit.json` |
| frontend-tests | 0 | PASS | `20261102T080616460054Z_frontend-tests.json` |
| frontend-build | 0 | PASS | `20261102T080622370474Z_frontend-build.json` |
| npm-audit-fix | 1 | KNOWN_ISSUE：修复后仍4个moderate | `20261102T080739824633Z_npm-audit-fix.json` |
| migrate | 0 | PASS | `20261102T080811373716Z_migrate.json` |
| doctor | 0 | PASS | `20261102T080815819790Z_doctor.json` |
| npm-lock | 0 | PASS | `20261102T081054768949Z_npm-lock.json` |
| smoke-final | 0 | PASS | `20261102T081056121242Z_smoke-final.json` |
| browser-e2e | 0 | PASS | `20261102T081106680306Z_browser-e2e.json` |
| pip-lock-install | 0 | PASS | `20261102T081555164588Z_pip-lock-install.json` |
| pip-check | 0 | PASS | `20261102T081556607464Z_pip-check.json` |
| npm-ci | 0 | PASS | `20261102T081557427548Z_npm-ci.json` |
| npm-audit-production | 0 | PASS | `20261102T081611563109Z_npm-audit-production.json` |
| default-ports-startup | 0 | PASS | `20261102T081716071837Z_default-ports-startup.json` |
| handoff-final | 0 | PASS | `20261102T082220890319Z_handoff-final.json` |
| git-final | 0 | PASS | `20261102T082221536410Z_git-final.json` |
| frontend-build-after-ci | 0 | PASS | `20261102T082221672333Z_frontend-build-after-ci.json` |
| not-implemented | 2 | EXPECTED：D0外命令返回2 | `20261102T082225141677Z_not-implemented.json` |

`smoke-final` 的子命令：31 pytest + 8 Vitest + TypeScript/Vite build，均成功。`frontend-build-after-ci` 确认锁文件重装后仍可构建。`not-implemented` 返回2是预期拒绝，不是未实现接口被伪装成功。

## 真实浏览器与默认端口

- Edge/Playwright：`缓存/playwright/2026-11-02T08-11-07-621Z-26024`，包含 `results.json`（2 passed）、`launcher.json`、`commands.json`、服务日志、4张截图和 `artifacts/**/trace.zip`。服务随机端口为64762/64763；数据库是空的工程fixture，未导入经营数据。
- 截图：`desktop-connected.png`、`mobile-connected.png`、`backend-stopped.png`、`backend-recovered.png`。截图已经实际查看，桌面/390px宽度没有横向溢出。
- 默认端口：`缓存/local-startup/20261102T081716/result.json` / `processes.json`，实测 `manage.py backend` 的8000及 `manage.py frontend` 的5173；直接健康/代理健康/OpenAPI/SQLite完整性均成功。
- 测试停止自己创建的进程树时，Windows 服务退出码1为有意停止，附 `intentional_stop=true`；对应taskkill退出0，测试总命令退出0。所有验证服务已清理，未停止用户服务。

## 来源、版本与数据状态

- 输入 V1.5 ZIP SHA256：`8fb3efe942f7bfd0602d54fdf14565af2d3f6d41e7354afbe6869a166c483f94`。
- Git：初始工作区为空且不是仓库，git status报告 not a git repository，初次PowerShell工具返回1；本轮git init成功。最终无commit，SHA=null，原始git状态见git-final记录。未覆盖用户修改。
- D0运行数据库SHA256：`5997333b758ba8986dc4b775e6dcd7125883da3c80f8fb3a1212793782bfc3c0`，仅工程元数据；**不是经营数据哈希**。
- 真实UCI文件未下载，业务数据SHA=null；模型未接入/未调用；未写论文或运行正式实验。
- Windows 11 build26200 / Python3.12.15 / Node24.22.0 / npm11.19.1 / Git2.56.0.windows.3 / SQLite3.53.1，详细版本见doctor输出及两种锁文件。

## 失败与范围

首次pytest缓存目录失败、npm全量审计未清零、Starlette弃用提示均见KNOWN_ISSUES和原始输出。未将handoff PASS当作业务通过；D1—D9及F01—F16完整业务验收没有预勾通过。下一步只有用户验收后才执行D1。
