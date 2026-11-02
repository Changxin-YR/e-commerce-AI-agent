# D4 实际证据索引

2026-11-02（Asia/Shanghai）。D4工程验证PASS，用户最终验收未执行；直接接续D5。原D3索引保留在docs/evidence/d4/D3_EVIDENCE_INDEX_ARCHIVE.md。

原始命令目录：D:/codex产出/电商智能体_D4业务页面/缓存/commands。command-records.json保存完整argv、时间、退出码和日志SHA；后续提交/封存命令另外留在交付回执。

| 证据 | 结果 |
|---|---|
| docs/evidence/d4/verification.json | 完成范围、原始文件与两份真实数据库的SHA及行数 |
| docs/evidence/d4/edge-final.json | 5 passed，三条真实业务链+两条健康回归 |
| docs/evidence/d4/edge-first-failed.json | 1 failed / 2 skipped / 2 passed，Vite配置热重启干扰 |
| docs/evidence/d4/pytest-final.xml | 158 passed，0 errors/failures/skipped |
| docs/evidence/d4/sql-verification.json | 21项独立SQL/Decimal核对，未调用生产计算函数 |
| docs/evidence/d4/monthly-ui-responses.json | Edge页面实际POST保存的9/10月完整JSON |
| docs/evidence/d4/refresh-restart.json | 同一查询JSON重启不变，刷新/历史读取POST=0 |
| docs/evidence/d4/initial-import.json / duplicate-import.json | 空库首次ZIP上传202，裸XLSX复用同批次200、541909行 |
| docs/evidence/d4/runtime-preparation.json | 从D3复制运行库，原库SHA一致 |

桌面/移动截图、trace、后台/前端日志在缓存/playwright/2026-11-02T14-36-54-972Z-31204；首轮失败在2026-11-02T14-31-28-053Z-35716，均封存到交付。截图已目视检查。

| 标签 | 退出码 | 命令记录文件 |
|---|---:|---|
| d4-handoff-initial | 0 | 20261102T141920278529Z_d4-handoff-initial.json |
| d4-build-first | 0 | 20261102T142800778300Z_d4-build-first.json |
| d4-vitest-first | 0 | 20261102T142928444270Z_d4-vitest-first.json |
| d4-build-second | 0 | 20261102T143127227444Z_d4-build-second.json |
| d4-edge-business-first | 1 | 20261102T143127228444Z_d4-edge-business-first.json |
| d4-pytest | 0 | 20261102T143155135923Z_d4-pytest.json |
| d4-edge-business-second | 0 | 20261102T143654197630Z_d4-edge-business-second.json |
| d4-dependencies | 0 | 20261102T143933961087Z_d4-dependencies.json |
| d4-diff | 0 | 20261102T143933961087Z_d4-diff.json |
| d4-doctor | 0 | 20261102T143933965388Z_d4-doctor.json |
| d4-handoff-final | 0 | 20261102T144557302355Z_d4-handoff-final.json |

E08业务历史页面、E10导入→9/10月查询→刷新现已真实通过。E01—E07/E09既有数据/API证据继续保留；D4另覆盖损坏上传、边界和实际后端停启。三位精确金额不转JS Number，显示值由服务端提供。

首轮不是PASS：运行时整理Vite配置的换行导致两次开发服务器重启，页面跳回概览使导入状态断言超时；数据已完整导入。固定代码后完整复跑5项通过。该失败未被删除，也未改称业务成功。

模型请求0；无正式论文、gold或冻结实验。4项npm开发依赖moderate遗留未在本阶段重新audit，Edge仍有NO_COLOR/FORCE_COLOR提示。

封存补充：首次staged diff因新增测试末尾空行退出2，移除后复查0。首次本地提交缺作者身份退出128；沿用历史Codex本地作者，仅对本次git调用设置，不更改全局配置。完整失败及复查记录已追加command-records.json，最终SHA见Git外回执。
