# V1.2 电商开发合同：数据、数据库、接口、验收与施工顺序

版本：2026-11-01。此文**是在 V1.1 的 `02_ECOMMERCE_SPEC.md` 上增加执行细节**，不代表应用已运行。

## 1. 第一轮（E-S1）的明确终点

一名用户在本地页面选择 UCI 官方历史文件（也可经 CLI 导入），后端导入 SQLite 并显示数据质量；选择 2011-09/2011-10 查询正向交易行金额、取消类金额、净交易金额、有效发票数和统计口径；刷新页面后仍能查看结果。无模型密钥必须可完成。

不要先建立完整管理后台、8 个工具、模型多节点流程，再到最后才检查导入。按 `E0→E1→E-S1→E-S2→其余功能→实验`；E-S1 只要求 3 个初始工具，其余在 E2/E3 扩展。真实导入时需防止 54 万行引起请求阻塞，提供查询状态或后台单任务处理；不要把 50 万行一次作为 API JSON 传给浏览器。

## 2. 数据主键与不可变来源

- 官方源数据：`https://archive.ics.uci.edu/dataset/352/online+retail`。实测核对基线见 `09_DATA_PREFLIGHT.md`；ZIP SHA256 `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`，XLSX SHA256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。实际下载与本地脚本必须再次核验；不符时记录来源变动并停止对旧回归值强制断言。
- `DatasetSnapshot(dataset_id, raw_sha256, schema_version, metric_version, source_url, acquired_at, source_time_min, source_time_max, row_count, status)`；`ImportBatch(batch_id, dataset_id, submitted_file_sha256, workbook_sha256, transform_version, status, row_count, imported_at, error)`；`TransactionRow(id, dataset_id, source_row_num, invoice_no, stock_code, description, quantity, invoice_date_source, customer_id, country, unit_price_raw, unit_price_milli_gbp, line_amount_milli_gbp, primary_class, quality_flags)`。同一数据集 `(dataset_id, source_row_num)` 唯一；对 XLSX 原内容计算 `workbook_sha256`，同一 workbook+变换版本只能有一份生效导入。若先上传官方 ZIP、之后上传从该 ZIP 解出的 XLSX，虽然容器 SHA 不同，内层 workbook SHA 相同，必须复用原数据快照，防止双计。保存原始上传容器 SHA 与内层 XLSX SHA 两者。不得根据全字段相等对原始行去重。
- `QualityIssue(id, dataset_id, row_ref, issue_code)`；`AnalysisRun`、`ToolCall`、`Report`、`ExperimentCase`、`ExperimentRun`、`ReviewRecord` 与 V1.1 契约对应。历史信息只追加或用版本引用；正式测试后不能覆盖冻结快照、参考答案和运行记录。
- 源文件 ZIP/XLSX 与字节哈希、字段字典和规范化版本都入库留档；读取 raw 时不得静默更改表格格式、日期时区、科学计数或缺失表示。`CustomerID` 是标识符，不当作连续数值计算或无凭据补齐。

## 3. 价格、行分类与互斥对账

这个规则仅适用于当前已审计 UCI 快照。原始单价原样保留，按实际审计证明的阈值：若与 0.001 GBP 网格的距离 `<=1E-9 GBP` 则规范化为 3 位小数，转换为整数千分英镑；若超过阈值，停止这一已冻结导入规则并显式报错，不能擅自四舍五入。不允许用 binary float 参与金额精确参考对账。

定义按下列**优先级的互斥主分类**（质量标签可重叠）：

