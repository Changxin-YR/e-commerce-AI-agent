# D0 收尾与 D1 实际证据索引

日期：2026-11-02（Asia/Shanghai）。D1工程核验PASS，READY_FOR_USER_ACCEPTANCE；D2未开始。

原始命令目录：`D:/codex产出/电商智能体_D1真实数据审计/缓存/commands`。两份独立审计子命令在同缓存的 `independent-audits/commands`。交付完整副本位于同任务 `交付/证据`。每条记录包含实际 argv、cwd、UTC起止时间、退出码、stdout/stderr；结构化总索引为 `docs/evidence/d1/command-records.json`。

## 核心结果

- 官方ZIP/XLSX实际取得并校验，两个SHA与旧参考一致；原件仅在本地data/raw。
- 新OOXML审计541909行，分类530104/9288/2517/0；两个历史独立脚本仅源路径适配后运行，除执行时间外全部字段一致。
- 33项实际交叉检查通过；70 pytest（31 D0 + 39 D1）通过，无警告。JUnit：docs/evidence/d1/pytest-final.xml。
- 缺文件和损坏文件退出2是预期拒绝；npm全量退出1是已识别的4项moderate开发依赖告警，生产审计退出0且漏洞0。
- D0原封存111文件一致，25命令输出及31/8/2测试结果核实。历史原索引已保存在 docs/evidence/d1/D0_EVIDENCE_INDEX_ARCHIVE.md；前端与浏览器本轮未重跑。

## 实际运行记录

| 标签 | 退出码 | 记录（相对D1缓存） |
|---|---:|---|
| handoff-initial | 0 | `commands/20261102T085006763699Z_handoff-initial.json` |
| npm-audit-full | 1 | `commands/20261102T085048678735Z_npm-audit-full.json` |
| httpx2-plan | 0 | `commands/20261102T085449139949Z_httpx2-plan.json` |
| d0-evidence-review | 0 | `commands/20261102T085655791335Z_d0-evidence-review.json` |
| dependency-tree | 0 | `commands/20261102T085824964067Z_dependency-tree.json` |
| npm-audit-retry | 1 | `commands/20261102T085824964067Z_npm-audit-retry.json` |
| httpx2-install | 0 | `commands/20261102T090315784681Z_httpx2-install.json` |
| d0-pytest-after-httpx2 | 0 | `commands/20261102T090847204059Z_d0-pytest-after-httpx2.json` |
| npm-audit-production | 0 | `commands/20261102T090933589112Z_npm-audit-production.json` |
| pip-check-d0 | 0 | `commands/20261102T090933590656Z_pip-check-d0.json` |
| git-safety-d0 | 1 | `commands/20261102T091349055511Z_git-safety-d0.json` |
| git-safety-d0-fixed | 0 | `commands/20261102T091604048613Z_git-safety-d0-fixed.json` |
| git-baseline | 0 | `commands/20261102T091720127253Z_git-baseline.json` |
| audit-deps-install | 0 | `commands/20261102T091736189852Z_audit-deps-install.json` |
| uci-download | 0 | `commands/20261102T091736189852Z_uci-download.json` |
| source-audit | 0 | `commands/20261102T092134228781Z_source-audit.json` |
| independent-audits | 0 | `commands/20261102T092306387232Z_independent-audits.json` |
| audit_retail | 0 | `independent-audits/commands/20261102T092306650251Z_audit_retail.json` |
| audit_normalization_and_reference | 0 | `independent-audits/commands/20261102T092400631560Z_audit_normalization_and_reference.json` |
| pytest-d1 | 0 | `commands/20261102T092422892480Z_pytest-d1.json` |
| source-http | 2 | `commands/20261102T092630010933Z_source-http.json` |
| d1-cross-verification | 0 | `commands/20261102T092931202552Z_d1-cross-verification.json` |
| verify-existing-zip | 0 | `commands/20261102T095522185285Z_verify-existing-zip.json` |
| verify-existing-xlsx | 0 | `commands/20261102T095522608425Z_verify-existing-xlsx.json` |
| missing-data-rejected | 2 | `commands/20261102T095522865605Z_missing-data-rejected.json` |
| pip-lock-d1 | 0 | `commands/20261102T095601036985Z_pip-lock-d1.json` |
| source-head-retry | 0 | `commands/20261102T095601113119Z_source-head-retry.json` |
| pytest-final | 0 | `commands/20261102T100028819317Z_pytest-final.json` |
| corrupt-file-rejected | 2 | `commands/20261102T100607393240Z_corrupt-file-rejected.json` |
| handoff-final | 0 | `commands/20261102T100640725197Z_handoff-final.json` |
| git-safety-d1 | 0 | `commands/20261102T100640729407Z_git-safety-d1.json` |
| pip-check-final | 0 | `commands/20261102T100641104563Z_pip-check-final.json` |
| diff-check-d1 | 2 | `commands/20261102T100641262000Z_diff-check-d1.json` |
| diff-check-d1-fixed | 0 | `commands/20261102T100737197524Z_diff-check-d1-fixed.json` |

首次npm TLS失败、source-http HEAD失败均保留且后续重试成功；首次敏感路径扫描和diff检查为核查工具/CRLF误报，修正后通过，见KNOWN_ISSUES。不得删除失败以伪造一次通过。

## 数据与版本索引

| 文件 | 用途 |
|---|---|
| data/manifest.json | 来源、两种哈希、文件大小、精度版本与证据SHA |
| docs/evidence/d1/audit.json | 新OOXML逐行分类、质量、原值样例、内部ZIP结构与整数范围 |
| docs/evidence/d1/audit_retail.json | 包内pandas/openpyxl独立审计本次输出 |
| docs/evidence/d1/audit_normalization_and_reference.json | 包内OOXML/Decimal独立审计本次输出 |
| docs/evidence/d1/comparison.json | 适配前后脚本SHA、环境与旧参考逐字段差异（空） |
| docs/evidence/d1/verification.json | 对当前真实源文件及三份输出的33项检查 |
| docs/evidence/d1/source-http.json、source-head-retry.json | 官方页面GET及ZIP HEAD证据 |
| docs/evidence/d1/d0-review.json | D0源码与原测试证据核查 |

原始数据SHA：ZIP `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`；XLSX `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`。

D0基线 `0740bf439c37dc344885d2f7c26568c157dd9571`。D1提交回执、修改文件列表和源码包SHA在 `D:/codex产出/电商智能体_D1真实数据审计/交付/git-receipt.json` 与 DELIVERY_MANIFEST.json，均在Git外记录以避免自引用。没有推送远程。

运行环境：Windows 11 build26200 / Python3.12.15 / pandas2.2.3 / openpyxl3.1.5 / numpy2.5.4 / pytest9.2.0；依赖完整版本以requirements.lock为准。D1无模型请求、无交易导入、无论文或正式实验。
