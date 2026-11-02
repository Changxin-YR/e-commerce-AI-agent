# UCI 真实原始文件说明

本交接包包含**实际审计脚本、审计 JSON 和历史对账结论**，但**未包含 23.7 MB 原始交易文件**；历史独立审计环境成功取得并计算过该原文件；V1.3 构包环境曾有下载失败。**Codex 用户 Windows 项目环境是否可取得仍未验证**。必须在用户本地按合法渠道下载真实文件，或让用户从官方页面下载后提供。

- 官方数据集：https://archive.ics.uci.edu/dataset/352/online+retail
- 官方 ZIP：https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip
- 数据引用：Chen, D. (2015). Online Retail. UCI ML Repository. DOI 10.24432/C5BW33；CC BY 4.0。
- ZIP SHA-256：`f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`
- XLSX SHA-256：`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`

```powershell
python scripts/download_source_data.py --download
# 或者用户自行下载后
python scripts/download_source_data.py --verify-zip 'C:\Downloads\online+retail.zip'
python scripts/download_source_data.py --verify-xlsx 'C:\Downloads\Online Retail.xlsx'
```

哈希不符时停止使用旧固定参考值，查明版本差异并重新实际审计。**不能用虚拟交易数据凑成功结果。**
