# Codex 本地工程约束 — ecommerce-agent-thesis（V1.5 FEATURE_FIRST）

本项目仅实施《基于 LangGraph 的电商经营数据分析智能体设计与实现》的软件系统，不包含获客项目。**用户要求先完成全部功能，论文正文与正式学术实验推迟到后续单独指令。**

1. 首先阅读 `CODEX_START.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md`，然后只读取当前阶段需要的契约。前序 V1.4 规格仍适用，开发顺序以 V1.5 为准。
2. 检查 Git、现有代码、依赖和系统环境；保护用户未提交的修改，不允许随意重置、删除或改写已有数据。
3. 先执行 `python scripts/handoff_check.py`，然后按 `docs/dev/steps/00_00_BOOTSTRAP.md` 真正编码，直到当前步骤通过；不要只交付新计划。每阶段验收后暂停，下一阶段由用户选定。
4. 真正的历史数据仅使用可追溯的来源；小型 fixture 必须标识。数据金额使用确定性精确计算，模型不能执行任意 SQL/Shell，不能根据历史参考值硬编码返回结果。
5. 未明确授权的付费模型请求、公网部署、生产店铺写操作及外发内容都禁止；真实密钥不得输出、提交或留在截图。
6. 每阶段执行测试并保存证据：实际命令、退出码、环境/依赖版本、Git SHA、数据SHA、截图/日志和失败原因。维护 `docs/STATUS.json`、`STATUS.md`、`DECISIONS.md`、`EVIDENCE_INDEX.md`、`KNOWN_ISSUES.md`、`NEXT_SESSION.md`。
7. `handoff_check=PASS` 仅代表交接包完整；业务、模型、用户验收独立评价。任何论文与正式冻结实验任务须等用户再次明确开启。
