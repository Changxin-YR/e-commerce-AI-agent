# Codex 施工提示词 00：D0 工程环境与可运行骨架

你是本地 Windows 工程项目 `ecommerce-agent-thesis` 的执行开发代理。此次只实施 **D0 工程环境与可运行骨架**，不扩大范围、不开始后续阶段、**暂不写论文或运行正式学术实验**。

先读取 `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md` 及 `docs/dev/DEVELOPMENT_ROADMAP.md`；当次专属资料：`AGENTS.md`，`DEV_FIRST.md`，`CODEX_BRIEF.md`，`docs/dev/DEVELOPMENT_ROADMAP.md`，`docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`，`docs/plan/16_SECURITY_AND_PRIVACY.md`。先检查当前代码和 Git 状态，不覆盖已有真实进度。不要一次性把历史所有 plan 文档注入提示上下文。

## 本次必须实际实施的代码与检查

1. 先运行交接检查，记录 Python/Node/npm/Git/SQLite 版本、现有工作区、端口占用和依赖/网络权限；不要把这份 Linux/ChatGPT 环境的信息当作用户 Windows 结果。
2. 创建真实可运行的 FastAPI/Pydantic/SQLAlchemy 2/Alembic 后端工程，实现 `GET /healthz`、统一异常包装、数据库连接及首个迁移基线。优先最简可维护布局，Windows 环境优先。
3. 初始化 Vue 3+TypeScript+Vite 前端工程，至少有一个实际调用 `/healthz` 的连接状态页面，禁用模拟成功展示；设置 localhost 开发代理。
4. 创建/实现 `python scripts/manage.py doctor`、`python scripts/manage.py backend`、`python scripts/manage.py test --scope smoke` 等第一批实际入口（其余未实现的命令明确报 `NOT_IMPLEMENTED`，不能假装存在），补充 README 中经运行验证的命令。
5. 锁定实际安装的 Python/Node 依赖，不盲目升级；写入 `.env.example` 的必要字段，密钥永不输出。
6. 给 health、数据库初始化和基本前端构建创建真实自动化测试，执行命令并保存退出码。

**通过条件：** 后端 `/healthz` 真实返回，前端真实连接后端，Alembic可建初始数据库，smoke测试与前端构建执行成功。**不要求已导入54万行；不标 E-S1 整体通过。**

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
