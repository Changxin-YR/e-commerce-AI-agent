# 来源登记与后续文献工作

V1.0规划核验日期：2026-10-29；V1.1增补核验日期：2026-10-31。第1—4节保留原核验记录，第5节列本次新增访问和实测证据。以下为一手项目、数据或官方说明，及已经核对元数据/摘要的学术文献入口。当前没有逐仓库部署验证、完整代码审计或正式模型实验。执行时记录实际访问时间和固定 commit/依赖版本；不能把网页有 README 当作系统已验证成熟。

## 1. 技术与开源参考

| ID | 一手来源 | 本方案的使用方式 | 后续执行要求 |
|---|---|---|---|
| T01 | [LangGraph GitHub](https://github.com/langchain-ai/langgraph)；[官方概览](https://docs.langchain.com/oss/python/langgraph/overview) | 两篇的共同编排基础，组合确定性代码和模型步骤 | 安装兼容版本并锁定；按官方 API 实现，记录实际版本 |
| T02 | [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | 需要保存状态/人工输入时参考 | 按实际版本选择最小用法，不为框架功能扩大范围 |
| T03 | [Shopify merchant 示例](https://github.com/Shopify/claude-for-commerce-examples/blob/main/merchant/README.md) | 参考商家工具接口、真实/模拟后端及执行边界；本方案不用其写店功能 | 该目录说明无商家 Web UI；不是直接可交付的本科业务系统，复用代码前检查文件许可 |
| T04 | [OpenOutFind](https://github.com/eracle/OpenOutFind) | 参考候选发现、匹配及导出的业务拆分 | 仓库标注 GPL-3.0；当前数据服务依赖按实际 README 核实，默认不整套复制或依赖付费客户源 |
| T05 | [Twenty AI agents](https://docs.twenty.com/user-guide/ai/capabilities/ai-agents) | 对象、记录和流程设计的可选阅读 | 不整套部署改造，不作为论文运行依赖 |
| T06 | [Shopify development stores](https://shopify.dev/docs/apps/build/stores/development-stores) | 说明开发店和测试数据的适用边界 | 本首版不需要店铺账号；将来接口测试与真实经营评估分开 |

这些来源支持技术设计参考。它们不能替本论文证明准确率、业务收益或原创贡献，也不能替代我们实际实现与验证。

## 2. 数据来源

| ID | 来源 | 已核实内容 | 本方案要求 |
|---|---|---|---|
| D01 | [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)；[数据 DOI](https://doi.org/10.24432/C5BW33) | 页面列 541,909 条记录、2010-12-01 至 2011-12-09、单价 GBP、CC BY 4.0 | 从官方入口下载；实际审计缺失、取消和精度；清洗与指标另行定义 |
| D02 | [Wikidata 数据访问](https://www.wikidata.org/wiki/Wikidata:Data_access) | 官方列出 SPARQL、实体/API 等访问方式 | 保存实际成功查询与响应；小范围取数、限速和版本记录 |
| D03 | [Wikidata 许可](https://www.wikidata.org/wiki/Wikidata:Licensing) | 结构化数据 CC0；其他命名空间文本有独立许可 | 只把对应结构化企业数据按 CC0 使用，不外推为官网全文许可 |
| D04 | [P856 官网属性](https://www.wikidata.org/wiki/Property:P856) | 当前或历史官方网站 URL 属性 | 核查身份、跳转和可用性，过时地址不能直接当当前官网 |
| D05 | [P452 行业属性](https://www.wikidata.org/wiki/Property:P452) | 企业相关行业属性 | 作为抽样元数据，不能作为人工匹配标签 |
| D06 | [Wikidata Query Service](https://query.wikidata.org/) | 官方查询入口 | 查询服务和后端可能变化，执行时核实实际可用接口并保存查询 |

推荐数据引用：Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 。按学校指定格式转换，不能将数据提交年份与原交易年份混淆。

企业官网引用在实际采集后逐条加入来源清单，不能预先生成未访问的链接和片段。官网资料的来源、时间与材料范围会影响标签，论文必须说明这一点。

## 3. 学术文献起点

| ID | 文献与原始入口 | 已核验范围 | 可用于什么 |
|---|---|---|---|
| A01 | Yao, S., et al. *ReAct: Synergizing Reasoning and Acting in Language Models*. [arXiv:2210.03629](https://arxiv.org/abs/2210.03629) | 作者、题名、摘要、预印本 2022，页面注明 ICLR 2023 定稿版本 | 工具交互与 Agent 研究背景；后续读原文再引用方法细节 |
| A02 | Liu, X., et al. *AgentBench: Evaluating LLMs as Agents*. [arXiv:2308.03688](https://arxiv.org/abs/2308.03688) | 作者、题名、摘要、预印本 2023，页面注明发表于 ICLR 2024 | Agent 任务评价与失败分析背景；不是本系统准确率的来源 |

这两条是文献检索起点，不能充当完整本科论文参考文献表。Codex 后续围绕各自研究问题检索：电商交易分析与数据问答、工具调用与可靠性、企业实体匹配/线索筛选、信息抽取与有依据生成、选择性预测与人工复核。按学院要求确定文献数量和中文/外文比例。

每篇文献登记作者、完整题名、年份、渠道、DOI/URL、访问日期、实际读到的范围、支持本论文的具体论点。没有读全文时不能写虚构页码、实验设定或数值；核验失败的条目不进入正式参考文献。

## 4. 开源复用记录模板

每份复制或改编代码记录：`source_url, source_commit, source_file, license, original_function, reused_lines_or_modules, modifications, new_contribution, disclosure_location`。只把作为依赖使用的框架登记为依赖，不夸大为自身实现；两篇使用的相同通用代码在两边均披露。

## 5. V1.1新增核验与实测

以下在2026-10-31实际读取或执行，来源事实与本项目设计建议分别记录：

| ID | 来源 | 核验内容 |
|---|---|---|
| R01 | [UCI官方ZIP](https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip)及[D01页面](https://archive.ics.uci.edu/dataset/352/online+retail) | 实际下载并审计原始XLSX，得到缺失、精度、时间及月度参考；见09和evidence，不是仅摘录网页 |
| R02 | [SQLite类型](https://www.sqlite.org/datatype3.html) | NUMERIC可采用INTEGER/REAL存储，不能仅靠类型声明保证Decimal精度 |
| R03 | [LangGraph持久化](https://docs.langchain.com/oss/python/langgraph/persistence) | 内存checkpointer重启丢失；本地可选SQLite实现 |
| R04 | [LangGraph中断](https://docs.langchain.com/oss/python/langgraph/interrupts) | 恢复时重新进入中断所在节点，需处理重入与幂等 |
| R05 | [LangGraph历史执行](https://docs.langchain.com/oss/python/langgraph/use-time-travel) | replay会再次执行后续节点，不能作为普通历史详情读取 |
| R06 | [LangChain结构化输出](https://docs.langchain.com/oss/python/langchain/structured-output) | ToolStrategy的handle_errors默认存在自动处理；实现时明确策略与预算 |
| R07 | [FastAPI后台任务](https://fastapi.tiangolo.com/tutorial/background-tasks/) | 响应后执行任务；10的持久化恢复是本项目应用设计 |
| R08 | [SQLite WAL](https://www.sqlite.org/wal.html) | 运行库版本、单写入者和官方修复说明，安装时据实际版本核查 |
| R09 | [Wikidata P856](https://www.wikidata.org/wiki/Property:P856)、[访问说明](https://www.wikidata.org/wiki/Wikidata:Data_access)、[WDQS手册](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual/en) | 官网可为历史地址，查询有限时/限流；实际端点与查询需在用户环境成功执行留证 |
| R10 | [Beckhoff条目](https://www.wikidata.org/wiki/Q16746790)与[企业官网](https://www.beckhoff.com/en-en/company/) | 只读核查一条真实名称/官网/业务资料链；未完成人工gold，也未完成12家或批量采集 |

获取网页不等于完成项目接口验收。本次WDQS参数化接口在受限执行网络中未完成联通验证，不能据此断言官方服务失效。UCI的实际审计与文档检查可以继续推进，状态详见08/09。
