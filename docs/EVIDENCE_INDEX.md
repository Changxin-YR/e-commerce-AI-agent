# D3 实际证据索引

日期：2026-11-02（Asia/Shanghai）。D3 工程验证PASS，READY_FOR_USER_ACCEPTANCE；D2原索引在 docs/evidence/d3/D2_EVIDENCE_INDEX_ARCHIVE.md，既有证据保留。

原始命令 `D:/codex产出/电商智能体_D3精确指标API/缓存/commands`，包含完整argv、cwd、UTC时间、退出码和stdout/stderr。docs/evidence/d3/command-records.json 另存记录与日志SHA；最终Git检查/提交/封存命令写在交付证据和git-receipt中。

| 证据 | 实际结果 |
|---|---|
| docs/evidence/d3/real-final.json | 87项真实HTTP/SQL核对全部通过；9/10月完全匹配，空态/部分覆盖、重复上传、错误、历史重启/GET不写库 |
| docs/evidence/d3/real-first.json | 首次真实87项通过，后续仅完善浏览器临时缓存路径，独立保留 |
| docs/evidence/d3/pytest-final.xml | 158 passed，0 failures/errors/skipped；D3 42项，含缺库、并发、精度、只读及严格参数 |
| docs/evidence/d3/independent-comparison.json | 两份包内独立脚本复跑，仅适配源路径，除执行时间外无差异；原文件未离开data/raw |
| docs/evidence/d3/audit_normalization_and_reference.json | 新一次真实OOXML价格/两个月开发参考；不是论文gold |
| docs/evidence/d3/audit_retail.json | 新一次真实工作簿质量审计 |
| docs/evidence/d3/openapi.json | 从实际运行服务下载，与参数/响应模型测试一致 |
| docs/evidence/d3/tool-schemas.json | 实际三个白名单工具Schema；fixture调用与API等价，底层series服务已真实数据对账 |
| docs/evidence/d3/edge-history.json | 本机Edge真实保存JSON两次GET，刷新内容不变；截图/trace在缓存/real-final/browser |
| docs/evidence/d3/edge-regression.json | 2项真实Edge健康/刷新/停启回归；截图/trace在缓存/playwright |
| docs/evidence/d3/runtime-preparation.json | D2源库SHA核对、复制、真实迁移0003成功，D2库保留 |

| 标签 | 退出码 | 记录（相对D3缓存） |
|---|---:|---|
| d3-handoff-initial | 0 | `commands/20261102T131654125416Z_d3-handoff-initial.json` |
| d3-pytest-first | 1 | `commands/20261102T133510578132Z_d3-pytest-first.json` |
| d3-pytest-second | 1 | `commands/20261102T133546662099Z_d3-pytest-second.json` |
| d3-runtime-migration | 0 | `commands/20261102T133638900541Z_d3-runtime-migration.json` |
| d3-pytest-lockfix | 0 | `commands/20261102T133758808501Z_d3-pytest-lockfix.json` |
| d3-independent-audits | 0 | `commands/20261102T134028871047Z_d3-independent-audits.json` |
| d3-real-metrics | 0 | `commands/20261102T134343786459Z_d3-real-metrics.json` |
| d3-pytest-final | 0 | `commands/20261102T134458819112Z_d3-pytest-final.json` |
| d3-frontend-tests-build | 0 | `commands/20261102T134530697692Z_d3-frontend-tests-build.json` |
| d3-build | 0 | `commands/20261102T134557737661Z_d3-build.json` |
| d3-edge-regression | 0 | `commands/20261102T134557737661Z_d3-edge-regression.json` |
| d3-real-final | 0 | `commands/20261102T134904697792Z_d3-real-final.json` |
| d3-dependencies | 0 | `commands/20261102T135004421129Z_d3-dependencies.json` |
| d3-doctor | 0 | `commands/20261102T135004422189Z_d3-doctor.json` |
| d3-handoff-final | 0 | `commands/20261102T135004422189Z_d3-handoff-final.json` |

首轮pytest退出1：父缓存目录尚未创建（69 passed / 85 setup errors）。第二轮退出1：153 passed / 1 failed，发现Windows锁文件初始化竞争。修复后154 passed；增补缺库/空库/损坏和锁竞争等用例，最终158 passed。失败日志与XML仍在D盘缓存/交付；未篡改为PASS。

d3-frontend-tests-build 的实际argv为 test --scope frontend，只执行8项Vitest；构建由独立 d3-build 执行成功。两次标签只是名称，结论以argv和真实输出为准。Python无弃用警告；Edge保留NO_COLOR/FORCE_COLOR提示。

E01—E07/E09数据及API要求已实测；E08已通过真实保存JSON的浏览器刷新与重启读取，但历史业务页面属于D4，不能声称E08完整页面验收。E10业务链未运行。付费模型调用0，论文和正式实验未开始。
