# Codex 施工提示词 03：D3 精确指标与只读 REST API

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D3 精确指标与只读 REST API**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`，`docs/plan/09_DATA_PREFLIGHT.md`，`docs/dev/IMPLEMENTATION_CLARIFICATIONS.md`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 实现 `/api/v1/datasets/{dataset_id}`、`/quality`、`/metrics/monthly?month=YYYY-MM` 和 `/healthz`，固定日期范围、精确字符串与报错码；其余工具按阶段至少实现 profile/metric_definitions/query_metric_series。
2. 查询只读取 READY 快照；确切区分无数据、合法空结果、部分月份和不支持字段；单价与金额不用二进制float参与真值聚合。
3. 用数据库真实聚合输出2011-09/10金额和正向发票数，使用独立审计脚本对账而非返回常量；验证时间左闭右开与月份缺失处理。
4. 运行 E01—E09，补充重复导入、0.001单价、2011-12部分覆盖、非法筛选、质量标签等测试；OpenAPI须与真实路由一致。
5. 已保存的只读查询历史经刷新仍可读取，不触发新导入或模型操作。

**通过条件：** 9/10 月四类指标与独立参考逐项完全一致；已实现API和错误/空状态实测；新加回归测试真实通过。

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
