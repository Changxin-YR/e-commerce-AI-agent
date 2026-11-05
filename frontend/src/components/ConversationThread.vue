<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Run } from '../api/agent'
import { runError, runLabels } from '../api/agent'
import AppIcon from './AppIcon.vue'
import StateBadge from './StateBadge.vue'
const props = defineProps<{ run: Run; connection: string }>()
defineEmits<{ report: [id: string] }>()
const viewport = ref<HTMLElement>(), following = ref(true)
const active = computed(() => ['QUEUED', 'RUNNING'].includes(props.run.run_status))
const messages = computed(() => props.run.messages?.length ? props.run.messages : [
  { id: props.run.run_id, role: 'user', text: props.run.input.question, status: 'complete' },
])
const phases: Record<string, string> = { received: '问题已接收，等待执行', model: '正在生成回复', tools: '正在调用数据工具', review: '正在核验结果与引用', finalize: '正在保存报告', clarify: '等待你补充条件', complete: '分析已完成' }
const names: Record<string, string> = { get_dataset_profile: '读取数据集概况', get_quality_summary: '检查数据质量', get_metric_definitions: '读取指标口径', query_metric_series: '查询指标趋势', rank_entities: '计算交易排名', compare_periods: '比较期间变化', decompose_change: '拆解变化贡献', inspect_transactions: '核对交易明细' }
function onScroll() { const el = viewport.value; if (el) following.value = el.scrollHeight - el.scrollTop - el.clientHeight < 72 }
async function toLatest() { following.value = true; await nextTick(); const el = viewport.value; if (el) el.scrollTop = el.scrollHeight }
watch(() => props.run, async () => { if (following.value) await toLatest() }, { immediate: true })
watch(() => props.run.run_id, toLatest)
</script>

<template>
  <div class="conversation-thread">
    <div ref="viewport" class="conversation-scroll" role="region" aria-label="分析对话记录" tabindex="0" @scroll="onScroll">
      <div v-for="turn in run.conversation_history ?? []" :key="turn.run_id" class="previous-turn">
        <article class="chat-message user"><span class="speaker">你</span><p>{{ turn.question }}</p></article>
        <article class="chat-message assistant"><span class="speaker"><AppIcon name="spark" />分析助手 · 先前回复</span><p>{{ turn.message || (runLabels[turn.status] ?? turn.status) }}</p>
          <ul v-if="turn.claims.length" class="previous-claims"><li v-for="claim in turn.claims" :key="claim.claim_id">{{ claim.label }}：{{ claim.value }} {{ claim.unit ?? '' }}</li></ul>
        </article>
      </div>
      <article v-for="message in messages" :key="message.id" class="chat-message" :class="message.role" :data-message-id="message.id">
        <template v-if="message.role === 'tool'">
          <details class="chat-tool"><summary><AppIcon name="activity" /><strong>{{ names[message.text] ?? message.text }}</strong><StateBadge :state="message.status">{{ runLabels[message.status] ?? message.status }}</StateBadge></summary>
            <p v-if="'error_code' in message && message.error_code" class="notice danger">{{ message.error_code }}</p>
            <pre v-if="'arguments' in message">{{ JSON.stringify(message.arguments, null, 2) }}</pre>
            <p v-if="'evidence_ref' in message" class="identifier">证据 {{ message.evidence_ref }}</p>
          </details>
        </template>
        <template v-else>
          <span class="speaker"><AppIcon v-if="message.role === 'assistant'" name="spark" />{{ message.role === 'user' ? '你' : '分析助手' }}<small v-if="message.status === 'draft'">正在输出 · 待核验</small><small v-else-if="message.status === 'rejected'">此版未通过核验</small><small v-else-if="message.status === 'interrupted'">未完成草稿</small></span>
          <p class="message-text" :class="{ 'is-streaming': message.status === 'draft' && active }">{{ message.text }}</p>
        </template>
      </article>
      <div v-if="run.result" class="chat-result">
        <div class="result-heading"><h3>分析结果</h3><StateBadge :state="run.result.business_result">{{ runLabels[run.result.business_result] ?? run.result.business_result }}</StateBadge></div>
        <p v-if="!run.messages?.some(m => m.role === 'assistant' && m.text === run.result?.message)">{{ run.result.message }}</p>
        <div v-if="run.result.claims.length" class="table-scroll" role="region" aria-label="核验后的数值" tabindex="0"><table><thead><tr><th>指标</th><th>精确值</th></tr></thead><tbody><tr v-for="claim in run.result.claims" :key="claim.claim_id"><th>{{ claim.label }}</th><td class="exact-value">{{ claim.value }} {{ claim.unit ?? '' }}</td></tr></tbody></table></div>
        <p class="muted">数值来自工具证据，说明文字仍需结合业务判断。</p>
        <button v-if="run.result_ref" class="secondary" @click="$emit('report', run.result_ref)"><AppIcon name="report" />查看完整报告与引用</button>
      </div>
      <p v-if="run.error_code" class="notice danger" role="alert">{{ runError(run.error_code) }} <code>{{ run.error_code }}</code></p>
      <div class="chat-progress" role="status" aria-live="polite"><AppIcon :name="active ? 'activity' : run.run_status === 'PASS' ? 'check' : 'warning'" /><span>{{ run.cancel_requested && active ? '正在停止，保留已收到的记录…' : active ? (phases[run.phase] ?? '正在执行') : (runLabels[run.run_status] ?? run.run_status) }}</span><small v-if="active">{{ connection === 'reconnecting' ? '连接中断，正在重连…' : connection === 'unavailable' ? '实时连接不可用，请刷新任务' : connection === 'polling' ? '正在刷新状态' : '实时接收' }}</small></div>
    </div>
    <button v-if="!following" class="secondary jump-latest" @click="toLatest">回到最新消息</button>
  </div>
</template>
