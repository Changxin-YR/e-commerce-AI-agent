# D0 收尾核查（2026-11-02）

本轮用户明确授权 D0 收尾和 D1；D0 历史交付保持原样。111 个源码文件与 D0 SOURCE_MANIFEST.json 的 SHA-256 全部一致，25 份命令记录的 stdout/stderr 可定位。保存的 smoke 输出包含 31 pytest、8 Vitest；Edge results.json 为 expected=2、unexpected=0、skipped=0。核查原始结果见 D1 缓存 d0-review.json。

## npm 依赖审计

本轮首次 npm audit 因 TLS 中断退出 1；重试实际成功取得报告，退出 1 表示仍有 4 项 moderate（high=0、critical=0）。npm audit --omit=dev 退出 0，漏洞数 0。以下版本由 package-lock 与 npm ls 同时确认，全部 dev=true。

| 依赖 | 实际版本与链 | 告警及影响 | 修复建议 |
|---|---|---|---|
| glob | 10.5.0，@vue/test-utils 2.4.11 → js-beautify 1.15.4 | GHSA-3g3m-2fjr-6pw4：AbortSignal 取消后仍可能继续遍历文件系统，资源消耗；同时继承 minimatch 告警 | 等待 js-beautify 支持修复版本；当前约束 ^10.4.2，报告受影响版本最高 14.0.1，不能直接强制跨主版本覆盖 |
| minimatch | 9.0.9，glob 与 editorconfig 共用 | GHSA-g3hv-75wg-m249：globparts 放大导致拒绝服务；报告受影响 <11.0.1 | 需上游适配 >=11.0.1；当前两个父依赖分别约束 ^9.0.4/^9.0.1 |
| editorconfig | 1.0.7，js-beautify → editorconfig | 通过 minimatch 间接受影响，不是第三个独立漏洞 | 更新兼容上游后重新锁定与验证 |
| js-beautify | 1.15.4，@vue/test-utils → js-beautify | 通过 glob/editorconfig 间接受影响，不是第四个独立漏洞 | 评估 @vue/test-utils/js-beautify 的兼容升级，复跑 Vitest、构建与浏览器测试 |

本项目链路用于测试输出格式化，未在 frontend/src 中引用；生产依赖审计无上述包。依赖存在不等于已经证明能从当前应用远程触发，但处理不可信匹配模式/文件树时有资源风险。本轮保留锁文件，未执行 npm audit fix --force 或添加跨主版本 override。npm 的 fixAvailable=true 不是兼容性证明。告警原始 URL 保存在命令 JSON 输出中。

## 测试客户端弃用提示

实际 Starlette 1.10.0 testclient.py 优先导入 httpx2，回退 httpx 时发弃用警告。先以 requirements.lock 约束执行 pip dry-run，仅新增 httpx2=2.16.0、httpcore2=2.16.0、truststore=0.10.5，不升级已锁运行依赖。安装后 31 pytest 全部通过且无警告，pip check 通过。保留 httpx 供现有工程测试工具使用；新增版本已进入 requirements.in/lock。

## Git 与排除

初始 HEAD=UNBORN。已检查 .env/.env.*、虚拟环境、node_modules、数据库及 raw 目录的忽略规则；补充密钥容器、各 SQLite sidecar、ZIP/XLSX 的排除。提交前检查候选文件、敏感模式和文件大小。基线提交使用本地 Codex <codex@localhost> 身份（本机未配置作者），不伪称用户签名，不推送远程。实际 SHA 将在 D1 状态和 Git 证据中记录。

所有本轮命令、退出码与输出：D:/codex产出/电商智能体_D1真实数据审计/缓存/commands；最终交付保留副本。旧 D0 文档中的未提交/警告状态是历史事实，以本文件与最新 STATUS 为当前状态。
