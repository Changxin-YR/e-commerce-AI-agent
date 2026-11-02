# Codex 施工提示词 06：D6 B1/B2 LangGraph 真实智能体

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D6 B1/B2 LangGraph 真实智能体**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`docs/plan/10_RUNTIME_CONTRACT.md`，`docs/plan/02_ECOMMERCE_SPEC.md`，`docs/plan/21_V14_DECISIONS.md`，`docs/dev/IMPLEMENTATION_CLARIFICATIONS.md`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 阅读已锁定 LangGraph 与模型提供方官方文档，创建可切换 provider 适配层；在没有合法授权与额度前，保持真实外呼关闭，先通过 fake-provider 工程测试。
2. 真实模型授权到位时，显式配置模型名、工具调用支持、请求/Token上限，先做5个开发冒烟：单月问数、多月比较、缺月份追问、不支持利润、可控工具错误。
3. B1必须是正常多轮工具循环；B2共享同一工具/输出/基础安全约束，增加条件校验、差额对账、关键数字引用核验和有限恢复。两者都保存每次尝试、tool_calls、真实用量或未知。
4. 构建持久 run_id/thread_id、SQLite checkpoint、WAITING_INPUT，实际测试同一run追问、重启后恢复、重复输入幂等、历史GET不增加请求；模型失败/额度耗尽/未知请求状态准确。
5. 不做90+10题正式批量学术实验；该阶段仅是功能开发和小规模冒烟。

**通过条件：** B1/B2的真实外部调用（已授权）分别通过关键场景、同run恢复成功且预算受控；没有授权时只能标代码工程PASS、真实模型BLOCKED。

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
