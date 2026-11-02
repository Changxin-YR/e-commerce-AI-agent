# D8 工程交付

实现与安全矩阵见D8_SECURITY.md。后端新增64KiB普通API请求体与15秒读取期限，上传仍分块写盘；Host/Origin拒绝多值歧义；嵌套字典键值脱敏；Markdown处理CR；页面/API防嵌套与nosniff头。健康页面兼容阶段升级，统一测试入口自动使用当前源库的隔离副本。

263 pytest、28 Vitest、完整9项Edge及TypeScript/Vite构建通过。真实UCI 541909行上的15个scripted任务与114项HTTP/重启/未知调用/重复补答检查通过；报表158、月度21独立SQL核对通过。实际浏览器验证存储问题的XSS转义、跨Origin表单403、超限JSON413且报告数不变。所有失败和复测记录保留。

Python68项固定依赖无已知漏洞；npm生产依赖0，4项开发moderate告警仍存在，常规修复预演changed=0。真实模型调用0、BLOCKED_AUTHORIZATION，真实模型冒烟未完成；用户验收未进行，论文/学术实验未开始。

D7业务库/checkpoint保持原SHA；D8默认运行与最终浏览器数据分别封存。交付在D:/codex产出/电商智能体_D8安全稳定/交付，含源码ZIP、运行数据、命令/截图/trace和哈希清单；最终本地提交见git-receipt.json，无远程推送。持续授权继续D9。
