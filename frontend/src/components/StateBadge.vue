<script setup lang="ts">
defineProps<{ state?: string }>()
</script>
<template><span class="state-tag" :data-state="state"><span class="state-dot" aria-hidden="true"></span><slot /></span></template>
