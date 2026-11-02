<script setup lang="ts">
import HealthPanel from './components/HealthPanel.vue'
import RetailWorkspace from './components/RetailWorkspace.vue'
const healthView = new URL(location.href).searchParams.get('view') === 'health'
</script>

<template><HealthPanel v-if="healthView" /><RetailWorkspace v-else /></template>