1. `INVALID`：必要字段（InvoiceNo、StockCode、Quantity、InvoiceDate、UnitPrice）无法按明确字典解析，或规范化阈值失败。保留源行、保存逐行原因，阻止把无法确定月份的记录用于时间指标。
2. `POSITIVE`：InvoiceNo 不以 C/c 开头；Quantity > 0 且规范化 UnitPrice > 0。
3. `CANCELLATION`：InvoiceNo 以 C/c 开头；Quantity < 0 且规范化 UnitPrice > 0。
4. `EXCLUDED_OTHER`：其他所有可解析行（零价、非 C 负数量、负单价等），保留详情与原因。**包括 InvoiceNo 以 C/c 开头但 Quantity >=0 的可解析行（即使单价>0）；该类不得计入 POSITIVE/CANCELLATION。** 对 C 前缀+正数量等边界必须保留质量原因，不能因历史原文件中这一组合行数为 0 而省略代码分支。

对每个 snapshot，`raw_row_count = INVALID + POSITIVE + CANCELLATION + EXCLUDED_OTHER`。已审计基线为 `541909 = 0 + 530104 + 9288 + 2517`（仅在该原文件及冻结规则下，其他来源不可套用）。单项 `quality_flags` 计数允许重叠，不可把缺客户号、零价、重复候选相加当成排除数。

运费、手工调整、银行收费等符合 POSITIVE/CANCELLATION 的行仍被包含；因此指标使用“交易行金额”而非“商品 GMV、财务收入、退款实付”。这不是未经验证的商品分类。

`line_amount_milli_gbp = quantity * unit_price_milli_gbp`，正向金额和取消绝对值在整数千分单位累计，净金额 `positive_sum - cancellation_abs_sum`。整数运算前防止过大数量溢出数据库 64 位；本快照已验证范围，未来上传超范围拒绝而不是溢出。API 以**字符串**返回精确 GBP 小数（固定三位表示，如 `"1019687.622"`），前端仅展示层将金额 `ROUND_HALF_UP` 为两位，避免 JS Number 转换改变精确值。

时间遵循源文件本地时刻、时区未明确：月份窗口 `[YYYY-MM-01 00:00, next_month 00:00)`；不要当 UTC 或北京时间转化。按行的 InvoiceDate 归月，订单计数是该月 `POSITIVE` 中不同 `InvoiceNo` 的数量；如果未来快照出现同一发票跨月，必须在质量报告提示它可被多个期间计入，不得默默“修正”发票标识。对于当前文件，审计已记录同一发票不同时间戳但未跨月。

## 4. 已测回归对账（不是正式 gold）

| 月份 | 正向金额 GBP（三位） | 取消类 GBP（三位） | 净额 GBP（三位） | 有效发票数 |
|---|---:|---:|---:|---:|
| 2011-09 | 1058590.172 | 38902.550 | 1019687.622 | 1837 |
| 2011-10 | 1154979.300 | 84274.630 | 1070704.670 | 2040 |

两个净额差 `51017.048` GBP。已复算的正向行数分别为 49261、59304，取消类分别为 805、1200。**V1.1 证据脚本是独立的开发参考，不得把其数值说成所有人审完成的正式标注真值。** `verify-metrics` 必须按项目数据库真实运行并与独立审计脚本结果逐项对比，不得给出硬编码常量作为接口结果。

## 5. 最小 REST 契约：固定路径和语义

路径前缀 `/api/v1`；FastAPI OpenAPI 必须与实现一致。认证首版仅 localhost 单用户，文件上传限制见安全协议。所有错误响应为 `{ "error": { "code": "...", "message": "...", "details": {} }, "request_id": "..." }`，禁用未审查的异常栈回传。

