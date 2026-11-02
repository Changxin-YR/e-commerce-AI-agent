<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { agentApi, runError, runLabels } from '../api/agent'
import type { Capabilities, Report, ReportItem, Run, RunItem } from '../api/agent'
import { errorText } from '../api/retail'
const props = defineProps<{ view: string; datasetId: string; ready: boolean }>()
const emit = defineEmits<{ navigate: [view: string] }>()
const capabilities = ref<Capabilities | null>(null), error = ref(''), busy = ref(false), loading = ref(false)
const question = ref(''), variant = ref('B2'), run = ref<Run | null>(null), report = ref<Report | null>(null)
const answers = ref<Record<string, string>>({}), runs = ref<RunItem[]>([]), reports = ref<ReportItem[]>([])
const runTotal = ref(0), reportTotal = ref(0), runOffset = ref(0), reportOffset = ref(0)
const dateFrom = ref('2011-09-01'), dateTo = ref('2011-10-01'), baselineFrom = ref(''), baselineTo = ref('')
const country = ref(''), stock = ref(''), metric = ref('net_amount')
const canModel = computed(() => !!capabilities.value && capabilities.value.executor_ready && (capabilities.value.test_fixture || !capabilities.value.blocker_code))
let alive = true, initialized = false, generation = 0, poll: ReturnType<typeof setTimeout> | undefined
const submissions = new Map<string, string>()
function submission(kind: string, body: unknown) {
  const signature = kind + JSON.stringify(body)
  if (!submissions.has(signature)) submissions.set(signature, crypto.randomUUID())
  return { ...body as object, idempotency_key: submissions.get(signature) }
}
function locate(view: string, key?: string, id?: string) {
  const url = new URL(location.href); url.searchParams.set('view', view); url.searchParams.delete('query')
  if (key && id) { url.searchParams.delete(key === 'run' ? 'report' : 'run'); url.searchParams.set(key, id) }
  history.replaceState(null, '', url); emit('navigate', view)
  window.scrollTo({ top: 0, behavior: 'instant' })
}
async function loadLists() {
  const [r, p] = await Promise.all([agentApi.runs(runOffset.value), agentApi.reports(reportOffset.value)])
  if (!alive) return
  runs.value = r.items; runTotal.value = r.total; reports.value = p.items; reportTotal.value = p.total
}
async function safe(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await action() } catch (cause) { if (alive) error.value = errorText(cause) }
  finally { if (alive) busy.value = false }
}
function setRun(value: Run) {
  const changed = run.value?.run_id !== value.run_id || run.value?.revision !== value.revision
  run.value = value
  if (changed) answers.value = Object.fromEntries((value.pending_input?.fields ?? []).map(f => [f, '']))
  if (poll) clearTimeout(poll)
  if (['QUEUED', 'RUNNING'].includes(value.run_status)) {
    const current = generation
    poll = setTimeout(async () => {
      try {
        const latest = await agentApi.run(value.run_id)
        if (!alive || current !== generation) return
        setRun(latest)
        if (!['QUEUED', 'RUNNING'].includes(latest.run_status)) await loadLists()
      } catch (cause) { if (alive && current === generation) error.value = errorText(cause) }
    }, 800)
  }
}
async function openRun(id: string) {
  const current = ++generation
  const value = await agentApi.run(id)
  if (!alive || current !== generation) return
  setRun(value); locate('tasks', 'run', id)
}
async function openReport(id: string) {
  const current = ++generation
  const value = await agentApi.report(id)
  if (!alive || current !== generation) return
  report.value = value; locate('reports', 'report', id)
}
async function createAgent() {
  await safe(async () => {
    const value = await agentApi.create(submission('create', { dataset_id: props.datasetId, variant: variant.value, question: question.value }))
    if (!alive) return
    generation++; setRun(value); locate('tasks', 'run', value.run_id); await loadLists()
  })
}
async function createReport() {
  await safe(async () => {
    const query = { metric: metric.value, date_from: dateFrom.value, date_to: dateTo.value, ...(country.value ? { country: country.value } : {}), ...(stock.value ? { stock_code: stock.value } : {}) }
    const baseline = baselineFrom.value || baselineTo.value ? { date_from: baselineFrom.value, date_to: baselineTo.value } : null
    const value = await agentApi.createReport(submission('report', { dataset_id: props.datasetId, query, baseline }))
    if (!alive) return
    report.value = value; locate('reports', 'report', value.report_id); await loadLists()
  })
}
async function act(kind: string) {
  const selected = run.value
  if (!selected) return
  await safe(async () => {
    const payload = { revision: selected.revision, ...(kind === 'input' ? { answers: answers.value } : {}) }
    const value = await agentApi.action(selected.run_id, kind, kind === 'cancel' ? {} : submission(selected.run_id + kind, payload))
    if (!alive) return
    generation++; setRun(value); locate('tasks', 'run', value.run_id); await loadLists()
  })
}
async function pageList(kind: 'run' | 'report', direction: number) {
  await safe(async () => {
    if (kind === 'run') runOffset.value += direction * 20
    else reportOffset.value += direction * 20
    await loadLists()
  })
}
watch(() => props.view, async view => {
  if (!['analysis', 'reports', 'tasks'].includes(view) || initialized) return
  initialized = true; loading.value = true
  await safe(async () => {
    capabilities.value = await agentApi.capabilities(); await loadLists()
    const url = new URL(location.href)
    if (url.searchParams.get('report') && view === 'reports') await openReport(url.searchParams.get('report')!)
    else if (url.searchParams.get('run') && view === 'tasks') await openRun(url.searchParams.get('run')!)
  })
  loading.value = false
}, { immediate: true })
onUnmounted(() => { alive = false; generation++; if (poll) clearTimeout(poll) })
const pretty = (value: unknown) => JSON.stringify(value, null, 2)
const duration = computed(() => run.value?.started_at && run.value?.ended_at ? `${Math.max(0, Date.parse(run.value.ended_at) - Date.parse(run.value.started_at)) / 1000} 秒（含等待）` : '未结束')
</script>

