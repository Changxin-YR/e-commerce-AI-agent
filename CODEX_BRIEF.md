> **V1.5 当前指令：功能优先**。本文件保留原 V1.4 需求与未来研究规则，但当前一切开发顺序、论文延后和功能验收以 `DEV_FIRST.md`、`CODEX_START.md`、`docs/dev/DEVELOPMENT_ROADMAP.md` 为准。E4-E6 研究/论文阶段暂不执行；工程日志与模型冒烟仍需真实记录。

# CODEX_BRIEF.md — 电商智能体本科论文开发短契约（V1.4）

> **开工必读。** 本文件是约定的快速入口，不取代详细合同。这里只讲电商，不执行获客研究；文档与审计脚本不代表业务代码已经完成。

## 1. 研究目标与不可变边界

题目：《基于 LangGraph 的电商经营数据分析智能体设计与实现》。一个本地单用户 Web 系统，将**真实 UCI 历史交易明细**导入 SQLite，对自然语言经营问题完成**条件澄清→白名单工具调用→精确计算→结果/引用核验→报告与历史保存**。

主要研究问题：在相同模型、数据、工具与预算约束下，增强 B2 的显式条件检查、跨工具一致性与有限修复，是否比正常的基础 B1 多轮工具 Agent 更可靠？额外耗费多少时间、请求与 token？有负面结果也如实写论文。

明确不做：淘宝/抖店生产账号接入；实时店铺、利润、广告 ROAS、实际退款与成本原因推理；自动修改价格、支付、库存、营销发送、生产平台写操作；多租户、分布式部署。未来产品愿景不是本论文验收范围。

## 2. 选型与成果

Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、SQLite；Vue 3+TS+Vite；LangGraph；一个经实际验证支持 tools 的模型。初期 Windows/PowerShell、127.0.0.1、本地单执行器，不使用 Redis/Celery/云服务器。实际版本现场验证后固定；不事先杜撰依赖版本。

最终功能：数据集导入和质量、经营概览、智能分析（含缺参追问）、报告详情、任务/实验记录，共 **5 个功能视图**；允许用 3 个路由+Tab/抽屉组合，不能减少功能。8 个受限工具：`get_dataset_profile`、`get_metric_definitions`、`get_quality_summary`、`query_metric_series`、`rank_entities`、`compare_periods`、`decompose_change`、`inspect_transactions`。按先后开发，不需第一阶段写完 8 个。

测试底线：pytest 关键计算/导入/API；必要的 Vitest 数值显示与交互；**2—3 个自动化浏览器关键流程**（或记录环境阻碍和真实人工浏览器验证，未执行项不能写 PASS）。安全仅测实际存在的输入/攻击面；电商不做任意 URL 抓取，获客 SSRF 项为 N/A，但上传 ZIP/XLSX、公式注入、SQL 注入、密钥和 localhost Origin 保护不能丢。

## 3. 真实数据与金额（不得自行改口径）

来源：[UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)，ZIP 已审计 SHA256 `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`，XLSX SHA256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。**Codex 自己的 Windows 环境必须再下载/核对；不符则新建审计版本，不得套用旧 reference。** 原文件不包含在包中。先运行 `python scripts/download_source_data.py --download`，失败可用官方页面手动下载再 `--verify-zip/--verify-xlsx`。

已审计基线：`541909=530104(POSITIVE)+9288(CANCELLATION)+2517(EXCLUDED_OTHER)+0(INVALID)`；价格存在 `0.001 GBP`。保留来源原值与疑似重复行；按经审计的 0.001 精度网格正则化，计算和 SQLite 聚合用整数千分英镑，不用 float/SQLite REAL 求和；API 传三位精度**字符串**。不把费用条目说成纯商品 GMV 或财务收入。C 前缀且正数量不归正向或取消，必须在其他类并保留原因。

开发对账：2011-09 正向 `1058590.172`、取消 `38902.550`、净额 `1019687.622`、正向发票 `1837`；2011-10 正向 `1154979.300`、取消 `84274.630`、净额 `1070704.670`、正向发票 `2040`。这些是**开发参考值**，绝不可硬编码成业务 API 或当人审完成的论文 gold。

## 4. 六个阶段，按可验证切片推进

