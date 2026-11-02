# D2 导入与恢复使用说明

本阶段提供数据库、真实 ZIP/XLSX 导入、批次状态与质量 API。经营指标 API、工具和数据页面属于后续阶段。数据仅接受 D1 已审计工作簿，未知哈希返回 `WORKBOOK_VERSION_REQUIRES_AUDIT`，需要先进行新版本审计；HTTP/CLI 没有跳过哈希的选项。

## 本机运行

在项目根目录执行，管理脚本会使用 `.venv`：

```powershell
python scripts/manage.py migrate
python scripts/manage.py import-data 'data/raw/online_retail_uci352.zip'
python scripts/manage.py import-data 'data/raw/Online_Retail.xlsx'
python scripts/manage.py backend
```

导入成功退出 0；缺文件、损坏、未知版本、导入失败或尚未 READY 退出 1。重复传入同一工作簿返回同一批次/数据集。CLI 可加 `--database <已迁移数据库>`、`--output <结果JSON>`。生产 CLI 不接受 fixture 哈希。

当前 `.env` 指向 `D:/codex产出/电商智能体_D2数据库导入/缓存/runtime/app.sqlite3`；D0 数据库保留。上传临时文件在同任务 `缓存/imports`，原始容器和 XLSX 内容寻址副本仍只在项目 `data/raw`。`.env`、数据库、依赖和原始文件均不入 Git。请保留运行数据库；交付目录另存数据库备份，源码 ZIP 不包含数据库与原始文件。

真实 HTTP 上传示例（默认端口；服务已启动）：

```powershell
curl.exe -H 'Origin: http://127.0.0.1:8000' -F 'file=@data/raw/online_retail_uci352.zip;type=application/zip' http://127.0.0.1:8000/api/v1/datasets/imports
```

返回 `batch_id`、`dataset_id` 后轮询。OpenAPI 位于 `/docs`，严格 localhost Host 与可信 Origin 仍适用；默认前端 Origin 为 `http://127.0.0.1:5173`。

| 路径 | 行为 |
|---|---|
| `POST /api/v1/datasets/imports` | 单个 multipart 字段 `file`；新任务 202，已 READY 的同一快照 200 |
| `GET /api/v1/datasets/imports/{batch_id}` | 状态、已提交行数、尝试次数、脱敏错误、容器哈希列表 |
| `GET /api/v1/datasets/{dataset_id}` | 来源、版本、币种、日期；非 READY 时完整行数/日期为 null |
| `GET /api/v1/datasets/{dataset_id}/quality` | READY 才返回完整统计；导入中/失败返回 409 `DATASET_NOT_READY` |

## 数据与状态约定

- `DatasetSnapshot` 唯一键：`workbook_sha256 + transform_version`。转换版本与 D1 相同，为 `uci352-ooxml-milligbp-v1`。
- 对外 `raw_sha256`、`data_hash` 均指 XLSX 字节哈希。`submitted_file_sha256` 固定为首次容器，`containers` 追加不同的 ZIP/XLSX 来源；哈希、字节数、格式均保存。
- `TransactionRow` 唯一键：数据集 + Excel 物理行号。8 个单元格的类型、OOXML `<v>` 文本与解析文本保存在 `raw_fields`；价格原文另存 `unit_price_raw`，整数千分价/行金额分列存储。源日期是未指定时区的本地时刻，序列值仍在原字段中。
- 分类优先级为 INVALID、POSITIVE、CANCELLATION、EXCLUDED_OTHER。C/c 前缀且非负数量归其他类。缺客户号不删除，疑似重复不删除。重复标签指全部 8 个解析字段相同且出现在首行之后，质量标签重叠统计。
- `QualityIssue` 保存数据集、源行号及独立问题码。`AnalysisRun`、`Report` 本轮只建立最小关联表，没有运行智能体或生成报告。
- Decimal 按 0.001 GBP 网格、ROUND_HALF_UP 计算，偏差大于 `1E-9` 为 INVALID；不使用浮点累计金额。单价、数量、行金额及全文件绝对金额均校验 int64 边界。任何 INVALID 保留行/原因并使批次 FAILED。
- 每 2,000 行提交一个块，进度可查询；完整遍历后再次按数据库实际行/问题计数对账，最后在同一事务发布 READY。未完成的数据不能用于完整质量结果或未来指标。
- 本地进程级文件锁控制一个写入执行器；同一服务内线程池串行处理。其他进程可查询或复用已存在批次，不能抢占写任务。
- 启动时若取得写入锁，遗留 QUEUED/IMPORTING 标记为 FAILED / `IMPORT_INTERRUPTED`。重复提交同一文件会清理该失败快照的部分行，重新处理并保留失败历史、递增 attempt；不会修改 READY 快照。
- 正常关闭等待自己提交的工作结束。进程被终止时锁由操作系统释放。数据库自身损坏或磁盘写入不可用时仍需恢复本地存储，不能承诺在不可写数据库中保存错误。

## 输入资源边界

上传文件最多 50 MiB；请求总长最多文件上限加 64 KiB，实际流量仍计数。60 秒接收时限。ZIP 必须只有一个 XLSX；XLSX 包最多 256 成员、总解压大小 256 MiB、压缩比例不超过 200，最多 600,000 数据行。关系 XML 最多 1 MiB/文件，共享字符串最多 32 MiB。当前官方工作簿的 184,640,367 字节工作表 XML 实测能通过这些限制。

拒绝路径穿越、绝对上传路径、符号链接 ZIP 成员、重复成员、加密/不支持压缩、宏/嵌入对象/外部关系和 XML 实体；单元格公式不会执行且使数据行 INVALID。扩展名、MIME 与实际内容分别检查。解析/导入默认 300 秒协作式时限，在文件准备、逐行解析和发布前检查，不声称是独立沙箱进程的硬实时中止。

## 复跑验证

```powershell
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp 'D:/codex产出/电商智能体_D2数据库导入/缓存/pytest-new-run'
.venv/Scripts/python.exe scripts/verify_import.py --database 'D:/codex产出/电商智能体_D2数据库导入/缓存/new-run/app.sqlite3' --output 'D:/codex产出/电商智能体_D2数据库导入/缓存/new-run/evidence'
python scripts/manage.py test --scope frontend
python scripts/manage.py test --scope e2e
```

实际运行使用 `.venv/Scripts/python.exe` 调用 `verify_import.py`；该脚本不会自动切换 Python。使用新目录可保留旧证据。SQL 验证直接查询数据库并与 D1 独立 JSON 比较，不调用生产导入计数函数，不把参考值作为业务 API 返回值。工程验收记录不属于正式学术实验。