<template>
  <div v-show="['analysis', 'reports', 'tasks'].includes(view)" class="agent-workspace">
    <p v-if="loading" role="status">正在读取任务与报告…</p>
    <div v-if="error" class="notice danger" role="alert">{{ error }} <button class="secondary" @click="safe(async () => { capabilities = await agentApi.capabilities(); await loadLists() })">重试读取</button></div>
    <section v-if="view === 'analysis'" aria-label="智能分析">
      <div v-if="capabilities?.test_fixture" class="notice warning" data-testid="fixture-banner">当前为脚本测试夹具，仅验证工程交互，不代表真实模型能力。</div>
      <div v-else-if="capabilities?.blocker_code" class="notice warning" data-testid="model-blocked">{{ runError(capabilities.blocker_code) }}（{{ capabilities.blocker_code }}）</div>
      <div class="analysis-grid">
        <form class="surface report-form" @submit.prevent="createReport">
          <h2>确定性报表 <span class="state-tag">B0 · 无模型费用</span></h2>
          <p>四项月度指标、国家与交易条目排名；可增加基期比较和国家变化拆解。</p>
          <label for="report-from">起始日期</label><input id="report-from" v-model="dateFrom" type="date" required />
          <label for="report-to">结束日期（不含）</label><input id="report-to" v-model="dateTo" type="date" required />
          <label for="report-metric">排名与比较指标</label><select id="report-metric" v-model="metric"><option value="net_amount">净交易金额</option><option value="positive_amount">正向交易行金额</option><option value="cancellation_amount">取消类金额</option><option value="positive_invoice_count">有效发票数</option></select>
          <label for="report-country">报表国家筛选</label><input id="report-country" v-model="country" maxlength="128" placeholder="留空为全部" />
          <label for="report-stock">报表商品代码</label><input id="report-stock" v-model="stock" maxlength="128" placeholder="留空为全部" />
          <details><summary>可选：与基期比较</summary><label for="baseline-from">基期起始日期</label><input id="baseline-from" v-model="baselineFrom" type="date" /><label for="baseline-to">基期结束日期（不含）</label><input id="baseline-to" v-model="baselineTo" type="date" /><p class="muted">发票数不作可加性变化拆解。</p></details>
          <button type="submit" :disabled="busy || !ready">{{ busy ? '正在处理…' : '生成确定性报表' }}</button>
          <p v-if="!ready" class="muted">请先导入并选择可查询的数据集。</p>
        </form>
        <form class="surface agent-form" @submit.prevent="createAgent">
          <h2>智能问数</h2><p>描述期间、指标和筛选条件。信息不足时，任务会等待补充条件。</p>
          <label for="variant">分析方案</label><select id="variant" v-model="variant"><option value="B2">B2 · 条件与结果核验</option><option value="B1">B1 · 多轮工具调用</option></select>
          <label for="question">经营问题</label><textarea id="question" v-model="question" required maxlength="4000" rows="6" placeholder="例如：比较 2011 年 9 月和 10 月的净交易金额。" />
          <button type="submit" :disabled="busy || !ready || !canModel">提交分析任务</button>
          <p class="muted">{{ capabilities?.provider ?? '未配置提供方' }} · {{ capabilities?.model_id ?? '未配置模型' }}</p>
          <p>历史报告和确定性报表始终可独立读取。</p>
        </form>
      </div>
    </section>

    <section v-if="view === 'tasks'" aria-label="任务与实验记录">
      <p class="notice">正式学术实验暂未开始。此处仅展示开发任务与实际记录的用量，不展示实验成绩。</p>
      <article v-if="run" class="surface run-detail" data-testid="run-detail">
        <div class="result-heading"><h2>任务详情 · {{ run.variant }}</h2><span class="state-tag" data-testid="run-status">{{ runLabels[run.run_status] ?? run.run_status }}</span></div>
        <p>{{ run.input.question }}</p><p class="identifier">{{ run.run_id }} · {{ run.thread_id }}</p>
        <p>阶段 {{ run.phase }} · {{ duration }}</p>
        <p v-if="run.parent_run_id" class="identifier">重跑来源 {{ run.parent_run_id }}</p>
        <div v-if="run.error_code" class="notice danger" data-testid="run-error">{{ runError(run.error_code) }}（{{ run.error_code }}）</div>
        <form v-if="run.run_status === 'WAITING_INPUT' && run.pending_input" class="reply-form" @submit.prevent="act('input')">
          <h3>补充条件</h3><p>{{ run.pending_input.message }}</p>
          <div v-for="(field, index) in run.pending_input.fields" :key="field"><label :for="`answer-${index}`">{{ field }}</label><input :id="`answer-${index}`" v-model="answers[field]" required maxlength="2000" /></div>
          <button type="submit" :disabled="busy">补答并继续同一任务</button>
        </form>
        <div class="action-row">
          <button v-if="run.result_ref" :disabled="busy" @click="safe(() => openReport(run!.result_ref!))">查看报告</button>
          <button v-if="['QUEUED', 'INTERRUPTED'].includes(run.run_status)" class="secondary" :disabled="busy" @click="act('resume')">恢复任务</button>
          <button v-if="!['PASS', 'FAIL', 'CANCELLED'].includes(run.run_status)" class="secondary" :disabled="busy" @click="act('cancel')">取消任务</button>
          <button v-if="['PASS', 'FAIL', 'CANCELLED'].includes(run.run_status)" class="secondary" :disabled="busy || (run.variant !== 'B0' && !canModel)" @click="act('rerun')">重新运行</button>
          <button class="secondary" :disabled="busy" @click="safe(() => openRun(run!.run_id))">刷新任务</button>
        </div>
        <dl class="result-counts"><div><dt>已占用请求</dt><dd>{{ run.usage.requests_reserved }}</dd></div><div><dt>已确认 token</dt><dd>{{ run.usage.confirmed_total_tokens ?? '未知' }}</dd></div><div><dt>消耗未知的调用</dt><dd>{{ run.usage.unknown_usage_attempts }}</dd></div></dl>
        <p class="muted">{{ run.usage.basis }} · 费用未核实；测试夹具不计作真实调用。提供方 {{ run.config.provider }} / {{ run.config.model_id ?? '无' }}</p>
        <details><summary>工具调用与模型尝试</summary><ul><li v-for="call in run.tool_calls" :key="call.id">{{ call.tool_name }} · {{ call.result.status }} <code>{{ call.result.tool_call_id }}</code></li></ul><ul><li v-for="attempt in run.attempts" :key="attempt.attempt_id">{{ attempt.status }} · {{ attempt.source }} · {{ attempt.provider }}/{{ attempt.model_id }} · {{ attempt.error_code }}</li></ul></details>
      </article>
      <div class="surface"><div class="result-heading"><h2>开发任务 <span class="muted">{{ runTotal }} 条</span></h2><button class="secondary" :disabled="busy" @click="safe(loadLists)">刷新列表</button></div>
        <p v-if="!runs.length" class="empty-state">还没有任务。可前往智能分析生成确定性报表。</p>
        <ol class="history-list"><li v-for="item in runs" :key="item.run_id"><div><h3>{{ item.variant }} · {{ item.question }}</h3><p>{{ runLabels[item.run_status] ?? item.run_status }} · {{ item.created_at }}</p><p v-if="item.error_code">{{ item.error_code }}</p><p class="identifier">{{ item.run_id }}</p></div><button class="secondary" :disabled="busy" @click="safe(() => openRun(item.run_id))">打开任务</button></li></ol>
        <div v-if="runTotal > 20" class="pagination"><button :disabled="busy || runOffset === 0" @click="pageList('run', -1)">上一页任务</button><span>{{ runOffset + 1 }}–{{ Math.min(runOffset + 20, runTotal) }} / {{ runTotal }}</span><button :disabled="busy || runOffset + 20 >= runTotal" @click="pageList('run', 1)">下一页任务</button></div>
      </div>
    </section>

    <section v-if="view === 'reports'" aria-label="报告详情">
      <article v-if="report" class="surface report-detail" data-testid="report-detail">
        <div class="result-heading"><h2>{{ report.content.variant }} · 历史交易报告</h2><span class="state-tag">{{ runLabels[report.content.business_result] ?? report.content.business_result }}</span></div>
        <p v-if="report.content.test_fixture" class="notice warning" data-testid="report-fixture">测试夹具生成的工程报告，不代表真实模型能力。</p>
        <p>{{ report.content.message }}</p><p v-if="report.content.variant !== 'B0'" class="muted">模型说明文字需人工复核；下列数值已从保存的工具结果解析。</p>
        <p class="identifier">{{ report.report_id }} · {{ report.created_at }} · 数据集 {{ report.dataset_id }}</p>
        <div class="action-row"><a class="button-link" :href="agentApi.exportURL(report.report_id, 'json')" download>导出 JSON</a><a class="button-link secondary" :href="agentApi.exportURL(report.report_id, 'markdown')" download>导出 Markdown</a><button class="secondary" :disabled="busy" @click="safe(() => openRun(report!.run_id))">查看来源任务</button></div>
        <p v-if="!report.content.claims.length" class="notice">本报告没有可引用数值。请查看证据状态、数据覆盖或不支持原因；空值不代表零。</p>
        <div v-else class="table-scroll"><table><caption>关键数值 · 原精度保留</caption><thead><tr><th>指标</th><th>精确值</th><th>证据引用</th></tr></thead><tbody><tr v-for="claim in report.content.claims" :key="claim.claim_id"><th>{{ claim.label }}</th><td class="exact-value">{{ claim.value }} {{ claim.unit ?? '' }}</td><td><details><summary>{{ claim.field_path }}</summary><code>{{ claim.tool_call_id }}</code><p>口径 {{ claim.metric_version }}</p><pre>{{ pretty(claim.period) }}</pre><pre>{{ pretty(claim.filters) }}</pre><code>{{ claim.snapshot_hash }}</code></details></td></tr></tbody></table></div>
        <h3>数据来源、范围与过滤器</h3><pre>{{ pretty(report.content.provenance) }}</pre><pre>{{ pretty(report.content.parameters) }}</pre>
        <h3>证据状态</h3><ul><li v-for="(item, index) in report.content.tool_statuses" :key="index">{{ item.tool }} · {{ runLabels[item.status] ?? item.status }} · {{ pretty(item.period) }}</li></ul>
        <h3>不可判定项与警告</h3><ul><li v-for="item in report.content.limitations" :key="item">{{ item }}</li><li v-for="item in report.content.warnings" :key="item">{{ item }}</li></ul>
        <details><summary>完整工具证据与保存内容哈希</summary><code>{{ report.content_sha256 }}</code><div v-for="item in report.evidence" :key="item.tool_call_id"><h3>{{ item.tool }}</h3><pre>{{ pretty(item.data) }}</pre></div></details>
      </article>
      <div class="surface"><div class="result-heading"><h2>已保存报告 <span class="muted">{{ reportTotal }} 条</span></h2><button class="secondary" :disabled="busy" @click="safe(loadLists)">刷新报告列表</button></div><p class="muted">刷新、导出和回看均只读，不触发模型请求。</p>
        <p v-if="!reports.length" class="empty-state">尚无报告。前往智能分析创建确定性报表。</p>
        <ol class="history-list"><li v-for="item in reports" :key="item.report_id"><div><h3>{{ item.variant }} · {{ item.test_fixture ? '测试夹具报告' : '分析报告' }}</h3><p>{{ item.created_at }} · {{ runLabels[item.business_result] ?? item.business_result }}</p><p class="identifier">{{ item.report_id }}</p></div><button class="secondary" :disabled="busy" @click="safe(() => openReport(item.report_id))">打开报告</button></li></ol>
        <div v-if="reportTotal > 20" class="pagination"><button :disabled="busy || reportOffset === 0" @click="pageList('report', -1)">上一页报告</button><span>{{ reportOffset + 1 }}–{{ Math.min(reportOffset + 20, reportTotal) }} / {{ reportTotal }}</span><button :disabled="busy || reportOffset + 20 >= reportTotal" @click="pageList('report', 1)">下一页报告</button></div>
      </div>
    </section>
  </div>
</template>
