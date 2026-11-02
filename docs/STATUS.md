# 电商智能体开发状态（V1.5 FEATURE_FIRST）

更新时间：2026-11-02T21:56:49.252368+08:00。

- **D3_READY_FOR_USER_ACCEPTANCE**：D0—D3 工程验证通过。本轮完成后停止，D4—D9 未开始。
- 真实源 541909 行完整保留，分类 POSITIVE 530104 / CANCELLATION 9288 / EXCLUDED_OTHER 2517 / INVALID 0。官方 ZIP/XLSX 哈希与既有版本一致；两份独立审计复跑无统计差异。
- 月度/序列指标从 SQLite 整数千分英镑聚合，9/10 月四项核心指标与独立 OOXML 参考、独立 SQL 全部一致。三位精确字符串和两位 ROUND_HALF_UP 显示值分别输出。
- 实现数据集列表、月度与月序列、指标定义、三项受限工具、显式 POST 保存查询和只读历史 GET。仅 READY 数据参与指标；NO_DATA / EMPTY_RESULT / PARTIAL_PERIOD / 非法参数区分处理。
- 158 pytest（D3 42 项）、8 Vitest、2 Edge 健康回归、TypeScript/Vite 构建、87 项真实 HTTP/SQL 核对通过。另有真实 Edge 打开保存 JSON 并刷新测试；业务历史页面留待 D4，不能宣称前端业务链完成。
- 迁移 `0003_query_history`，当前 .env 使用 D3 缓存/runtime/app.sqlite3；从 D2 库复制迁移，D2 封存库保留。两次真实验收显式保存共 2 份查询；GET、刷新和重启读取数据库 SHA 不变。服务已停止。
- 修复回归发现的 Windows 初始锁文件竞争；首次 pytest 父缓存目录缺失和随后竞争失败日志均保留。最终 pytest 无警告，Edge 颜色环境提示仍有记录。
- Git D2 基线 `49c2bbd403fffd571926c9ca3329ded77fcdba0a`；D3 SHA 与文件清单在 `D:/codex产出/电商智能体_D3精确指标API/交付/git-receipt.json`。仅本地提交、无推送。
- 4 项既有 npm moderate 为开发依赖遗留，本轮未升级或重跑 audit；生产 audit=0 是 D0/D1 证据。模型调用 0，论文、正式实验与人工 gold 未开始。

完整接口使用见 docs/D3_METRICS.md，交付见 docs/D3_DELIVERY.md，命令和失败记录见 docs/EVIDENCE_INDEX.md。