| 方法与路径 | 请求 / 响应要点 | 幂等 / 失败 |
|---|---|---|
| `GET /healthz` | 服务、SQLite状态及版本摘要；不泄露敏感路径 | 无副作用 |
| `POST /api/v1/datasets/imports` | multipart 单文件或受限官方ZIP，返回 `batch_id, dataset_id, status, raw_sha256` | 相同文件或 ZIP 内相同 XLSX 内容返回原批次，不重复入库；不合法文件400/413/422 |
| `GET /api/v1/datasets/{dataset_id}` | 元数据、来源、范围、币种、版本 | 404时真实响应 |
| `GET /api/v1/datasets/{dataset_id}/quality` | 互斥行计数、重叠质量标签、警告 | 导入中返回清楚状态，不造成功值 |
| `GET /api/v1/datasets/{dataset_id}/metrics/monthly?month=2011-09` | 精确字符串、显示值、有效发票数、有效行数、排除数、`metric_version`、`data_hash`、`warnings` | 月份不合法422，无数据返回 `NO_DATA` 而非0收入；不完整月份标 `PARTIAL_PERIOD` |
| `GET /api/v1/reports/{report_id}` | 保存报告及其 tool refs | 纯读取，不启动新模型 |
| `/api/v1/runs` 相关路径 | `POST /api/v1/runs`、`GET /api/v1/runs/{run_id}`、`POST /api/v1/runs/{run_id}/input` 等，详见 `10_RUNTIME_CONTRACT.md` | 提交键、版本和恢复约束 |

建议月度结果样例（只是 schema 示范，不是 API 已运行记录）：

```json
{
  "dataset_id": "uci-online-retail:<actual_sha256>",
  "month": "2011-09",
  "currency": "GBP",
  "metric_version": "retail-v1.2",
  "positive_amount_exact": "1058590.172",
  "cancellation_amount_exact": "38902.550",
  "net_amount_exact": "1019687.622",
  "positive_invoice_count": 1837,
  "positive_row_count": 49261,
  "cancel_row_count": 805,
  "warnings": [],
  "status": "PASS"
}
```

`actual_sha256` 由真实导入计算、不可直接复制占位符返回。金额同一字段所有响应格式统一，时间范围与查询参数都要写入证据引用。

## 6. 后续完整工具与分析端

实现原 `02_ECOMMERCE_SPEC.md` 的八个受限工具。模型无任意 SQL、文件系统、Shell 或 URL 访问权；白名单工具的 JSON schema 明确字段、允许操作及最大返回行数。工具输出附 `tool_call_id, snapshot_hash, metric_version, filter, period, exact_values, warnings`。展示的关键数字必须从已存工具值派生，不允许模型自由写数后无校验当真。

B1/B2 都有完整多轮工具调用，受同一通用约束；B2 增加显式条件检查、跨工具汇总核对、关键数字核验和有限修复，差异需要在代码和运行记录中可观察。澄清题使用持久 `WAITING_INPUT`，固定用户回复脚本适用于批量实验；重启、重复提交和历史只读按 `10` 实测。

## 7. 具体门禁测试（第一轮必须运行，不要求实验已完成）

| 编号 | 断言 |
|---|---|
| E01 | 原始行、互斥分类及文件哈希可复核；无真实文件则 `BLOCKED_DATA` |
| E02 | 再传同一字节，或将相同 XLSX 用 ZIP 与裸文件分别上传，复用原数据快照、金额不翻倍 |
| E03 | 2011-09/10 两月精确指标与本文件独立参考完全一致；展示两位小数另测 |
| E04 | 四个 0.001 单价记录均保留，整数千分价=1 |
| E05 | 2011-12 明确 PARTIAL_PERIOD，数据范围之外不会冒用其他月份 |
| E06 | 抽查至少一条负价格、非C负数量、零价和重复候选，行分类正确、质量标签可交叉 |
| E07 | API 禁止自由 SQL、不合法筛选、任意文件路径与非本地公开访问 |
| E08 | 浏览器刷新仍能查询已保存真实结果；历史页面不产生新模型请求 |
| E09 | 对导入损坏 ZIP/超限文件返回明确错误，不崩进程或覆盖旧快照 |
| E10 | 自动测试、实际浏览器操作、命令退出码、数据哈希和截图证据在 `docs/EVIDENCE_INDEX.md` 可定位 |

如果首轮成功，接着扩展其余指标、图表、LangGraph、完整页面和实验。不要以 E-S1 通过宣称 E0—E6 全部通过。
