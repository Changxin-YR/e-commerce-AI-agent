<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchHealth, HealthError } from '../api/health'
import type { HealthResponse } from '../api/health'
import WorkspaceShell from './WorkspaceShell.vue'

const state = ref<'loading' | 'success' | 'error'>('loading')
const health = ref<HealthResponse | null>(null)
const error = ref('')
const errorCode = ref('')
const checkedAt = ref('')
let controller: AbortController | undefined
let timeout: ReturnType<typeof setTimeout> | undefined
let unmounted = false
function navigate(view: string) { location.assign(`/?view=${view}`) }

const title = computed(() => ({
  loading: '正在检查本地连接',
  success: '本地服务已连接',
  error: '本地服务暂不可用',
})[state.value])

async function checkConnection() {
  if (controller) controller.abort()
  if (timeout) clearTimeout(timeout)
  const active = new AbortController()
  controller = active
  state.value = 'loading'
  health.value = null
  error.value = ''
  errorCode.value = ''
  let timedOut = false
  timeout = setTimeout(() => { timedOut = true; active.abort() }, 8000)

  try {
    const result = await fetchHealth(active.signal)
    if (unmounted || controller !== active) return
    health.value = result
    state.value = 'success'
    checkedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (cause: unknown) {
    if (unmounted || controller !== active) return
    error.value = timedOut
      ? '健康检查超过 8 秒。请确认后端服务已启动，然后重新检查。'
      : cause instanceof HealthError
        ? cause.message
        : '无法连接后端。请确认本地服务已启动，然后重新检查。'
    errorCode.value = timedOut ? 'TIMEOUT' : cause instanceof HealthError ? cause.code : 'NETWORK_ERROR'
    state.value = 'error'
  } finally {
    if (controller === active && timeout) clearTimeout(timeout)
  }
}

onMounted(checkConnection)
onUnmounted(() => {
  unmounted = true
  controller?.abort()
  if (timeout) clearTimeout(timeout)
})
</script>

<template>
  <WorkspaceShell view="health" @navigate="navigate">
    <div class="health-content">
      <div class="intro">
        <h1>服务状态</h1>
        <p class="intro-copy">检查 AI 工作台依赖的本地后端与数据库连接。</p>
      </div>

      <section class="connection-panel" aria-labelledby="connection-title">
        <div class="connection-summary" :class="state">
          <span class="status-icon" aria-hidden="true">{{ state === 'success' ? '✓' : state === 'error' ? '!' : '…' }}</span>
          <div class="status-content" role="status" aria-live="polite">
            <h2 id="connection-title" data-testid="health-status">{{ title }}</h2>
            <p v-if="state === 'success'">健康接口与 SQLite 数据库均已响应。</p>
            <p v-else-if="state === 'loading'">正在请求后端健康接口，请稍候。</p>
            <p v-else>当前无法确认服务就绪，请根据提示检查。</p>
          </div>
          <button type="button" :disabled="state === 'loading'" @click="checkConnection">
            {{ state === 'loading' ? '检查中…' : '重新检查' }}
          </button>
        </div>

        <div v-if="state === 'error'" class="error-message" role="alert" data-testid="health-error">
          <p>{{ error }}</p>
          <span>错误标识：{{ errorCode }}</span>
        </div>

        <dl class="connection-details">
          <div><dt>服务版本</dt><dd>{{ health?.version ?? '等待连接' }}</dd></div>
          <div><dt>数据库</dt><dd>{{ health ? `SQLite ${health.database.sqlite_version}` : '尚未确认' }}</dd></div>
          <div><dt>迁移版本</dt><dd>{{ health?.database.schema_revision ?? '尚未确认' }}</dd></div>
          <div><dt>最近成功检查</dt><dd>{{ checkedAt || '尚无成功记录' }}</dd></div>
        </dl>
        <div class="endpoint-note"><span>检查接口</span><code>GET /healthz</code><span>由本地后端实时返回</span></div>
      </section>

      <aside class="scope-note" aria-labelledby="scope-title">
        <span class="scope-symbol" aria-hidden="true">i</span>
        <div>
          <h2 id="scope-title">服务连接检查</h2>
          <p>服务连接正常后，可返回工作台继续分析。模型是否可用，请查看智能分析页的实际状态。</p><a class="button-link secondary" href="/?view=analysis">返回 AI 工作台</a>
        </div>
      </aside>
    </div>
  </WorkspaceShell>
</template>
