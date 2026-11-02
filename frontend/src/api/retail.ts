export type ImportStatus = 'QUEUED' | 'IMPORTING' | 'READY' | 'FAILED'
export type ResultStatus = 'PASS' | 'NO_DATA' | 'EMPTY_RESULT' | 'PARTIAL_PERIOD'
export interface Dataset {
  dataset_id: string; status: ImportStatus; data_hash: string; source_url: string
  row_count: number | null; source_time_min: string | null; source_time_max: string | null
  metric_version: string; transform_version: string; currency: 'GBP'
}
export interface Quality extends Dataset {
  raw_row_count: number; primary_class_counts: Record<string, number>
  quality_flags: Record<string, number>; duplicate_candidates_after_first: number
  duplicates_retained: boolean; warnings: string[]
}
export interface Batch {
  batch_id: string; dataset_id: string; status: ImportStatus; processed_rows: number
  attempt: number; error_code: string | null; workbook_sha256: string
  containers: { sha256: string; bytes: number; kind: string }[]
}
export interface Monthly {
  dataset_id: string; data_hash: string; metric_version: string; month: string
  status: ResultStatus; period_start: string; period_end_exclusive: string
  filters: { country: string | null; stock_code: string | null }
  positive_amount_exact: string | null; positive_amount_display: string | null
  cancellation_amount_exact: string | null; cancellation_amount_display: string | null
  net_amount_exact: string | null; net_amount_display: string | null
  positive_invoice_count: number | null; matched_row_count: number; source_row_count: number
  primary_class_counts: Record<string, number>; warnings: string[]
}
export interface Series {
  dataset_id: string; data_hash: string; metric_version: string; metric: string; unit: string
  status: ResultStatus; date_from: string; date_to: string; warnings: string[]
  filters: { country: string | null; stock_code: string | null }
  points: { month: string; status: ResultStatus; value_exact: string | null; value_display: string | null }[]
}
export interface HistoryItem {
  query_id: string; dataset_id: string; kind: 'monthly' | 'series'; status: ResultStatus
  parameters: { month?: string; date_from?: string; date_to?: string; country?: string; stock_code?: string }
  created_at: string
}
export interface Saved extends Omit<HistoryItem, 'status'> {
  result: Monthly | Series; result_sha256: string
}
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Definitions {
  metric_version: string; warnings: string[]
  definitions: { metric: string; label: string; formula: string; inclusion: string; exclusions: string }[]
}

export class ApiError extends Error {
  constructor(public readonly code: string, message: string) { super(message) }
}
const messages: Record<string, string> = {
  DATABASE_UNAVAILABLE: '数据库暂不可用，请检查本地服务后重试。',
  DATABASE_NOT_READY: '数据库尚未就绪，请先完成迁移。',
  DATASET_NOT_READY: '数据仍在导入或导入失败，完成后才能查询。',
  NOT_FOUND: '记录不存在，请刷新数据列表或重新选择查询。',
  UPLOAD_TOO_LARGE: '文件超过 50 MiB，请选择原始官方 ZIP 或 XLSX。',
  CORRUPT_SOURCE: '文件损坏或不是有效工作簿，请重新选择官方原文件。',
  UNAUDITED_SOURCE: '文件未通过来源哈希审计，请选择已审计的官方原文件。',
  WRITER_BUSY: '已有任务正在写入，请稍后重试。',
  VALIDATION_ERROR: '参数无效，请检查月份和筛选条件。',
}
export function errorText(cause: unknown): string {
  return cause instanceof ApiError ? `${cause.message}（${cause.code}）` : '无法完成操作，请重试。'
}

// Amounts cross the transport boundary as strings. Never coerce them to Number.
function validateDecimals(value: unknown, key = ''): void {
  if (key.endsWith('_exact') || key.endsWith('_display')) {
    if (value !== null && (typeof value !== 'string' || !/^-?\d+(?:\.\d+)?$/.test(value))) {
      throw new ApiError('INVALID_RESPONSE', '金额响应格式异常，已停止展示。')
    }
  } else if (value && typeof value === 'object') {
    for (const [name, child] of Object.entries(value)) validateDecimals(child, name)
  }
}
export async function request<T>(url: string, options: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, { ...options, headers: { Accept: 'application/json', ...options.headers }, cache: 'no-store', signal: controller.signal })
    let data: unknown
    try { data = await response.json() } catch {
      throw new ApiError(response.ok ? 'INVALID_RESPONSE' : `HTTP_${response.status}`, '接口未返回有效数据，请确认后端已启动后重试。')
    }
    if (!response.ok) {
      const raw = (data as { error?: { code?: unknown } })?.error?.code
      const code = typeof raw === 'string' && /^[A-Z0-9_]{1,80}$/.test(raw) ? raw : `HTTP_${response.status}`
      throw new ApiError(code, messages[code] ?? '操作未完成，请核对文件或参数后重试；如持续失败请查看本地服务日志。')
    }
    if (!data || typeof data !== 'object') throw new ApiError('INVALID_RESPONSE', '接口返回的数据不完整。')
    validateDecimals(data)
    return data as T
  } catch (cause) {
    if (cause instanceof ApiError) throw cause
    throw new ApiError(controller.signal.aborted ? 'TIMEOUT' : 'NETWORK_ERROR', controller.signal.aborted
      ? '请求超时。导入或保存可能仍在服务端进行，请重试查看状态。' : '无法连接后端，请启动本地服务后重试。')
  } finally { clearTimeout(timer) }
}
const base = '/api/v1'
export const api = {
  datasets: () => request<Page<Dataset>>(`${base}/datasets?limit=100`),
  quality: (id: string) => request<Quality>(`${base}/datasets/${encodeURIComponent(id)}/quality`),
  definitions: () => request<Definitions>(`${base}/metric-definitions`),
  history: (id: string, offset = 0) => request<Page<HistoryItem>>(`${base}/datasets/${encodeURIComponent(id)}/queries?limit=20&offset=${offset}`),
  saved: (id: string) => request<Saved>(`${base}/queries/${encodeURIComponent(id)}`),
  saveMonth: (id: string, month: string, country: string, stock: string, key: string) => request<Saved>(`${base}/datasets/${encodeURIComponent(id)}/queries`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
      idempotency_key: key, query: { kind: 'monthly', month, ...(country ? { country } : {}), ...(stock ? { stock_code: stock } : {}) },
    }),
  }),
  batch: (id: string) => request<Batch>(`${base}/datasets/imports/${encodeURIComponent(id)}`),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Batch>(`${base}/datasets/imports`, { method: 'POST', body: form }, 75000)
  },
}

export const statusLabel: Record<string, string> = {
  PASS: '完整月份', NO_DATA: '无数据', EMPTY_RESULT: '筛选结果为空', PARTIAL_PERIOD: '月份覆盖不完整',
  QUEUED: '等待导入', IMPORTING: '正在导入', READY: '可查询', FAILED: '导入失败',
}
export const classLabel: Record<string, string> = { POSITIVE: '正向交易行', CANCELLATION: '取消类行', EXCLUDED_OTHER: '其他排除行', INVALID: '无效行' }
