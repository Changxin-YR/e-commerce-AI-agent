import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import AgentWorkspace from '../src/components/AgentWorkspace.vue'

// test_fixture values deliberately exceed JS's safe numeric precision.
const report = { report_id: 'rep_fixture', run_id: 'run_fixture', dataset_id: 'ds_fixture', created_at: 'fixture', content_sha256: 'hash', evidence: [], content: {
  variant: 'B0', message: '<img src=x onerror=alert(1)>', test_fixture: true, business_result: 'PASS', warnings: [], limitations: ['fixture'], provenance: {}, parameters: {}, tool_statuses: [],
  claims: [{ claim_id: 'claim_fixture', label: '<script>bad()</script>', value: '9007199254740993.001', unit: 'GBP', tool_call_id: 'tc_fixture', field_path: 'points.0.value_exact', metric_version: 'fixture', snapshot_hash: 'hash', period: {}, filters: {} }],
} }
const waiting = { run_id: 'run_fixture', variant: 'B2', dataset_id: 'ds_fixture', thread_id: 'thread_fixture', parent_run_id: null, revision: 3,
  run_status: 'WAITING_INPUT', phase: 'clarify', pending_input: { message: '哪个月份？', fields: ['period'] }, input: { question: 'fixture question' },
  config: { provider: 'test_fixture', model_id: 'scripted' }, usage: { requests_reserved: 1, confirmed_total_tokens: null, unknown_usage_attempts: 1, basis: 'test_fixture' }, attempts: [], tool_calls: [], result_ref: null, error_code: null }
let view: VueWrapper | undefined
const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body)))
function transport(url: string) {
  if (url.endsWith('/capabilities')) return json({ blocker_code: 'BLOCKED_AUTHORIZATION', executor_ready: true, test_fixture: false })
  if (url.includes('/runs/run_fixture')) return json(waiting)
  if (url.includes('/reports/rep_fixture')) return json(report)
  return json({ items: [], total: 0 })
}
beforeEach(() => { window.history.replaceState(null, '', '/'); vi.stubGlobal('fetch', vi.fn(transport)); vi.stubGlobal('scrollTo', vi.fn()) })
afterEach(() => { view?.unmount(); view = undefined; vi.unstubAllGlobals() })
async function boot(tab: string) { view = mount(AgentWorkspace, { props: { view: tab, datasetId: 'ds_fixture', ready: true } }); await flushPromises(); return view }

it('blocks live submissions while keeping B0 available', async () => {
  const wrapper = await boot('analysis')
  expect(wrapper.get('[data-testid="model-blocked"]').text()).toContain('BLOCKED_AUTHORIZATION')
  expect(wrapper.get('.agent-form button').attributes('disabled')).toBeDefined()
  expect(wrapper.get('.report-form button').attributes('disabled')).toBeUndefined()
})
it('escapes report prose and labels and preserves exact amount on read-only reload', async () => {
  window.history.replaceState(null, '', '/?view=reports&report=rep_fixture')
  const wrapper = await boot('reports')
  expect(wrapper.get('.exact-value').text()).toBe('9007199254740993.001 GBP')
  expect(wrapper.text()).toContain('<script>bad()</script>')
  expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.find('script').exists()).toBe(false)
  expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method)).toBe(true)
})
it('keeps unknown usage distinct from zero on a waiting task', async () => {
  window.history.replaceState(null, '', '/?view=tasks&run=run_fixture')
  const wrapper = await boot('tasks')
  expect(wrapper.get('[data-testid="run-status"]').text()).toBe('等待补充条件')
  expect(wrapper.text()).toContain('未知'); expect(wrapper.get('label[for="answer-0"]').text()).toBe('period')
})
it('reuses the same reply key after a lost response', async () => {
  const bodies: { idempotency_key: string; revision: number; answers: object }[] = []
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => {
    if (options?.method === 'POST') {
      bodies.push(JSON.parse(options.body as string))
      if (bodies.length === 1) return Promise.reject(new TypeError('lost response'))
      return json({ ...waiting, run_status: 'PASS', pending_input: null, result_ref: 'rep_fixture', revision: 5 })
    }
    return transport(url)
  }))
  window.history.replaceState(null, '', '/?view=tasks&run=run_fixture')
  const wrapper = await boot('tasks')
  await wrapper.get('#answer-0').setValue('2011-09')
  await wrapper.get('.reply-form').trigger('submit'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('NETWORK_ERROR')
  await wrapper.get('.reply-form').trigger('submit'); await flushPromises()
  expect(bodies).toHaveLength(2); expect(bodies[0]).toEqual(bodies[1])
  expect(bodies[1]?.revision).toBe(3)
  expect(wrapper.get('[data-testid="run-status"]').text()).toBe('已完成')
})
it('renders a real timeout error and rerun action without fabricating a report', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('/runs/run_fixture')
    ? json({ ...waiting, run_status: 'FAIL', error_code: 'MODEL_TIMEOUT', pending_input: null }) : transport(url)))
  window.history.replaceState(null, '', '/?view=tasks&run=run_fixture')
  const wrapper = await boot('tasks')
  expect(wrapper.get('[data-testid="run-error"]').text()).toContain('超时')
  expect(wrapper.find('[data-testid="report-detail"]').exists()).toBe(false)
})

