# GitHub 参考调研

日期 2026-11-03。实际通过 HTTPS 下载 GitHub raw 文件并阅读 README、组件实现、package.json 与许可证。原文件保存在 D:/codex产出/电商智能体_AI前端全面优化_20261103/缓存/references。manifest.json 和 supplement.json 保留失败记录。GitHub API 返回 403 rate limit exceeded，无法核实分支精确 commit SHA；以下是抓取时分支快照，不宣称最新发布版。

| 项目 / 实际阅读位置 | 借鉴与适用原因 | 不直接照搬 / 兼容性 |
|---|---|---|
| [Vben Admin](https://github.com/vbenjs/vue-vben-admin) main README.md、package.json、LICENSE、[layout.vue](https://github.com/vbenjs/vue-vben-admin/blob/main/packages/effects/layouts/src/basic/layout.vue) | 页壳分离、菜单/面包屑/内容层次；同为 Vue 3，适合提取轻量 WorkspaceShell | README 明确 5.x 与旧版不兼容；不引入 monorepo stores、权限生成、多标签页和主题配置系统 |
| [Pure Admin](https://github.com/pure-admin/vue-pure-admin) main README.md、package.json、LICENSE、[src/layout/index.vue](https://github.com/pure-admin/vue-pure-admin/blob/main/src/layout/index.vue) | 侧栏与内容布局解耦，按屏幕折叠，源码含 760/990 响应式判断 | 快照 Vue ^3.5.43 与本项目 3.5.44 接近；其 Pinia、Tailwind、Element Plus、路由等均不是本项目必需，不整体迁移 |
| [shadcn-vue](https://github.com/unovue/shadcn-vue) **dev** README.md、package.json、LICENSE、[Button.vue / index.ts](https://github.com/unovue/shadcn-vue/tree/dev/apps/v4/registry/new-york-v4/ui/button)、[Sidebar.vue](https://github.com/unovue/shadcn-vue/blob/dev/apps/v4/registry/new-york-v4/ui/sidebar/Sidebar.vue) | 按钮 default/secondary/outline/ghost 语义、focus-visible/disabled/aria-invalid 状态；桌面与手机导航分别处理 | dev package 2.9.0 是仓库版本，不等于全组件安装版本。代码依赖 Reka UI/Tailwind/CVA；本次用现有 Vue+CSS 实现这些模式。main README 为旧占位资料，已纠正到 dev，不能拿旧分支作当前事实 |
| [Tabler](https://github.com/tabler/tabler) **dev** README.md、package.json、LICENSE、[core/scss/_variables.scss](https://github.com/tabler/tabler/blob/dev/core/scss/_variables.scss) | 清晰的中后台密度、可配置 CSS/Sass tokens、关闭渐变、reduced-motion、统一尺寸 | Bootstrap 5 为基础；引入整包会重复 reset 与布局。只参考密度和语义层次，不引入 Bootstrap、插件集合或图标包 |
| [Element Plus](https://github.com/element-plus/element-plus) dev README.md、LICENSE、packages/element-plus/package.json、[form.vue](https://github.com/element-plus/element-plus/blob/dev/packages/components/form/src/form.vue)、[var.scss](https://github.com/element-plus/element-plus/blob/dev/packages/theme-chalk/src/common/var.scss) | 字段标签、校验信息、表单状态与 tokens 分层；复用原生 required 和明确字段错误 | peer Vue ^3.3.7 可容纳 3.5.44，但本次不安装；dev 包版本 0.0.0-dev.1 不是发布版。不复制其校验依赖/命名空间运行时 |
| [shadcn/ui](https://github.com/shadcn-ui/ui) main README.md、LICENSE.md、package.json、[sidebar.tsx](https://github.com/shadcn-ui/ui/blob/main/apps/v4/registry/new-york-v4/ui/sidebar.tsx) | 桌面侧栏与移动开关独立；状态可控、可访问标签与键盘交互 | React/Radix 组件不能直接用于 Vue。本项目用 Vue 实现非模态折叠菜单，不引入 React 或全局快捷键冲突 |

六个项目读取的许可证均为 MIT。若未来复制实质代码或分发其依赖，须保留对应版权与许可声明；本次借鉴交互原则，独立实现组件，没有复制上游组件、安装新 UI 依赖或改变本项目代码许可。下载副本中的原 LICENSE 保留。

Vue Flow 未采用：仓库没有图编辑器，LangGraph 后端任务不等于前端画布，故不创造流程编辑器依赖。

未核实：API 限流下的 commit SHA；Tabler core/scss/_tables.scss、最初猜测的 Vben 核心 layout 路径和 Pure sidebar/vertical.vue 均 404；不声称读过这些路径。实际参考用上表成功读取文件替代。外部线上演示没有执行交互测试，未借其数据作产品数据。

落地选择：保留 Vue 3 + 原生控件 + CSS tokens；抽取统一页壳、SVG 图标、状态标签；高饱和马卡龙色只用于 AI 入口和少量功能区，保留中性色工作面、真实数据、精确金额与现有安全边界。
