# D8 实际证据索引

D8离线工程验证PASS，真实模型BLOCKED_AUTHORIZATION。前序索引保留在evidence/d8/D7_EVIDENCE_INDEX_ARCHIVE.md。

| 文件 | 实际证据 |
|---|---|
| docs/evidence/d8/verification.json | 测试数量、浏览器用例、数据库计数/SHA、依赖结果、失败说明 |
| docs/evidence/d8/pytest-final.xml | 263 passed，无失败/错误/跳过 |
| docs/evidence/d8/edge-final.json | 最终完整9 passed，前序失败保留于D盘 |
| docs/evidence/d8/security-browser.json | 真实Edge XSS无弹窗、跨源403、JSON413、报告不变 |
| docs/evidence/d8/agent-restart.json | 真实UCI+scripted provider的15任务/114断言；未知用量不记0 |
| docs/evidence/d8/browser-report-sql.json | 158项真实报表独立SQL核对 |
| docs/evidence/d8/browser-monthly-sql.json | 21项月度独立SQL核对 |
| docs/evidence/d8/python-audit.json | pip-audit对68项锁定依赖的原始结果 |
| docs/evidence/d8/source-audit.json | 来源哈希、55份不可变资料、零模型预算和配置密钥状态 |
| docs/evidence/d8/runtime-preparation.json | D7两库复制与原SHA |

完整命令argv/退出码/stdout/stderr：D:/codex产出/电商智能体_D8安全稳定/缓存/commands。最终浏览器目录缓存/playwright/2026-11-02T16-37-54-406Z-42432；首次失败目录2026-11-02T16-33-02-497Z-5356。截图、trace和服务日志均保留。首次定向10失败/8过、首次全量pytest262过/1失败、首次浏览器7过/1失败/1未执行未改写。

Python审计68项零已知漏洞；npm生产audit退出0，开发audit退出1的4项moderate不能误写成全零。source-audit当前未配置真实key，真实key扫描为N/A；假key脱敏由测试覆盖。封存交付提供git-receipt、SOURCE_MANIFEST、DELIVERY_MANIFEST。