it('fills an editable example without submitting or invoking the model', async () => {
  const wrapper = await boot('analysis')
  await wrapper.get('.suggestion').trigger('click')
  expect((wrapper.get('#question').element as HTMLTextAreaElement).value).toContain('2011 年 9 月')
  expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method)).toBe(true)
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(true)
})

it('rejects reversed or incomplete date ranges before calling the report API', async () => {
  const wrapper = await boot('analysis')
  await wrapper.get('#report-from').setValue('2011-11-01')
  await wrapper.get('.report-form').trigger('submit'); await flushPromises()
  expect(wrapper.get('#report-form-error').text()).toContain('结束日期必须晚于')
  await wrapper.get('#report-from').setValue('2011-09-01')
  await wrapper.get('#baseline-from').setValue('2011-08-01')
  await wrapper.get('.report-form').trigger('submit'); await flushPromises()
  expect(wrapper.get('#report-form-error').text()).toContain('完整基期')
  expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method)).toBe(true)
})

it('does not claim an unverified configured model is verified', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => url.endsWith('/capabilities')
    ? json({ blocker_code: null, executor_ready: true, live_model_status: 'CONFIGURED_UNVERIFIED', provider: 'test_fixture', model_id: 'unverified_fixture' }) : transport(url)))
  const wrapper = await boot('analysis')
  expect(wrapper.text()).toContain('模型配置就绪')
  expect(wrapper.text()).not.toContain('模型已验证')
  expect(wrapper.get('.agent-form button').attributes('disabled')).toBeDefined()
  await wrapper.get('#question').setValue('fixture question')
  expect(wrapper.get('.agent-form button').attributes('disabled')).toBeUndefined()
})

it('does not pull the user back to a report after navigating away during its request', async () => {
  let resolve!: (value: Response) => void
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => options?.method === 'POST'
    ? new Promise<Response>(done => { resolve = done }) : transport(url)))
  const wrapper = await boot('analysis')
  await wrapper.get('.report-form').trigger('submit')
  history.pushState(null, '', '/?view=datasets')
  await wrapper.setProps({ view: 'datasets' })
  resolve(new Response(JSON.stringify(report))); await flushPromises()
  expect(wrapper.emitted('navigate')).toBeUndefined()
  expect(location.search).toBe('?view=datasets')
})

