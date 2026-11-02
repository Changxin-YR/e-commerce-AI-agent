# D6 实际证据索引

D6离线工程PASS；真实模型BLOCKED_AUTHORIZATION。前序索引保存在docs/evidence/d6/D5_EVIDENCE_INDEX_ARCHIVE.md。

| 文件 | 证据 |
|---|---|
| docs/evidence/d6/verification.json | 224 pytest、114真实HTTP/进程断言、运行库/checkpoint SHA与行数 |
| docs/evidence/d6/pytest-first.xml | 首轮局部28通过 |
| docs/evidence/d6/pytest-full.xml | 首轮全量217通过/3旧版本预期失败 |
| docs/evidence/d6/pytest-final.xml | 最终224通过，无failure/error/skipped |
| docs/evidence/d6/real-verification.json | 最终15个scripted任务的状态/用量/引用与114断言 |
| docs/evidence/d6/real-first-verification.json | 第一轮15任务/114断言，未覆盖 |
| docs/evidence/d6/runtime-preparation.json | D5库复制到D6且原SHA一致 |
| docs/evidence/d6/official-docs-manifest.json | 官方持久化/中断/SQLite/provider文档抓取身份 |

完整命令、退出码和stdout/stderr在D:/codex产出/电商智能体_D6智能体/缓存/commands；服务日志分别在real-first和real-final。所有子进程已停止。交付git-receipt/SOURCE_MANIFEST/DELIVERY_MANIFEST记录最终提交与逐文件哈希。源码不含.env、数据原文件、数据库或依赖。
