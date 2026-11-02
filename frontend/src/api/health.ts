export interface HealthResponse {
  status: 'ok'
  service: 'ecommerce-agent'
  version: string
  stage: 'D2'
  database: {
    status: 'ok'
    engine: 'sqlite'
    sqlite_version: string
    schema_revision: string
  }
}

export class HealthError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message)
    this.name = 'HealthError'
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function nonempty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isHealth(value: unknown): value is HealthResponse {
  return record(value)
    && value.status === 'ok'
    && value.service === 'ecommerce-agent'
    && value.stage === 'D2'
    && nonempty(value.version)
    && record(value.database)
    && value.database.status === 'ok'
    && value.database.engine === 'sqlite'
    && nonempty(value.database.sqlite_version)
    && nonempty(value.database.schema_revision)
}

export async function fetchHealth(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch('/healthz', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    signal,
  })

  if (!response.ok) {
    if (response.status === 503) {
      throw new HealthError('后端尚未就绪。请检查数据库迁移及后端日志，然后重新检查。', 'HTTP_503')
    }
    throw new HealthError(`健康检查返回 HTTP ${response.status}。请检查后端服务及本地代理。`, `HTTP_${response.status}`)
  }

  let data: unknown
  try {
    data = await response.json()
  } catch {
    throw new HealthError('接口未返回有效的健康检查结果，请检查后端服务及本地代理。', 'INVALID_RESPONSE')
  }
  if (!isHealth(data)) {
    throw new HealthError('接口返回的状态不完整，暂时无法确认连接，请检查后端服务。', 'INVALID_RESPONSE')
  }
  return data
}
