# D2 交付说明

2026-11-02，D2 数据库、批量导入、幂等和失败恢复通过工程验证，**READY_FOR_USER_ACCEPTANCE**。本轮不进入 D3，未调用模型、未写论文、未执行正式学术实验。

## 已实现

新增六张业务/关联表与 Alembic `0002_import`；原始行唯一键、workbook+转换版本唯一键及日期/发票/商品/国家/质量索引。提供 multipart ZIP/XLSX 后台导入、批次查询、profile/quality、CLI；完整使用及错误/恢复规则见 docs/D2_IMPORT.md。

生产解析直接读取 OOXML，按 Decimal 0.001 GBP 网格和 1E-9 容差转换整数千分金额，保存原始数值表示。每 2000 行落库，完整对账才发布 READY；失败保留行和错误，重试清理该失败快照重新处理；并发、进程中断及未知来源版本有明确处理。

## 真实核验结果

ZIP `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`；XLSX `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`，仍匹配 D1。原始文件只在项目 data/raw，未改写。

实际 HTTP 完整导入耗时 **115.969 秒**，541909 行，分类为 POSITIVE 530104 / CANCELLATION 9288 / EXCLUDED_OTHER 2517 / INVALID 0。132 次导入期间质量请求实测返回 409，完整后才返回 200。快照 `ds_9561855056bc9d83ca5a82c198b5130b`，批次 `ib_9561855056bc9d83ca5a82c198b5130b`。

客户号缺失135080、描述缺失1454、零价2515、负价2、负数量10624、非C负数量1336、重复候选5268，全部保留。4条原文 `1E-3` 的千分价均为1；51170条价格尾差按规则处理。日期范围2010-12-01 08:26至2011-12-09 12:50，数据库显示毫秒 `.000`；这是格式差异，时区未改、统计无差异。

41项独立 SQL/HTTP 核对全部通过：行数/分类/全部质量标签、每月行数、精度、整数金额、9/10月开发参考、SQLite完整性与外键、ZIP/XLSX/CLI重复导入、进程重启与GET只读。9月净额1019687.622、10月1070704.670 GBP来自独立SQL验证，未构建D3业务API。重复后仍只有1快照、1批次和541909行，金额未翻倍。

## 实际命令与测试

完整参数、起止时间、退出码和日志哈希见 docs/evidence/d2/command-records.json 与 EVIDENCE_INDEX.md。命令由 scripts/record_command.py 记录；下表为主体：

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `.venv/Scripts/python.exe scripts/verify_d1_evidence.py --output <D2缓存>/d1-input-recheck.json` | 0 | 33项 D1 输入交叉核验 |
| `.venv/Scripts/python.exe scripts/verify_import.py --database <D2缓存>/runtime/app.sqlite3 --output <D2缓存>/real-import` | 0 | 首次真实HTTP导入及41核对 |
| 同上，`--output <D2缓存>/real-final` | 0 | 最终代码复核41项；复用既有快照 |
| `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp <D2缓存>/pytest-final --junitxml <D2缓存>/pytest-final.xml` | 0 | 116 passed；46项为D2新增 |
| `python scripts/manage.py test --scope frontend` | 0 | 8 Vitest |
| `python scripts/manage.py build` | 0 | TypeScript/Vite成功 |
| `python scripts/manage.py test --scope e2e` | 0 | 2真实Edge健康/重启回归 |
| `python scripts/import_data.py <不存在的XLSX> --output <D2缓存>/missing-source.json` | 1 | 预期 SOURCE_NOT_FOUND，未伪造成功 |
| `python -m pip install --disable-pip-version-check --no-index -r requirements.lock` / `python -m pip check` | 0 / 0 | 实际锁与安装一致、依赖无冲突 |
| `python scripts/handoff_check.py` | 0 | 55份不可变资料哈希一致 |

安全负例包括路径穿越/符号链接ZIP、压缩比例/成员/上传限额、无Content-Length流式超限、错误MIME/结构、截断/多文件、宏/外部关系/XML实体、未知哈希、字段/epoch错误、公式、精度/整数越界和SQL样式文本。部分提交失败重试、同时请求幂等、中断恢复均使用明确的test_fixture；真实数据验收由独立HTTP/SQL流程完成。

## Git、文件与交付

D1基线 `bf92c1f5672f0ecbc05169215c5274d3ebdd7d39`；D2最终SHA和完整修改列表见 `D:/codex产出/电商智能体_D2数据库导入/交付/git-receipt.json`。仅本地提交，无推送。

主要新增：backend/app/imports/（source、rows、service、locks、routes），backend/app/errors.py，0002_import迁移，scripts/import_data.py、scripts/verify_import.py、tests/test_imports.py、docs/D2_IMPORT.md、docs/evidence/d2/。模型/配置/API schema、manage、健康页兼容、依赖锁、manifest和六份状态文档同步更新。源码保留原项目位置。

交付目录保存源码ZIP、逐文件SHA、Git回执、完整命令/浏览器证据、文档和运行库备份。原始ZIP/XLSX不进入交付ZIP或Git。运行库SHA `7c1d3f06e8af2945a1d1f3a681bf2dd171bea8baa0af717eb898ab78d644c334`，676319232字节；当前 .env 使用 D2 缓存/runtime 的库，D0 库保留。

## 残留与停止点

4项原 npm moderate 开发依赖告警继续记录，未强制升级；Python弃用问题已解决。当前仅支持已审计版本、单本地写入器，导入UI/确定性指标API尚未开发。本轮没有未解决的D2阻断；详见KNOWN_ISSUES。

**D2工程验证通过，等待用户验收；下一步D3未经授权不开始。**
