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
