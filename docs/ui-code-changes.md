# 前端修改清单

源码在原仓库实施；交付和截图在 D:/codex产出/电商智能体_AI前端全面优化_20261103/交付。

| 文件 / 页面 | 实际变化 | 保留的业务行为 |
|---|---|---|
| frontend/src/navigation.ts | 六业务视图统一元数据；默认 AI 首页；保留旧 query 深链接 | 原 view/query/run/report 参数兼容 |
| components/WorkspaceShell.vue | 统一侧栏、功能分组、位置导航、动态标题、移动折叠菜单、跳转内容与焦点返回 | 服务状态和全部六个业务入口可达 |
| components/AppIcon.vue / StateBadge.vue | 本地 SVG 与语义状态复用 | 图标装饰隐藏于辅助技术；状态仍有文字 |
| style.css | 扩展既有 tokens 为紫色 AI 品牌与三种马卡龙辅助色；统一字体、控件、表格、间距、响应式 | 表格内部滚动，不截断业务值；无外部字体或新增 UI 库 |
| RetailWorkspace.vue：概览 | 参数工具条、真实月度摘要、精确表格、AI 继续分析入口 | 金额保持字符串；两位显示和三位原值都保留，来源与警告可展开 |
| RetailWorkspace.vue：导入 | 文件选择分区、质量统计、进度、失败与重试样式 | 官方 ZIP/XLSX、50MiB、哈希审计、幂等复用与轮询未变 |
| RetailWorkspace.vue：历史 | 统一记录列表、可操作空态、服务端分页、加载/错误分离 | 历史打开仍 GET，不重算或调用模型 |
| AgentWorkspace.vue：分析 | 主 AI 输入、示例填入/编辑、真实模型能力状态、三步执行说明；B0 表单移为下方支持功能 | B1/B2 方案、4000 字限制、当前数据集、模型授权拦截、B0 所有参数保留 |
| AgentWorkspace.vue：任务 | 真实阶段译名、工具执行记录、补答区、用量、取消 dialog | revision 和幂等键、轮询、同 run 补答、恢复/重跑 API 不变；取消需确认 |
| AgentWorkspace.vue：报告 | 结论/数值/导出/来源/警告分层，参数 JSON 折叠、移动长标识换行 | 精确值、证据字段、内容哈希、JSON/Markdown 导出与来源任务都保留；不使用 v-html |
| AgentWorkspace.vue：状态 | 日期范围及基期成对校验；beforeunload 未提交提醒；切页保留草稿；晚返回请求不抢回页面；分页失败复原 offset | API 请求结构不变；只增加客户端反馈与防竞态处理 |
| useRetail.ts | AI 默认入口、popstate、历史读取加载状态、切页使旧月查询失效 | 原存储键、接口、数据集选择、精确值校验、保存幂等键保持 |
| HealthPanel.vue | 共用页壳、明确返回 AI 入口、统一连接状态 | 8 秒超时、真实 health JSON 检验、清空过期状态与重试保持 |
| api/agent.ts | 新增 answer/unsupported/clarify 中文展示映射 | 无请求、响应类型、权限或计算契约变化 |
| index.html / public/favicon.svg | 产品标题、主题色与 AI 标识 | 无外部资源、分析代码或埋点 |

## 测试变化

原 28 项 Vitest 断言保留；新增 7 项覆盖 AI 默认/旧链接、移动导航状态、示例只填入不提交、未提交提醒、日期拒绝、模型已配置未验证、晚响应不改用户当前页。原测试使用更明确的健康按钮和导航标签选择器，概览测试显式进入 overview，适配用户要求的 AI 默认首页。

原 9 项 Edge 流程保留。business.spec.ts 使用显式数据/概览入口，既有金额、导入、SQL、刷新、停服恢复断言未减少。reports.spec.ts 新增第 10 项取消确认：默认焦点、Escape、不提前 POST、确认后状态 CANCELLED。

本机资源紧张时完整导入出现超过 240 秒的等待；增加 E2E_IMPORT_TIMEOUT_MS 可选环境变量（240000–900000ms，默认仍 240000ms），只控制测试等待。报表流程的上传结果断言从默认 10 秒对齐应用原有 75 秒上传请求上限。未改变任何数据断言、应用超时或后端导入逻辑；超时失败日志仍保留。

## 影响与边界

没有修改 backend/、数据库 schema、.env、package.json 或 package-lock.json，没有删除页面或业务测试。没有引入 Vue Router/Pinia/Element Plus/Tailwind/React，没有使用 Mock 替换应用真实接口。单元测试继续使用显式 fixture；浏览器业务测试使用独立真实 UCI 数据库和明确标识的脚本模型。

原目录中的 8000/5173 为用户已有服务，测试不关闭这两个进程。浏览器回归自建随机端口、独立库、关闭付费模型，测试自行清理自己创建的服务。

本次未提交 Git、未推送或部署。最初工作区干净，最终变更留在工作区供审阅；旧 D9 封存证据保留。
