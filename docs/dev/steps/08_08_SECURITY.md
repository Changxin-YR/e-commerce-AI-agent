# Codex 施工提示词 08：D8 安全、可靠性、自动化端到端

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D8 安全、可靠性、自动化端到端**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`docs/plan/16_SECURITY_AND_PRIVACY.md`，`docs/plan/10_RUNTIME_CONTRACT.md`，`docs/plan/fixtures/security_inputs.json`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 按已实现攻击面测试：ZIP/XML解压与路径、上传大小、无效日期/筛选/参数化SQL、XSS、CSV公式注入、localhost Host/Origin与CSRF、模型密钥泄漏、未授权收费调用、历史GET副作用、预算越界。
2. 至少实现2—3条真正运行的Playwright E2E（真实导入概览、精确月度+刷新、AI缺参追问+恢复）；暂无模型授权的相关E2E标BLOCKED，不能让fake模型结果冒充真实外部调用。
3. 测试后端重启、状态/检查点存储、重复上传、重复用户答复、对账和异常日志；性能上确认54万行不会一次吐给前端。
4. 做必要的重构和问题修复，统一测试命令与CI可选，不加生产云部署/分布式架构。

**通过条件：** 实际安全与E2E证据可追溯，所有严重阻断缺陷修复复测，残留问题明确记录。

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
