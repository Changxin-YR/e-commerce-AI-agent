# D3 指标与查询历史使用说明

当前版本 `0.3.0`，数据库迁移 `0003_query_history`，口径 `retail-v1.2`。仅分析 READY 快照。数据集元数据列表/详情仍可展示非 READY 状态，质量/指标/工具 profile 返回 409。`data_hash` 始终是 XLSX SHA。

| 方法/路径 | 作用 |
|---|---|
| GET /healthz | 校验真实连接、表、版本和项目标记 |
| GET /api/v1/datasets?limit=20&offset=0 | 按采集时间和ID稳定排序，最多100条 |
| GET /api/v1/datasets/{id} | 元数据、币种、源日期、版本 |
| GET /api/v1/datasets/{id}/quality | 完整质量报告 |
| GET /api/v1/metric-definitions | 四项公式、包含/排除与显示规则；可重复 metric_names 参数选择 |
| GET /api/v1/datasets/{id}/metrics/monthly?month=2011-09 | 月度四项指标、互斥分类和覆盖状态 |
| GET /api/v1/datasets/{id}/metrics/series | metric、date_from、date_to 必填，granularity仅month；最多36桶 |
| POST /api/v1/datasets/{id}/queries | 保存服务端计算结果；新记录201，同键同参数200，异参数409 |
| GET /api/v1/datasets/{id}/queries | 分页历史摘要 |
| GET /api/v1/queries/{query_id} | 原保存JSON，不重新执行查询；SHA错误409 |

月度/序列仅允许 `country`、`stock_code` 筛选，严格字面匹配，不去空格/改大小写；不支持额外字段、空字符串、重复标量、自由SQL/路径/URL参数。指标仅为 positive_amount / cancellation_amount / net_amount / positive_invoice_count。不支持指标422 UNSUPPORTED_METRIC，其余参数错误422 VALIDATION_ERROR；不存在404 NOT_FOUND；非READY409 DATASET_NOT_READY；数据库未就绪/不可用503。错误统一 ErrorResponse，OpenAPI 取实际服务 `/openapi.json`。

期间为源时间的 `[开始日期00:00,结束日期00:00)`，date_to排除，不转UTC或北京时间。覆盖使用源首末交易的日界 `[2010-12-01,2011-12-10)`，明确标记 basis=observed_source_day_bounds；首日08:26之前不误判为整月缺失，但观测日界并不证明中间每日都有业务。

| 结果状态（HTTP200） | 含义与数值 |
|---|---|
| PASS | 源期间有记录、筛选有匹配、完整月覆盖 |
| NO_DATA | 原期间没有任何源行，包括完全越界和内部缺月；金额和发票数为null |
| EMPTY_RESULT | 原期间有源行，但合法筛选没有匹配；金额为"0.000"、发票0 |
| PARTIAL_PERIOD | 有匹配但源日期覆盖不全或请求截断月份；返回已观测金额并附警告 |

空筛选优先 EMPTY_RESULT，但保留 coverage 和部分覆盖警告；序列不把缺月补成零收入。source_row_count 是该期间未筛选源行数，matched_row_count 是筛选后所有行数。四类互斥计数合计 matched_row_count；质量标签允许交叉，不参与该加总。有效发票为每期间 POSITIVE 内不同InvoiceNo；不同月份的去重发票数不可直接当全区间唯一发票数。

SQLite SUM 只加整数千分英镑。取消类按负行金额的绝对值，净额为正向减取消；金额字段 exact固定三位字符串，display用服务端 Decimal ROUND_HALF_UP 固定两位，显示负零归零。原行级0.001仍保留，最后汇总再显示舍入，不逐行舍入后相加。前端应原样展示字符串。

缺客户号、重复候选与符合条件的费用条目保留；不称商品专属GMV/财务收入/退款实付。跨月发票会产生 INVOICES_SPAN_MONTHS 提示。query_fingerprint包含数据哈希、版本、期间和筛选，便于追溯。

显式保存例子（后端已启动）：

```powershell
$base = 'http://127.0.0.1:8000'
$dataset = 'ds_9561855056bc9d83ca5a82c198b5130b'
$payload = @{ idempotency_key = 'manual-september-001'; query = @{ kind = 'monthly'; month = '2011-09' } } | ConvertTo-Json -Depth 4
$saved = Invoke-RestMethod "$base/api/v1/datasets/$dataset/queries" -Method Post -Headers @{Origin=$base} -ContentType 'application/json' -Body $payload
Invoke-RestMethod "$base/api/v1/queries/$($saved.query_id)"
```

保存序列时 query 使用 kind=series、metric、date_from/date_to，以及可选筛选。普通月度/序列 GET 不保存；历史 GET 验证已有结果SHA并直接返回。唯一提交键+BEGIN IMMEDIATE防并发双存；重复提交先查已保存结果，不重新计算。历史保留 workbook/transform/metric 版本。没有模型SDK或调用入口。

三项内部工具在 backend/app/metrics/tools.py：execute_tool(service,name,arguments)；tool_schemas() 返回受限JSON Schema。profile只接受dataset_id，definitions只接受metric_names，series接受dataset_id和上述受限期间参数。结果包含tool_call_id、snapshot_hash、metric_version、filter、period、完整result与warnings；definitions为无数据集的版本化定义，snapshot_hash为null。D3只提供内部Python入口，未连接模型或实现后续五工具；GET不持久化工具调用。

复跑（项目根PowerShell；替换为未使用的新目录名，同一次运行的证据目录不可重用）：

```powershell
python scripts/manage.py migrate
.venv/Scripts/python.exe scripts/run_independent_audits.py --source data/raw/Online_Retail.xlsx --output 'D:/codex产出/电商智能体_D3精确指标API/缓存/independent-rerun-001'
python scripts/manage.py verify-metrics --database 'D:/codex产出/电商智能体_D3精确指标API/缓存/runtime/app.sqlite3' --output 'D:/codex产出/电商智能体_D3精确指标API/缓存/real-rerun-001' --reference 'D:/codex产出/电商智能体_D3精确指标API/缓存/independent-rerun-001/audit_normalization_and_reference.json' --browser
```

verify-metrics 要求现有真实READY库，不自动创建/导入。缺库/空库/损坏明确失败并保存本次FAIL证据。校验真实原始哈希、独立审计和独立SQL、实际HTTP结果，重复上传ZIP/XLSX验证幂等，并测试损坏/50MiB超限上传。它显式新增一份查询历史，提交键含输出目录末级名称，因此每次使用不同末级目录名；会启动/停止自己的随机端口后端。--browser使用本机Edge打开真实历史JSON并刷新，不证明Vue业务页面已完成。raw文件不复制出data/raw；其他证据与浏览器临时缓存都在D3任务目录。

当前库由D2副本迁移，旧库与旧证据保留。模型、报告/运行管理与D4业务页面仍未开始。运行数据备份不包含在源码ZIP中。
