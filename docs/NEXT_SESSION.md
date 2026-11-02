# 下一次接续入口：D2 已完成，等待验收

1. 读取 AGENTS.md、DEV_FIRST.md、CODEX_BRIEF.md、docs/STATUS.json、docs/EVIDENCE_INDEX.md 与实际 Git 状态。当前 D2_READY_FOR_USER_ACCEPTANCE；不要自动进入 D3。
2. D1 基线 `bf92c1f5672f0ecbc05169215c5274d3ebdd7d39`，D2 最终 SHA 与文件清单见 D:/codex产出/电商智能体_D2数据库导入/交付/git-receipt.json。未推送远程。
3. 官方 ZIP/XLSX 仍仅在项目 data/raw；data/manifest.json 保存两个 SHA。D2 已真正导入 541909 行，分类 530104/9288/2517/0，对照 D1 无统计差异。
4. .env 已切换 D2 运行库 D:/codex产出/电商智能体_D2数据库导入/缓存/runtime/app.sqlite3，原 D0 库保留。交付/运行数据/app.sqlite3 是封存备份；不要随意清理当前运行库。服务验证后已停止。
5. 先参阅 docs/D2_IMPORT.md。manage migrate/import-data 可运行；POST /api/v1/datasets/imports、GET 批次/profile/quality 已实现。raw_sha256/data_hash 指 XLSX，ZIP/bare XLSX 复用稳定数据集与批次 ID。
6. 当前 116 pytest、8 Vitest、2 Edge、构建和 41 项真实 SQL/HTTP 核对通过。原始 HTTP 导入约 116 秒，随后实际重复上传/CLI 和服务重启验证通过。docs/evidence/d2 与 D 盘缓存保存真实证据，后续复跑使用新目录。
7. 当前只支持已审计 workbook 哈希。未知版本须先重新审计；不公开 fixture 允许列表。失败快照不能提供完整质量或指标；重试同文件清理该失败快照的部分行并保留失败历史。模型预算仍为 0。
8. 收到用户明确授权 D3 后，再读 docs/dev/steps/03_03_METRICS.md（以实际目录为准）、生产指标契约及 D2 输入说明，基于 READY 数据集实现确定性指标。D2 独立 SQL 核对不是 D3 API，不要硬编码参考金额。

D3—D9、论文和正式实验仍未开始。前端本轮只调整健康状态兼容并回归；导入页面未实现，也未声称浏览器完成了导入交互。
