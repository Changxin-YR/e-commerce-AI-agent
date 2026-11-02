# Codex 施工提示词 09：D9 全功能验收与最终工程交付

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D9 全功能验收与最终工程交付**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`docs/dev/FEATURE_ACCEPTANCE.md`，`docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`，`docs/plan/16_SECURITY_AND_PRIVACY.md`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 对照 `docs/dev/FEATURE_ACCEPTANCE.md` 的F01—F16逐项跑实际功能演示，记录READY/BLOCKED与证据；不得凭代码存在自动判PASS。
2. 再次执行原始文件hash/导入分类/月度金额/八工具/五视图/模型B1/B2/追问恢复/报告导出/历史GET/E01-E10和主要安全测试。
3. 从干净的依赖和迁移起点跑一次Windows本地安装/初始化/启动/停止/浏览器操作的复现流程（在当前环境具备Windows时），记录软件实际版本、配置与命令。
4. 修订 README、接口说明、安装手册、用户操作步骤与演示脚本，保留真实测试和开发日志；只生成工程材料，绝不写论文正文或伪造正式实验统计。
5. 检查Git差异/许可证/数据来源及密钥/大文件排除，完成最终工程交接报告；用户尚未确认之前最多标READY_FOR_USER_ACCEPTANCE。

**通过条件：** F01—F16均有真实证据或明确BLOCKED，未有严重遗留；用户实际确认后才能标USER_ACCEPTED。**论文和正式大规模学术实验继续延期。**

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
