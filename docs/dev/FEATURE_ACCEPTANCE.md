# V1.5：功能完整性验收矩阵（全为待实现，不得预勾）

验收结果由 Codex 实际运行证据填入 `docs/STATUS.json` / `docs/EVIDENCE_INDEX.md`。本清单不是已经测试的记录。`HANDOFF_CHECK=PASS` 只表明交接包完整。

| ID | 用户可见能力 | 必须的证据 | 状态 |
|---|---|---|---|
| F01 | UCI 原始 ZIP/XLSX 可下载/导入，哈希、许可、来源真实显示 | 真实下载校验+完整导入日志 | NOT_STARTED |
| F02 | 541909 行分类及原值可查、质量标签真实、重复导入不翻倍 | E01/E02/E04/E06/E09，数据库断言 | NOT_STARTED |
| F03 | 月度交易金额与发票数精确，空区间/部分月份正确 | E03/E05，9/10月独立对账 | NOT_STARTED |
| F04 | 商品/国家排名、时间系列、期间差额和变化拆解可查 | 工具测试+差额对账 | NOT_STARTED |
| F05 | 八个工具有稳定输入/输出、权限/上限和证据字段 | 八工具真实数据调用及负例 | NOT_STARTED |
| F06 | B1 真实多轮工具 Agent 能回答已知查询 | 实际 provider/tool_calls/usage与截图 | NOT_STARTED |
| F07 | B2 能校验参数、金额与引用并有限恢复 | 错误注入与校验拒绝案例 | NOT_STARTED |
| F08 | 缺参询问→同 run 补答→重启后恢复、重复输入幂等 | run_id/thread_id与持久数据/测试 | NOT_STARTED |
| F09 | 不支持利润/库存等指标会给出理由 | 真实开发用例，不返回假数 | NOT_STARTED |
| F10 | 五个功能视图实际连接 API、空/失败状态完整 | 浏览器操作+截图或视频+API日志 | NOT_STARTED |
| F11 | 报告能够保存、精确引用、导出 | 报告内容与tool refs对账 | NOT_STARTED |
| F12 | 历史只读，不重复花费模型调用 | 重复GET测试和usage计数对照 | NOT_STARTED |
| F13 | 上传/导出/SQL/CSRF/密钥保护和异常输入受控处理 | 安全测试及实际响应 | NOT_STARTED |
| F14 | Windows 操作说明能实际安装、迁移、启动、停止并运行测试 | 本地执行命令、退出码及环境摘要 | NOT_STARTED |
| F15 | 关键 pytest/Vitest/Playwright 与回归用例实测 | 原始测试记录与失败修复 | NOT_STARTED |
| F16 | 代码与资料可复现；没有伪造的论文/实验结果 | lock、Git、源文件哈希、状态对账 | NOT_STARTED |

最终仅当 F01—F16 中所有必需项有真实证据，且用户完成实机操作确认后才可标 `USER_ACCEPTED`。缺 Key 或运行环境时不能把 `BLOCKED` 写成 `PASS`。正式论文/批量实验仍保持 NOT_STARTED，属于另一阶段，不计为本期功能缺陷。
