# 本次审查的实际数据证据

本目录JSON来自2026-10-31实际执行，审计对象为UCI官方Online Retail原始XLSX。数据来源、哈希、许可和口径见../09_DATA_PREFLIGHT.md。没有人工标注记录，没有模型实验结果，没有业务系统通过记录。

## 复跑方法

1. 从09给出的官方ZIP下载原数据，核对ZIP和XLSX哈希。
2. 新建独立审计目录，复制本目录两个.py脚本进去。将原XLSX命名为Online_Retail.xlsx放在两个脚本旁边。
3. 依据audit_environment.json检查Python、pandas和openpyxl；项目依赖选择与锁定另做，不自动把审查环境当开发标准。
4. 在新目录运行：

```bash
python audit_retail.py
python audit_normalization_and_reference.py
```

两脚本会写出对应JSON。不要在本目录直接覆盖本次审查结果；保留每次实际执行的时间、源码版本和输入哈希。第二个脚本断言本快照541,909行且价格规范化差值不超过1E-9 GBP，发现不符会停止。源码与JSON可供检查，不能将程序自动输出伪称真人复核。

## 说明

audit_retail.json中缺失/重复统计使用pandas解析后的八个字段；原XML价格表示另行统计。特殊代码列表仅用于审计，含字母的代码也可能是真实商品，不能据该列表直接删除或断定非商品。

audit_normalization_and_reference.json中included_non_digit_stock_codes表示纳入金额的非纯数字代码，包含正常商品后缀；这不是经过人工核验的费用类别表。

原数据引用：Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 。数据许可CC BY 4.0。审计脚本与规范化方案为本次新增处理，解释与限制见09。
