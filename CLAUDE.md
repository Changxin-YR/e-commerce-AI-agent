# Claude Code 工程验收入口

这是已经完成 D0—D9 离线工程的实际 Git 仓库。当前任务是验收和检查，不能依据旧开工包中的 D0/NOT_STARTED 重新开发整个系统。

1. 先阅读 `AGENTS.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md`、`docs/D9_ACCEPTANCE.md`，再读仓库内的 `docs/CLAUDE_ACCEPTANCE.md`。按 AGENTS 要求了解 CODEX_START/DEV_FIRST/CODEX_BRIEF，但其原始起始状态是历史信息。55 份不可变契约保留原字节。
2. 源码基线：`6526e81674649068eac1a1a69a6a63d63a8fc8f2`。本机 D9 封存材料在 `../交付物/D9最终工程交付/`，迁移凭据及详细本机指南在 `../交付物/项目迁移记录/`；这些大文件不随 GitHub 克隆分发。本次只增加交接文件、复制本机交付物及迁移本机运行配置，没有改变原有业务源码。
3. 用户本机 `.env` 的数据库路径是 `sqlite:///./data/runtime/app.sqlite3`，配套 `data/runtime/app.checkpoints.sqlite3`；相对路径按仓库根目录解析。GitHub 克隆不含这些本地文件，首次复现按 README 安装、迁移和导入。`.env` 不得输出、提交或收入验收报告。本机构建/上传/测试缓存仍在 `D:/codex产出/电商智能体_项目迁移与Claude验收/缓存`。
4. 当前状态为 `READY_FOR_USER_ACCEPTANCE`，用户尚未最终确认。F06—F09 真实模型仍 `BLOCKED_AUTHORIZATION`，真实外部调用 0，付费开关 false，真实请求/token 预算 0。132 条历史模型尝试属于 scripted 工程夹具，不能称为实际供应商验证。B0 不用模型。
5. 先检查 Git 状态与哈希。保护用户改动和 D9 封存件，执行会写入业务数据的验证时使用新副本。GitHub 仓库包含源码、锁定依赖清单、工程文档及已入库证据；另机复现需要按 README 取得官方数据、创建本地配置、安装依赖、迁移与导入。
6. 独立记录本轮 PASS/FAIL/BLOCKED/NOT_RUN，不照抄历史结果。用户已授权将本次工程提交到指定 GitHub 仓库；后续验收没有自动修复或再次发布的授权。真实模型付费调用、部署、论文/gold/正式学术实验仍未授权，也不能自授 USER_ACCEPTED。
