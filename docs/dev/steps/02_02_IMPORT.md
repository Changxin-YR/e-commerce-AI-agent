# Codex 施工提示词 02：D2 数据库、批量导入与幂等

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D2 数据库、批量导入与幂等**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`，`docs/dev/IMPLEMENTATION_CLARIFICATIONS.md`，`docs/plan/16_SECURITY_AND_PRIVACY.md`，`docs/plan/fixtures/ecommerce_contract_cases.json`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 使用 SQLAlchemy 和 Alembic 实现 DatasetSnapshot、ImportBatch、TransactionRow、QualityIssue 及最小 AnalysisRun/Report 关联表，设置唯一键和主要筛选索引；按 `docs/dev/IMPLEMENTATION_CLARIFICATIONS.md` 定义 workbook 与容器哈希。
2. 实现受限 ZIP/XLSX 文件上传或 CLI 导入、后台状态查询、批量/流式解析与写入；检查文件体积、Zip成员、压缩比例、扩展名/实际内容及目录穿越风险；失败不把半导入快照设 READY。
3. 严格落实 4 类互斥行分类、价格 0.001 GBP 精度、客户缺失不误删、原始重复行不误删、品质问题重叠统计；保留可追踪来源。
4. 对官方 ZIP 及其内部相同 XLSX 的不同上传，实现 workbook哈希 + transform版本幂等，不使金额加倍；重复导入返回稳定状态。
5. 完成 API 上传/质量查询与 CLI，并用有标记的边界 fixture 和真实原始文件分别测试；记录实测行数、耗时与异常处理。

**通过条件：** 541909 行真实导入并对账，分类为 530104/9288/2517/0（只针对已审计原文件），ZIP/XLSX重复导入无翻倍；失败状态和安全负例可测。

## 本轮共同约束

- 只修改 `ecommerce-agent-thesis` 当前工作区；先检查 Git/未提交改动；不得删除用户既有内容。
- 当前是 **FEATURE_FIRST** 模式：**不写论文正文，不跑正式冻结大规模学术实验**；开发测试、事实来源和运行证据需要如实保存。
- 只用真实已经取得的历史数据做业务验收；允许标记为 `test_fixture` 的少量测试数据做单元测试，禁止冒充真实经营结果。
- 未经用户明确授权的付费模型调用、生产平台写入、公网部署和外发消息一律不执行。
- 遇到资源阻断时，记录 `BLOCKED` 与具体阻碍，不替换为虚假 PASS；可以继续本阶段独立的工作。
- 每完成一段就实测；记录命令/退出码/错误/证据路径与 Git SHA，更新 STATUS.json、STATUS.md、EVIDENCE_INDEX、KNOWN_ISSUES、DECISIONS、NEXT_SESSION。
- 本轮完成后提交**仅该阶段**的代码、测试与问题报告，不擅自宣布全系统完成；是否进入下一阶段由用户决定。

## 最终汇报格式

1. 本阶段实际完成的代码/接口/页面、Git改动或 commit SHA。
2. 实测命令和退出码、通过/失败/阻断的用例、证据文件位置。
3. 数据和模型的**真实**状态（未取得=未取得，未运行=未运行）。
4. 更新后的 docs 状态与存在的风险，以及**下一步编号**，不提前跳过阶段门槛。

**现在执行本轮任务，提交真实代码和验证记录，不要只输出实现方案。**
