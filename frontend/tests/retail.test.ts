import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import RetailWorkspace from '../src/components/RetailWorkspace.vue'
import { request, ApiError } from '../src/api/retail'

// test_fixture: synthetic transport values, deliberately beyond safe JS Number precision.
const dataset = { dataset_id: 'ds_fixture', status: 'READY', data_hash: 'fixture_hash', source_url: 'https://archive.ics.uci.edu/dataset/352/online+retail', row_count: 4, source_time_min: '2011-09-01', source_time_max: '2011-12-09', currency: 'GBP', metric_version: 'fixture-v1', transform_version: 'fixture-v1' }
const quality = { ...dataset, raw_row_count: 4, primary_class_counts: { POSITIVE: 2, CANCELLATION: 1, EXCLUDED_OTHER: 1, INVALID: 0 }, quality_flags: { MISSING_CUSTOMER_ID: 1 }, duplicate_candidates_after_first: 1, warnings: [] }
function saved(status = 'PASS', exact: string | null = '9007199254740993.001', display: string | null = '9007199254740993.00') {
  return { query_id: 'q_fixture', dataset_id: dataset.dataset_id, kind: 'monthly', parameters: { month: '2011-09' }, result_sha256: 'fixture_result_hash', created_at: '2011-09-01', result: {
    dataset_id: dataset.dataset_id, data_hash: dataset.data_hash, metric_version: 'fixture-v1', month: '2011-09', status, filters: { country: null, stock_code: null },
    positive_amount_exact: exact, positive_amount_display: display, cancellation_amount_exact: exact, cancellation_amount_display: display, net_amount_exact: exact, net_amount_display: display,
    positive_invoice_count: exact === null ? null : 2, source_row_count: 4, matched_row_count: 4, primary_class_counts: quality.primary_class_counts, warnings: [], period_start: '2011-09-01', period_end_exclusive: '2011-10-01',
  } }
}
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
let wrapper: VueWrapper | undefined
let historyItems: unknown[] = [], result = saved()
let postCount = 0
function transport(url: string, options?: RequestInit): Promise<Response> {
  if (url.includes('/metric-definitions')) return Promise.resolve(json({ metric_version: 'fixture-v1', definitions: [], warnings: [] }))
  if (url.includes('/quality')) return Promise.resolve(json(quality))
  if (url.endsWith('/queries') && options?.method === 'POST') { postCount++; return Promise.resolve(json(result)) }
  if (url.includes('/queries?')) return Promise.resolve(json({ items: historyItems, total: historyItems.length, limit: 20, offset: 0 }))
  if (url.includes('/queries/')) return Promise.resolve(json(result))
  return Promise.resolve(json({ items: [dataset], total: 1, limit: 100, offset: 0 }))
}
async function boot() { wrapper = mount(RetailWorkspace); await flushPromises(); return wrapper }
beforeEach(() => {
  window.history.replaceState(null, '', '/?view=overview')
  localStorage.clear(); historyItems = []; result = saved(); postCount = 0
  vi.stubGlobal('fetch', vi.fn(transport))
})
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals(); vi.useRealTimers() })

