# D9 工程验收矩阵

2026-11-03（Asia/Shanghai）：离线工程与独立安装复现完成，交付状态READY_FOR_USER_ACCEPTANCE。**全功能不能标FULL PASS或USER_ACCEPTED**：F06—F09的实际模型链仍BLOCKED_AUTHORIZATION，真实调用0，最终用户实机验收未进行。机械核验、追问/重启/预算等脚本工程测试通过不能替代实际模型。

## F01—F16

| ID | 能力 | 状态 | 证据/限制 |
|---|---|---|---|
| F01 | 官方数据取得与导入 | READY | import 41项/原SHA复核；本轮使用先前官方取得原件，来源下载证据仍保留于D1 |
| F02 | 原值/分类/质量/幂等 | READY | 新库541909行，四类及四个千分价/重复候选独立对账 |
| F03 | 月度精确金额/空集/覆盖 | READY | metrics 85项、浏览器月度21项独立SQL |
| F04 | 排名/序列/比较/拆解 | READY | 八工具57HTTP/265断言 |
| F05 | 八工具schema与边界 | READY | tools-verification与pytest非法参数/上限/空集用例 |
| F06 | 真实模型B1多轮调用 | BLOCKED | BLOCKED_AUTHORIZATION；真实调用0，scripted多轮工程测试通过 |
| F07 | 真实模型B2核验与恢复 | BLOCKED | 机械核验/错误注入/有限恢复pytest通过；实际模型未冒烟 |
| F08 | 真实模型追问重启恢复 | BLOCKED | 同run/thread、重复补答和中断预算的脚本15任务/114断言通过；实际模型链未验证 |
| F09 | 真实模型不支持问题回答 | BLOCKED | 工具与脚本provider拒绝利润等字段通过；实际模型措辞/工具选择未验证 |
| F10 | 五视图/交互/错误 | READY | 完整9项Edge，桌面与移动截图；模型阻断和fixture明确展示 |
| F11 | 报告保存/引用/导出 | READY | 浏览器报表158/默认端口报表92独立SQL，JSON/Markdown下载 |
| F12 | 历史只读无重复调用 | READY | 重启前后报告/任务/导出相同、模型尝试未增加 |
| F13 | 上传/SQL/CSRF/XSS/密钥 | READY | D8安全矩阵、D9全量25项新增安全回归/跨源表单；CSV导出N/A |
| F14 | Windows独立安装/迁移/启动停止 | READY | 新.venv/npm ci、空库迁移、完整导入、默认8000/5173的23检查；停止使用自有进程树终止 |
| F15 | 自动化回归 | READY | 干净环境统一test --scope all退出0：263 pytest/28 Vitest/9 Edge/构建 |
| F16 | 工程可复现/无伪造研究 | READY | 固定依赖完全匹配、可执行源码逐字节一致、55契约、源SHA和本地提交；论文/正式实验未开始 |

READY仅表示工程交付准备完成，最终确认属于用户。原不可变FEATURE_ACCEPTANCE仍保留原字节；本页和evidence/d9/acceptance-matrix.json记录实际结果。

## E01—E10

| ID | 状态 | 实测依据 |
|---|---|---|
| E01 | PASS | 新库import分类/源SHA/原值 |
| E02 | PASS | ZIP/XLSX重复上传+CLI复用，未翻倍 |
| E03 | PASS | metrics9/10月精确值、前端显示与独立SQL |
| E04 | PASS | 四条0.001原始1E-3及整数千分价1 |
| E05 | PASS | 2011-12 PARTIAL_PERIOD、范围外NO_DATA |
| E06 | PASS | 负价/非C负数量/零价/重复候选独立抽查 |
| E07 | PASS | 参数化SQL、白名单/非法参数/Host-Origin |
| E08 | PASS | 真实浏览器保存查询/报告刷新、GET无模型副作用 |
| E09 | PASS | 损坏ZIP/超限/攻击输入拒绝且旧库保留 |
| E10 | PASS | 干净环境全量自动化、命令退出码/哈希/截图 |

## 本轮实测

独立目录先无.venv/node_modules/数据库，重新pip安装68项固定依赖和npm ci，pip freeze与锁完全匹配。空库迁移后完整导入541909行。统一test --scope all退出0，263 pytest、28 Vitest、9 Edge和构建通过。独立导入41、月度85、八工具265（57 HTTP）、脚本恢复114、默认端口启动/报告/重启23、默认报告独立SQL92、浏览器报表158/月度21项通过。

实际Python3.12.15/SQLite3.53.1/Node24.22.0/npm11.19.1/Edge，证据命令在D9缓存/commands。源码复制后文件夹由reproduction改名ecommerce-agent-thesis，以符合不可变项目名校验；安装来自全新依赖环境，最终运行使用该目录.venv，未借用原项目依赖。可执行源码逐文件与原仓库一致。完整界面在1280×900与390×844核对。

默认端口8000/5173实际启动并终止自有进程树，重启读取同报告，未模拟人工Ctrl+C。明细一次最多50条，本轮实际响应40105字节；首次完整导入内部处理151.39秒。仅为本机观察，不是性能承诺或正式学术实验。

## 仍需用户完成

- 按D9_OPERATIONS亲自操作并确认最终验收。
- 若要验收F06—F09，另行提供明确模型预算授权/实际模型ID与凭据，执行B1/B2单月、比较、追问恢复、unsupported/工具错误等真实冒烟，保存实际提供方/用量；未授权前预算保持0。
- npm4项开发moderate保留；生产0、Python固定依赖无已知漏洞（D8审计，同锁未变）。无公网发布、多用户或代码分发许可证承诺。论文/gold/正式实验继续未开始。
