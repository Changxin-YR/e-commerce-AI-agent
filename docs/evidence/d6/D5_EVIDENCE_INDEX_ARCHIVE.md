# D5 实际证据索引

D5工程验证PASS。D4索引保存在docs/evidence/d5/D4_EVIDENCE_INDEX_ARCHIVE.md；此前D0—D4证据不覆盖。

| 文件 | 实际证据 |
|---|---|
| docs/evidence/d5/verification.json | 阶段范围、195 pytest、数据库/源哈希与真实模型0调用 |
| docs/evidence/d5/real-verification.json | 57真实HTTP请求/完整结果、265独立核对、前后数据库SHA相同 |
| docs/evidence/d5/tool-schemas.json | 八个真实JSON Schema |
| docs/evidence/d5/pytest-full.xml | 195 passed、0 failure/error/skipped |
| docs/evidence/d5/pytest-first.xml | 6 passed/73 setup errors，缺少测试父目录 |
| docs/evidence/d5/pytest-second.xml | 78 passed/1 failure，测试预期错误码修正 |
| docs/evidence/d5/runtime-preparation.json | D4库复制到D5且SHA一致，仅修改env运行/缓存键 |

原始命令、完整argv、退出码、stdout/stderr在D:/codex产出/电商智能体_D5八工具/缓存/commands；汇总与日志SHA在交付/command-records.json。真实服务日志位于缓存/real-first/server.log，进程由验证脚本启动并停止。测试均为开发验证，不是人审gold或学术实验。

handoff_check核对55份不可变资料；最终Git/封存命令和SHA见D盘git-receipt。真实模型BLOCKED_AUTHORIZATION，用户最终验收未执行。D6—D9继续。
