# D1 封存输入与 D2 导入交接

以下为 D1 封存的输入约定；用户续接后 D2 已完成真实导入，实施结果见文末与 D2_DELIVERY.md。下一阶段 D3 仍须等待授权。

## 输入与身份

读取 `data/manifest.json`，重新检查本地 `data/raw/online_retail_uci352.zip` 和 `data/raw/Online_Retail.xlsx` 的当前字节哈希。两者分别为容器哈希与工作簿哈希，不能混用。ZIP 内 `Online Retail.xlsx` 与本地带下划线名称的 XLSX 内容相同。

快照身份应基于内部 `workbook_sha256` 加变换版本；上传 ZIP 后再上传同一 XLSX，必须复用相同有效快照。原始疑似重复行则全部保留，来源主键使用 `(dataset_id, source_row_num)`；本版物理数据行号为 2—541910。

缺失文件不能靠已保存的 manifest 或 audit.json 假判 READY；缺失应 BLOCKED_DATA，哈希变化则单独记录版本，重新审计。已有下载脚本只接受已知官方哈希；新版本先保留来源/实际哈希，不能修改常量来强迫旧参考 PASS。新审计命令允许对另一路径 XLSX 显式使用 `--allow-new-version`，输出 NEW_VERSION_REQUIRES_REVIEW；独立旧基线复跑仍拒绝哈希不同的输入。

## 解析与精度门槛

字段字典为 `docs/data-dictionary.md`；来源事实与质量为 `docs/data-quality.md`。必须保留八个字段原值、原行号、原价格 OOXML 文本，解析字段另存。CustomerID 缺失是 null，不是 0；不补描述、时区或金额。

价格转换版本：`uci352-ooxml-milligbp-v1`。Decimal 三位网格、ROUND_HALF_UP、容差<=1E-9，整数千分英镑用于金额与 SQLite 聚合。超精度容差不能静默舍入；必要字段无效应保留源行及原因，阻断错误快照完成。逐行和聚合均要防 64 位越界，不能仅以当前快照安全推断任意上传也安全。

主分类按 INVALID、POSITIVE、CANCELLATION、EXCLUDED_OTHER 的优先级互斥判定，C/c+非负数量边界不得省略；可重叠质量标签独立存储。全部行对账必须满足 541909=0+530104+9288+2517（仅该 SHA 的开发参考）。不按疑似重复标签删行，不因客户缺失排除非客户统计。

源时间时区未指定；按原 InvoiceDate 归月，月区间左闭右开。2011-12 必须提示不完整。正向发票计数是过滤后的 distinct InvoiceNo，不能把 25900 总发票标识当正向订单数。

## 交付证据与命令

`docs/evidence/d1/` 中有本次三份实际审计 JSON、comparison.json 与 verification.json。`docs/plan/evidence/` 是历史参考，禁止覆盖。审计脚本不导入 backend，不参与未来生产指标计算，保持独立参照。

以下从项目根目录运行。为每次复跑选择新输出目录；不会覆盖已有证据：

```powershell
$py = '.\.venv\Scripts\python.exe'
$run = 'D:\codex产出\电商智能体_D1真实数据审计\缓存\复跑_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
& $py scripts/download_source_data.py --download
& $py scripts/audit_source_data.py --zip data/raw/online_retail_uci352.zip --xlsx data/raw/Online_Retail.xlsx --output "$run\source"
& $py scripts/run_independent_audits.py --source data/raw/Online_Retail.xlsx --output "$run\independent"
New-Item -ItemType Directory -Path "$run\verification-input" | Out-Null
Copy-Item "$run\source\audit.json" "$run\verification-input"
Copy-Item "$run\independent\*.json" "$run\verification-input"
& $py scripts/verify_d1_evidence.py --evidence "$run\verification-input" --output "$run\verification.json"
```

正式记录每个命令时，用 `scripts/record_command.py --output <本次commands目录> --label <标签> -- <命令>` 包装，记录实际 argv、cwd、起止时间、退出码、stdout/stderr。每一步应检查 `$LASTEXITCODE`，失败不得继续宣布成功。测试用例里的小型输入明确为 test_fixture，不属于真实原始数据。

D2 尚未实施的验收包括：541909 行真实数据库导入、事务/失败恢复、跨容器幂等、API 查询与导入状态。D1 的 PASS 不代表这些测试通过。

## D2 实施结果（2026-11-02追加）

上文为D1封存输入，现已被D2真实导入验证：541909行、分类及价格/质量统计一致，ZIP/XLSX幂等，41项核对通过。当前使用/恢复命令见D2_IMPORT.md，结果见D2_DELIVERY.md；原始审计证据没有覆盖。下一阶段是D3，仍需用户授权。
