# 2026-11-05 修复：环境 ACL、依赖与 STREAM-02

- **ENV-01 / RESOLVED**：项目 `.venv`、`node_modules`、`data/runtime` 与源码带旧沙箱“低完整性”标签，导致 `.venv` Python 无法写 D 盘缓存/临时目录；首轮 pytest 196 setup errors、E2E 3 failed/9 did not run。已对项目树重设 Medium 完整性，失败日志保留，重跑 282 pytest / 12 Edge 通过。
- **ENV-02 / RESOLVED**：`frontend/node_modules/@esbuild/win32-x64` 缺少 `esbuild.exe`，Vitest 启动即失败。按 `package-lock.json` 执行 `npm ci` 修复，锁文件未改。
- **DATA-01 / RESOLVED**：`data/raw` 缺少官方 ZIP/XLSX，E2E 导入链无法运行。从 D9 封存缓存恢复并按 `data/manifest.json` 复核 SHA-256；文件仍在 `.gitignore` 内。
- **STREAM-02 / LOCAL_RESOLVED, LIVE_NOT_RETESTED**：模型末轮 `message` 未转义双引号导致的语法失败，新增 `tolerant_json.parse_decision` 做语法级恢复；schema、证据引用、金额一致性与 B2 对账校验未放宽。5 项新增回归通过；本轮 0 次真实模型请求，真实追问仍不能宣称通过。
- **STREAM-03 / OPEN / 外部服务阻断**：供应商 TLS/HTTP 间歇失败仍未解决，本轮未关闭证书校验、未自动重试、未扩预算。

完整修复记录与测试结果见 [fix-and-targeted-tests-20261105.md](fix-and-targeted-tests-20261105.md)。

# 2026-11-03 最新补充：连接复用及真实报告验证

当前 PARTIAL：本地工程 PASS，真实首轮“我有哪些数据？”已生成并核验报告，连续追问仍未通过（模型 JSON 格式错误后，纠错轮上游 MODEL_HTTP_ERROR）。连接复用降低重复握手；仅格式纠错不再携带工具定义，限额与校验不变。最后省略空 tools 字段通过本地测试，未再次付费复测。

测试：277 项完整 pytest；最终协议调整后 43 项相关 pytest；39 Vitest；类型检查/构建通过。此前 Edge 12+7 项证据保留，本次只读检查真实对话与报告。累计 17 次请求尝试，已知 88728 token，4 次用量未知，预算占用 156180（不是账单）。

完整证据、成功与失败运行 ID 见 [AI 流式对话升级报告](ai-streaming-upgrade.md)。下方为先前阶段历史记录。不要覆盖用户配置、删除失败数据、自动反复调用付费模型；下一步若要继续排查，应先确认网关结构化输出/无工具请求兼容性及可靠的请求计量。未提交 Git、推送、部署或开始论文实验。

# 当前已知问题（D3 收尾）

