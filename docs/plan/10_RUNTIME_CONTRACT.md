# 本地任务运行与恢复契约

> V1.4 电商澄清：所有公开 runs 路径均已写成完整 `/api/v1/runs...`；健康检查保留 `/healthz`。本项目只实现电商业务状态，不实施本文件历史背景中涉及的获客逻辑。


版本：V1.1｜日期：2026-10-31（Asia/Shanghai）

适用：电商与获客两个独立项目。本文补充 V1.0 已有的任务记录、累计预算和实验隔离规则，不替代业务 SPEC 与共同实验协议。本文中的接口、字段和验证是待实现要求，不能据此宣称代码已存在或验证已通过。

## 1. 实施范围

首版采用本地单执行器：每个项目同时执行一个分析任务，其他任务在业务数据库中保存为待执行。FastAPI 接收请求并提供查询；执行器调用同一套业务工具和 LangGraph 流程。可使用应用进程内的轻量执行器或独立本地进程，选择后写入 `docs/DECISIONS.md`。

本项目无需 Celery、Redis 或分布式队列。持久化任务表负责保存已接收的工作，checkpoint 负责保存图状态；仅把函数交给 `BackgroundTasks` 不等于实现了重启恢复。不要将浏览器连接或内存任务列表作为唯一状态来源。

启动时检查历史任务：原 `RUNNING` 统一改为 `INTERRUPTED`，保留最后阶段和中断原因；`WAITING_INPUT` 保持等待；`QUEUED` 保持待执行。首版重启后由用户明确启动或恢复任务，不要求自动续跑。程序正常运行期间，执行器可以依次执行已提交的任务。

## 2. 状态、结果与字段

运行状态使用：

- `QUEUED`：已持久接收，尚未开始。
- `RUNNING`：执行器正在处理。
- `WAITING_INPUT`：已保存暂停状态，等待补充条件或人工决定。
- `INTERRUPTED`：执行被进程终止等原因打断。
- `PASS`：完成本次约定处理，业务结果另存。
- `FAIL`：本次处理未完成，保存错误码和已有部分结果。
- `CANCELLED`：用户取消；已发生调用及其用量仍保留。

主要迁移为 `QUEUED → RUNNING → PASS/FAIL`；运行中可转入 `WAITING_INPUT`、`INTERRUPTED` 或 `CANCELLED`。等待输入和中断任务经过状态、版本及预算检查后才能恢复为 `RUNNING`。取消在下一安全边界生效，不承诺撤回已经发出的模型请求。

`run_status` 与业务判断分开。获客正常输出 `insufficient_evidence` 可以完成本次判断；模型超时不得被改写为该类别。电商实验首轮澄清题按固定 rubric 验收，不因交互任务仍等待答复而自动计失败。阶段交付状态继续使用共享规则中的独立状态表。

运行记录最少保存：

| 字段 | 要求 |
|---|---|
| `run_id / thread_id / parent_run_id` | 稳定身份；重跑关联原运行；不同实验题和重复使用独立 thread |
| `variant / run_status / phase / revision` | 方案、执行状态、当前阶段、并发修改版本 |
| `input_ref / data_version / config_hash` | 可追溯的输入、数据与冻结配置 |
| `checkpoint_id / pending_input` | 最后可用检查点及待回答字段 |
| `budget_limit / budget_consumed` | 额度上限与已占用额度，恢复不得清零 |
| `result_ref / error_code` | 已保存输出或明确错误，允许保留部分结果 |
| `created_at / started_at / updated_at / ended_at` | 带时区的实际时间；人工等待时间另计 |

大文件、网页快照和交易表保存在业务数据层，图状态保存引用及必要摘要。模型密钥不进入图状态或运行记录。

## 3. API 建议与公共输出

下列为建议接口命名，可以结合已有工程调整，但行为必须保持，并更新 OpenAPI：

| 接口 | 行为 |
|---|---|
| `POST /api/v1/runs` | 校验输入并先写入任务，再返回 `run_id`；同一提交键重试返回同一任务 |
| `GET /api/v1/runs/{run_id}` | 只读状态、已有结果及待输入字段，不触发执行 |
| `POST /api/v1/runs/{run_id}/input` | 校验待答字段、提交键和 `revision`，恢复同一暂停任务 |
| `POST /api/v1/runs/{run_id}/resume` | 仅恢复允许恢复的中断任务，检查checkpoint及版本 |
| `POST /api/v1/runs/{run_id}/rerun` | 创建新run和新thread，保留 `parent_run_id`，不覆盖原输出 |
| `POST /api/v1/runs/{run_id}/cancel` | 登记取消，返回实际状态；重复请求不产生额外副作用 |

状态冲突、重复运行和旧版本提交必须明确拒绝或返回已完成结果，不能同时启动两个执行器处理同一任务。单执行器仍需要数据库条件更新或等效锁定，防止双击或重复请求。

