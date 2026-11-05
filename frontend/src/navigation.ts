export const views = [
  { id: 'analysis', name: '智能分析', icon: 'spark', description: '从一个经营问题出发，让分析过程与数据证据清晰可见。', group: '智能工作区' },
  { id: 'overview', name: '经营概览', icon: 'chart', description: '按月查看真实交易指标，保留每一笔金额的原始精度。', group: '智能工作区' },
  { id: 'reports', name: '报告详情', icon: 'report', description: '阅读分析结论，追溯数值依据，导出完整报告。', group: '智能工作区' },
  { id: 'tasks', name: '任务与实验', icon: 'activity', description: '查看执行进度、补充分析条件，并追踪实际工具与用量。', group: '记录与数据' },
  { id: 'datasets', name: '数据与导入', icon: 'database', description: '管理分析的数据基础，检查来源、导入进度与质量。', group: '记录与数据' },
  { id: 'history', name: '查询历史', icon: 'history', description: '回到已保存的查询结果，继续你的经营分析。', group: '记录与数据' },
] as const
export function currentView() {
  const url = new URL(location.href)
  const view = url.searchParams.get('view')
  return views.some(item => item.id === view) ? view! : url.searchParams.has('query') ? 'overview' : 'analysis'
}
