<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { agentApi, runError, runLabels, subscribeRun } from '../api/agent'
import type { Capabilities, Report, ReportItem, Run, RunItem } from '../api/agent'
import { errorText } from '../api/retail'
import type { Dataset } from '../api/retail'
import AppIcon from './AppIcon.vue'
import StateBadge from './StateBadge.vue'
import ConversationThread from './ConversationThread.vue'
const props = defineProps<{ view: string; datasetId: string; ready: boolean; dataset?: Dataset }>()
const emit = defineEmits<{ navigate: [view: string] }>()
const capabilities = ref<Capabilities | null>(null), error = ref(''), busy = ref(false), loading = ref(false)
const question = ref(''), variant = ref('B2'), run = ref<Run | null>(null), report = ref<Report | null>(null)
const answers = ref<Record<string, string>>({}), runs = ref<RunItem[]>([]), reports = ref<ReportItem[]>([])
const runTotal = ref(0), reportTotal = ref(0), runOffset = ref(0), reportOffset = ref(0)
const dateFrom = ref('2011-09-01'), dateTo = ref('2011-10-01'), baselineFrom = ref(''), baselineTo = ref('')
const country = ref(''), stock = ref(''), metric = ref('net_amount')
const formError = ref(''), cancelDialog = ref<HTMLDialogElement>(), lastQuestion = ref('')
const questionInput = ref<HTMLTextAreaElement>()
const connection = ref('idle')
const activeRun = computed(() => !!run.value && ['QUEUED', 'RUNNING'].includes(run.value.run_status))
const waitingInput = computed(() => run.value?.run_status === 'WAITING_INPUT')
const chatRun = computed(() => run.value?.variant !== 'B0' ? run.value : null)
const reportSignature = () => JSON.stringify([dateFrom.value, dateTo.value, baselineFrom.value, baselineTo.value, country.value, stock.value, metric.value])
const savedFormSignature = ref(reportSignature())
const draftChanged = computed(() => question.value !== lastQuestion.value || reportSignature() !== savedFormSignature.value)
const modelState = computed(() => !capabilities.value ? '正在检查模型' : capabilities.value.test_fixture ? '脚本测试模式' : capabilities.value.blocker_code ? '模型暂不可用' : !capabilities.value.executor_ready ? '执行服务未就绪' : '模型配置就绪')
const examples = [
  { title: '比较经营变化', text: '比较 2011 年 9 月和 10 月的净交易金额，列出变化最大的国家。', icon: 'chart', color: 'mint', detail: '对比期间，定位变化' },
  { title: '发现交易贡献', text: '2011 年 9 月，哪些国家的净交易金额最高？请给出排名和数据依据。', icon: 'report', color: 'peach', detail: '查看排名，回溯依据' },
  { title: '检查数据质量', text: '请检查当前数据集的质量，说明缺失值、取消类交易和重复候选情况。', icon: 'shield', color: 'lemon', detail: '理解数据，明确边界' },
]
async function useExample(text: string) { question.value = text; await nextTick(); questionInput.value?.focus() }
function warnUnsaved(event: BeforeUnloadEvent) { if (draftChanged.value) { event.preventDefault(); event.returnValue = '' } }
const phaseNames: Record<string, string> = { received: '接收问题', clarify: '等待补充条件', model: '理解问题与规划', tools: '调用数据工具', review: '核对工具结果', finalize: '整理分析报告', verify: '核对工具结果', complete: '分析完成', report: '整理报告', running: '执行中' }
const canModel = computed(() => !!capabilities.value && capabilities.value.executor_ready && (capabilities.value.test_fixture || !capabilities.value.blocker_code))
let alive = true, initialized = false, generation = 0, poll: ReturnType<typeof setTimeout> | undefined
let closeStream: (() => void) | undefined, streamRunId = ''
function stopStream() { closeStream?.(); closeStream = undefined; streamRunId = ''; if (poll) clearTimeout(poll) }
const submissions = new Map<string, string>()
function submission(kind: string, body: unknown) {
  const signature = kind + JSON.stringify(body)
  if (!submissions.has(signature)) submissions.set(signature, crypto.randomUUID())
  return { ...body as object, idempotency_key: submissions.get(signature) }
}
function locate(view: string, key?: string, id?: string) {
  const url = new URL(location.href); url.searchParams.set('view', view); url.searchParams.delete('query')
  if (key && id) { url.searchParams.delete(key === 'run' ? 'report' : 'run'); url.searchParams.set(key, id) }
  if (url.href !== location.href) history.pushState(null, '', url)
  emit('navigate', view)
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
  if (!['QUEUED', 'RUNNING'].includes(value.run_status)) { stopStream(); connection.value = 'settled'; return }
  if (!['analysis', 'tasks'].includes(props.view)) { stopStream(); return }
  if (typeof EventSource !== 'undefined') {
    if (streamRunId === value.run_id && closeStream) return
    stopStream(); streamRunId = value.run_id; connection.value = 'connecting'
    closeStream = subscribeRun(value.run_id, latest => {
      if (!alive || streamRunId !== latest.run_id || run.value?.run_id !== latest.run_id) return
      setRun(latest)
      if (!['QUEUED', 'RUNNING'].includes(latest.run_status)) void loadLists().catch(() => {})
    }, state => { if (alive && run.value?.run_id === value.run_id) connection.value = state })
  } else {
    connection.value = 'polling'
    if (poll) clearTimeout(poll)
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
async function openRun(id: string, target = 'tasks') {
  const origin = location.href, view = props.view
  const current = ++generation
  const value = await agentApi.run(id)
  if (!alive || current !== generation || origin !== location.href || view !== props.view) return
  setRun(value); locate(target, 'run', id)
}
async function openReport(id: string) {
  const origin = location.href, view = props.view
  const current = ++generation
  const value = await agentApi.report(id)
  if (!alive || current !== generation || origin !== location.href || view !== props.view) return
  report.value = value; locate('reports', 'report', id)
}
async function createAgent() {
  if (!canModel.value || !props.ready || !question.value.trim() || activeRun.value || waitingInput.value || run.value?.run_status === 'INTERRUPTED') return
  const submittedQuestion = question.value
  const origin = location.href, view = props.view
  await safe(async () => {
    const value = await agentApi.create(submission('create', { dataset_id: chatRun.value?.dataset_id ?? props.datasetId, variant: variant.value, question: question.value,
      ...(chatRun.value ? { conversation_parent_run_id: chatRun.value.run_id } : {}) }))
    if (!alive) return
    if (question.value === submittedQuestion) { question.value = ''; lastQuestion.value = '' }
    if (origin === location.href && view === props.view) { generation++; setRun(value); locate('analysis', 'run', value.run_id) }
    await loadLists()
  })
}
async function createReport() {
  if (!props.ready || busy.value) return
  formError.value = ''
  if (!dateFrom.value || !dateTo.value || dateFrom.value >= dateTo.value) formError.value = '结束日期必须晚于起始日期，且不包含结束当天。'
  else if (!!baselineFrom.value !== !!baselineTo.value || (baselineFrom.value && baselineFrom.value >= baselineTo.value)) formError.value = '请填写完整基期，且基期结束日期须晚于起始日期。'
  if (formError.value) { await nextTick(); document.querySelector<HTMLElement>('#report-form-error')?.focus(); return }
  const submittedSignature = reportSignature()
  const origin = location.href, view = props.view
  await safe(async () => {
    const query = { metric: metric.value, date_from: dateFrom.value, date_to: dateTo.value, ...(country.value ? { country: country.value } : {}), ...(stock.value ? { stock_code: stock.value } : {}) }
    const baseline = baselineFrom.value || baselineTo.value ? { date_from: baselineFrom.value, date_to: baselineTo.value } : null
    const value = await agentApi.createReport(submission('report', { dataset_id: props.datasetId, query, baseline }))
    if (!alive) return
    savedFormSignature.value = submittedSignature
    report.value = value
    if (origin === location.href && view === props.view) locate('reports', 'report', value.report_id)
    await loadLists()
  })
}
async function act(kind: string) {
  const selected = run.value
  const origin = location.href, view = props.view
  if (!selected) return
  await safe(async () => {
    const payload = { revision: selected.revision, ...(kind === 'input' ? { answers: answers.value } : {}) }
    const value = await agentApi.action(selected.run_id, kind, kind === 'cancel' ? {} : submission(selected.run_id + kind, payload))
    if (!alive) return
    if (origin === location.href && view === props.view) { generation++; setRun(value); locate(view === 'analysis' ? 'analysis' : 'tasks', 'run', value.run_id) }
    await loadLists()
  })
}
async function pageList(kind: 'run' | 'report', direction: number) {
  await safe(async () => {
    const previousRun = runOffset.value, previousReport = reportOffset.value
    if (kind === 'run') runOffset.value += direction * 20
    else reportOffset.value += direction * 20
    try { await loadLists() }
    catch (cause) { runOffset.value = previousRun; reportOffset.value = previousReport; throw cause }
  })
}
async function loadView() {
  const view = props.view
  if (!['analysis', 'tasks'].includes(view)) stopStream()
  if (!['analysis', 'reports', 'tasks'].includes(view)) return
  loading.value = true
  await safe(async () => {
    if (!initialized) { capabilities.value = await agentApi.capabilities(); await loadLists(); initialized = true }
    const url = new URL(location.href)
    if (url.searchParams.get('report') && view === 'reports' && url.searchParams.get('report') !== report.value?.report_id) await openReport(url.searchParams.get('report')!)
    else if (url.searchParams.get('run') && ['analysis', 'tasks'].includes(view)) await openRun(url.searchParams.get('run')!, view)
    else if (view === 'analysis' && run.value) { setRun(run.value); locate('analysis', 'run', run.value.run_id) }
  })
  loading.value = false
  if (alive && view !== props.view) await loadView()
}
watch(() => props.view, loadView, { immediate: true })
function restoreRoute() {
  const url = new URL(location.href)
  if ((url.searchParams.get('view') ?? 'analysis') === 'analysis' && !url.searchParams.has('run')) {
    stopStream(); run.value = null; generation++
  }
  void nextTick(loadView)
}
onMounted(() => { window.addEventListener('beforeunload', warnUnsaved); window.addEventListener('popstate', restoreRoute) })
onUnmounted(() => { alive = false; generation++; stopStream(); window.removeEventListener('beforeunload', warnUnsaved); window.removeEventListener('popstate', restoreRoute) })
function newConversation() {
  if (activeRun.value || waitingInput.value) return
  stopStream(); run.value = null; generation++; submissions.clear()
  const url = new URL(location.href); url.searchParams.delete('run'); url.searchParams.delete('report'); history.pushState(null, '', url)
  void nextTick(() => questionInput.value?.focus())
}
function composerKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); void createAgent() }
}
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
      <div class="ai-workbench" :class="{ 'has-conversation': chatRun }">
        <div class="ai-main" :data-testid="chatRun ? 'run-detail' : undefined">
          <div class="ai-intro"><span class="ai-symbol"><AppIcon name="spark" /></span><div><h2>{{ chatRun ? '和数据一起，把问题聊清楚' : '你的经营问题，从这里开始' }}</h2><p>边对话，边执行。实时查看回复、工具调用与有据可查的结果。</p></div></div>
          <div v-if="chatRun" class="conversation-heading"><StateBadge :state="chatRun.run_status" data-testid="run-status">{{ runLabels[chatRun.run_status] ?? chatRun.run_status }}</StateBadge><span class="muted">{{ chatRun.config.model_id }} · {{ chatRun.variant }}</span><button class="text-button" :disabled="activeRun || waitingInput || busy" @click="newConversation">新对话</button></div>
          <ConversationThread v-if="chatRun" :run="chatRun" :connection="connection" @report="id => safe(() => openReport(id))" />
          <div v-if="chatRun && ['FAIL', 'CANCELLED'].includes(chatRun.run_status)" class="action-row"><button class="secondary" :disabled="busy || !canModel" @click="act('rerun')">重新运行</button><button class="text-button" :disabled="busy" @click="safe(() => openRun(chatRun!.run_id))">查看任务与用量</button></div>
          <button v-if="chatRun && connection === 'unavailable'" class="secondary" :disabled="busy" @click="safe(() => openRun(chatRun!.run_id, 'analysis'))">重新连接</button>
          <form v-if="waitingInput && run?.pending_input" class="reply-form chat-reply" @submit.prevent="act('input')">
            <h3>补充条件，继续分析</h3><p>{{ run.pending_input.message }}</p>
            <div v-for="(field, index) in run.pending_input.fields" :key="field"><label :for="`chat-answer-${index}`">{{ field }}</label><input :id="`chat-answer-${index}`" v-model="answers[field]" required maxlength="2000" /></div>
            <div class="action-row"><button type="submit" :disabled="busy || !canModel">补答并继续同一任务</button><button type="button" class="secondary" :disabled="busy" @click="cancelDialog?.showModal()">取消任务</button></div>
          </form>
          <div v-if="chatRun?.run_status === 'INTERRUPTED'" class="notice warning"><p>服务曾中断，已保存当前记录。可恢复执行，或开启新对话。</p><button class="secondary" :disabled="busy" @click="act('resume')">恢复任务</button><button class="secondary" :disabled="busy" @click="cancelDialog?.showModal()">取消任务</button></div>
          <form class="agent-form chat-composer" :aria-busy="busy" @submit.prevent="createAgent">
            <label for="question" class="sr-only">经营问题</label><textarea id="question" ref="questionInput" v-model="question" :disabled="busy || waitingInput" required maxlength="4000" :rows="chatRun ? 3 : 5" aria-describedby="question-help model-state" :placeholder="waitingInput ? '请先补充上方条件' : chatRun ? '继续追问，或输入下一步想分析的内容…' : '想了解什么？例如：比较 2011 年 9 月和 10 月的净交易金额，哪些国家贡献了主要变化？'" @keydown="composerKey" />
            <div class="composer-toolbar"><div class="mode-select"><AppIcon name="shield" /><label for="variant" class="sr-only">分析方案</label><select id="variant" v-model="variant" :disabled="busy || activeRun || waitingInput"><option value="B2">B2 · 条件与结果核验</option><option value="B1">B1 · 多轮工具调用</option></select></div><button v-if="activeRun" type="button" class="secondary" :disabled="busy || run?.cancel_requested" @click="act('cancel')"><AppIcon name="activity" />{{ run?.cancel_requested ? '正在停止…' : '停止执行' }}</button><button v-else type="submit" :disabled="busy || !ready || !canModel || !question.trim() || waitingInput || run?.run_status === 'INTERRUPTED'"><AppIcon name="arrow" />{{ busy ? '正在发送…' : chatRun ? '继续对话' : '开始分析' }}</button></div>
          </form>
          <div id="question-help" class="composer-help"><span>{{ question.length }}/4000 · Enter 发送，Shift + Enter 换行</span><span v-if="draftChanged">草稿未提交</span></div>
          <p v-if="!ready" class="notice warning">请先导入并选择可查询的数据集。<button class="text-button" @click="emit('navigate', 'datasets')">前往数据与导入</button></p>
          <div v-if="!chatRun" class="suggestion-heading"><h3>从这些问题开始</h3><span>点击填入，可继续编辑</span></div>
          <div v-if="!chatRun" class="suggestion-grid"><button v-for="example in examples" :key="example.title" class="suggestion" :class="example.color" :disabled="busy" @click="useExample(example.text)"><AppIcon :name="example.icon" /><strong>{{ example.title }}</strong><span>{{ example.detail }}</span><AppIcon name="arrow" /></button></div>
        </div>
        <aside class="ai-context" aria-label="分析能力与执行方式">
          <div class="context-title"><AppIcon name="spark" /><h3>分析助手</h3></div>
          <StateBadge :state="canModel ? 'CONFIGURED' : 'WAITING_INPUT'">{{ modelState }}</StateBadge>
          <p id="model-state" class="model-name">{{ capabilities?.model_id ?? '尚未配置模型' }}</p>
          <p class="muted">{{ capabilities?.provider ?? '等待提供方信息' }}</p>
          <p v-if="chatRun" class="muted">当前对话使用创建时的数据集，切换数据集后请开启新对话。</p>
          <div class="context-divider"></div><h3>一次分析如何完成</h3>
          <ol class="process-guide"><li><span>1</span><div><strong>理解经营问题</strong><p>缺少必要条件时向你追问</p></div></li><li><span>2</span><div><strong>调用数据工具</strong><p>在当前数据集上精确计算</p></div></li><li><span>3</span><div><strong>形成分析报告</strong><p>保留数值引用与工具证据</p></div></li></ol>
          <div class="context-source"><AppIcon name="database" /><div><strong>当前分析基础</strong><p>{{ dataset?.row_count?.toLocaleString('zh-CN') ?? '—' }} 行源记录</p><small>{{ dataset?.source_time_min?.slice(0, 10) ?? '等待导入' }} 至 {{ dataset?.source_time_max?.slice(0, 10) ?? '—' }}</small></div></div>
          <p class="muted">历史数据不包含成本、广告或库存，不能据此计算利润或判断商业因果。</p>
        </aside>
      </div>
      <form class="surface report-form" :aria-busy="busy" @submit.prevent="createReport">
        <div class="result-heading"><div><h2>确定性报表</h2><p>直接计算月度指标、国家与交易条目排名，也可与基期比较。</p></div><StateBadge state="READY">B0 · 无模型费用</StateBadge></div>
        <fieldset :disabled="busy"><legend class="sr-only">报表参数</legend><div class="report-fields">
          <div><label for="report-from">起始日期</label><input id="report-from" v-model="dateFrom" type="date" required /></div>
          <div><label for="report-to">结束日期（不含）</label><input id="report-to" v-model="dateTo" type="date" required /></div>
          <div><label for="report-metric">排名与比较指标</label><select id="report-metric" v-model="metric"><option value="net_amount">净交易金额</option><option value="positive_amount">正向交易行金额</option><option value="cancellation_amount">取消类金额</option><option value="positive_invoice_count">有效发票数</option></select></div>
          <div><label for="report-country">报表国家筛选</label><input id="report-country" v-model="country" maxlength="128" placeholder="留空为全部" /></div>
          <div><label for="report-stock">报表商品代码</label><input id="report-stock" v-model="stock" maxlength="128" placeholder="留空为全部" /></div>
        </div><details><summary>可选：与基期比较</summary><div class="baseline-fields"><div><label for="baseline-from">基期起始日期</label><input id="baseline-from" v-model="baselineFrom" type="date" /></div><div><label for="baseline-to">基期结束日期（不含）</label><input id="baseline-to" v-model="baselineTo" type="date" /></div></div><p class="muted">发票数不作可加性变化拆解。</p></details></fieldset>
        <p v-if="formError" id="report-form-error" role="alert" tabindex="-1" class="notice danger">{{ formError }}</p>
        <div class="report-submit"><p class="muted">{{ ready ? '所有结果基于当前数据集，保存后可随时回看。' : '请先导入并选择可查询的数据集。' }}</p><button type="submit" :disabled="busy || !ready"><AppIcon name="report" />{{ busy ? '正在处理…' : '生成确定性报表' }}</button></div>
      </form>
    </section>

    <section v-if="view === 'tasks'" aria-label="任务与实验记录">
      <p class="page-note">此处展示实际分析任务与用量；正式学术实验尚未开始。</p>
      <article v-if="run" class="surface run-detail" data-testid="run-detail">
        <div class="result-heading"><h2>任务详情 · {{ run.variant }}</h2><StateBadge :state="run.run_status" data-testid="run-status">{{ runLabels[run.run_status] ?? run.run_status }}</StateBadge></div>
        <p>{{ run.input.question }}</p><p class="identifier">{{ run.run_id }} · {{ run.thread_id }}</p>
        <template v-if="run.variant !== 'B0'"><button class="secondary" :disabled="busy" @click="safe(() => openRun(run!.run_id, 'analysis'))">进入对话继续分析</button><ConversationThread :run="run" :connection="connection" @report="id => safe(() => openReport(id))" /></template>
        <div class="execution-status" role="status" aria-live="polite"><AppIcon :name="run.run_status === 'PASS' ? 'check' : 'activity'" /><div><strong>{{ phaseNames[run.phase] ?? run.phase }}</strong><p>{{ duration }}<span v-if="['QUEUED', 'RUNNING'].includes(run.run_status)"> · 任务仍在执行，状态会自动更新</span></p></div></div>
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
          <button v-if="!['PASS', 'FAIL', 'CANCELLED'].includes(run.run_status)" class="secondary" :disabled="busy" @click="cancelDialog?.showModal()">取消任务</button>
          <button v-if="['PASS', 'FAIL', 'CANCELLED'].includes(run.run_status)" class="secondary" :disabled="busy || (run.variant !== 'B0' && !canModel)" @click="act('rerun')">重新运行</button>
          <button class="secondary" :disabled="busy" @click="safe(() => openRun(run!.run_id))">刷新任务</button>
        </div>
        <dl class="result-counts"><div><dt>已占用请求</dt><dd>{{ run.usage.requests_reserved }}</dd></div><div><dt>已确认 token</dt><dd>{{ run.usage.confirmed_total_tokens ?? '未知' }}</dd></div><div><dt>消耗未知的调用</dt><dd>{{ run.usage.unknown_usage_attempts }}</dd></div></dl>
        <p class="muted">{{ run.usage.basis }} · 费用未核实；测试夹具不计作真实调用。提供方 {{ run.config.provider }} / {{ run.config.model_id ?? '无' }}</p>
        <div class="tool-timeline"><h3>工具执行记录 <span class="muted">{{ run.tool_calls.length }} 次</span></h3><p v-if="!run.tool_calls.length" class="muted">尚无工具调用记录。</p><ol><li v-for="(call, index) in run.tool_calls" :key="call.id"><span class="step-index">{{ index + 1 }}</span><div><strong>{{ call.tool_name }}</strong><p><StateBadge :state="call.result.status">{{ runLabels[call.result.status] ?? call.result.status }}</StateBadge><code>{{ call.result.tool_call_id }}</code></p></div></li></ol></div>
        <details><summary>模型尝试与用量依据</summary><ul><li v-for="attempt in run.attempts" :key="attempt.attempt_id">{{ attempt.status }} · {{ attempt.source }} · {{ attempt.provider }}/{{ attempt.model_id }} · {{ attempt.error_code }}</li></ul><p v-if="!run.attempts.length" class="muted">本任务未记录模型尝试。</p></details>
      </article>
      <div class="surface"><div class="result-heading"><h2>开发任务 <span class="muted">{{ runTotal }} 条</span></h2><button class="secondary" :disabled="busy" @click="safe(loadLists)">刷新列表</button></div>
        <div v-if="!runs.length && !loading && !error" class="empty-state"><AppIcon name="activity" /><p>还没有任务。开始一次智能分析，或生成确定性报表。</p><button class="secondary" @click="emit('navigate', 'analysis')">开始分析</button></div>
        <ol class="history-list"><li v-for="item in runs" :key="item.run_id"><div><h3>{{ item.variant }} · {{ item.question }}</h3><p>{{ runLabels[item.run_status] ?? item.run_status }} · {{ item.created_at }}</p><p v-if="item.error_code">{{ item.error_code }}</p><p class="identifier">{{ item.run_id }}</p></div><button class="secondary" :disabled="busy" @click="safe(() => openRun(item.run_id))">打开任务</button></li></ol>
        <div v-if="runTotal > 20" class="pagination"><button :disabled="busy || runOffset === 0" @click="pageList('run', -1)">上一页任务</button><span>{{ runOffset + 1 }}–{{ Math.min(runOffset + 20, runTotal) }} / {{ runTotal }}</span><button :disabled="busy || runOffset + 20 >= runTotal" @click="pageList('run', 1)">下一页任务</button></div>
      </div>
    </section>

    <section v-if="view === 'reports'" aria-label="报告详情">
      <article v-if="report" class="surface report-detail" data-testid="report-detail">
        <div class="result-heading"><div><p class="muted">{{ report.content.variant === 'B0' ? '确定性分析' : 'AI 智能分析' }} · {{ report.content.variant }}</p><h2>历史交易分析报告</h2></div><StateBadge :state="report.content.business_result">{{ runLabels[report.content.business_result] ?? report.content.business_result }}</StateBadge></div>
        <p v-if="report.content.test_fixture" class="notice warning" data-testid="report-fixture">测试夹具生成的工程报告，不代表真实模型能力。</p>
        <p>{{ report.content.message }}</p><p v-if="report.content.variant !== 'B0'" class="muted">模型说明文字需人工复核；下列数值已从保存的工具结果解析。</p>
        <p class="identifier">{{ report.report_id }} · {{ report.created_at }} · 数据集 {{ report.dataset_id }}</p>
        <div class="action-row"><a class="button-link" :href="agentApi.exportURL(report.report_id, 'json')" download>导出 JSON</a><a class="button-link secondary" :href="agentApi.exportURL(report.report_id, 'markdown')" download>导出 Markdown</a><button class="secondary" :disabled="busy" @click="safe(() => openRun(report!.run_id))">查看来源任务</button></div>
        <p v-if="!report.content.claims.length" class="notice">本报告没有可引用数值。请查看证据状态、数据覆盖或不支持原因；空值不代表零。</p>
        <div v-else class="table-scroll" role="region" tabindex="0" aria-label="数据表格，可横向滚动"><table><caption>关键数值 · 原精度保留</caption><thead><tr><th>指标</th><th>精确值</th><th>证据引用</th></tr></thead><tbody><tr v-for="claim in report.content.claims" :key="claim.claim_id"><th>{{ claim.label }}</th><td class="exact-value">{{ claim.value }} {{ claim.unit ?? '' }}</td><td><details><summary>{{ claim.field_path }}</summary><code>{{ claim.tool_call_id }}</code><p>口径 {{ claim.metric_version }}</p><pre>{{ pretty(claim.period) }}</pre><pre>{{ pretty(claim.filters) }}</pre><code>{{ claim.snapshot_hash }}</code></details></td></tr></tbody></table></div>
        <details class="evidence-section"><summary>数据来源、范围与过滤器</summary><pre>{{ pretty(report.content.provenance) }}</pre><pre>{{ pretty(report.content.parameters) }}</pre></details>
        <h3>证据状态</h3><ul><li v-for="(item, index) in report.content.tool_statuses" :key="index">{{ item.tool }} · {{ runLabels[item.status] ?? item.status }} · {{ pretty(item.period) }}</li></ul>
        <h3>不可判定项与警告</h3><ul><li v-for="item in report.content.limitations" :key="item">{{ item }}</li><li v-for="item in report.content.warnings" :key="item">{{ item }}</li></ul>
        <details><summary>完整工具证据与保存内容哈希</summary><code>{{ report.content_sha256 }}</code><div v-for="item in report.evidence" :key="item.tool_call_id"><h3>{{ item.tool }}</h3><pre>{{ pretty(item.data) }}</pre></div></details>
      </article>
      <div class="surface"><div class="result-heading"><h2>已保存报告 <span class="muted">{{ reportTotal }} 条</span></h2><button class="secondary" :disabled="busy" @click="safe(loadLists)">刷新报告列表</button></div><p class="muted">刷新、导出和回看均只读，不触发模型请求。</p>
        <div v-if="!reports.length && !loading && !error" class="empty-state"><AppIcon name="report" /><p>尚无报告。完成一次分析，结果会保存在这里。</p><button class="secondary" @click="emit('navigate', 'analysis')">创建分析报告</button></div>
        <ol class="history-list"><li v-for="item in reports" :key="item.report_id"><div><h3>{{ item.variant }} · {{ item.test_fixture ? '测试夹具报告' : '分析报告' }}</h3><p>{{ item.created_at }} · {{ runLabels[item.business_result] ?? item.business_result }}</p><p class="identifier">{{ item.report_id }}</p></div><button class="secondary" :disabled="busy" @click="safe(() => openReport(item.report_id))">打开报告</button></li></ol>
        <div v-if="reportTotal > 20" class="pagination"><button :disabled="busy || reportOffset === 0" @click="pageList('report', -1)">上一页报告</button><span>{{ reportOffset + 1 }}–{{ Math.min(reportOffset + 20, reportTotal) }} / {{ reportTotal }}</span><button :disabled="busy || reportOffset + 20 >= reportTotal" @click="pageList('report', 1)">下一页报告</button></div>
      </div>
    </section>
    <dialog ref="cancelDialog" class="confirm-dialog" aria-labelledby="cancel-title"><h2 id="cancel-title">确认取消当前任务？</h2><p>已保存的工具记录与实际用量会保留。取消后可从任务记录重新运行。</p><div class="action-row"><button class="secondary" autofocus @click="cancelDialog?.close()">继续保留任务</button><button class="danger-button" @click="cancelDialog?.close(); act('cancel')">确认取消任务</button></div></dialog>
  </div>
</template>
