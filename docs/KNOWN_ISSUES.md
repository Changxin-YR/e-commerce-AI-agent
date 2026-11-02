# 当前已知问题（D1 收尾）

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
- **D2—D9 / NOT_STARTED**：尚未交易数据库导入、业务 API、真实 Agent 或完整系统验收。人工 gold、论文与正式学术实验继续延期。

证据目录和每次失败/通过的实际命令见 EVIDENCE_INDEX.md；D1 当前无未解决的阶段阻断。
