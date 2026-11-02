# 电商经营数据分析智能体

本地单用户历史交易分析应用：FastAPI、SQLite/Alembic、Vue 3、LangGraph。使用官方UCI Online Retail 541909行，提供导入与质量、经营概览、智能分析、报告详情、任务记录五项功能，另保留查询历史。金额使用整数千分英镑计算，API返回三位精度字符串。

D9离线工程交付与干净复现已完成。确定性报表B0可直接使用；B1/B2代码与脚本provider工程测试已实现，**实际模型仍BLOCKED_AUTHORIZATION**，没有真实供应商冒烟结果。最终状态与验收数量以`docs/STATUS.json`、`docs/EVIDENCE_INDEX.md`、`docs/D9_ACCEPTANCE.md`为准。用户本人尚未实机验收，论文和正式学术实验未开始。

## 本机启动

项目根目录：`C:\Users\27363\Desktop\毕业论文\电商智能体的实现\ecommerce-agent-thesis`。源码留原位；当前运行库、配套checkpoint与额外交付位于`D:\codex产出\电商智能体_D9最终工程交付`。备份前停止服务，成对保留业务库和checkpoint。

已安装的本机环境无需重复初始化。两个PowerShell窗口分别执行：

```powershell
Set-Location 'C:\Users\27363\Desktop\毕业论文\电商智能体的实现\ecommerce-agent-thesis'
python scripts/manage.py backend
```

```powershell
Set-Location 'C:\Users\27363\Desktop\毕业论文\电商智能体的实现\ecommerce-agent-thesis'
python scripts/manage.py frontend
```

浏览器打开`http://127.0.0.1:5173`。后端健康为`http://127.0.0.1:8000/healthz`，接口文档为`http://127.0.0.1:8000/docs`。服务仅监听本机；端口冲突会失败。停止时在各窗口按Ctrl+C。

## 首次安装或独立复现

实测环境：Windows 11、Python 3.12.15、Node.js 24.22.0、npm 11.19.1、Git 2.56.0、SQLite 3.53.1。最低Python3.11、Node22.12；浏览器测试使用已安装Microsoft Edge。

用户先创建`D:\codex产出`。独立源码文件夹命名为`ecommerce-agent-thesis`（不可变交接校验按此名称识别项目）。在该根目录执行，不覆盖已有.env或数据库：

```powershell
$taskCache = 'D:\codex产出\电商智能体_本地运行\缓存'
New-Item -ItemType Directory -Force -Path $taskCache | Out-Null
$env:D0_CACHE_DIR = $taskCache
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
npm --prefix frontend ci --no-fund
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python scripts/manage.py doctor
python scripts/manage.py migrate
```

模板默认库为`D:/codex产出/电商智能体_本地运行/缓存/runtime/app.sqlite3`。多份独立复现分别设置.env中的DATABASE_URL、D0_CACHE_DIR、IMPORT_CACHE_DIR，避免共用库。管理器自动使用项目.venv，无需激活或改执行策略。使用requirements.lock和frontend/package-lock.json，不自行升级。

```powershell
python scripts/download_source_data.py --download
python scripts/manage.py import-data data/raw/online_retail_uci352.zip
```

也可从“数据与导入”上传官方ZIP/XLSX。只接受已审计SHA，最多50MiB。来源/许可/哈希见data/manifest.json；原文件留在项目data/raw，不进Git或源码ZIP。同内容ZIP/XLSX复用快照，不增加交易行。

## 使用与验证

无模型即可查看2011年9月/10月精确指标、保存查询，在“智能分析”的确定性报表表单生成B0报告、导出JSON/Markdown并重启回看。完整操作、恢复与演示见`docs/D9_OPERATIONS.md`，接口见`docs/D9_API.md`。

```powershell
python scripts/handoff_check.py
python scripts/manage.py test --scope smoke
python scripts/manage.py test --scope e2e
# 或顺序运行全部：
python scripts/manage.py test --scope all
```

smoke执行pytest、Vitest和构建。e2e使用真实Edge、随机本机端口、独立库，从完整导入到概览/报告/历史/停服恢复；补答恢复使用明确的脚本provider。需要项目data/raw下官方两文件及当前配置的已导入库，可用E2E_SOURCE_DATABASE指定另一已审计源库。测试自动停止自己创建的服务，保留失败、trace和截图。

| 命令 | 用途 |
|---|---|
| `python scripts/manage.py doctor` | 实际依赖/端口/SQLite检查，不输出密钥 |
| `python scripts/manage.py migrate` | 显式迁移至0004_agent_runtime，可重复 |
| `python scripts/manage.py build` | 构建到D0_CACHE_DIR/frontend-dist |
| `python scripts/manage.py test --scope backend` | 后端测试 |
| `python scripts/manage.py test --scope frontend` | 前端测试 |
| `python scripts/manage.py verify-metrics --database <库> --output <新目录>` | HTTP/独立SQL核对，会新增一条查询历史 |
| `.venv/Scripts/python.exe scripts/verify_tools.py --database <库> --output <新目录>` | 八工具真实数据/边界核对 |
| `.venv/Scripts/python.exe scripts/verify_agent.py --database <验证库> --output <新目录>` | 开发用scripted恢复验证，会新增夹具任务 |

download-data/verify-data/tools/agent/evaluate是管理器预留别名，返回NOT_IMPLEMENTED；使用上表专用脚本或API。正式实验入口未开放。D0_CACHE_DIR名称为历史兼容，指当前任务缓存。

```powershell
python scripts/record_command.py --output 'D:/codex产出/电商智能体_本地运行/缓存/commands' --label smoke -- python scripts/manage.py test --scope smoke
```

不要把密钥放在命令参数中。模型开关默认false，总请求/Token及每run Token预算0。已有key不代表收费授权；真实模型需要用户明确预算、实际模型ID和供应商冒烟后单独验收。脚本夹具不证明真实模型表现。源数据没有成本/广告/库存，不能计算利润/ROAS或判断商业因果。

## 故障与限制

- 缺库/未迁移：检查.env路径后执行migrate，不删除已有库；健康GET不会建库。
- 页面暂不可用：检查后端和端口，恢复后点“重新检查”。变更API要求可信Origin，CLI HTTP需加`Origin: http://127.0.0.1:5173`。
- 未授权模型：B1/B2保持阻断，B0可使用。
- 代码/配置变更后未终结run可能RUN_CONFIG_CHANGED，应新建关联run，不改旧checkpoint。
- npm保留4项开发依赖moderate告警，生产审计0；Python固定依赖本次审计未发现已知漏洞。见D8_SECURITY和KNOWN_ISSUES。

数据署名：Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. DOI 10.24432/C5BW33，CC BY 4.0。数据许可不等于本项目代码开源许可；仓库暂未声明代码分发许可证，依赖各自保留上游许可证。提交仅本地保存，未远程推送。

PACKAGE_MANIFEST及旧规格中的NOT_STARTED是原始交接资料；55份不可变契约保持原字节，当前状态以STATUS/EVIDENCE_INDEX为准。