B1/B2 使用相同基础输出结构：`run_id`、`run_status`、`business_result`、`action`、`result_ref`、`evidence_refs`、`warnings`、`error_code`、`usage`。业务字段按对应 SPEC 定义；没有值时明确为空或未知。共同使用类型校验、权限限制、基础网络及格式处理策略。B2 新增条件检查、跨工具对账、数字或证据核验及有界业务恢复；不得将这些差异隐藏到公共适配层，也不得削弱 B1 基础保护。

## 4. Checkpoint 与幂等写入

本地首版采用文件型 `SqliteSaver`；异步图使用与锁定版本兼容的 `AsyncSqliteSaver`。业务库与checkpoint库可以分文件保存，身份通过 `run_id/thread_id` 关联；不要假设两个文件的更新天然构成同一事务。

任务接收记录先于图调用提交。按所用版本核实 `durability` 行为；需要验证节点间崩溃恢复时采用同步持久化，或明确记录替代方案能恢复到的边界。恢复前检查输入、规则与代码配置；不兼容时保留原任务并要求新建运行，不强行加载旧状态。

`interrupt()` 恢复会重跑所在节点。将澄清或复核暂停放入独立节点；不要用宽泛异常捕获吞掉中断。报告、事实和复核记录使用稳定业务键，例如 `run_id + step_id + output_kind`，数据库约束与幂等写入共同防止重复。即使写操作放在暂停之后，写入成功而checkpoint未保存时仍可能重做，必须保留幂等约束。

重复提交相同恢复请求应返回当前状态或已保存结果。明确修改已有人工决定时创建可追踪的新版本，不能无声覆盖历史决定。首版不承诺外部模型请求严格只发生一次。

## 5. 预算持久化与未知调用结果

沿用现有每任务和实验总上限。模型请求统一经provider适配层；显式配置SDK自动重试、`ToolStrategy.handle_errors`、节点重试与应用层重试，禁止多层默认重试绕开计数。所有方案使用相同基础策略；B2业务恢复另行标记并计入相同上限。

每次尝试在发送请求前持久保存 `attempt_id`、所属run、调用来源、请求配置哈希和额度占用。记录 `RESERVED / SENT / SUCCEEDED / FAILED / UNKNOWN_OUTCOME` 等尝试状态、请求ID、返回用量和错误。工具内部模型调用走相同入口。单项目执行器同时检查任务额度和实验批次额度。

如果进程在保存尝试后、取得确定响应前终止，将无法确认的尝试标记为 `UNKNOWN_OUTCOME`。它可能已经送达并产生费用，不能当作未调用、零用量或免费重试。恢复时保守占用该次额度；确切发送数、Token和费用未知则分别标记未知。额度占用量不应被表述为已经确认的供应商计费量。必要的再次请求作为新attempt，继续消耗剩余额度。

达到额度上限立即停止新调用，保存部分结果和预算错误。重启、恢复、格式修复都不能清零原任务计数；新建运行也必须继续受实验批次总额度约束。

## 6. 历史只读与必要验证

历史详情和报告只读取已保存输出。LangGraph replay会重新执行检查点之后的节点，可能再次调用模型或API，不能用于普通历史展示。重新执行或分支实验必须由明确操作触发、形成新记录，并展示原运行关联。

进入完整页面验收前，实际执行以下三项：

1. **暂停恢复。** 用开发样本触发澄清，关闭后端再启动，以原thread恢复；重复提交同一答复，确认结果正确且报告、复核记录没有重复。
2. **执行中断。** 在可控调用边界停止后端；重启后任务显示中断。已有结果、尝试和额度仍在，未知请求不记零；恢复或重开行为符合契约。使用fixture测试中断不充当真实模型效果实验。
3. **历史查看。** 打开历史任务、报告并刷新页面，确认没有新增模型请求、额度变化或旧结果改写。

保存命令、run_id、状态前后值及断言结果。任一未执行项明确标记，不能根据代码阅读宣布通过。

## 7. 官方事实与本项目设计的区别

以上状态、字段、接口、单执行器和保守额度策略是本项目设计要求。以下为核验日期2026-10-31的官方行为依据，具体API仍按项目锁定版本验证：

- LangGraph内存checkpointer不能跨进程重启保留；SQLite实现适用于本地工作流，需单独安装对应包：
  https://docs.langchain.com/oss/python/langgraph/persistence
  https://docs.langchain.com/oss/python/langgraph/checkpointers
- interrupt恢复会重新进入节点，重复副作用需要幂等处理：
  https://docs.langchain.com/oss/python/langgraph/interrupts
- replay重新执行后续节点，包含模型/API调用：
  https://docs.langchain.com/oss/python/langgraph/use-time-travel
- ToolStrategy的 `handle_errors` 有默认错误处理行为，需显式核对：
  https://docs.langchain.com/oss/python/langchain/structured-output
- FastAPI后台任务在响应之后执行；多进程重任务可采用更大的任务工具，但本项目恢复语义仍由应用实现：
  https://fastapi.tiangolo.com/tutorial/background-tasks/
- doctor须记录Python实际 `sqlite3.sqlite_version`、journal mode和checkpoint包版本。若启用WAL，核对官方当前WAL-reset修复说明，选择包含修复的运行库；不能只凭pip锁文件判断SQLite版本：
  https://www.sqlite.org/wal.html
