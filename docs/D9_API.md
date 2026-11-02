# API与配置说明

后端本机8000、前端同源代理5173，业务前缀/api/v1，/docs提供交互文档，/openapi.json为机器schema，实际OpenAPI随D9证据保存。

变更方法要求唯一可信Origin（配置的前后端localhost/127.0.0.1来源），所有HTTP要求唯一localhost Host。普通请求体最多64KiB/15秒；上传最多50MiB并分块接收。无公开认证/多租户。错误为`{"error":{"code":"...","message":"...","details":{}},"request_id":"..."}`。400输入错误、403来源拒绝、404不存在、409状态/版本/幂等冲突、413超限、415MIME、422参数、503库未就绪。

| 方法与路径 | 行为 |
|---|---|
| GET /healthz | 库/schema/project marker只读检查 |
| POST /api/v1/datasets/imports | multipart单file，ZIP/XLSX；新批次202、READY复用200 |
| GET /api/v1/datasets/imports/{batch_id} | 稳定批次/进度/失败历史 |
| GET /api/v1/datasets | 分页数据集 |
| GET /api/v1/datasets/{dataset_id} | 来源/SHA/版本/时间 |
| GET /api/v1/datasets/{dataset_id}/quality | 分类/质量/重复候选 |
| GET /api/v1/metric-definitions | 口径与限制 |
| GET /api/v1/datasets/{dataset_id}/metrics/monthly | month=YYYY-MM，可选country/stock_code |
| GET /api/v1/datasets/{dataset_id}/metrics/series | metric、date_from/date_to，可选筛选；结束不含 |
| POST /api/v1/datasets/{dataset_id}/queries | 显式保存查询、idempotency_key |
| GET /api/v1/datasets/{dataset_id}/queries | 查询列表 |
| GET /api/v1/queries/{query_id} | 已保存JSON只读 |
| GET /api/v1/tools | 八工具JSON schema |
| POST /api/v1/tools/{tool_name} | 参数化只读工具；仍需Origin |
| GET /api/v1/agent/capabilities | 授权/配置/执行器/预算/夹具状态 |
| POST /api/v1/runs | dataset_id、variant、question、idempotency_key，可选constraints；202新建/200复用 |
| GET /api/v1/runs、GET /api/v1/runs/{run_id} | 分页历史/已存状态/引用/用量，无执行副作用 |
| POST /api/v1/runs/{run_id}/input | revision、idempotency_key、answers，恢复同run |
| POST /api/v1/runs/{run_id}/resume | revision、idempotency_key，恢复QUEUED/INTERRUPTED |
| POST /api/v1/runs/{run_id}/rerun | revision、idempotency_key，新run/thread，保留parent |
| POST /api/v1/runs/{run_id}/cancel | 幂等登记取消 |
| POST /api/v1/reports | B0：dataset_id、query、idempotency_key，可选baseline；201新建/200复用 |
| GET /api/v1/reports、GET /api/v1/reports/{report_id} | 列表/详情，核对已保存引用，不重新计算交易 |
| GET /api/v1/reports/{report_id}/export | format=json或markdown，安全附件名；无CSV/HTML/Excel |

八工具为get_dataset_profile、get_metric_definitions、get_quality_summary、query_metric_series、rank_entities、compare_periods、decompose_change、inspect_transactions。排名/拆解top_k最多50，明细limit最多50，列表limit最多100；不接受SQL/Shell/模型指定路径。具体参数以GET/tools为准。

金额为字符串，例如`"1019687.622"`，不要转为JS Number后累计；两位展示由后端Decimal计算。raw_sha256/data_hash均指内部XLSX，ZIP容器SHA另记。引用包括tool_call_id/field_path、版本/过滤器/期间，不能只相信模型文本。

PowerShell示例，先用GET/datasets取得实际dataset_id：

```powershell
$originHeaders = @{ Origin = 'http://127.0.0.1:5173' }
$requestBody = @{
  dataset_id = '实际dataset_id'
  idempotency_key = [guid]::NewGuid().ToString('N')
  query = @{ metric='net_amount'; date_from='2011-09-01'; date_to='2011-10-01' }
} | ConvertTo-Json -Depth 6
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/reports' -Method Post -Headers $originHeaders -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($requestBody))
```

同幂等键/内容返回原结果，同键不同内容409。示例日期不是业务硬编码。attempt发送前持久占用预算，未知结果不能算零费用；请求/token限额不是已确认货币费用上限。实际付费调用需另行明确授权。
