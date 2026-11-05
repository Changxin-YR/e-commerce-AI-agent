import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import App from '../src/components/HealthPanel.vue'

// test_fixture: transport responses only; no business or trading data.
const healthy = {
  status: 'ok', service: 'ecommerce-agent', version: '0.8.0', stage: 'D8',
  database: { status: 'ok', engine: 'sqlite', sqlite_version: 'test_fixture', schema_revision: '0004_agent_runtime' },
}
let wrapper: VueWrapper | undefined

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('local health connection', () => {
  it('shows pending until the actual fetch resolves, then displays verified values', async () => {
    let resolve!: (value: Response) => void
    const request = vi.fn(() => new Promise<Response>((done) => { resolve = done }))
    vi.stubGlobal('fetch', request)
    wrapper = mount(App)
    expect(wrapper.get('[data-testid="health-status"]').text()).toContain('正在检查')
    expect(wrapper.get('.connection-summary button').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('test_fixture')
    expect(request).toHaveBeenCalledWith('/healthz', expect.objectContaining({ method: 'GET', cache: 'no-store', signal: expect.any(AbortSignal) }))
    resolve(response(healthy))
    await flushPromises()
    expect(wrapper.get('[data-testid="health-status"]').text()).toBe('本地服务已连接')
    expect(wrapper.text()).toContain('SQLite test_fixture')
    expect(wrapper.text()).toContain('0004_agent_runtime')
  })

  it('treats 503 as unavailable without displaying server internals', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ error: { code: 'DB_ERROR', message: 'private-path-and-secret' } }, 503)))
    wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('HTTP_503')
    expect(wrapper.text()).not.toContain('private-path-and-secret')
    expect(wrapper.text()).not.toContain('SQLite test_fixture')
  })

  it.each([
    ['invalid schema', () => response({ status: 'ok' })],
    ['invalid stage', () => response({ ...healthy, stage: 'arbitrary' })],
    ['wrong service', () => response({ ...healthy, service: 'unrelated-service' })],
    ['HTML fallback', () => new Response('<html>SPA fallback</html>', { status: 200 })],
  ])('rejects a 200 %s instead of claiming success', async (_, result) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(result()))
    wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('INVALID_RESPONSE')
    expect(wrapper.get('[data-testid="health-status"]').text()).toBe('本地服务暂不可用')
  })

  it.each(['D8', 'D9'])('accepts compatible health schema after stage advancement to %s', async (stage) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ ...healthy, stage })))
    wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('[data-testid="health-status"]').text()).toBe('本地服务已连接')
  })

  it('retries after a network error and performs a new backend request', async () => {
    const request = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(response(healthy))
    vi.stubGlobal('fetch', request)
    wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('NETWORK_ERROR')
    await wrapper.get('.connection-summary button').trigger('click')
    await flushPromises()
    expect(request).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="health-status"]').text()).toBe('本地服务已连接')
  })

  it('clears stale successful data if a later health check fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(healthy)).mockRejectedValueOnce(new TypeError('offline')))
    wrapper = mount(App)
    await flushPromises()
    await wrapper.get('.connection-summary button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="health-status"]').text()).toBe('本地服务暂不可用')
    expect(wrapper.text()).not.toContain('SQLite test_fixture')
    expect(wrapper.text()).toContain('尚未确认')
  })

  it('bounds a hanging health request to eight seconds', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })))
    wrapper = mount(App)
    await vi.advanceTimersByTimeAsync(8001)
    expect(wrapper.get('[role="alert"]').text()).toContain('TIMEOUT')
    expect(wrapper.get('.connection-summary button').attributes('disabled')).toBeUndefined()
  })
})