- **K01 / OPEN / 非阻断**：4 个 npm moderate 均为 @vue/test-utils 的间接开发依赖：js-beautify 1.15.4、glob 10.5.0、editorconfig 1.0.7、minimatch 9.0.9。两个根告警为 glob 取消后遍历及 minimatch 模式放大资源消耗。生产 audit=0；不进行未经评估的主版本强制升级。分析、影响和建议见 D0_CLOSEOUT.md。
- **K02 / RESOLVED**：Starlette 优先使用 httpx2。约束安装仅新增 httpx2/httpcore2/truststore；31 项 D0 回归及最终 70 pytest 均无原弃用警告。
- **K03 / RESOLVED**：D0 首次 pytest 缓存父目录缺失；历史失败保留，修复已验证。
- **K04 / RESOLVED**：D0 归档目录审批服务曾 503；当时正常重试后成功，保留历史说明。
- **K05 / INFO**：D0 npm glob/esbuild/颜色环境提示保留于原日志；本轮未改前端锁或源码，旧前端/Edge 证据已核对，未冒充重新执行。
- **K06 / RESOLVED**：原仓库无提交；已建立本地 D0 基线，D1 提交单独封存。敏感路径、原始文件和大文件均检查排除；新增 .gitattributes 保持不可变交接字节。
- **K07 / RESOLVED**：本轮首次 npm audit 与来源 HEAD 网络 TLS 失败；后续实际重试成功，原失败记录保留。官方 ZIP 实际下载成功，未禁用 TLS 验证。
- **K08 / RESOLVED / 核查脚本**：首次 Git 敏感模式检查把空 MODEL_API_KEY 的下一行误判为值，Windows stdin 换行也导致忽略检查误报。限定空白为水平空白、改为 argv 传路径后通过；没有发现实际密钥，首次失败日志保留。
- **K09 / INFO / 历史格式**：基线 diff --check 检出不可变旧 Markdown 的行尾双空格（换行标记）。按字节哈希保护规则保留，不修改旧资料；D1 新增修改单独检查。
- **K10 / RESOLVED / 格式核查**：关闭自动换行转换后，首次 D1 diff 检查将 Windows CRLF 的 CR 误作尾空白。通过 whitespace 属性接受 CRLF，保持文件字节；同时移除新增加的 README 末尾空行，复查通过。
- **数据局限 / 已记录**：135080 客户号缺失、1454 描述缺失、5268 重复候选全部保留；2011-12 不完整；时区未声明；交易行金额含费用条目。不是 D1 阻断，也不能宣称是完备客户分析或财务收入数据。
- **D4—D9 / NOT_STARTED**：D3 确定性指标、三项工具与查询历史已完成；业务页面、Agent 与完整系统验收仍待后续。人工 gold、论文与正式学术实验继续延期。

证据目录和每次失败/通过的实际命令见 EVIDENCE_INDEX.md；D3 当前无未解决的阶段阻断。

- **K11 / INFO / 单机边界**：一个写入执行器；其他进程可查询和复用批次。未知 workbook SHA 拒绝，需要新审计版本。超时为有限输入下的协作式期限，不是进程沙箱硬超时。
- **K12 / INFO / 前端范围**：当前页面仍是健康连接页，D2 使用 HTTP/CLI 导入；浏览器 2 项回归并不证明导入 UI 已实现。后续 D4 才实现业务页面。
- **K13 / INFO / 测试输出**：本轮 Edge 2 项通过，Node 保留 NO_COLOR/FORCE_COLOR 环境提示；Python 116 项测试无弃用警告。
- **K14 / INFO / 运行文件**：676319232 字节运行库位于 D2 缓存/runtime，交付/运行数据另存同 SHA 备份。缓存清理会影响该运行库；保留备份后才可主动清理。磁盘/数据库自身不可写时需先恢复存储，再重新提交失败导入。

- **K15 / RESOLVED / 格式检查**：D2首次staged diff检查发现新locks.py文件末尾多余空行（退出2）；已移除，最终diff复查通过。失败与复查记录均保留。


- **K16 / RESOLVED / Windows竞争**：D3第二次全量pytest发现并发首建归档锁文件时，在锁外初始化字节可能碰到另一持有者并抛PermissionError，被导入层误报CORRUPT_SOURCE。改为无缓冲打开、先取得OS锁后初始化；并发回归与96次真实锁争用测试通过。
- **K17 / RESOLVED / D3测试目录**：首次pytest的指定basetemp父目录未建立，69通过/85 setup errors。补建本任务pytest父目录后继续，不复用失败运行目录；失败证据保留。
- **K18 / INFO / D3运行库**：当前.env改指D3缓存/runtime。D2库保留；D3数据库和封存备份路径/SHA见D3_DELIVERY。清理缓存前必须保留实际运行库；本轮最终有2份显式保存的查询记录。
- **K19 / INFO / 覆盖与页面**：覆盖以观测日界为依据，不证明中间每一天有交易；空缺月份返回NO_DATA/null。真实JSON的Edge刷新已通过，但Vue历史/导入/月度页面仍属于D4。
- **K20 / INFO / 版本和调用范围**：目前只支持retail-v1.2与三项内部工具，不提供自由SQL或模型。definitions无dataset时snapshot_hash=null；其余结果有明确快照身份。全系统验收仍未完成。
- **D3输出补充**：最终158 pytest无警告；8 Vitest和2 Edge重新执行通过，Edge仍有颜色环境提示。K05/K13为历史轮次记录，不能作为本轮未执行的说明。npm依赖未变，本轮未重新audit。


## D4 当前覆盖（上文 D4 未实现描述为历史快照）

