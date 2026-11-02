# 下一次接续入口：D1 已完成，等待验收

1. 先读 AGENTS.md、DEV_FIRST.md、CODEX_BRIEF.md、docs/STATUS.json、docs/EVIDENCE_INDEX.md 和实际 Git 状态。
2. 当前 D1 工程验证 PASS、READY_FOR_USER_ACCEPTANCE。用户若只继续收尾或反馈 D1 问题，修复 D1；**未明确验收并授权 D2 时不得数据库导入**。
3. D0 基线 `0740bf439c37dc344885d2f7c26568c157dd9571`；D1 最终提交在 `D:/codex产出/电商智能体_D1真实数据审计/交付/git-receipt.json`。原始 ZIP/XLSX 仅在项目 data/raw，未提交、未打入源码交付 ZIP。
4. 官方原始数据已取得并通过 SHA 与独立审计。先运行 `python scripts/download_source_data.py --verify-zip data/raw/online_retail_uci352.zip`，对照 data/manifest.json；文件不存在不能凭旧 JSON 当成功。
5. D1 可复跑脚本为 scripts/audit_source_data.py、scripts/run_independent_audits.py、scripts/verify_d1_evidence.py；命令见 docs/D2_DATA_INPUT.md。每次使用新的 D 盘缓存目录，保留旧结果。
6. 实测 541909 行、8 字段，分类 530104/9288/2517/0；4 条 0.001 保留，重复候选 5268 保留。两份历史脚本复跑无实质差异，33 交叉检查、70 pytest 通过。旧 D0 的 8 Vitest/2 Edge 证据已核查；本轮没有重新声称执行前端/浏览器测试。
7. 4 个间接开发依赖 moderate 仍 OPEN；生产 audit=0。Starlette/httpx 弃用已通过增加 httpx2 安全消除。详情见 docs/D0_CLOSEOUT.md。
8. 用户明确允许 D2 后再读 docs/dev/steps/02_02_IMPORT.md 与 docs/D2_DATA_INPUT.md，实施真实导入、交易表、幂等和失败恢复。D1 审计函数是独立参考，不直接充当生产指标实现。

继续使用当前工作区 .venv/node_modules/.env；模型预算仍为 0。额外交付与本任务缓存复用 `D:/codex产出/电商智能体_D1真实数据审计`；D2 若作为新任务建立对应新目录。论文及正式冻结实验继续延期。
