# D7 报告与五项功能视图

本阶段在已有数据导入、月度概览与查询历史上增加智能分析、报告详情、任务/实验记录。保留查询历史入口，因此导航有六个入口，覆盖契约要求的五项功能。正式学术实验继续延期，任务页不展示虚构成绩。

## 确定性报表 B0

在“智能分析”选择起始日期、结束日期（不含）、排名与比较指标、可选国家/商品过滤器，点击“生成确定性报表”。B0 不使用模型、不占用模型预算。报告保存四项月度指标、国家和交易条目 Top 10、其他项与全量合计的工具证据；填写基期后增加期间比较，以及可加金额的国家变化拆解。有效发票数不作跨实体可加拆解。日期仍采用源本地日期，金额保持精确字符串。

可选基期缺数据时报告为 PARTIAL_RESULT，不能以本期正常数据掩盖未完成比较。NO_DATA 不产生零金额主张；EMPTY_RESULT 表示有源期间但筛选没有命中；PARTIAL_PERIOD 显示已观测范围和警告。排名、其他项、占比、差额与详细覆盖在完整工具证据中可查看。

API 创建：`POST /api/v1/reports`，请求为 `dataset_id`、`idempotency_key`、`query`（SeriesParams）和可选 `baseline`（date_from/date_to）。首次 201，相同内容与提交键 200，不同内容复用键 409。查询后通过单一数据库事务保存 run、tool calls 和 report；同一键并发可重复执行只读计算，但不会重复保存任务/报告，也不调用模型。

## B1/B2 与任务交互

已有 `/api/v1/runs` 接口连接前端。无授权时明确显示 BLOCKED_AUTHORIZATION 并禁用真实模型提交；B0 与历史读取可用。脚本 provider 只能在隔离测试应用中通过代码注入，页面和报告明确显示“测试夹具，非真实模型能力”，不通过生产配置自动打开。

任务页面支持等待/运行/补答/中断/失败/取消状态；显示提供方、模型、阶段、关联父任务、总历时（含等待）、请求、token、未知用量及工具尝试。补答携带当前 revision 与提交键，网络响应丢失时同一答复重用键；重复创建也保留相同键。终态重跑创建新 run/thread 与 parent_run_id；B0 重跑使用确定性服务。恢复仍执行 D6 的配置/代码/数据版本兼容检查。

## 历史与导出

`GET /api/v1/reports?limit=20&offset=0` 返回分页列表。`GET /api/v1/reports/{report_id}` 返回保存报告、工具证据和内容哈希。`GET /api/v1/reports/{report_id}/export?format=json|markdown` 导出 JSON 或纯文本 Markdown；固定生成文件名，不接受任意导出路径。不提供 CSV/Excel 或 HTML 导出。

报告关键数值逐项通过保存的 tool_call_id/field_path 重新解析，核对值、单位（新报告）、快照、版本、期间与过滤器；引用缺失或不一致拒绝展示/导出，不自动改写历史。内容 SHA-256 指向数据库中原始保存的 content，JSON 外层还有只读的证据及展示元数据。D6 旧报告不改写；缺少的新展示字段只从已保存 run 数据派生，因此旧报告不具备新报告全部来源展示字段。

JSON 保持原数值字符串，Markdown 转义 HTML/Markdown 元字符。Vue 默认文本插值，不执行模型文本或商品描述中的 HTML。报告中的模型说明仍标记需人工复核；程序引用校验不等于真实模型能力验证，也不构成商业因果证据。

浏览器 URL 保存 `view=reports&report=...` 或 `view=tasks&run=...`。刷新/回看/导出只发 GET，不创建新任务、重算统计或触发模型。列表每页 20 条，上限 100；原交易行不整体传给前端。

## 本地操作

在已激活虚拟环境的两个 PowerShell 窗口分别执行 `python scripts/manage.py backend` 和 `python scripts/manage.py frontend`，以 Ctrl+C 停止各自服务，`python scripts/manage.py doctor` 检查环境与端口。现有 `.env` 指向 D7 缓存/runtime 的业务库与同目录 checkpoint；D6 原库保留。交付中的“运行数据”提供两库配套备份，清理任务缓存前先保留备份。

浏览器验证使用已安装 Edge/Playwright。Browser plugin not available。主链路：官方文件上传/复用 → 分析 → 报告 → 下载 → 重启后历史；脚本夹具链路：B2 追问 → 服务重启 → 同 run 补答 → 引用真实 UCI 数值的报告。后者只证明工程交互，真实模型链路仍受授权阻断。
