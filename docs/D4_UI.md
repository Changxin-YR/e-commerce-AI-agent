# D4 本地业务工作区

前端增加经营概览、数据与导入、查询历史三个功能入口。健康诊断保留在 `/?view=health`。后端沿用 D3 的 0.3.0 API、迁移 0003_query_history 和 retail-v1.2 口径；这不代表 D6 智能体或 D7 五视图已完成。

## 实际操作

在项目根的两个 PowerShell 窗口分别执行：

```powershell
python scripts/manage.py backend
python scripts/manage.py frontend
```

打开 `http://127.0.0.1:5173/`。在“数据与导入”选择 `data/raw/online_retail_uci352.zip` 或 `data/raw/Online_Retail.xlsx`，点击“上传并导入”。页面显示等待/正在导入、已处理行数、成功或失败。首次导入会轮询批次；刷新可用已保存批次 ID 继续轮询。相同工作簿的 ZIP 与 XLSX 复用批次，不增加交易行。

在“经营概览”选择 `2011-09`、`2011-10`，分别点击“查询并保存”。国家与商品代码可留空，填写时按源字段精确匹配，不自动去空格或大小写转换。查询条件变更后旧结果会清空；每份保存结果同时显示其月份、筛选、数据哈希、指标版本和查询 ID。

页面直接显示 API 的两位显示字符串及三位精确字符串，不把金额转为 JavaScript Number，也不在浏览器重新计算。有效发票数是该月正向交易行中的不同 InvoiceNo 数量。取消类金额不能解释为实际退款，交易行金额不能解释为纯商品 GMV 或财务收入。

选择 `2011-12` 可看到月份覆盖不完整；`2012-01` 显示无数据且金额为“—”；在有数据月份使用不存在的合法国家筛选时显示“筛选结果为空”，金额为 0.000。源时区未声明，结束日期不包含在统计期间。

查询成功后 URL 保存 `?query=<id>`。刷新、重启后或打开“查询历史”只发 GET 读取原保存 JSON；没有 POST 重算或模型请求。不依赖浏览器内存保存业务结果。没有查询 URL 时会加载当前数据集最近的服务端历史。浏览器存储只保存数据集/批次指针；存储不可用仍能查询及通过 URL/历史恢复。已有 D3 序列历史也可只读显示。

请求有超时上限，导入/保存超时可能已经在服务端完成。连续重试同一查询沿用提交键，避免因丢失响应重复存储。文件类型/大小、失败批次、损坏文件、后端不可用均有明确提示和重试入口。错误正文不直接展示服务端内部异常。

## 工程检查

以下命令均应通过 `scripts/record_command.py` 保存完整 argv、退出码与日志到本次独立缓存目录：

```powershell
python scripts/manage.py test --scope frontend
python scripts/manage.py test --scope backend
python scripts/manage.py build
python scripts/manage.py test --scope e2e
```

Edge 套件保留两个健康回归，新增三条真实业务流程。业务用例在新的隔离 SQLite 库里通过 UI 完整导入官方文件，不用 mock 数据代替验收；损坏上传明确标 test_fixture。截图、trace、命令与响应保存在 D0_CACHE_DIR/playwright 下每次独立运行目录。完整首次导入需要数分钟，测试期间不要修改 Vite 配置或业务源码，以免热重载改变正在操作的页面。

`scripts/verify_ui.py` 使用只读 SQLite 和独立 SQL/Decimal 核对真实浏览器捕获的 9/10 月响应。它不导入生产聚合函数，检查三项金额的精确/显示值、发票数、数据库保存 JSON、哈希及行数。

本阶段运行库在 `D:/codex产出/电商智能体_D4业务页面/缓存/runtime/app.sqlite3`，从已封存 D3 库复制，原库保留。首次 UI 导入的独立库另留在 Playwright 的 business 目录。全部原始 ZIP/XLSX 仍仅在项目 data/raw；源码和封存包不含原始文件、密钥、依赖或运行数据库。

模型调用数为 0；正式论文、冻结学术实验、生产店铺、公网部署及远程推送未执行。
