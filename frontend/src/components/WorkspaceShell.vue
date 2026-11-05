<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { views } from '../navigation'
import AppIcon from './AppIcon.vue'
const props = defineProps<{ view: string }>()
const emit = defineEmits<{ navigate: [view: string] }>()
const menuOpen = ref(false), menuButton = ref<HTMLButtonElement>()
const activeName = computed(() => views.find(item => item.id === props.view)?.name ?? '服务状态')
const groups = ['智能工作区', '记录与数据']
watch(() => props.view, () => { document.title = `${activeName.value} · 电商 AI 工作台`; menuOpen.value = false }, { immediate: true })
function go(view: string) { menuOpen.value = false; emit('navigate', view); void nextTick(() => document.querySelector<HTMLElement>('#main-content')?.focus()) }
function closeMenu() { if (menuOpen.value) { menuOpen.value = false; menuButton.value?.focus() } }
</script>
<template>
  <div class="retail-shell" @keydown.esc="closeMenu">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="workspace-topbar">
      <button ref="menuButton" class="icon-button mobile-menu secondary" :aria-expanded="menuOpen" aria-controls="workspace-sidebar" aria-label="切换导航" @click="menuOpen = !menuOpen"><AppIcon name="menu" /></button>
      <div class="breadcrumb"><span>工作台</span><AppIcon name="chevron" /><span>{{ activeName }}</span></div>
      <div class="topbar-meta"><span class="local-dot" aria-hidden="true"></span><span>本地工作区</span><a href="/?view=health">服务状态<AppIcon name="activity" /></a></div>
    </header>
    <aside id="workspace-sidebar" class="workspace-sidebar" :class="{ 'is-open': menuOpen }">
      <a class="retail-brand" href="/?view=analysis"><span class="brand-symbol"><AppIcon name="spark" /></span><span>电商智能体<small>经营数据分析工作台</small></span></a>
      <nav class="workspace-nav" aria-label="功能视图">
        <div v-for="group in groups" :key="group" class="nav-group"><p>{{ group }}</p>
          <button v-for="item in views.filter(value => value.group === group)" :key="item.id" :class="{ active: view === item.id }" :aria-label="item.name" :aria-current="view === item.id ? 'page' : undefined" @click="go(item.id)"><AppIcon :name="item.icon" /><span>{{ item.name }}</span><span v-if="item.id === 'analysis'" class="ai-label" aria-hidden="true">AI</span></button>
        </div>
      </nav>
      <div class="sidebar-note"><AppIcon name="shield" /><strong>每个结论，回到证据</strong><p>基于历史交易数据<br />保留精确金额与来源</p></div>
      <a class="sidebar-service" href="/?view=health"><AppIcon name="activity" />检查服务连接<AppIcon name="chevron" /></a>
    </aside>
    <div class="workspace-body"><main id="main-content" class="retail-main" tabindex="-1"><slot /></main>
      <footer class="retail-footer"><span>电商 AI 工作台</span><span>历史数据分析 · 数值可追溯</span></footer>
    </div>
  </div>
</template>
