import { request } from './retail'
import type { Page } from './retail'

export interface Capabilities {
  live_model_status: string; blocker_code: string | null; executor_ready: boolean; test_fixture: boolean
  provider: string | null; model_id: string | null
}
export interface RunItem {
  run_id: string; dataset_id: string; variant: string; run_status: string; phase: string
  question: string; created_at: string; result_ref: string | null; error_code: string | null
}
export interface Run extends RunItem {
  revision: number; thread_id: string; parent_run_id: string | null; ended_at: string | null; started_at: string | null
  pending_input: { message: string; fields: string[] } | null
  input: { question: string }; config: { provider: string; model_id: string | null }
  usage: { requests_reserved: number; confirmed_total_tokens: number | null; known_partial_tokens: number; unknown_usage_attempts: number; basis: string }
  attempts: { attempt_id: string; status: string; source: string; provider: string; model_id: string; error_code: string | null }[]
  tool_calls: { id: string; tool_name: string; result: { status: string; tool_call_id?: string } }[]
  cancel_requested?: boolean
  messages?: ConversationMessage[]
  conversation_history?: { run_id: string; question: string; message: string; claims: Claim[]; status: string }[]
  result?: Report['content'] | null
}
export interface ConversationMessage {
  id: string; role: 'user' | 'assistant' | 'tool'; text: string; status: string; created_at: string
  arguments?: Record<string, unknown>; error_code?: string; evidence_ref?: string
}
export interface Claim {
  claim_id: string; label: string; value: string | number; unit?: string; tool_call_id: string; field_path: string
  snapshot_hash: string; metric_version: string; period: unknown; filters: unknown
}
export interface ReportItem {
  report_id: string; run_id: string; created_at: string; variant: string; test_fixture: boolean; business_result: string
}
export interface Report {
  report_id: string; run_id: string; dataset_id: string; created_at: string; content_sha256: string
  content: {
    variant: string; message: string; test_fixture: boolean; business_result: string; claims: Claim[]
    warnings: string[]; limitations: string[]; provenance: Record<string, unknown>; parameters: unknown
    tool_statuses: { tool: string; status: string; period: unknown }[]
  }
  evidence: { tool_call_id: string; tool: string; data: Record<string, unknown> }[]
}
const base = '/api/v1'
const post = <T>(url: string, body: unknown) => request<T>(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }, 60000)
export const agentApi = {
  capabilities: () => request<Capabilities>(`${base}/agent/capabilities`),
  runs: (offset = 0) => request<Page<RunItem>>(`${base}/runs?limit=20&offset=${offset}`),
  run: (id: string) => request<Run>(`${base}/runs/${encodeURIComponent(id)}`),
  create: (body: unknown) => post<Run>(`${base}/runs`, body),
  action: (id: string, kind: string, body: unknown) => post<Run>(`${base}/runs/${encodeURIComponent(id)}/${kind}`, body),
  reports: (offset = 0) => request<Page<ReportItem>>(`${base}/reports?limit=20&offset=${offset}`),
  report: (id: string) => request<Report>(`${base}/reports/${encodeURIComponent(id)}`),
  createReport: (body: unknown) => post<Report>(`${base}/reports`, body),
  exportURL: (id: string, format: string) => `${base}/reports/${encodeURIComponent(id)}/export?format=${format}`,
}
export function subscribeRun(id: string, onSnapshot: (run: Run) => void, onState: (state: string) => void) {
  const source = new EventSource(`${base}/runs/${encodeURIComponent(id)}/events`)
  source.onopen = () => onState('connected')
  source.onerror = () => onState('reconnecting')
  source.addEventListener('snapshot', event => {
    try {
      const value = JSON.parse((event as MessageEvent).data) as Run
      if (value.run_id !== id || !value.run_status) throw new Error('Invalid run snapshot')
      onState('connected'); onSnapshot(value)
    } catch { onState('reconnecting') }
  })
  source.addEventListener('settled', () => { source.close(); onState('settled') })
  source.addEventListener('stream-error', () => { source.close(); onState('unavailable') })
  return () => source.close()
}
export const runLabels: Record<string, string> = {
  QUEUED: '已排队', RUNNING: '正在分析', WAITING_INPUT: '等待补充条件', INTERRUPTED: '运行中断',
  PASS: '已完成', FAIL: '运行失败', CANCELLED: '已取消', NO_DATA: '无数据', EMPTY_RESULT: '筛选结果为空', PARTIAL_PERIOD: '期间覆盖不完整', PARTIAL_RESULT: '仅部分结果可用',
  answer: '已形成结论', unsupported: '不支持的分析范围', clarify: '需要补充条件',
}
export const runError = (code: string | null) => ({
  BLOCKED_AUTHORIZATION: '尚未授权真实模型调用；可使用确定性报表。',
  BLOCKED_CREDENTIALS: '模型配置不完整；可使用确定性报表。',
  MODEL_TIMEOUT: '模型响应超时。已发生用量保留，未知消耗不会记为零。',
  PROCESS_INTERRUPTED: '服务曾中断，可在配置兼容时恢复任务。',
  RUN_CONFIG_CHANGED: '执行配置已变化，请重新运行创建新任务。',
  MODEL_BUDGET_EXHAUSTED: '本次分析或项目的请求 / token 额度不足。已保存工具结果，可检查服务端环境变量中的预算后重新运行。',
  MODEL_CONTEXT_LIMIT: '对话与工具证据超出单次请求上限。请开启新对话，缩小分析范围。',
  MODEL_AUTH_ERROR: '模型服务拒绝了凭据，请检查服务端环境变量中的密钥及访问权限。',
  MODEL_ENDPOINT_ERROR: '模型接口地址或模型名称不可用，请检查服务端环境变量。',
  MODEL_RATE_LIMIT: '模型服务限流或余额不足，请稍后手动重试并检查供应商额度。',
  MODEL_REQUEST_REJECTED: '模型服务不接受当前请求格式，请检查模型是否支持流式输出和工具调用。',
  MODEL_STREAM_INTERRUPTED: '模型连接在输出完成前中断。已输出内容保留为草稿，可重新运行。',
  MODEL_OUTPUT_TRUNCATED: '模型输出被截断，尚未生成完整结果。请缩小问题范围或检查输出长度上限。',
  MODEL_OUTCOME_UNKNOWN: '未收到完整模型响应，请检查连接或接口配置；已发生用量可能未知。',
  MODEL_HTTP_ERROR: '模型服务返回异常状态，请稍后重新运行。',
  MODEL_CONNECTION_ERROR: '无法连接模型服务，请检查服务端网络及模型接口地址。',
  MODEL_INVALID_RESPONSE: '模型服务返回了无法解析的响应，请检查接口兼容性后重试。',
  INVALID_OUTPUT_SCHEMA: '模型未返回完整的结构化结论，已保留工具证据，可重新运行。',
}[code ?? ''] ?? '任务未完成，请查看错误码与已保存的工具结果。')
