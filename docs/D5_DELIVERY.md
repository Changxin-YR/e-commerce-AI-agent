# D5 交付与验证

D5工程验证PASS，READY_FOR_USER_ACCEPTANCE；用户未最终验收。已补齐五个业务工具，统一八工具Schema/证据及HTTP入口；源码仍在原仓库，D盘封存额外交付。下一步D6真实LangGraph代码与fake-provider恢复验证，模型预算0仍阻断真实外呼。

全量pytest 195通过（新增37）；真实UCI数据库57次HTTP工具调用、265项核对通过。参考脚本用独立SQL按发票前缀、数量和规范单价重新分类/乘算，不调用生产聚合函数。覆盖四指标、国家/商品排名、两期比较、金额拆解前列+其他、明细50行、质量/定义/元信息、非法参数、NO_DATA/EMPTY_RESULT/PARTIAL_PERIOD及零基期。数据库SHA在全部只读请求前后完全相同。

9/10月净额差实际核对为51017.048 GBP；并列排名、缺地区、同发票跨月/跨商品不重复总体计数、负基期和零变化由明确test_fixture测试覆盖，未冒充真实数据案例。

首轮6 passed/73 setup errors：pytest basetemp父目录遗漏，补建后使用新目录。第二轮78 passed/1 failed：测试误把AppError的业务说明当异常字符串，实际异常字符串为错误码；修正预期后全量195通过。失败XML/原始日志完整保留。前端源码未变，D4 20 Vitest/5 Edge/构建证据保留，本阶段未重复执行或冒写新PASS。

运行库D:/codex产出/电商智能体_D5八工具/缓存/runtime/app.sqlite3为D4库逐字节复制，541909行、2条保存查询、0003_query_history，SHA76a1b09bf229ee826660762ff914a8f94afeafab4fdd5b7fee574d3d068eaac4。旧D4/D3库保持原字节；服务已停止。原ZIP/XLSX哈希再次核对正确，只在项目data/raw保留。

代码基线e0c43541bf19f4c179522305e147e5f5dfe4736b，最终提交/改动清单在D:/codex产出/电商智能体_D5八工具/交付/git-receipt.json。源码ZIP逐Git文件核对、55不可变资料核对、数据库备份和交付文件SHA清单一起封存；无远程推送。
