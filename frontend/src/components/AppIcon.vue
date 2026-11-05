<script setup lang="ts">
defineProps<{ name: string }>()
const paths: Record<string, string> = {
  spark: 'M12 3 14.5 9.5 21 12 14.5 14.5 12 21 9.5 14.5 3 12 9.5 9.5Z M19 2v4 M17 4h4',
  chart: 'M4 4v16h16 M8 15v-4 M12 15V7 M16 15v-6',
  report: 'M6 3h9l4 4v14H6Z M14 3v5h5 M9 12h7 M9 16h7',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  database: 'M20 6c0 2-4 3-8 3S4 8 4 6s4-3 8-3 8 1 8 3Z M4 6v12c0 2 4 3 8 3s8-1 8-3V6 M4 12c0 2 4 3 8 3s8-1 8-3',
  history: 'M4 5v5h5 M4 10a8 8 0 1 1 0 5 M12 7v5l3 2',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  refresh: 'M20 4v6h-6 M4 20v-6h6 M5 9a7 7 0 0 1 12-4l3 3 M4 16l3 3a7 7 0 0 0 12-4',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
  check: 'M5 12l4 4L19 6',
  chevron: 'm9 5 7 7-7 7',
  shield: 'M12 3 4 6v6c0 4 8 9 8 9s8-5 8-9V6Z M8 12l3 3 5-6',
  upload: 'M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6',
  warning: 'M12 3 2 21h20Z M12 9v5 M12 17v1',
  close: 'm6 6 12 12 M18 6 6 18',
  code: 'm8 6-6 6 6 6 M16 6l6 6-6 6 M14 3l-4 18',
}
</script>
<template><svg class="app-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] ?? paths.spark" /></svg></template>
