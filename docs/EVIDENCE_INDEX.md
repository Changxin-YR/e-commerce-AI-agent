# 2026-11-05 修复与针对性测试

本机工程修复与回归证据：`docs/fix-and-targeted-tests-20261105.md`；任务缓存 `D:/codex产出/电商智能体_项目修复与针对性测试/缓存`（`logs/`、`commands/`、`playwright/`）。实测 282 pytest、39 Vitest、12 Edge、build PASS、manager smoke exit 0；首轮环境失败（pytest 196 setup errors、Edge 3 failed/9 did not run）原始日志保留。0 次真实模型请求，外部 TLS 阻断仍未解除。

# 2026-11-03 最新补充：连接复用及真实报告验证

当前 PARTIAL：本地工程 PASS，真实首轮“我有哪些数据？”已生成并核验报告，连续追问仍未通过（模型 JSON 格式错误后，纠错轮上游 MODEL_HTTP_ERROR）。连接复用降低重复握手；仅格式纠错不再携带工具定义，限额与校验不变。最后省略空 tools 字段通过本地测试，未再次付费复测。

测试：277 项完整 pytest；最终协议调整后 43 项相关 pytest；39 Vitest；类型检查/构建通过。此前 Edge 12+7 项证据保留，本次只读检查真实对话与报告。累计 17 次请求尝试，已知 88728 token，4 次用量未知，预算占用 156180（不是账单）。

完整证据、成功与失败运行 ID 见 [AI 流式对话升级报告](ai-streaming-upgrade.md)。下方为先前阶段历史记录。不要覆盖用户配置、删除失败数据、自动反复调用付费模型；下一步若要继续排查，应先确认网关结构化输出/无工具请求兼容性及可靠的请求计量。未提交 Git、推送、部署或开始论文实验。

# 2026-11-03 最新补充：AI 流式对话

验收 PARTIAL：流式对话、本地工程与浏览器回归通过（273 pytest、39 Vitest、12 项完整 Edge、最终 7 项针对性 Edge，以及类型检查/构建）。真实供应商已返回增量和工具调用，但完整报告链被间歇性 TLS 握手失败阻断；当前问题是 MODEL_CONNECTION_ERROR，不是旧版的未授权状态。原 `.env` 与预算未变，无数据库迁移。

本轮有限真实验证预占 7 次请求：24666 个已确认 token，3 次消耗未知；未知预占未清零。没有宣称真实模型全流程通过。代码、所有问题及失败证据见 [AI 流式对话升级报告](ai-streaming-upgrade.md)。交付：D:/codex产出/电商智能体_AI前端全面优化_20261103/交付/流式对话升级。旧 UI 与 D9 的结果是历史快照，保留原记录。

# 2026-11-03 最新补充：AI 前端 UI 优化

本次 UI/本地工程验收 PASS：AI 作为默认首页，七页统一侧栏与马卡龙品牌色，真实任务/报告证据保留；35 Vitest、263 pytest、最终 10 Edge、28 视口组合、类型检查/构建通过。源码留原位；交付见 D:/codex产出/电商智能体_AI前端全面优化_20261103/交付。完整证据、失败重试与限制见 docs/ui-validation-results.md。

以下 D9 内容是历史快照。当前既有服务能力为 CONFIGURED_UNVERIFIED，与旧授权阻断状态不同；本次没有调用真实付费模型、修改配置或重新证明模型能力。原 D9、论文和最终用户验收状态不因 UI 完成而自动升级。

# D9 最终工程证据索引

工程READY_FOR_USER_ACCEPTANCE，实际模型BLOCKED_AUTHORIZATION。前序索引归档evidence/d9/D8_EVIDENCE_INDEX_ARCHIVE.md。

| 文件 | 证据 |
|---|---|
| docs/evidence/d9/verification.json | 最终测试/数据库SHA/计数/性能观察/失败与限制 |
| docs/evidence/d9/acceptance-matrix.json | F01—F16实际READY/BLOCKED，E01—E10 PASS |
| docs/evidence/d9/clean-all.stdout.txt | 干净环境263 pytest/28 Vitest/9 Edge/构建的实际输出 |
| docs/evidence/d9/clean-source-verification.json | 可执行源码逐字节、Python锁完全匹配、独立目录身份 |
| docs/evidence/d9/edge-final.json | 完整9项Edge原结果 |
| docs/evidence/d9/import-verification.json | 空库完整导入41项核对 |
| docs/evidence/d9/metrics-verification.json | 月度/参数/查询历史85项 |
| docs/evidence/d9/tools-verification.json | 八工具57HTTP/265独立断言 |
| docs/evidence/d9/agent-verification.json | 15个scripted任务/114恢复与预算断言，真实调用0 |
| docs/evidence/d9/default-verification.json | 默认8000/5173启动、B0生成、停服重启、GET无副作用23项 |
| docs/evidence/d9/default_report-verification.json | 默认端口生成报告92项独立SQL |
| docs/evidence/d9/browser_report-verification.json | 浏览器报表158项独立SQL |
| docs/evidence/d9/browser_monthly-verification.json | 浏览器月度21项独立SQL |
| docs/evidence/d9/security-browser.json | 跨源403、超限413、XSS无弹窗、报告不变 |
| docs/evidence/d9/openapi.json | 当前实际0.9.0接口schema |
| docs/evidence/d9/runtime-preparation.json | D8库复制与初始干净依赖/数据库状态 |

实际命令argv/退出码/原始输出位于D:/codex产出/电商智能体_D9最终工程交付/缓存/commands。浏览器目录缓存/playwright/2026-11-02T16-59-09-574Z-56368，含桌面/移动截图、trace、服务日志与独立库。首次Agent目录名重复导致200（脚本期望202）、首次metrics脚本缺导入路径均保留原失败，修复另建-final目录复测。未把失败改写为PASS。

所有原始命令、失败和最终结果随D盘交付封存，SOURCE_MANIFEST/DELIVERY_MANIFEST及git-receipt提供Git和逐文件SHA。真实模型没有授权，不能把scripted证据冒充实际供应商调用。
