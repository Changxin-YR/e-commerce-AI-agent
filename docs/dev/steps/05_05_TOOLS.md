# Codex 施工提示词 05：D5 全八业务白名单工具

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D5 全八业务白名单工具**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`docs/plan/02_ECOMMERCE_SPEC.md`，`docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`，`docs/dev/IMPLEMENTATION_CLARIFICATIONS.md`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 完整实现8个工具：get_dataset_profile、get_metric_definitions、get_quality_summary、query_metric_series、rank_entities、compare_periods、decompose_change、inspect_transactions。
2. 所有工具复用确定性服务层，JSON Schema/Pydantic校验参数；限制可用过滤字段、时间区间、排序方式、top_k和明细limit≤50，严禁任意SQL、shell、路径访问。
3. 工具返回结构化数值字符串、dataset/snapshot hash、metric_version、tool_call_id、期间、过滤条件、warnings、明确错误码。
4. 期间差额、百分比零基期、排名并列规则、商品/国家拆解之和与总差额对账；无数据或未知字段拒绝假结果。
5. 将工具作为 B0 确定性报表的服务能力，编写单元/API/真实数据回归；不需要模型Key。

**通过条件：** 每个工具均有实际真实数据调用和非法参数/边界测试，八工具返回可追溯一致。

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