- **K12/K19 / RESOLVED_IN_D4**：Vue上传、轮询、质量、月度金额与保存历史已完成；E08/E10业务链真实Edge通过，不再只以JSON页面替代。
- **K21 / RESOLVED / 测试执行干扰**：首轮Edge完整导入后，运行期间修改Vite配置造成热重启，业务断言因页面切换超时（1 failed/2 skipped/2 passed）。固定源码完整重跑5 passed；两轮证据均保留。
- **K22 / INFO / 两份数据库**：默认D4运行库保留D3的2条历史；独立首次UI导入库有5条历史，分别封存，路径/SHA在d4/verification.json。清理缓存前保留运行库和备份。
- **K23 / INFO / 移动布局**：390px页面无整体横向溢出；精确金额表可横向滚动查看完整列。桌面和移动截图留档。
- **D5—D9 / PENDING**：八工具补全、真实LangGraph、报告/五视图及最终验收继续推进。模型预算为0，真实模型BLOCKED_AUTHORIZATION；fake-provider不能充当真实调用证据。
- **未变遗留**：4项npm moderate开发依赖告警未在D4升级或重新audit；Edge保留NO_COLOR/FORCE_COLOR提示，Python158测试无警告。

- **K24 / RESOLVED / 封存检查**：首次staged diff检出business.spec.ts末尾空行，已移除。首次提交因本机未设作者失败；沿用先前Codex <codex@localhost>，仅本次git -c设置作者，不修改全局用户配置。失败命令与复查保留。

## D5 当前覆盖

- K20的三工具限制已在D5解除，八工具实现并通过真实数据验证；仅retail-v1.2，任意SQL/模型外呼仍不可用。
- K25 / RESOLVED：首次pytest父目录遗漏导致73 setup errors，补建新目录；第二轮一项AppError错误码匹配预期修正。最终195通过，失败证据全部保留。
- D6—D9继续：真实模型预算0、BLOCKED_AUTHORIZATION；fake-provider结果只能证明离线工程逻辑。最终实机验收仍待用户。
- 当前.env数据库改指D5缓存/runtime，D4封存库未改动。清理任务缓存之前必须保留实际使用库/交付备份。

- D5封存diff首次发现两份新增日志末尾空行，已移除；失败与复查命令保留。

## D6 当前覆盖

- D6真实LangGraph代码和离线流程已验证；真实模型BLOCKED_AUTHORIZATION，尚未验证真实供应商tools/用量/五场景表现。DeepSeek适配层仅通过MockTransport，不能据此声称联网成功。
- 首次全量3项旧doctor/OpenAPI预期失败，更新到D6后224通过，失败日志保留。安装pip短暂超时重试成功。
- 首次官方HTML提取输出遇Windows GBK编码，使用UTF-8后读取成功；非业务执行失败。
- B2机械核验覆盖显式条件、金额引用和可对账关系；自由语言语义/解释仍需真实模型及最终用户验收。配置/代码变化后的待补答任务拒绝强制恢复，应新建关联run。
- 当前.env指向D6缓存/runtime，旧D5库保留；D6运行库含两轮明确标识的scripted开发任务，不能冒充真实模型任务。清理缓存前保留数据库与checkpoint配套备份。
- D7报告/五视图、D8安全稳定、D9最终复现尚待完成。npm4项moderate开发依赖告警仍为历史未解决项。
- D6封存diff首次发现新增文档末尾空行，已移除；随后发现原始失败XML中pytest自带的缩进空行，按该单个证据路径关闭whitespace检查，保留原始XML字节。两次失败及复查记录在缓存/commands。

## D7 当前覆盖（覆盖上述历史待实现描述）

- D7报告/五视图已实现并验证；238 pytest、25 Vitest、8个浏览器最终用例通过。无实际模型验证，BLOCKED_AUTHORIZATION继续保留。
- 首次13项pytest setup error因pytest父目录缺失，补建后全部通过；原记录保留。
- 首次浏览器发现favicon.ico 404，新增本地SVG图标修复；报告导出按钮对比度、导航滚动位置与移动分页已修正并截图复核。
- 两次全量浏览器仍有D3旧schema断言，均已更新到0004_agent_runtime；最终2项健康定向回归通过。最后完整轮的7过/1失败原JSON保留，不伪称该命令退出0。
- D7默认运行库与独立浏览器库分别保存；D6两库保留。恢复旧D6未终结任务仍受代码配置哈希限制，须按RUN_CONFIG_CHANGED提示重新运行。
- D8安全稳定和D9复现验收待继续；4项npm moderate开发依赖告警仍为未解决历史项。用户最终验收不能由Codex代授。