describe('monthly business UI', () => {
  it('preserves exact and display strings beyond Number.MAX_SAFE_INTEGER', async () => {
    const view = await boot()
    await view.get('.query-form').trigger('submit'); await flushPromises()
    expect(view.get('[data-testid="net_amount-exact"]').text()).toBe('9007199254740993.001')
    expect(view.get('[data-testid="net_amount-display"]').text()).toBe('9007199254740993.00')
    expect(location.search).toBe('?query=q_fixture')
    expect(postCount).toBe(1)
  })
  it.each([
    ['NO_DATA', null, null, '无数据', '—'],
    ['EMPTY_RESULT', '0.000', '0.00', '筛选结果为空', '0.000'],
    ['PARTIAL_PERIOD', '0.001', '0.00', '月份覆盖不完整', '0.001'],
  ])('distinguishes %s with server values and coverage text', async (status, exact, display, label, expected) => {
    result = saved(status!, exact, display)
    const view = await boot()
    await view.get('.query-form').trigger('submit'); await flushPromises()
    expect(view.get('[data-testid="result-status"]').text()).toBe(label)
    expect(view.get('[data-testid="net_amount-exact"]').text()).toBe(expected)
  })
  it('loads a URL history pointer through GET only, including after remount', async () => {
    window.history.replaceState(null, '', '/?query=q_fixture')
    await boot()
    expect(wrapper!.text()).toContain('9007199254740993.001')
    wrapper!.unmount(); await boot()
    expect(wrapper!.text()).toContain('9007199254740993.001')
    expect(postCount).toBe(0)
  })
  it('restores recent server history without browser storage', async () => {
    historyItems = [{ ...result, status: 'PASS' }]
    await boot()
    expect(wrapper!.find('[data-testid="saved-result"]').exists()).toBe(true)
    expect(postCount).toBe(0)
  })
  it('clears an old result when query conditions change', async () => {
    const view = await boot()
    await view.get('.query-form').trigger('submit'); await flushPromises()
    await view.get('#month').setValue('2011-10')
    expect(view.find('[data-testid="saved-result"]').exists()).toBe(false)
  })
  it('reuses submission key after a lost response', async () => {
    const keys: string[] = []
    vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        keys.push(JSON.parse(options.body as string).idempotency_key)
        if (keys.length === 1) return Promise.reject(new TypeError('lost response'))
      }
      return transport(url, options)
    }))
    const view = await boot()
    await view.get('.query-form').trigger('submit'); await flushPromises()
    expect(view.get('[role="alert"]').text()).toContain('NETWORK_ERROR')
    await view.get('.query-form').trigger('submit'); await flushPromises()
    expect(keys).toHaveLength(2); expect(keys[0]).toBe(keys[1])
    expect(view.find('[data-testid="saved-result"]').exists()).toBe(true)
  })
  it('reports a failed persisted batch and allows retry', async () => {
    localStorage.setItem('retail.batch', 'ib_fixture')
    vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => url.includes('/imports/')
      ? Promise.resolve(json({ batch_id: 'ib_fixture', dataset_id: dataset.dataset_id, status: 'FAILED', error_code: 'IMPORT_TIMEOUT', processed_rows: 2, attempt: 1, containers: [] })) : transport(url, options)))
    const view = await boot()
    await view.get('.workspace-nav button[aria-label="数据与导入"]').trigger('click')
    expect(view.get('[data-testid="batch-status"]').text()).toBe('导入失败')
    expect(view.get('[data-testid="import-error"]').text()).toContain('IMPORT_TIMEOUT')
    expect(view.get('#source-file').attributes('disabled')).toBeUndefined()
  })
  it('does not replace the active page URL when a previous monthly query finishes late', async () => {
    let resolve!: (value: Response) => void
    vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => options?.method === 'POST'
      ? new Promise<Response>(done => { resolve = done }) : transport(url, options)))
    const view = await boot()
    await view.get('.query-form').trigger('submit')
    await view.get('.workspace-nav button[aria-label="数据与导入"]').trigger('click')
    resolve(json(result)); await flushPromises()
    expect(location.search).toBe('?view=datasets')
    expect(view.get('h1').text()).toBe('数据与导入')
    expect(view.find('[data-testid="saved-result"]').exists()).toBe(false)
  })
})

describe('transport rejection', () => {
  it('rejects numeric amounts instead of silently rounding', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ net_amount_exact: 123 })))
    await expect(request('/fixture')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })
  it('does not display raw server internals', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ error: { code: 'INTERNAL_ERROR', message: 'secret-private-file' } }, 500)))
    try { await request('/fixture') } catch (cause) {
      expect(cause).toBeInstanceOf(ApiError)
      expect((cause as Error).message).not.toContain('secret-private-file')
    }
  })
  it('bounds a hanging request', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))))
    const pending = expect(request('/fixture', {}, 200)).rejects.toMatchObject({ code: 'TIMEOUT' })
    await vi.advanceTimersByTimeAsync(201); await pending
  })
})
