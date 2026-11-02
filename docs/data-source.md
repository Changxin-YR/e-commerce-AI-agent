# 原始数据来源与版本封存

本机取得日期：2026-11-02（Asia/Shanghai）。来源为 UCI Machine Learning Repository 的 Online Retail（数据集 352）。引用：Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. DOI 10.24432/C5BW33。官方页面声明许可 CC BY 4.0。本轮仅读取、审计原文件并生成派生审计报告，未改写原文件。

- 数据集页面：`https://archive.ics.uci.edu/dataset/352/online%2Bretail`
- 实际下载 URL：`https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip`
- 下载方法：包内原始 `scripts/download_source_data.py --download`，urllib HTTPS 读取；下载后先验证 ZIP 及内层 XLSX SHA，再保存已验证容器。
- 页面 GET 实测 HTTP 200，最终 URL 与请求相同；页面 HTML 174303 字节，SHA-256 为 `92f168c5bd71a7f08e03b14f490231e97a0c18bbf3505513e3fe879589221ed7`。
- ZIP HEAD 首次 TLS 中断，重试 HTTP 200、最终 URL 未改变。HEAD 响应没有给出 Content-Length/Last-Modified；不伪造服务器版本时间，采用实际本地文件字节数与内容哈希识别版本。

| 对象 | 本地路径 | 字节数 | SHA-256 |
|---|---|---:|---|
| 官方原始容器 | data/raw/online_retail_uci352.zip | 23715478 | f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b |
| 内层工作簿 | data/raw/Online_Retail.xlsx | 23715344 | 43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d |

ZIP 内成员原名为 `Online Retail.xlsx`；本地名称使用下划线，仅文件名不同，文件内容相同。与 2026-10-31 历史审计的两项参考 SHA 完全一致，无新版本差异。当前官方文件已核对为历史基线，不根据“下载日期不同”虚构数据更新。

数据集网页将两项标识列与 6 个特征分开描述，工作簿实际共有 8 列，详见字段字典。网页“无缺失”不取代实际读取；原文件存在客户号和描述缺失，详见质量报告。

证据目录：`docs/evidence/d1/` 中有 source-http.json、source-head-retry.json、三份审计 JSON 和 comparison.json。完整页面原件与实际命令日志归档在 `D:/codex产出/电商智能体_D1真实数据审计/交付/证据/`。下载命令的起止时间、退出码和源文件校验输出保存在 command 记录中；manifest 记录其路径和 SHA。

原始 ZIP/XLSX 只在本地项目 `data/raw/` 保存，不纳入 Git 或额外源码 ZIP。不将官方真实原件复制到 D 盘缓存；D 盘保存审计结果、脚本适配副本、测试 fixture 和来源网页。这遵循本轮明确的原始文件路径要求。拿到不同 SHA 时须保留新来源与实际 SHA 并重新审计，不能覆盖旧参考或强制匹配旧计数。
