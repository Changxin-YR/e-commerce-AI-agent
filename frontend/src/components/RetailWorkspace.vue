<script setup lang="ts">
import { useRetail } from '../useRetail'
import { classLabel, statusLabel } from '../api/retail'
const {
  tab, datasets, selected, dataset, quality, definitions, history, historyTotal, historyOffset,
  saved, monthly, series, month, country, stock, busy, queryBusy, uploadBusy,
  error, queryError, importError, historyError, batch, importMessage, file,
  refresh, selectDataset, clearResult, queryMonth, openHistory, loadHistory, upload, pollBatch,
} = useRetail()
function chooseFile(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] ?? null }
const amountRows = [
  { name: '正向交易行金额', key: 'positive_amount' },
  { name: '取消类金额', key: 'cancellation_amount' },
  { name: '净交易金额', key: 'net_amount' },
] as const
const tabs = [{ id: 'overview', name: '经营概览' }, { id: 'datasets', name: '数据与导入' }, { id: 'history', name: '查询历史' }]
</script>

<template>
  <div class="retail-shell">
    <header class="retail-header">
      <a href="/" class="retail-brand">电商经营分析<span>历史交易工作区</span></a>
      <a href="/?view=health" class="service-link">服务状态</a>
    </header>
    <nav class="workspace-nav" aria-label="功能视图">
      <button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" :aria-current="tab === item.id ? 'page' : undefined" @click="tab = item.id">{{ item.name }}</button>
    </nav>
    <main class="retail-main">
      <div class="workspace-heading">
        <div><h1>{{ tabs.find(item => item.id === tab)?.name }}</h1><p>UCI Online Retail 历史交易数据。金额单位 GBP，时间沿用源文件。</p></div>
        <button class="secondary" :disabled="busy" @click="refresh">{{ busy ? '正在加载…' : '刷新数据' }}</button>
      </div>
      <div v-if="error" class="notice danger" role="alert" data-testid="workspace-error">{{ error }}</div>
      <div class="dataset-selector">
        <label for="dataset">当前数据集</label>
        <select id="dataset" :value="selected" :disabled="busy || !datasets.length" @change="selectDataset(($event.target as HTMLSelectElement).value, false)">
          <option v-if="!datasets.length" value="">{{ busy ? '加载中' : '尚未导入数据' }}</option>
          <option v-for="item in datasets" :key="item.dataset_id" :value="item.dataset_id">{{ item.source_time_min?.slice(0, 10) ?? '待处理' }} 至 {{ item.source_time_max?.slice(0, 10) ?? '待处理' }} · {{ statusLabel[item.status] }} · {{ item.dataset_id }}</option>
        </select>
        <span v-if="dataset" class="state-tag" :data-state="dataset.status">{{ statusLabel[dataset.status] }}</span>
      </div>

      <section v-if="tab === 'datasets'" aria-label="数据与导入" class="data-grid">
        <div class="surface import-panel">
          <h2>导入官方原文件</h2>
          <p class="muted">选择已审计的 ZIP 或 XLSX，单个文件不超过 50 MiB。相同工作簿会复用已有批次。</p>
          <form @submit.prevent="upload">
            <label for="source-file">源数据文件</label>
            <input id="source-file" type="file" accept=".zip,.xlsx" :disabled="uploadBusy" @change="chooseFile" />
            <button type="submit" :disabled="uploadBusy || !file">{{ uploadBusy ? '正在上传或处理…' : '上传并导入' }}</button>
          </form>
          <div v-if="importMessage" role="status" class="notice success" data-testid="import-message">{{ importMessage }}</div>
          <div v-if="importError" class="notice danger" role="alert" data-testid="import-error">{{ importError }}</div>
          <div v-if="batch" class="batch-progress" aria-live="polite">
            <h3 data-testid="batch-status">{{ statusLabel[batch.status] }}</h3>
            <p>已处理 <strong data-testid="processed-rows">{{ batch.processed_rows }}</strong> 行 · 第 {{ batch.attempt }} 次尝试</p>
            <progress v-if="uploadBusy" aria-label="正在处理导入"></progress>
            <p class="identifier">批次 {{ batch.batch_id }}</p>
            <button v-if="!uploadBusy" class="secondary" @click="pollBatch(batch.batch_id)">检查批次状态</button>
            <details><summary>文件哈希</summary><p>XLSX SHA-256</p><code>{{ batch.workbook_sha256 }}</code><div v-for="container in batch.containers" :key="container.sha256"><p>{{ container.kind }} 容器</p><code>{{ container.sha256 }}</code></div></details>
          </div>
        </div>
        <div class="surface">
          <h2>数据质量</h2>
          <p v-if="!quality" class="empty-state">{{ dataset?.status === 'READY' ? '正在加载质量报告；如加载失败请刷新数据。' : '导入完成后显示互斥分类、质量标签与来源。' }}</p>
          <template v-else>
            <p class="quality-total">保留全部源行 <strong data-testid="raw-row-count">{{ quality.raw_row_count }}</strong></p>
            <dl class="class-counts"><div v-for="(count, key) in quality.primary_class_counts" :key="key"><dt>{{ classLabel[key] ?? key }}</dt><dd>{{ count }}</dd></div></dl>
            <p class="notice">重复候选 {{ quality.duplicate_candidates_after_first }} 行仍保留。缺失客户号不会自动排除；质量标签可以重叠，不能相加作为排除数。</p>
            <details><summary>查看质量标签与警告</summary><dl class="quality-flags"><div v-for="(count, flag) in quality.quality_flags" :key="flag"><dt>{{ flag }}</dt><dd>{{ count }}</dd></div></dl><ul><li v-for="warning in quality.warnings" :key="warning">{{ warning }}</li></ul></details>
          </template>
        </div>
      </section>

      <section v-if="tab === 'overview'" aria-label="月度经营概览">
        <div v-if="!dataset" class="surface empty-state"><h2>先导入一份历史数据</h2><p>导入后可选择月份，查看精确金额、有效发票数与数据覆盖情况。</p><button @click="tab = 'datasets'">前往数据与导入</button></div>
        <template v-else>
          <form class="query-form surface" @submit.prevent="queryMonth">
            <div><label for="month">查询月份</label><input id="month" v-model="month" type="month" required :disabled="busy || queryBusy" @input="clearResult" /></div>
            <div><label for="country">国家筛选 <span>可留空</span></label><input id="country" v-model="country" maxlength="128" placeholder="例如 United Kingdom" :disabled="busy || queryBusy" @input="clearResult" /></div>
            <div><label for="stock">商品代码 <span>可留空</span></label><input id="stock" v-model="stock" maxlength="128" placeholder="按源代码精确匹配" :disabled="busy || queryBusy" @input="clearResult" /></div>
            <button type="submit" :disabled="busy || queryBusy || dataset.status !== 'READY'">{{ queryBusy ? '正在查询…' : '查询并保存' }}</button>
          </form>
          <p v-if="dataset.status !== 'READY'" class="notice warning">当前数据集{{ statusLabel[dataset.status] }}，暂不能查询金额。</p>
          <div v-if="queryError" class="notice danger" role="alert" data-testid="query-error">{{ queryError }}</div>
          <div v-if="!saved && !queryBusy" class="empty-state">选择月份后点击“查询并保存”。刷新时将从服务端读取已保存结果。</div>
          <p v-if="queryBusy" role="status" class="empty-state">正在读取结果…</p>
          <article v-if="saved" class="surface result-panel" data-testid="saved-result">
            <div class="result-heading"><div><h2>{{ monthly?.month ?? `${series?.date_from} 至 ${series?.date_to}` }} 查询结果</h2><p>已保存，刷新可恢复</p></div><span class="state-tag" :data-state="saved.result.status" data-testid="result-status">{{ statusLabel[saved.result.status] }}</span></div>
            <div v-if="saved.result.status === 'NO_DATA'" class="notice warning">该期间没有源数据。空值不代表零收入，未自动替换为其他月份。</div>
            <div v-if="saved.result.status === 'EMPTY_RESULT'" class="notice">源期间有数据，但当前国家或商品筛选没有匹配行，金额为零。</div>
            <div v-if="saved.result.status === 'PARTIAL_PERIOD'" class="notice warning">该月份覆盖不完整。以下仅为已观测期间的金额，不能视作完整月份。</div>
            <template v-if="monthly">
              <p class="result-filters">国家：{{ monthly.filters.country ?? '全部' }}　商品：{{ monthly.filters.stock_code ?? '全部' }}</p>
              <div class="table-scroll"><table class="amount-table"><caption>月度交易行金额，GBP</caption><thead><tr><th scope="col">指标</th><th scope="col">显示金额（两位）</th><th scope="col">精确金额（三位）</th></tr></thead><tbody><tr v-for="row in amountRows" :key="row.key" :class="{ 'net-row': row.key === 'net_amount' }"><th scope="row">{{ row.name }}</th><td :data-testid="`${row.key}-display`">{{ monthly[`${row.key}_display`] ?? '—' }}</td><td :data-testid="`${row.key}-exact`">{{ monthly[`${row.key}_exact`] ?? '—' }}</td></tr></tbody></table></div>
              <dl class="result-counts"><div><dt>有效发票数</dt><dd data-testid="invoice-count">{{ monthly.positive_invoice_count ?? '—' }}</dd></div><div><dt>期间源行数</dt><dd>{{ monthly.source_row_count }}</dd></div><div><dt>筛选后行数</dt><dd>{{ monthly.matched_row_count }}</dd></div></dl>
              <p class="muted">统计期间 [{{ monthly.period_start }}, {{ monthly.period_end_exclusive }})。结束时间不含在内；源时区未声明。</p>
              <details><summary>本次查询的互斥分类</summary><dl class="class-counts"><div v-for="(count, key) in monthly.primary_class_counts" :key="key"><dt>{{ classLabel[key] ?? key }}</dt><dd>{{ count }}</dd></div></dl></details>
            </template>
            <div v-if="series" class="table-scroll"><table><caption>已保存序列 {{ series.metric }}（{{ series.unit }}）</caption><thead><tr><th>月份</th><th>显示值</th><th>精确值</th><th>覆盖状态</th></tr></thead><tbody><tr v-for="point in series.points" :key="point.month"><td>{{ point.month }}</td><td>{{ point.value_display ?? '—' }}</td><td>{{ point.value_exact ?? '—' }}</td><td>{{ statusLabel[point.status] }}</td></tr></tbody></table></div>
            <details v-if="saved.result.warnings.length"><summary>结果警告（{{ saved.result.warnings.length }}）</summary><ul><li v-for="warning in saved.result.warnings" :key="warning">{{ warning }}</li></ul></details>
            <div class="result-provenance"><span>口径 {{ saved.result.metric_version }}</span><span class="identifier">查询 {{ saved.query_id }}</span><details><summary>查看结果与来源哈希</summary><p>结果 SHA-256</p><code>{{ saved.result_sha256 }}</code><p>XLSX SHA-256</p><code>{{ saved.result.data_hash }}</code></details></div>
          </article>
          <details v-if="definitions" class="surface definitions"><summary>指标口径与使用边界</summary><p>正向金额减取消类金额得到净额。有效发票数为该月正向交易中的不同 InvoiceNo 数量。</p><p>包含符合分类条件的费用条目；不是商品专属 GMV、财务收入或实际退款。金额在服务端精确汇总后按 ROUND_HALF_UP 显示两位，原始三位值保留。</p><div v-for="item in definitions.definitions" :key="item.metric"><h3>{{ item.label }}</h3><p>{{ item.formula }}</p><p>{{ item.inclusion }}</p><p>{{ item.exclusions }}</p></div></details>
        </template>
      </section>

      <section v-if="tab === 'history'" class="surface" aria-label="已保存查询">
        <h2>已保存查询 <span class="muted">{{ historyTotal }} 条</span></h2>
        <p class="muted">打开历史只读取保存的结果，不重新计算或触发模型请求。</p>
        <div v-if="historyError" class="notice danger" role="alert">{{ historyError }}<button class="secondary" @click="loadHistory(historyOffset)">重试历史列表</button></div>
        <p v-if="!history.length" class="empty-state">当前数据集还没有已保存查询。</p>
        <ol class="history-list"><li v-for="item in history" :key="item.query_id"><div><h3>{{ item.parameters.month ?? `${item.parameters.date_from} 至 ${item.parameters.date_to}` }}</h3><p>{{ statusLabel[item.status] }} · {{ item.created_at }}</p><p class="identifier">{{ item.query_id }}</p></div><button class="secondary" @click="openHistory(item.query_id)">打开查询</button></li></ol>
        <div v-if="historyTotal > 20" class="pagination"><button class="secondary" :disabled="historyOffset === 0" @click="loadHistory(historyOffset - 20)">上一页</button><span>{{ historyOffset + 1 }}–{{ Math.min(historyOffset + 20, historyTotal) }} / {{ historyTotal }}</span><button class="secondary" :disabled="historyOffset + 20 >= historyTotal" @click="loadHistory(historyOffset + 20)">下一页</button></div>
      </section>

      <aside v-if="dataset" class="source-strip" aria-label="来源与范围">
        <h2>来源与范围</h2><p>{{ dataset.source_time_min }} 至 {{ dataset.source_time_max }} · {{ dataset.currency }} · 源时区未声明</p>
        <p>数据来源：<a v-if="dataset.source_url.startsWith('https://archive.ics.uci.edu/')" :href="dataset.source_url" target="_blank" rel="noopener noreferrer">UCI Online Retail</a><span v-else>{{ dataset.source_url }}</span></p>
        <details><summary>数据身份与版本</summary><p>数据集 {{ dataset.dataset_id }}</p><p>XLSX SHA-256</p><code data-testid="data-hash">{{ dataset.data_hash }}</code><p>转换 {{ dataset.transform_version }} · 指标 {{ dataset.metric_version }}</p></details>
      </aside>
    </main>
    <footer class="retail-footer"><span>本地历史数据分析</span><span>保留原始记录 · 精确金额可追溯</span></footer>
  </div>
</template>
