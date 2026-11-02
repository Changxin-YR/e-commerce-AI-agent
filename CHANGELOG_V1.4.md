# V1.4 交接包修改记录

这是对 V1.3 的**文档和执行门槛优化**。不含实际电商服务实现，不含真实模型实验成绩。

- `CODEX_BRIEF.md`: 一份只针对电商的简要规则，按阶段加载，不需要一次读完 15 万字档案。
- `CODEX_START.md`: 删除“寻找旧 V1.2 独立指令”的表述，改为可直接执行的首轮开发批次。
- `docs/plan/21_V14_DECISIONS.md`: Claude 评审逐项核实、范围收缩与不可删的学术对照，给出优先级。
- `docs/plan/13_ECOMMERCE_BUILD_CONTRACT.md`: 补充 C 前缀正数量边界和完整 runs 路径。
- `docs/plan/10_RUNTIME_CONTRACT.md`: 公共 runs 路径统一使用 `/api/v1`，保留澄清恢复与历史只读。
- `docs/plan/16_SECURITY_AND_PRIVACY.md`: 电商不适用的任意 URL 采集测试写明 N/A，保留必要上传/跨站防护。
- `scripts/download_source_data.py`: 原始历史下载/校验脚本纳入 immutable manifest，作为审计依据，不随意覆盖。
- `.env.example`: 增加可配置 `MODEL_BASE_URL` 与调用超时；未配置 Key 默认没有付费授权。
- `docs/plan/README.md`, `AGENTS.md`, `PROJECT_CHECKLIST.md`: 统一入口和分阶段验收。
- `data/raw/README.md`: 说明“历史审计成功”和“Windows 开发环境仍需验证”的区别。

基线 V1.3 的独立证据脚本和统计结果未修改。原数据必须由 Codex 在用户环境再核对。被覆盖的 V1.3 方案保留在此前 ZIP 中；V1.4 的明示澄清按 `21` 优先。
