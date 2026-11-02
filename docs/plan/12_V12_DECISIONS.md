> V1.3 项目独立包说明：本文件继承 V1.2 的双论文背景材料，本最终交接包只负责当前项目；另一论文的业务内容与文件名仅作历史背景，**不可在当前工程实现**。\n\n# V1.2 决策基线、冲突处理与开工门槛

版本：2026-11-01；状态：**开发交接资料已准备，应用尚未实施**。

## 1. 文档效力

1. 学校正式任务书、学术规范与用户对项目范围的明确决定优先于本包的建议；有冲突先登记，不自行假称学校已批准。
2. 具体工程决策按：本文件与 `13_ECOMMERCE_BUILD_CONTRACT.md`/`15_EVALUATION_FREEZE_CONTRACT.md`/`16_SECURITY_AND_PRIVACY.md` → `10_RUNTIME_CONTRACT.md` → 对应 `02/03_*_SPEC.md` → `04_EXPERIMENT_PROTOCOL.md` → `11_FIRST_SLICES.md` → `00_MASTER_PLAN.md`。实验伦理、真实数据、禁止伪造和权限限制属于不可被覆盖的共同底线。
3. 若 V1.2 与 V1.1 在同一字段、状态或接口上不一致，以 V1.2 的显式契约为准；Codex 必须把冲突写入 `docs/DECISIONS.md`，实际实现统一一种口径，不能两套并存。
4. V1.1 的 `evidence/` 是历史快照和真实审计结果，**不得修改其结论后仍沿用原 SHA-256 或宣称复跑通过**。审计在另一环境完成，用户 Windows 项目中的再次执行状态仍为 `NOT_STARTED`。

## 2. 已冻结的产品范围

| 属性 | 电商 | 获客 |
|---|---|---|
| 标题 | 基于 LangGraph 的电商经营数据分析智能体设计与实现 | 基于 LangGraph 的 B2B 客户线索研究与匹配智能体设计与实现 |
| 主要实体 | 历史交易明细、数据集版本、指标、分析任务 | 公开企业候选、官网快照、业务条件、证据、人工标签 |
| 初始数据 | UCI Online Retail 真正的历史表 | Wikidata 真实候选+对应企业网页材料 |
| 首片 | 无模型：导入→精确月度聚合→Web 查询 | 无模型：候选→身份核对→快照→证据定位→人工标注入口 |
| 后续模型能力 | 受限工具选择、问数、澄清、核验 | 结构化抽取、匹配、证据校验、需审路由 |
| 明确排除 | 平台真实写入、自动定价、退款、库存、利润 | 发信、私信、电话、个人邮箱推断、自动获客转化 |

独立 Git 工作树、SQLite、锁文件、数据、实验和论文。允许复制并注明出处的基础公共代码，不引入需要同时升级两个系统的共享可变 Python 包。两个项目无需统一部署。

## 3. 开发栈的实际决策

- Python >=3.11；Node 使用当前仍受支持的稳定 LTS（优先现有已安装且受支持的版本）。首次 `doctor` 记录精确版本，再验证 FastAPI、Pydantic v2、SQLAlchemy 2、LangGraph、checkpoint 的兼容关系并锁定；不填写未经真实安装的具体包版本。
- Vue 3 + TypeScript + Vite；SQLite 本地数据库；FastAPI；LangGraph 图。Windows PowerShell 为主文档环境，所有执行器命令使用相对项目根目录的路径。
- 模型供应商**待用户实际配置**。在未确认兼容 Tool Calling、结构化输出、用量字段和错误行为前，不假定某个所谓 OpenAI-compatible API 等同官方接口能力。只做兼容性冒烟和必要适配，真实模型验证状态独立。
- 后端绑定 `127.0.0.1`；电商默认 8000/5173，获客默认 8001/5174。若冲突，记录实际端口并更新前端配置。首版单用户本地演示，禁止 `0.0.0.0`、公网暴露、默认开放的文件管理接口。
- 应用任务运行使用数据库持久化、单执行器与 SQLite checkpoint；不依赖 Celery/Redis。只有数据库写入明确成功后才对用户返回已接收。

## 4. 状态字段不再混用

- **开发阶段** `NOT_STARTED | IN_PROGRESS | PASS | FAIL | BLOCKED | NOT_APPLICABLE`。
- **业务运行** `QUEUED | RUNNING | WAITING_INPUT | INTERRUPTED | PASS | FAIL | CANCELLED`，`PASS` 表示运行结束且得到合法结果，不是论文“实验通过”或企业“符合客户画像”。
- **正式实验单次** `NOT_RUN | PASS | FAIL | BLOCKED`，实验整体另计已尝试数/有效输出数/失败数/未运行数；`BLOCKED` 表示未执行且有确切前置阻碍，非模型预测为 false。
- **获客预测类别** `match | non_match | insufficient_evidence | null(运行失败)`；**复核动作** `accept | reject | review_required`（失败时 `review_required` 并保留 `error_code`）。**采集状态**、D1 三枚举和标签分别存在，不能互相覆盖。
- **论文格式**、**人类审核**、**模型验证**各自设置阻碍，不因为页面可以打开就标整项 PASS。

## 5. 种子预算与行动权限

- **默认真实模型支出授权：0。** 没有用户提供的模型凭据和可用额度、或未明确使用已有授权额度时，不自动请求收费接口。只完成无模型任务/模拟器分支测试，模型步骤标 BLOCKED，不以 mock 结果冒充实测。
- 若用户本地配置凭据，则仅以用户确认的 `MODEL_MAX_REQUESTS_PER_RUN`、`MODEL_MAX_TOTAL_REQUESTS`、`MODEL_MAX_TOTAL_TOKENS`、`MODEL_MAX_TOTAL_COST`（如供应商价格无法核实，费用阈值不得当作唯一保护）作为硬上限。无总额度配置时只允许**一次经用户授权的兼容性冒烟**，不能开启正式批量运行。
- 互联网访问仅限已允许的公开数据源与获确认的企业域名、公共文档；不得注册新付费服务或批量外联。对采集限制尊重 robots、条款和响应限流，不规避验证码或登录控制。
- 允许正常的可逆代码编辑、创建数据库、运行测试。涉及删除既有数据、覆盖历史研究记录、变更 ICP 定义、付费/外发/公网部署，先做不依赖这些行动的工作并提出具体阻碍。

## 6. 真实开发的开工判断

“**交接材料 READY**”仅表示：Codex 读到足够明确的输入、第一轮任务、接口/状态约定、验收脚本和阻碍策略。**“业务系统 READY”目前为 NOT_STARTED。** 两者不可互相替代。

Codex 第一轮必须实际执行：环境探测、依赖安装、源数据可用性检查、最小数据库与 API、前端功能、自动测试、实际页面核验；留下完整命令、退出码、样例输出、证据路径和 Git commit，或者对不能运行的步骤真实标 BLOCKED/FAIL。禁止凭规划文档标记代码 PASS。

## 7. 外部约束（核查日期 2026-11-01）

- UCI 数据及 CC BY 4.0：https://archive.ics.uci.edu/dataset/352/online+retail
- Wikimedia 2026 API 速率：https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- Wikidata SPARQL 服务限制：https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual
- LangGraph 持久化与中断：https://docs.langchain.com/oss/python/langgraph/persistence 和 https://docs.langchain.com/oss/python/langgraph/interrupts
- OWASP URL 抓取安全：https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

注意：这些是外部官方说明；本包约定的本地并发、预算、实体、流程是产品设计，不是假称来源发布了这些值。
