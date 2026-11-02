# 电商经营数据分析智能体 — Codex V1.5 功能优先开工入口

**本项目目前只有 V1.4 规范的 V1.5 开发顺序修订及辅助脚本，没有完成的业务代码。你的工作是实际编码与验证。** 用户已明确：**先实现全部功能，暂时不写论文、不跑正式大规模学术实验**。研究期的 B1/B2 对照协议保留但现在不执行。

## 先读最少且必要的文件

1. `AGENTS.md`、`DEV_FIRST.md`、`CODEX_BRIEF.md`、`docs/STATUS.json`、`docs/NEXT_SESSION.md`。
2. `docs/dev/DEVELOPMENT_ROADMAP.md`、`docs/dev/IMPLEMENTATION_CLARIFICATIONS.md`、`docs/dev/FEATURE_ACCEPTANCE.md`。
3. 只读取当前步骤所需的 `docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`、`09_DATA_PREFLIGHT.md`、`10_RUNTIME_CONTRACT.md`、`16_SECURITY_AND_PRIVACY.md`、`02_ECOMMERCE_SPEC.md` 等，不要默认把全部旧历史文档注入上下文；版本优先级见 DEV_FIRST。

## 立即开始 **D0**，本次不跳阶段

- 先执行 `python scripts/handoff_check.py` 检查资料；这不是业务验收。
- 完整读取并**实际执行** `docs/dev/steps/00_00_BOOTSTRAP.md`；完成环境检查、最小FastAPI+SQLAlchemy+Alembic/Vue3工程、health API、依赖锁和真实烟测。
- 本地运行代码和测试，记录命令、退出码、Git 状态、证据与未通过项；更新 docs 状态与 NEXT_SESSION。
- **本轮做到 D0 真实验收后暂停**，报告可复核的 D0 成果，让用户确认后再进入 D1。不要本轮构建整个后端/AI/论文，也不要只输出一份新的计划。

## 后续步骤的唯一顺序

`D1数据 → D2导入 → D3指标API → D4真实Vue数据页面 → D5八工具 → D6真实LangGraph B1/B2 → D7报告/五视图 → D8稳定安全测试 → D9用户功能验收`。

每次进入新阶段读取 `docs/dev/steps/` 对应提示词并核查前一步状态；保持逐阶段可验收。允许为修复本阶段测试回到之前模块，但不能把尚未完成的功能标PASS。

## 特别禁止

不能用虚拟交易数据冒充 UCI；不能把截图/静态假图称真实业务；不能让模型自行执行 SQL/Shell；不能无预算授权触发外部付费请求；不能写论文章节、填成绩或补导师签名；不能把 handoff_check PASS 当成系统完成。

现在直接开始 D0 真实代码开发。
