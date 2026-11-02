# 下一次 Codex 的唯一接续入口（V1.5 FEATURE_FIRST）

1. 在当前项目根目录读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_START.md`、`docs/STATUS.json` 和 `docs/dev/DEVELOPMENT_ROADMAP.md`。
2. 先检查 Git、工作区现有代码和上一轮证据；运行 `python scripts/handoff_check.py`，但不把它当业务验收。
3. 依据 `docs/STATUS.json` 和 `docs/EVIDENCE_INDEX.md` 查找最后**实际通过**的步骤；首次为 D0。只读取 `docs/dev/steps/NN_*.md` 对应提示词及其引用的详细契约。
4. 继续该步骤需要的真实编码、运行与测试；完成后更新 STATUS、EVIDENCE_INDEX、KNOWN_ISSUES、DECISIONS 和本文件，并向用户提交证据。
5. 用户明确要求先实现全部业务功能，不写论文章节，不跑冻结批量学术实验。真实模型与外部收费调用需要单独授权。

当前状态（2026-11-02）：**D0 工程验证通过，READY_FOR_USER_ACCEPTANCE；用户验收尚未发生。停止扩展新功能。**

- 31 pytest、8 Vitest、2 真实 Edge 浏览器测试及迁移/构建通过；API/页面/数据库默认端口启动也已实测，自动验证服务已停止。
- 后端 `backend.app.main:app`，初始迁移 `0001_bootstrap`；`python scripts/manage.py backend`/`frontend` 启动，页面默认 127.0.0.1:5173，完整命令见 README。
- 项目已有 .venv、node_modules、锁文件与本地 .env，勿覆盖已有配置；.env 不进 Git，模型预算仍为 0。
- 缓存与 D0 工程空库：`D:\codex产出\电商智能体_D0工程初始化\缓存`；最终包与证据：同任务 `交付`。源代码在原工作区子目录 ecommerce-agent-thesis。
- Git 已 init，无 commit（SHA=null）；保留全部现有文件，先查 git status，再核对交付哈希和证据。后续本任务修复复用原归档目录。
- 4 个 npm 间接开发依赖 moderate 与 Starlette 测试弃用警告未隐藏，详见 KNOWN_ISSUES。当前无 D0 运行阻断。
- 真实经营数据未取得、未导入，模型未接入且无任何真实模型调用；论文/正式实验未开始。

**下一步编号 D1**：只有用户明确验收 D0 并授权进入 D1 后，读取 `docs/dev/steps/01_01_DATA.md`，按其契约获取官方 UCI 文件、核对真实 SHA、复跑独立审计并记录来源/字段/精度。不要因为 D0 完成而自行下载数据或开发 D2；不要执行正式学术实验。

如果用户仅反馈 D0 问题，则修复当前阶段并重复与改动相关的验证，不跳阶段。
