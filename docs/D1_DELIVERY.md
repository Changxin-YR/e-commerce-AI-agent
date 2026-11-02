# D1 交付说明

2026-11-02（Asia/Shanghai），D0 收尾与 D1 工程验收通过，状态为 READY_FOR_USER_ACCEPTANCE。完成后停止，未进入 D2、未写论文、未做正式学术实验。

## 实际结果

官方 ZIP 23715478 字节、XLSX 23715344 字节，SHA-256 分别为 `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`、`43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`，均匹配旧参考。原件只存项目 data/raw，不进入 Git 或交付源码 ZIP。

唯一工作表 Online Retail，8 字段，541909 行，25900 个不同发票标识。源日期 2010-12-01 08:26:00—2011-12-09 12:50:00。互斥分类：530104 正向、9288 取消、2517 其他、0 无效。客户号缺失135080，描述缺失1454，零价2515，负价2，负数量10624，疑似重复5268（全部保留）。与旧参考没有统计差异。

真实 0.001 单价4条（原 XML 为1E-3）；51170条有表示尾差，最大7E-13 GBP，超过1E-9容差0条。原始表示与精确整数千分英镑转换痕迹可定位，原文件未改写。两份包内独立脚本复跑退出0，除实际执行时间外 JSON 全部一致；新增33项交叉校验通过。

## 实际命令与测试

完整 argv、cwd、时间、退出码及 stdout/stderr 见 EVIDENCE_INDEX.md 和 docs/evidence/d1/command-records.json。下表省略相同的 `.venv/Scripts/python.exe scripts/record_command.py --output ... --label ... --` 外层记录器。

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `python scripts/download_source_data.py --download` | 0 | 官方下载及内层 SHA 校验通过 |
| `python scripts/download_source_data.py --verify-zip data/raw/online_retail_uci352.zip` | 0 | 已有真实 ZIP 验证通过 |
| `python scripts/download_source_data.py --verify-xlsx data/raw/Online_Retail.xlsx` | 0 | 已有真实 XLSX 验证通过 |
| `python scripts/audit_source_data.py --zip data/raw/online_retail_uci352.zip --xlsx data/raw/Online_Retail.xlsx --output <source-audit>` | 0 | 541909行实际扫描并生成JSON |
| `python scripts/run_independent_audits.py --source data/raw/Online_Retail.xlsx --output <independent-audits>` | 0 | 两份原独立审计退出0，递归比对无实质差异 |
| `python scripts/verify_d1_evidence.py --output <d1-verification.json>` | 0 | 33项跨审计、当前原文件和脚本身份校验通过 |
| `python -m pytest tests -v -p no:cacheprovider --basetemp <任务缓存>/pytest/final --junitxml <任务缓存>/pytest-final.xml` | 0 | 70 passed，0失败/跳过/警告；31 D0 + 39 D1 |
| `python scripts/verify_d1_evidence.py --xlsx <不存在的文件> --output <missing-data-result.json>` | 2 | 预期拒绝，不凭旧JSON伪造成功 |
| `npm audit --json`（首次 / 重试） | 1 / 1 | 首次TLS失败；重试得到4项moderate开发依赖告警 |
| `npm audit --omit=dev --json` | 0 | 运行依赖漏洞0 |
| `python -m pip install --disable-pip-version-check -r requirements.lock` | 0 | 锁定依赖与实际已安装版本一致 |

pytest 中实际覆盖缺失/损坏 ZIP/XLSX、合法 ZIP 哈希不同、内层 SHA 不同、布局错误、网络异常、价格超精度和整数越界、C前缀+非负数量、证据目录拒绝覆盖。测试输入均明确 test_fixture；真实业务数据核验由上面的实际下载和审计命令完成。

D0旧证据已核实：111文件哈希一致、25命令输出存在、31 pytest/8 Vitest/2 Edge确实通过。本轮消除Starlette/httpx弃用提示后31后端回归无警告；前端与Edge未重跑，报告不把历史记录伪称本轮执行。

## 文件与 Git

- `data/manifest.json`：来源、版本、两项SHA、审计证据SHA、精度/分类及输入文档。
- `docs/data-source.md`、`docs/data-dictionary.md`、`docs/data-quality.md`：来源记录、字段字典、实测报告。
- `scripts/audit_source_data.py`、`scripts/run_independent_audits.py`、`scripts/verify_d1_evidence.py`、`tests/test_source_data.py`：可复跑审计与测试。
- `docs/evidence/d1/`：本轮三份真实审计JSON、独立比对、交叉核验、命令索引、JUnit与D0核查证据。
- `docs/D2_DATA_INPUT.md`：下一阶段输入和复跑说明；STATUS/KNOWN_ISSUES/DECISIONS/NEXT_SESSION/EVIDENCE_INDEX已同步。
- `.gitignore`、`.gitattributes`、requirements.in/lock：排除敏感和原始文件、保留不可变交接字节、锁定测试与审计依赖。

D0基线提交：`0740bf439c37dc344885d2f7c26568c157dd9571`。D1最终提交与阶段改动清单保存在 `D:/codex产出/电商智能体_D1真实数据审计/交付/git-receipt.json`，使用Git外回执避免自引用。只做本地提交，未推送。

交付目录 `D:/codex产出/电商智能体_D1真实数据审计/交付` 包含源码ZIP、逐文件哈希、Git回执、完整命令证据和交接文档。项目源码保持原位置。

## 遗留与停止点

4项npm moderate均属于间接开发依赖，已评估影响与上游约束，未做破坏性升级；详见D0_CLOSEOUT.md。其余本轮TLS重试、检查脚本误报、旧文档字节/换行问题均如实记录，当前无D1阻断。

数据库未导入交易，模型调用0，人工gold/论文/正式实验未开始。**D1通过工程核验，等待用户验收；收到明确授权前不进入D2。**