## D8 当前覆盖

- D8请求大小/头部歧义/键名脱敏/Markdown CR/健康兼容问题均修复复测。263 pytest、28 Vitest、完整9 Edge通过。首次失败记录保留。
- K01仍OPEN：npm生产0、开发4moderate；无high/critical，fix dry-run changed=0。Python68项固定依赖本次未发现已知漏洞；不代表所有供应链风险不存在。
- D7原库保持SHA；D8默认库含继承与新增共45个scripted任务+3个B0报表。真实模型仍BLOCKED_AUTHORIZATION，费用和未知用量不伪装为真实零费用结果。
- D9干净复现、当前README改写和完整功能矩阵待继续。最终实机验收仍由用户完成。

## D9 最终覆盖（以上阶段待实现描述为历史）

- D0—D9离线工程/干净复现完成，263 pytest/28 Vitest/9 Edge通过。实际模型F06—F09仍BLOCKED_AUTHORIZATION，最终用户实机未验收，不称FULL PASS。
- 首次Agent复跑因输出目录同名复用已有提交键，API正确200但脚本期望202；改为每轮UUID后114项通过。首次metrics新导入当前schema模块时缺sys.path，修复后85项通过；原失败保留。
- 独立复现目录先命名reproduction，安装后改名ecommerce-agent-thesis满足不可变project-name检查；实际管理器、测试均使用改名后Python -m入口，源码/锁一致。
- K01依旧：npm4项moderate开发依赖，生产0；Python68项同锁本次无已知漏洞。没有代码分发许可证，不擅自授予开源许可。
- 默认D9库63任务/63报告，60个明确scripted记录+3个B0；clean-runtime只有1个B0和1条查询，无模型尝试。源码/配对数据库/全部失败与最终证据封存。清缓存前保存库。
- 需要用户完成实机验收；真实模型费用授权、真实模型冒烟、论文和正式实验是后续独立门禁。当前无已知未修复严重工程缺陷。


## 2026-11-03 UI 当前边界

- UI 范围 PASS，无已知新增阻断级缺陷。390px 长警告横向溢出已修复。
- 本轮曾因完整导入/上传等待超时导致 2 失败、6 跳过；保留失败证据，环境资源紧张时用有界 E2E_IMPORT_TIMEOUT_MS；最终独立 10 项通过。
- 真实模型 CONFIGURED_UNVERIFIED，未在 UI 任务中收费测试；脚本 B2 只证明执行/补答工程链路。旧 D9 BLOCKED_AUTHORIZATION 是历史快照。
- 浏览器覆盖 Edge 与指定四宽度；未运行 Firefox/Safari，未完成整套读屏审计。文本对比自动扫描通过不等于全项 WCAG 认证。
- GitHub API 限流，使用实际读取的 raw 分支源码，commit SHA 未核实；项目无 ESLint 配置，本次未安装。

## 2026-11-03 流式对话升级

- STREAM-01 / RESOLVED：固定预占整笔 32768 token 导致第二轮必败，已改为本次请求的保守预占，保留所有预算边界与未知消耗。
- STREAM-02 / IMPLEMENTED, LIVE_NOT_FULLY_VERIFIED：模型工具结果重复 result/data 造成非法引用。送模结构已统一、中文约束及纠错提示已强化；实际最终报告尚受连接问题阻断，未放松引用校验。
- STREAM-03 / OPEN / 外部服务阻断：供应商 TLS 间歇性 UNEXPECTED_EOF_WHILE_READING，完整真实分析未通过。连接失败已单独显示，未关闭 TLS 或扩大额度。
- STREAM-04 / RESOLVED：导入异步完成抢回页面、分析 run 参数丢失、矮窗口输入框遮挡均已修复并浏览器回归。
- 真实请求/额度与离线夹具严格区分，完整报告见 ai-streaming-upgrade.md。