- **E0 环境与数据**：保护原工作区，doctor 记录 Python/Node/SQLite/端口；实际取得真实源文件，原始 SHA 与审计脚本复跑；无源文件时只标数据阻断，继续建模块。
- **E-S1 第一个必须跑通的垂直切片**：项目骨架、SQLAlchemy/Alembic、幂等导入（同 XLSX 内容的 ZIP 与裸文件不得双入）、质量统计、`GET /healthz`、`POST /api/v1/datasets/imports`、月度 API、一个真实 Vue 页面、独立对账、E01—E10。页面展示真实结果和数据状态；先实现 profile、metric_definitions、query_metric_series 三工具。
- **E-S2 最小真正的 Agent**：引入 `rank_entities`、`compare_periods` 两个工具（凑齐 5 个可用工具）；真实 provider 冒烟，通过后实现同模型同工具的 B1 与 B2；完成一次**同一 run 的缺参追问→暂停→回复→继续**，报告附结构化 tool evidence。模型 Key 缺失时，离线开发先走完，真实效果标 BLOCKED。
- **E3 补全功能**：加 `get_quality_summary`、`decompose_change`、`inspect_transactions` 达到八工具；其余四个功能视图可合并为 Tab；完成最小历史只读、任务持久化和异常测试。实现 SQLite checkpointer，恢复节点副作用幂等，防重复报告。**不做外部调用 exactly-once 保证。**
- **E4 研究准备**：30 条开发题、90 条主测试题和 10 条故障题；采用独立 SQL/Decimal 参考答案，严格 dev/test 隔离和固定澄清用户答复。本人真实抽查至少 20% 并记录，可请第二人辅助，但不得把本人抽查说成“独立双人盲审”。修复评分器的边界条件并冻结数据、代码、模型、提示词、预算。
- **E5/E6 实验+论文**：B0 固定统计模板；B1 **正常可多轮调用工具**；B2 增强校验和有界恢复。B1/B2 同模型/输入/工具/上限，分别 3 次，故障集单报。分析准确率、完整成功、澄清、超时、额外成本；最终提交六章论文、真实结果、复现材料、源码、5—10 分钟答辩演示。**不删 B1，不先写成绩。**

## 5. 模型/预算独立门槛

无 Key 或未获授权时 `ALLOW_PAID_MODEL_CALLS=false`、总请求/token上限=0，严禁真实付费调用。实际供应商和模型 ID 在 E-S2 冻结之前确定；先核实 tool-calling、输出格式、错误、token 用量。官方候选可以参考 [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)，**不要沿用未经核验的“V3/GLM4”固定版本名或猜测一次任务费用**。先用少量开发题得到真实平均请求数、token、已确认单位价格，再估算 90×2×3 的主实验成本，额外故障运行单列。

额外请求、自动重试、工具内模型调用必须通过统一预算入口。调用未得到结果时记录 UNKNOWN，不写零消耗。不自行充值、开户、联网推送或在日志输出 API Key。

## 6. 运行状态：只保留必要真实可靠性

接口对外统一 `/api/v1`，健康 `/healthz`。任务最少存 `run_id`、`thread_id`、`status`、`phase`、`input`、`checkpoint` 引用、结果/错误、时间和模型尝试。允许一个本地执行器；`GET` 历史只读。缺参时 `WAITING_INPUT`，重启后仍可补答；重复答复、重复导入、报告保存必须幂等。其余细化见 `10_RUNTIME_CONTRACT.md`，不要求自己发明分布式调度、完整审计网关或复杂微服务。

## 7. 每轮运行证据与停止条件

每个切片真实执行命令和退出码，保存数据文件哈希、pytest/Vitest/浏览器结果、日志、必要截图与 Git SHA；阶段状态在 `docs/STATUS.json`（主）和 `docs/STATUS.md`（同步）中更新，同时维护 `docs/EVIDENCE_INDEX.md`、`docs/KNOWN_ISSUES.md`、`docs/NEXT_SESSION.md`。`handoff_check=PASS` 只说明文档完整，不能标为业务完成。

若源文件无法取得，标 BLOCKED_DATA；无模型 Key，标 BLOCKED_CREDENTIALS；无人工复核，标 REVIEW_REQUIRED。其他不依赖该资源的功能继续。遇到学校模板与实际数据约束再根据真实输入调整；未经用户授权不能擅自删掉核心研究比较或谎称验收通过。

**详约索引**：数据/端点 `docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`；首片 `11_FIRST_SLICES.md`；运行 `10_RUNTIME_CONTRACT.md`；实验 `15_EVALUATION_FREEZE_CONTRACT.md`；安全 `16_SECURITY_AND_PRIVACY.md`；完整功能 `02_ECOMMERCE_SPEC.md`。如有冲突，以 `docs/plan/21_V14_DECISIONS.md` 为该项目的新版本执行级澄清，严格的数据真实性、学术规范和权限边界始终最高。
