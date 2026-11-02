# 电商智能体开发状态（V1.5 功能优先）

- **更新时间**：2026-11-02（Asia/Shanghai）；原位项目已从用户提供的 V1.5 ZIP 解压并实际开发。
- **项目交接**：55 项不可变资料检查 PASS。FastAPI 健康接口、SQLite/Alembic 基线、Vue 连接页和管理命令已实现。
- **当前阶段**：`D0_READY_FOR_USER_ACCEPTANCE`；工程验证 PASS、用户验收 PENDING。下一步为 D1，必须等待用户授权，D1—D9 仍为 NOT_STARTED。
- **验证**：31 pytest、8 Vitest、2 真实 Edge Playwright、TypeScript/Vite 构建、迁移、默认端口启动、数据库完整性及锁文件安装通过。第一次 pytest 失败及修复保留证据。
- **Git**：已初始化新仓库，尚无 commit；SHA=null，不伪造版本号。源码交付包含独立 SHA256 清单。
- **进程**：自动验证创建的服务已停止；使用 README 中两个启动命令即可重新运行。
- **已知限制**：4 个 npm 间接开发依赖 moderate 告警；生产依赖 audit 为 0。Starlette 测试客户端有 1 个弃用警告，当前测试通过。
- **论文正文**：`DEFERRED_BY_USER`，不撰写；正式冻结实验：`DEFERRED_UNTIL_FEATURE_ACCEPTANCE_AND_USER_APPROVAL`。
- **数据与模型**：UCI 文件未取得/未导入，业务数据 SHA=null；数据库只有两个工程表。模型未接入，外部模型调用 0，无付费授权。

状态以 `docs/STATUS.json` 为机器唯一来源，开发真实证据保存在 `docs/EVIDENCE_INDEX.md`，每完成一个阶段同步本文件。`handoff_check=PASS` 不代表业务通过。
