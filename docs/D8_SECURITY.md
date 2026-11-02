# D8 安全与可靠性审查

范围是本机单用户应用的实际输入面。审查采用 security-best-practices 技能中的 FastAPI/Vue 指引，并以本项目固定数据、只读工具、localhost 和零真实模型预算约束为准。不是生产安全认证。实际命令与最终数量见 `docs/evidence/d8/verification.json`。

## 发现与修复

| ID | 影响/级别 | 复现与处理 | 位置 |
|---|---|---|---|
| D8-01 | 中：JSON 在模型字段校验前无字节限制，可能占用过多内存 | 超过65536字节在业务代码前返回413；不信任Content-Length，分块/伪造长度同样限制；慢请求15秒返回408 | `backend/app/security.py`，`tests/test_security.py` |
| D8-02 | 低：多个Origin头仅取首值，存在解析歧义 | Host/变更请求Origin都要求唯一；拒绝null、错误端口、后缀欺骗；浏览器真实跨源表单403且报告数不变 | `backend/app/main.py`，`frontend/e2e/reports.spec.ts` |
| D8-03 | 中：脱敏只处理字典值，嵌套字段名中的配置密钥未替换 | 递归处理键与值；使用明确假密钥回归。未发现真实密钥泄漏，当前也未配置密钥 | `backend/app/agent/budget.py`，`tests/test_security.py` |
| D8-04 | 低：Markdown文本中的CR未规整，页面缺少防嵌套头 | CR/LF统一为空格；保留HTML/Markdown转义与attachment下载；API和本地Vite页面增加nosniff、DENY、frame-ancestors与no-referrer，关闭开发资源CORS | `backend/app/reports.py`，`frontend/vite.config.ts` |
| D8-05 | 功能回归：前端把健康阶段写死为D7，后端D8被误判不可用 | 验证服务身份和完整数据库结构，阶段接受D加数字；D8/D9回归，实际停服/重启重测 | `frontend/src/api/health.ts`，`frontend/tests/health.test.ts` |

上述新测试最初10失败/8通过，其中一个失败来自测试误用了不存在的`/api/v1/queries`列表路径；此断言已移除，真实历史分页在已有metrics测试覆盖。其余失败驱动上述修复。修复后新增25项后端用例通过。首次全量pytest还有一项旧OpenAPI版本断言；修正后全量通过。所有原始失败保留，未覆写。

## 实际安全矩阵

| 契约 | 判定及依据 |
|---|---|
| S01/S02/S03/S11 任意URL抓取/网页指令/抓取重试 | NOT_APPLICABLE：无用户指定URL抓取与发送功能。没有访问禁用地址。模型来源内容仍经工具白名单和输出schema验证。 |
| S04 ZIP/XML/上传 | 实测通过：50MiB上传；单XLSX外层ZIP；条目数/总解压量/200倍压缩比限制；路径/符号链接/重复条目/不支持压缩拒绝；defusedxml拒绝实体；外链/宏/公式及未知SHA拒绝；超时/中断不发布部分快照。详见`test_imports.py`、`test_security.py`及真实浏览器导入。 |
| S05 CSV/Excel公式导出 | NOT_APPLICABLE：只提供JSON与纯文本Markdown。请求CSV格式422；导入公式有拒绝测试，不冒称CSV导出测试。 |
| S06 非法参数/SQL/路径 | 实测通过：严格schema/日期/分页/白名单工具，SQL值参数化；恶意筛选视为文本空结果，不能执行SQL；交易明细最多50条；请求体在解码前受限。 |
| S07 未授权模型 | 实测通过授权拒绝：付费false、真实总请求/Token/每run Token为0；HTTP适配层仅mock测试，脚本provider不能从普通配置/API选择。实际模型能力仍BLOCKED_AUTHORIZATION。 |
| S08 重复/恢复/预算 | 实测通过离线机制：同提交键/补答键/报告身份幂等；进程终止后的SENT转UNKNOWN_OUTCOME，保留32768占用；恢复新增尝试而不抹除未知用量；共享总预算限制新run。 |
| S09 GET历史 | 实测通过：多次报告/任务GET及重启刷新结果与用量不变，不调用provider、不新增报告。 |
| S10 输出与凭据 | 实测通过假密钥保护、异常栈/内部路径隐藏、Vue文本渲染、Markdown转义与安全附件名。真实配置无密钥，真实密钥扫描标N/A；禁止把“没有密钥”写成实际密钥泄漏检测成功。 |
| S12 localhost/CSRF | 实测通过Host/Origin负例及真实Edge跨源表单403；正常页面仍可导入/生成报表/补答。无通配CORS凭据。 |

`BoundedBodyMiddleware`只对普通API采用64KiB缓冲；上传保留既有分块写盘与50MiB上限，避免将官方文件整体读进内存。`manage.py test --scope all`可顺序执行后端、前端、构建和完整浏览器测试；浏览器报告使用当前配置的已导入数据库副本，也支持`E2E_SOURCE_DATABASE`指定已审计源库。

## 依赖与剩余限制

Python的68项固定依赖经独立pip-audit 2.10.1、PyPI已知漏洞数据检查，未返回已知漏洞；`pip check`通过。锁文件没有逐包SHA，pip-audit对此保留建议提示；这不是供应链完整安全保证。审计工具安装在D8缓存独立环境，没有改项目依赖。

npm生产依赖审计为0；开发依赖仍4项moderate（glob/minimatch及其上游js-beautify/editorconfig），无high/critical。`npm audit fix --dry-run --json`实际结果changed=0；未强制跨主版本覆盖。风险限于开发测试工具的文件匹配输入，应用不开放这些工具作为上传处理器。保留K01，不将全依赖审计标为零漏洞。

运行仍为本机单执行器，解析超时为有界输入下的协作期限；不提供任意工作簿、生产多用户或公网部署保证。真实模型冒烟、最终用户实机验收继续未完成；论文和正式学术实验延期。D7原运行库和checkpoint保持原SHA，D8只使用阶段副本。
