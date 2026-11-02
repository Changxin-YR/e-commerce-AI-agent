# D5 八工具接口与计算规则

GET /api/v1/tools 返回八个完整JSON Schema；POST /api/v1/tools/{tool_name} 接收该Schema定义的JSON参数，需本地可信Origin。服务端内部调用execute_tool使用同一校验和只读服务。没有SQL、路径、Shell、URL参数。错误使用error.code及HTTP状态，正常响应有status/data/evidence/warnings/error；result为D3兼容字段。

工具为get_dataset_profile、get_metric_definitions、get_quality_summary、query_metric_series、rank_entities、compare_periods、decompose_change、inspect_transactions。除全局指标定义可省dataset_id外，均要求READY快照；definitions指定dataset_id可绑定相同证据身份。

所有日期为ISO日期左闭右开，单区间最多36月；country/stock_code为严格字面等值过滤。quality/inspect可省两端日期查看整个快照；有日期时两端必须同时指定，不能纳入无法解析日期的行。full quality显示完整导入summary，其质量标签允许重叠，不能相加当作排除数。

排名dimension为product/country，top_k严格整数1—50，order为asc/desc。相同数值使用竞赛排名（1、1、3），实体按Unicode二进制升序，null最后；top_k为硬行数上限，可截断并列。null单独标未知，不和源字符串“未知”合并。返回全局total_exact、各组和group_total_exact及other_exact。发票计数按期间直接COUNT DISTINCT，不累加月计数；跨商品/国家不具可加性，明确警告且占比以组值之和为分母。

compare输入baseline/current两个区间。差额=本期-基期；百分比使用Decimal、六位ROUND_HALF_UP。基期0/负数返回null及ZERO_BASELINE/NEGATIVE_BASELINE，不显示无穷增长。期间覆盖、长度不同或重叠独立提示；源覆盖依据观测日界，不证明中间每天有交易。

decompose仅接受三项金额，拒绝发票数（NON_ADDITIVE_METRIC）。按变化绝对值降序显示最多50组，剩余项合并other_delta_exact；全部实体差额与总差额精确对账，不等则报RECONCILIATION_FAILED。总差额0时贡献比例null。构成拆解不是因果证明。

inspect最多50行，可按主分类和源行号升/降序；保留source_row_num、源价格文本、三位金额、质量标签，返回总命中和截断状态。CustomerID不暴露给模型，完整原始行仍保存在交易库。NO_DATA金额null；有源数据但合法筛选为空为EMPTY_RESULT/0。

tool_call_id由规范参数和真实结果确定性SHA生成；evidence包含快照/变换/指标版本、期间、过滤器、查询指纹、命中/排除计数及可供报告引用的exact_values路径。全局定义无数据集时hash=null并标global_metric_definitions，绝不伪造来源。
