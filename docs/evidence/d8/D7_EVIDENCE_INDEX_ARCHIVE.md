# D7 实际证据索引

D7离线工程验证PASS；真实模型BLOCKED_AUTHORIZATION。前序索引归档docs/evidence/d7/D6_EVIDENCE_INDEX_ARCHIVE.md，历史证据不改写。

| 文件 | 证据 |
|---|---|
| docs/evidence/d7/verification.json | 238 pytest、25 Vitest、8个最终浏览器用例及来源、库SHA/计数、失败记录 |
| docs/evidence/d7/pytest-final.xml | 最终238通过，failure/error/skipped均0 |
| docs/evidence/d7/edge-full-before-health-fix.json | 全量最后轮7过/1旧schema断言失败，保留原始结果 |
| docs/evidence/d7/edge-health-final.json | 修正旧schema后2项健康用例实际通过 |
| docs/evidence/d7/browser-report-sql.json | 真实浏览器捕获报告158项独立SQL/引用核对 |
| docs/evidence/d7/browser-monthly-sql.json | 真实浏览器月度结果21项独立核对 |
| docs/evidence/d7/runtime-report-sql.json | 默认运行库3个B0报表158项独立核对 |
| docs/evidence/d7/runtime-reports.json | 默认运行库B0创建、18次GET无新增模型尝试 |
| docs/evidence/d7/runtime-preparation.json | D6两库复制身份，D6原件保留 |

完整命令argv/退出码/stdout/stderr在D:/codex产出/电商智能体_D7报告五视图/缓存/commands；所有首次失败也保留。Playwright每轮在缓存/playwright的独立目录，含截图、trace、原始API、数据库与服务日志。最后完整轮2026-11-02T16-04-30-464Z-52924；健康复测2026-11-02T16-09-45-869Z-48192。Browser plugin not available，使用项目已安装Edge/Playwright。截图核查涵盖桌面1280×900和移动390×844，无整体水平溢出；无相关应用控制台错误（故意的后端停止/非法上传测试保留预期错误）。

D盘交付git-receipt/SOURCE_MANIFEST/DELIVERY_MANIFEST记录本地提交及逐文件哈希。源码ZIP排除.env、原ZIP/XLSX、数据库与依赖；运行数据另存。
