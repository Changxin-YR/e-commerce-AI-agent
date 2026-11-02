> **最新优先级：** 用户已要求先实现全部软件功能、不写论文正文。请先读 `DEV_FIRST.md`、`docs/dev/DEVELOPMENT_ROADMAP.md` 与本阶段 `docs/dev/steps/NN_*.md`；历史文档的论文/正式实验步骤暂缓。

# V1.4 电商项目开发文档索引（按需加载）

**优先读：** 根目录 `CODEX_START.md` + `CODEX_BRIEF.md`。交接资料就绪不代表应用/实验就绪。

| 任务 | 读哪些规范 | 目的 |
|---|---|---|
| 开工/第一次真实数据切片 | `21_V14_DECISIONS.md`, `13_ECOMMERCE_BUILD_CONTRACT.md`, `11_FIRST_SLICES.md`, `09_DATA_PREFLIGHT.md` | 当次必须的文件/金额/REST/测试 |
| 模型/澄清/历史 | `10_RUNTIME_CONTRACT.md`, `02_ECOMMERCE_SPEC.md` | SqliteSaver、单线程任务恢复、八工具 |
| 安全/上传 | `16_SECURITY_AND_PRIVACY.md` | 电商适用的 S04—S10、S12；不适用项 N/A |
| 正式实验/论文 | `15_EVALUATION_FREEZE_CONTRACT.md`, `04_EXPERIMENT_PROTOCOL.md`, `07_SOURCE_REGISTER.md` | B0/B1/B2、抽查、冻结和参考文献 |
| 历史依据（不默认全读） | `00_MASTER_PLAN.md`, `01_SHARED_RULES.md`, `08_REVIEW_AND_CHANGES.md`, `12_V12_DECISIONS.md`, `20_V12_GAP_AUDIT.md` | 保留决策溯源；忽略与本项目无关的获客内容 |

优先级和争议处理在 `21_V14_DECISIONS.md`。`fixtures/` 只用于软件测试；`evidence/` 是历史独立审计，不代表 Codex 用户机器已运行或本项目已完成人工复核。
