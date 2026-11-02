# D3 交付与验收记录

结论：**D3工程验证PASS，READY_FOR_USER_ACCEPTANCE**。停止在D3，D4业务页面、后续工具/模型/论文/正式学术实验不在本轮范围。

实现backend/app/metrics下的严格请求/响应契约、整数SQL指标、三项受限工具、显式查询历史服务和路由；新增0003_query_history迁移。数据集列表、月度/序列、指标定义及历史GET/POST已接入FastAPI；health为0.3.0/D3。已有导入元数据GET改为只读连接，迁移校验随真实head更新。修复真实回归发现的Windows锁初始化竞争。前端仅适配health类型和回归，另用Edge验证真实JSON刷新。

| 月份 | 正向GBP | 取消GBP | 净额GBP | 正向发票 |
|---|---:|---:|---:|---:|
| 2011-09 | 1058590.172 | 38902.550 | 1019687.622 | 1837 |
| 2011-10 | 1154979.300 | 84274.630 | 1070704.670 | 2040 |

以上数字由实际API输出、独立SQL和本轮重跑的独立OOXML审计三方逐项对账，没有硬编码到生产服务。两月净额差51017.048 GBP。显示值在服务端Decimal舍入；四条原1E-3单价的整数千分价仍为1。

真实源仍为541909行，530104/9288/2517/0互斥对账。ZIP SHA `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`；XLSX SHA `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。两份独立审计与既有参考无差异（仅运行时间不同）。原始重复候选、缺客户号和费用条目保留，2011-12明确部分覆盖，源时区不作假设。

| 实际命令（外层record_command保存完整argv） | 退出码/结果 |
|---|---|
| .venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp .../pytest/final --junitxml .../pytest-final.xml | 0；158 passed，0警告 |
| python scripts/manage.py test --scope frontend | 0；8 Vitest |
| python scripts/manage.py build | 0；TypeScript及Vite |
| python scripts/manage.py test --scope e2e | 0；2 Edge健康回归 |
| .venv/Scripts/python.exe scripts/run_independent_audits.py --source data/raw/Online_Retail.xlsx --output .../independent | 0；两份独立脚本无差异 |
| python scripts/manage.py verify-metrics --database .../runtime/app.sqlite3 --output .../real-final --reference .../independent/audit_normalization_and_reference.json --browser | 0；87真实检查和Edge保存JSON刷新 |
| python scripts/handoff_check.py / manage.py doctor / python -m pip check | 均0；55不可变文件、环境、依赖通过 |

完整命令、最初失败和修复见EVIDENCE_INDEX及docs/evidence/d3/command-records.json，不能把两次失败抹去。软件fixture均标注test_fixture，不充当真实经营数据。

E01哈希与分类、E02再上传ZIP/XLSX、E03精确月度、E04千分价、E05部分/越界、E06质量样例、E07非法输入/Host、E09损坏/超限均通过。E08在D3范围只验证真实保存JSON的浏览器刷新、后台重启、内容一致和数据库SHA不变；D4业务历史页面未实现。最终两个保存记录来自两次显式验收POST，不是GET副作用。

当前库 `D:/codex产出/电商智能体_D3精确指标API/缓存/runtime/app.sqlite3`，676335616字节，SHA `76a1b09bf229ee826660762ff914a8f94afeafab4fdd5b7fee574d3d068eaac4`。新库由D2真实库复制后迁移，旧D2源库SHA保持不变；交付/运行数据备份另封存。当前服务已停止。

D2基线 `49c2bbd403fffd571926c9ca3329ded77fcdba0a`；D3最终提交SHA与全部修改文件清单见 `D:/codex产出/电商智能体_D3精确指标API/交付/git-receipt.json`。源码保留原项目位置，源码ZIP、文档/证据、数据库备份与逐文件哈希清单在 `D:/codex产出/电商智能体_D3精确指标API/交付`。原始ZIP/XLSX只留项目data/raw；.env、密钥、依赖、数据库和大文件不入Git/源码ZIP。无远程推送。

遗留：4项npm moderate开发依赖告警未升级，本轮没有重新audit；Edge颜色提示非阻断。缺失客户号/重复/不完整月份属于数据边界。模型调用0，人工gold/论文/正式实验未开始。用户验收并授权后下一步为D4。
