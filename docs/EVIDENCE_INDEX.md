# D2 实际证据索引

日期：2026-11-02（Asia/Shanghai）。D2 工程验证 PASS，READY_FOR_USER_ACCEPTANCE。D1 原索引归档在 docs/evidence/d2/D1_EVIDENCE_INDEX_ARCHIVE.md，原 D1 证据未覆盖。

本轮原始命令目录：`D:/codex产出/电商智能体_D2数据库导入/缓存/commands`；每份 JSON 含实际 argv、cwd、UTC 时间、退出码、stdout/stderr 文件名。结构化索引 `docs/evidence/d2/command-records.json` 还包含记录/日志 SHA。完整副本在同任务 `交付/证据`。

| 证据 | 真实结果 |
|---|---|
| docs/evidence/d2/real-import.json | 新库真实 HTTP 导入 541909 行，115.969 秒；41 核对通过，132 次导入中质量 GET 返回 409；ZIP/XLSX/CLI 幂等、重启持久化 |
| docs/evidence/d2/real-final.json | 最终代码再次通过 41 核对；既有快照复用，非第二次全量导入；数据库字节哈希未变 |
| docs/evidence/d2/pytest-final.xml | 116 passed，0 failed/errors/skipped；D2 新增 46 项 |
| docs/evidence/d2/d1-input-recheck.json | 本轮开工前 D1 输入/独立证据 33 项再核对通过 |
| docs/evidence/d2/missing-source.json | 缺文件明确 FAILED / SOURCE_NOT_FOUND，命令退出 1 为预期负例 |
| 缓存/playwright/2026-11-02T12-51-46-777Z-37984 | 2 项真实 Edge 健康/刷新/停服务/重启回归，截图、日志、JSON 报告与 trace；不是导入 UI 测试 |
| data/manifest.json | 官方 ZIP/XLSX 来源与身份；D2 数据集、批次和导入证据 SHA |

SQL 验证脚本 scripts/verify_import.py 直接查询真实数据库；没有引用生产导入计数函数，也没有创建月度业务 API。fixture 仅用于软件边界、异常与恢复测试，不充当真实数据验收或论文 gold。

## 实际命令与退出码

下表标签对应完整 argv 和日志；每条记录均已核对输出文件存在。外层统一使用 scripts/record_command.py。

| 标签 | 退出码 | 记录（相对本轮缓存） |
|---|---:|---|
| d2-handoff-initial | 0 | `commands/20261102T122221590014Z_d2-handoff-initial.json` |
| import-dependencies | 0 | `commands/20261102T122221590014Z_import-dependencies.json` |
| d1-input-recheck | 0 | `commands/20261102T122221845137Z_d1-input-recheck.json` |
| pytest-first | 0 | `commands/20261102T123933289106Z_pytest-first.json` |
| real-http-import | 0 | `commands/20261102T124353075604Z_real-http-import.json` |
| frontend-regression | 0 | `commands/20261102T124532276246Z_frontend-regression.json` |
| pytest-final | 0 | `commands/20261102T125145957274Z_pytest-final.json` |
| edge-regression | 0 | `commands/20261102T125145958547Z_edge-regression.json` |
| frontend-build | 0 | `commands/20261102T125145980093Z_frontend-build.json` |
| real-http-final | 0 | `commands/20261102T125145980093Z_real-http-final.json` |
| handoff-final | 0 | `commands/20261102T125406464875Z_handoff-final.json` |
| pip-check-final | 0 | `commands/20261102T125406465914Z_pip-check-final.json` |
| pip-lock-final | 0 | `commands/20261102T125406466975Z_pip-lock-final.json` |
| doctor-final | 0 | `commands/20261102T125406478393Z_doctor-final.json` |
| missing-source-rejected | 1 | `commands/20261102T125406499093Z_missing-source-rejected.json` |
| git-safety-final | 0 | `commands/20261102T130333890366Z_git-safety-final.json` |
| staged-diff-check | 2 | `commands/20261102T130551735141Z_staged-diff-check.json` |
| staged-diff-check-fixed | 0 | `commands/20261102T130803923748Z_staged-diff-check-fixed.json` |

完整命令包括实际 pytest/HTTP/CLI/构建/浏览器/依赖锁及 handoff；预期缺源负例不能误标失败为成功。Python 最终无警告；浏览器 Node 输出 NO_COLOR/FORCE_COLOR 提示，不影响测试。未运行付费模型、论文或正式实验。

Git 安全检查、最终 diff 与封存回执在交付/证据及 git-receipt.json；这些在状态文档冻结之后执行，避免自引用哈希。Git 源码 ZIP 与逐文件清单匹配，原始 ZIP/XLSX、.env、密钥、依赖及数据库不入源码归档。

首次staged diff检查退出2仅因locks.py末尾空行，修正后退出0；记录保留，见K15。
