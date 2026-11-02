# UCI Online Retail 字段字典（D1 实测）

来源版本见 `data/manifest.json`。唯一工作表 `Online Retail`，A1:H1 为下表字段名；数据物理行号为 2—541910，共 541909 行。行号必须随原行保留，不以发票号或全字段内容替代来源行主键。此处是 D2 输入约定，尚未建立交易数据库表。

| 列 / 字段 | 实测表示与业务含义 | D2 输入要求 | 实测缺失行 |
|---|---|---|---:|
| A / InvoiceNo | 数值单元格或共享字符串；发票标识，包含 C 取消前缀、A 调整前缀 | 保存标识文本；C/c 判断仅用于分类，不改写原值；必要字段 | 0 |
| B / StockCode | 数值单元格或共享字符串；商品/费用/调整代码 | 保存字符串和大小写，不要求全数字，不按正则删除；必要字段 | 0 |
| C / Description | 共享字符串或缺失；条目说明 | 保存原文和 null，不补写描述；可为空 | 1454 |
| D / Quantity | OOXML 数字，当前为整数；范围 -80995 至 80995 | Decimal 解析后验证有限且整数，再转 int；不取绝对值；必要字段 | 0 |
| E / InvoiceDate | Excel 1900 日历序列数字、带时间小数 | 同时保留源序列表示与解析后的源本地时间；时区未声明，不转 UTC/北京时间；必要字段 | 0 |
| F / UnitPrice | GBP 单价，OOXML `<v>` 文本；包含 `1E-3` 与二进制表示尾差 | `unit_price_raw` 保存原文本；Decimal 检查后转整数千分英镑；必要字段 | 0 |
| G / CustomerID | 数值形式的客户标识或缺失 | 保存可空标识文本，不用 float 标识、不补 0；缺失不排除非客户金额指标 | 135080 |
| H / Country | 共享字符串，38 个不同值 | 保存来源国家标签，不补国家、不按当前地理名录更名 | 0 |

所有原始单元格表示的最终依据是未修改的 XLSX；解析后的 float 或 `str(float)` 不能冒充 OOXML 文本。日期解析使用 openpyxl 的 1900 日历规则，日期中使用 float 仅用于 Excel 日期序列转换，价格和金额不使用 float。共享字符串索引先解析成源文本；空单元格与数字 0 分开。

## D2 派生字段的定义

- `source_row_num`：原 Excel 物理行号（首条为 2）；与 workbook 快照构成唯一来源引用。
- `unit_price_raw`：F 列原始 `<v>` 文本，例如 `1E-3`、`2.5499999999999998`；保留科学计数法与尾差。
- `unit_price_milli_gbp`：`Decimal(unit_price_raw)` 以 ROUND_HALF_UP 规范化到 0.001 后乘 1000，且必须为 64 位有符号整数。
- `line_amount_milli_gbp`：整数 Quantity × 整数千分单价；先检查乘积与聚合上界。
- `primary_class`：依次 INVALID → POSITIVE → CANCELLATION → EXCLUDED_OTHER，四者互斥；必要字段解析失败优先 INVALID。
- `quality_flags`：可同时包含缺客户号、缺描述、零价、负价、非 C 负数量、疑似重复等；不能将标签总数当排除行数。

POSITIVE 为非 C/c 发票、Quantity>0、规范化价格>0；CANCELLATION 为 C/c 发票、Quantity<0、规范化价格>0。C/c 且数量>=0 必须归 EXCLUDED_OTHER 并保留原因；当前实际文件该组合为 0，边界由明确标识的测试 fixture 验证。

疑似重复：按解析后的八字段比较，每组首次之后 5268 行，重复组共覆盖 10147 行。全部保留；这与 D2 的相同文件重复导入幂等是不同概念。
