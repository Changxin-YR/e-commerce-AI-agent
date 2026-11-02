import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, errorText } from './api/retail'
import type { Batch, Dataset, Definitions, HistoryItem, Monthly, Quality, Saved, Series } from './api/retail'

const storage = {
  get(key: string) { try { return localStorage.getItem(`retail.${key}`) } catch { return null } },
  set(key: string, value: string) { try { localStorage.setItem(`retail.${key}`, value) } catch { /* URL and server history remain usable. */ } },
}
export function useRetail() {
  const requestedView = new URL(location.href).searchParams.get('view')
  const tab = ref(requestedView && ['overview', 'datasets', 'history', 'analysis', 'reports', 'tasks'].includes(requestedView) ? requestedView : 'overview'), datasets = ref<Dataset[]>([]), selected = ref('')
  const quality = ref<Quality | null>(null), definitions = ref<Definitions | null>(null)
  const history = ref<HistoryItem[]>([]), historyTotal = ref(0), historyOffset = ref(0)
  const saved = ref<Saved | null>(null), month = ref(''), country = ref(''), stock = ref('')
  const busy = ref(false), queryBusy = ref(false), uploadBusy = ref(false)
  const error = ref(''), queryError = ref(''), importError = ref(''), historyError = ref('')
  const batch = ref<Batch | null>(null), importMessage = ref(''), file = ref<File | null>(null)
  const dataset = computed(() => datasets.value.find(item => item.dataset_id === selected.value))
  const monthly = computed(() => saved.value?.kind === 'monthly' ? saved.value.result as Monthly : null)
  const series = computed(() => saved.value?.kind === 'series' ? saved.value.result as Series : null)
  let alive = true, queryGeneration = 0, datasetGeneration = 0
  let pollTimer: ReturnType<typeof setTimeout> | undefined
  let submission: { signature: string; key: string } | undefined
  function current(generation: number) { return alive && generation === queryGeneration }
  function clearResult() {
    queryGeneration++
    queryBusy.value = false
    saved.value = null
    queryError.value = ''
  }
  function setLocation(result: Saved) {
    const url = new URL(location.href)
    url.searchParams.set('query', result.query_id)
    for (const key of ['view', 'run', 'report']) url.searchParams.delete(key)
    window.history.replaceState(null, '', url)
    storage.set('dataset', result.dataset_id)
  }
  async function loadHistory(offset = 0) {
    const id = selected.value
    historyError.value = ''
    try {
      const page = await api.history(id, offset)
      if (!alive || selected.value !== id) return
      history.value = page.items; historyTotal.value = page.total; historyOffset.value = offset
    } catch (cause) { if (alive && selected.value === id) historyError.value = errorText(cause) }
  }
  async function selectDataset(id: string, restore = true) {
    const generation = ++datasetGeneration
    selected.value = id; storage.set('dataset', id)
    clearResult(); quality.value = null; history.value = []; historyTotal.value = 0; error.value = ''; busy.value = true
    const item = datasets.value.find(value => value.dataset_id === id)
    if (!item || item.status !== 'READY') { busy.value = false; return }
    month.value = item.source_time_min?.slice(0, 7) ?? ''; country.value = ''; stock.value = ''
    const results = await Promise.allSettled([api.quality(id), api.history(id)])
    if (!alive || generation !== datasetGeneration) return
    const [q, h] = results
    if (q.status === 'fulfilled') quality.value = q.value
    else error.value = errorText(q.reason)
    if (h.status === 'fulfilled') {
      history.value = h.value.items; historyTotal.value = h.value.total; historyOffset.value = 0
    } else historyError.value = errorText(h.reason)
    busy.value = false
    const queryId = new URL(location.href).searchParams.get('query')
    if (restore && tab.value === 'overview' && queryId) await openHistory(queryId)
    else if (restore && tab.value === 'overview' && history.value[0]) await openHistory(history.value[0].query_id)
  }
  async function openHistory(id: string) {
    clearResult()
    const generation = queryGeneration
    queryBusy.value = true
    try {
      const result = await api.saved(id)
      if (!current(generation)) return
      if (result.dataset_id !== selected.value) {
        // Explicit URLs must never display a result under an unrelated dataset.
        await selectDataset(result.dataset_id, false)
        if (!alive || selected.value !== result.dataset_id) return
      }
      month.value = result.parameters.month ?? ''
      country.value = result.parameters.country ?? ''; stock.value = result.parameters.stock_code ?? ''
      saved.value = result; setLocation(result); tab.value = 'overview'
    } catch (cause) { if (current(generation)) queryError.value = errorText(cause) }
    finally { if (current(generation)) queryBusy.value = false }
  }
  async function refresh() {
    busy.value = true; error.value = ''
    try {
      const [page, defs] = await Promise.all([api.datasets(), api.definitions()])
      if (!alive) return
      datasets.value = page.items; definitions.value = defs
      const preferred = selected.value || storage.get('dataset')
      const item = page.items.find(value => value.dataset_id === preferred) ?? page.items.find(value => value.status === 'READY') ?? page.items[0]
      if (item) await selectDataset(item.dataset_id)
      else { selected.value = ''; quality.value = null; saved.value = null; tab.value = 'datasets' }
    } catch (cause) { if (alive) error.value = errorText(cause) }
    finally { if (alive) busy.value = false }
  }
  async function queryMonth() {
    if (queryBusy.value || !dataset.value || dataset.value.status !== 'READY') return
    clearResult()
    const generation = queryGeneration
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month.value)) { queryError.value = '请选择有效月份。'; return }
    const signature = JSON.stringify([selected.value, month.value, country.value, stock.value])
    // Reuse after a transport failure so a server-side success cannot produce duplicate history.
    if (submission?.signature !== signature) submission = { signature, key: crypto.randomUUID() }
    queryBusy.value = true
    try {
      const result = await api.saveMonth(selected.value, month.value, country.value, stock.value, submission.key)
      if (!current(generation)) return
      saved.value = result; setLocation(result)
      await loadHistory()
    } catch (cause) { if (current(generation)) queryError.value = errorText(cause) }
    finally { if (current(generation)) queryBusy.value = false }
  }
  async function pollBatch(id: string) {
    if (pollTimer) clearTimeout(pollTimer)
    importError.value = ''
    try {
      const value = await api.batch(id)
      if (!alive) return
      batch.value = value
      if (value.status === 'READY') {
        uploadBusy.value = false; importMessage.value = '导入完成，全部源行已核对，可开始查询。'
        await refresh(); await selectDataset(value.dataset_id, false)
      } else if (value.status === 'FAILED') {
        uploadBusy.value = false; importError.value = `导入失败（${value.error_code ?? 'IMPORT_FAILED'}）。请重新选择原文件上传重试。`
      } else {
        uploadBusy.value = true
        pollTimer = setTimeout(() => void pollBatch(id), 1500)
      }
    } catch (cause) { if (alive) { uploadBusy.value = false; importError.value = errorText(cause) } }
  }
  async function upload() {
    if (!file.value || uploadBusy.value) return
    importError.value = ''; importMessage.value = ''; batch.value = null
    if (!/\.(zip|xlsx)$/i.test(file.value.name)) { importError.value = '请选择 ZIP 或 XLSX 文件。'; return }
    if (file.value.size > 50 * 1024 * 1024) { importError.value = '文件超过 50 MiB，请选择官方原文件。'; return }
    uploadBusy.value = true
    try {
      const value = await api.upload(file.value)
      if (!alive) return
      batch.value = value; storage.set('batch', value.batch_id)
      if (value.status === 'READY') {
        importMessage.value = '相同工作簿已导入，已复用已有批次，未增加交易行。'
        uploadBusy.value = false; await refresh(); await selectDataset(value.dataset_id, false); tab.value = 'datasets'
      } else await pollBatch(value.batch_id)
    } catch (cause) { if (alive) { uploadBusy.value = false; importError.value = errorText(cause) } }
  }
  onMounted(async () => {
    await refresh()
    const previous = storage.get('batch')
    if (previous && alive) {
      try {
        const value = await api.batch(previous)
        if (!alive) return
        batch.value = value
        if (value.status === 'QUEUED' || value.status === 'IMPORTING') await pollBatch(previous)
        else if (value.status === 'FAILED') importError.value = `上次导入失败（${value.error_code}），请重新上传重试。`
      } catch (cause) { if (alive) importError.value = errorText(cause) }
    }
  })
  onUnmounted(() => { alive = false; queryGeneration++; datasetGeneration++; if (pollTimer) clearTimeout(pollTimer) })
  return { tab, datasets, selected, dataset, quality, definitions, history, historyTotal, historyOffset, saved, monthly, series,
    month, country, stock, busy, queryBusy, uploadBusy, error, queryError, importError, historyError, batch, importMessage, file,
    refresh, selectDataset, clearResult, queryMonth, openHistory, loadHistory, upload, pollBatch }
}
