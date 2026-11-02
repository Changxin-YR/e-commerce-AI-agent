# D6 智能体与运行接口

实际依赖：LangGraph 1.2.19、checkpoint-sqlite 3.1.3、checkpoint 4.3.1，完整版本见requirements.lock；本机Python3.12.15/SQLite3.53.1。官方文档抓取哈希见evidence/d6/official-docs-manifest.json；原文在D盘缓存/official-docs。核实interrupt所在节点恢复会重新进入、thread_id固定和SqliteSaver同步持久化。严格MsgPack/JSON模块白名单为空、pickle关闭；图只保存普通JSON数据。SQLite WAL使用本机已含WAL-reset修复的运行库。

API：GET /api/v1/agent/capabilities；POST/GET /api/v1/runs；GET /api/v1/runs/{id}；POST .../input、resume、rerun、cancel。创建包含dataset_id、B1/B2、question、idempotency_key，可选constraints为严格SeriesParams。补答包含revision、idempotency_key、answers，字段须精确匹配pending_input.fields。旧revision/不同内容复用提交键返回409。rerun创建新run/thread并记录parent_run_id。

图：model→tools→model多轮，模型输出结构化action/message/claims；review后进入独立clarify中断节点或finalize。B1保留正常工具循环与公共类型/引用/权限/预算保护。B2增加显式用户条件匹配、期间差额、排名合计、拆解余项和跨工具对账，以及数字引用/无依据因果文本拒绝；最多2次业务修复，仍计入共同预算。自然语言含义及无法机械核验的解释仍需真实模型和人工验收；没有宣称通用语义核验。

报告数值由保存的tool_call_id和field_path解析，金额维持三位字符串。B1保留model_value但展示值由工具确定；B2额外拒绝model_value不符。无数据不生成零金额；部分期间保留工具警告；模型说明标MODEL_COMMENTARY_REQUIRES_HUMAN_REVIEW。D7继续实现公开报告与导出页面。

独占OS租约配单线程执行器；任务先入库再调度。重启RUNNING变INTERRUPTED，WAITING_INPUT和QUEUED保留，未主动发送新请求。所有恢复检查代码/提示词/配置哈希和数据版本。SQLite checkpoint另存同目录，durability=sync。报告run_id唯一、工具run/step/position唯一、提交run/key唯一，已成功模型步骤可复用保存响应。进程中断窗口不承诺外部调用exactly-once。

预算入口在发送前持久化RESERVED→SENT，记录请求哈希、提供方/模型、来源及token占用；成功后按真实返回用量调整占用。缺少usage或中断保留null与完整占用，不写零。每任务和全项目额度同时限制，重启/重跑不清零。SDK/HTTP自动重试均为0；未知结果只能由显式恢复触发新attempt并继续占额度。费用始终null，未核实计费。

DeepSeek HTTPS适配器仅允许https://api.deepseek.com，无重定向/代理和任意URL；模型ID需要用户配置并实际验证。默认ALLOW_PAID_MODEL_CALLS=false、总请求/token及任务token为0；无授权创建任务会留下明确FAIL/BLOCKED_AUTHORIZATION且0attempt。已设置key本身不等于授权。禁用外部LangSmith tracing。ScriptedProvider只能通过app_env=test的代码注入，不能从公开API或.env开启，其使用量标test_fixture_no_network。

本阶段测试为开发工程验证，没有真实外部模型调用，没有正式学术实验或人工gold。