class FixtureEventSource {
  static instances: FixtureEventSource[] = []
  onopen?: () => void
  onerror?: () => void
  listeners = new Map<string, (event: MessageEvent) => void>()
  close = vi.fn()
  constructor(public url: string) { FixtureEventSource.instances.push(this) }
  addEventListener(name: string, callback: (event: MessageEvent) => void) { this.listeners.set(name, callback) }
  emit(name: string, value: unknown) { this.listeners.get(name)?.({ data: JSON.stringify(value) } as MessageEvent) }
}
const running = { ...waiting, run_status: 'RUNNING', phase: 'model', pending_input: null, revision: 4, messages: [
  { id: 'q', role: 'user', text: 'fixture question', status: 'complete' },
  { id: 'a', role: 'assistant', text: '正在', status: 'draft' },
] }
function streamFixture() {
  FixtureEventSource.instances = []; vi.stubGlobal('EventSource', FixtureEventSource)
  vi.stubGlobal('fetch', vi.fn((url: string) => url.endsWith('/capabilities')
    ? json({ blocker_code: null, executor_ready: true }) : url.includes('/runs/run_fixture') ? json(running) : transport(url)))
  window.history.replaceState(null, '', '/?view=analysis&run=run_fixture')
}

it('updates the same streamed message without duplication and closes on completion', async () => {
  streamFixture(); const wrapper = await boot('analysis')
  const source = FixtureEventSource.instances[0]!
  expect(wrapper.get('[data-message-id="a"]').text()).toContain('正在')
  source.emit('snapshot', { ...running, messages: [...running.messages.slice(0, 1), { ...running.messages[1], text: '正在查询真实数据' }] })
  await flushPromises()
  expect(wrapper.findAll('[data-message-id="a"]')).toHaveLength(1)
  expect(wrapper.get('[data-message-id="a"]').text()).toContain('正在查询真实数据')
  source.emit('snapshot', { ...running, run_status: 'PASS', phase: 'complete', messages: [] })
  await flushPromises(); expect(source.close).toHaveBeenCalled()
  expect(location.search).toContain('view=analysis')
})

it('reconnects without posting again and releases the stream on navigation', async () => {
  streamFixture(); const wrapper = await boot('analysis'); const source = FixtureEventSource.instances[0]!
  source.onerror?.(); await flushPromises()
  expect(wrapper.text()).toContain('连接中断，正在重连')
  expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method)).toBe(true)
  await wrapper.setProps({ view: 'datasets' }); expect(source.close).toHaveBeenCalled()
  source.emit('snapshot', { ...running, messages: [{ id: 'late', role: 'assistant', text: 'stale update', status: 'draft' }] })
  await wrapper.setProps({ view: 'analysis' }); await flushPromises()
  expect(wrapper.find('[data-message-id="late"]').exists()).toBe(false)
})

it('sends a follow-up with the existing conversation and dataset, then stays in chat', async () => {
  const bodies: Record<string, unknown>[] = []
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => {
    if (options?.method === 'POST') { bodies.push(JSON.parse(options.body as string)); return json({ ...waiting, run_id: 'run_next', run_status: 'PASS' }) }
    if (url.endsWith('/capabilities')) return json({ blocker_code: null, executor_ready: true })
    if (url.includes('/runs/run_fixture')) return json({ ...waiting, run_status: 'PASS', pending_input: null })
    return transport(url)
  }))
  window.history.replaceState(null, '', '/?view=analysis&run=run_fixture')
  const wrapper = await boot('analysis')
  await wrapper.setProps({ datasetId: 'different_dataset' })
  await wrapper.get('#question').setValue('继续分析')
  await wrapper.get('.agent-form').trigger('submit'); await flushPromises()
  expect(bodies[0]?.conversation_parent_run_id).toBe('run_fixture')
  expect(bodies[0]?.dataset_id).toBe('ds_fixture')
  expect(location.search).toContain('view=analysis'); expect(location.search).toContain('run=run_next')
})

it('does not send on IME composition or Shift Enter', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => url.endsWith('/capabilities') ? json({ blocker_code: null, executor_ready: true }) : transport(url)))
  const wrapper = await boot('analysis')
  await wrapper.get('#question').setValue('输入中的中文')
  await wrapper.get('#question').trigger('keydown', { key: 'Enter', isComposing: true })
  await wrapper.get('#question').trigger('keydown', { key: 'Enter', shiftKey: true })
  expect(vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method)).toBe(true)
})
