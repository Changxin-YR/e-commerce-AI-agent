# 待完成和已知阻碍

- **D0 无未解决的运行阻断**：31 pytest、8 Vitest、2 真浏览器用例、迁移和构建均通过；这不表示 D1—D9 业务已完成。
- **K01 / OPEN / 开发依赖**：npm 初次审计 5 个 moderate；在 semver 范围内执行 `npm audit fix` 后仍有 4 个（glob、minimatch 及 js-beautify/editorconfig 间接链）。命令退出 1 已保留，不宣称全量依赖审计通过。当前 `npm audit --omit=dev` 为 0，high/critical 为 0；本轮未强行覆盖传递依赖主版本。后续依赖维护或 D8 应核查上游修复并重测。
- **K02 / OPEN / 测试兼容提示**：锁定的 Starlette 1.10.0 TestClient 提示 httpx 已弃用，建议 httpx2；当前 httpx 0.28.1 的所有测试通过。未为消除提示而盲目更换测试依赖；后续有正式兼容迁移时处理。没有隐藏该警告。
- **K03 / RESOLVED / 缓存目录**：首次 pytest 18 passed/13 errors，原因是 `--basetemp` 的父目录不存在；manage.py 现先创建任务专属 pytest 父目录，再选唯一运行目录。修复后 31 passed，首次日志保留。
- **K04 / RESOLVED / 环境审批服务**：第一次申请创建 D 盘任务目录时自动审批服务返回 503，操作未执行；同一审批正常重试后成功。没有绕过审批或声称提前写入 D 盘。
- **K05 / INFO / 工具提示**：npm 提示 esbuild postinstall 尚无 allowScripts 记录、glob 旧版弃用；现有 Windows 平台包下 npm ci、构建及浏览器测试均成功。Node 另有 NO_COLOR/FORCE_COLOR 环境提示，未影响测试。
- **K06 / INFO / 版本范围**：本次验证仅覆盖所记录的 Windows/Python/Node/Edge 环境；未进行跨平台或公网部署验收。Git 仓库无 commit，SHA=null，源码由交付 ZIP/文件哈希定位。
- **范围外 / NOT_STARTED**：UCI 获取与审计为 D1、真实导入为 D2；模型接入与合法预算另需授权；人工 gold、正式论文实验、学院模板及论文正文按用户要求延期。未将这些事项伪标 PASS。

所有原始失败、依赖提示、已通过测试及浏览器停止/恢复记录见 `EVIDENCE_INDEX.md`。服务在测试中被有意终止时，Windows 子进程退出 1 并标记 intentional_stop=true；这与测试失败区分记录。
