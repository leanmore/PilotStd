<script setup lang="ts">
defineOptions({ name: 'SystemResources' })
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import ProgressBar from 'primevue/progressbar'
import { getSystemResources } from '@/api/system'
import type { RouteTag } from '@/types/route-tag'
import PageContainer from '@/components/ui/PageContainer.vue'
import AppCard from '@/components/ui/AppCard.vue'

const { t } = useI18n()

const cpu = ref({ percent: 0, count: 0 })
const memory = ref({ percent: 0, total: 0, available: 0 })
const disk = ref({ percent: 0, total: 0, free: 0 })
let timer: ReturnType<typeof setInterval> | null = null

const formatBytes = (b: number) => (b / (1024 * 1024 * 1024)).toFixed(1) + ' GB'

const fetchResources = async (routeTag?: RouteTag) => {
  try {
    const resp = await getSystemResources(routeTag ? { routeTag } : undefined)
    if (resp.data.cpu) cpu.value = resp.data.cpu
    if (resp.data.memory) memory.value = resp.data.memory
    if (resp.data.disk) disk.value = resp.data.disk
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchResources('/resources')
  timer = setInterval(() => fetchResources('/resources'), 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <PageContainer :max-width="900" :title="t('system_resources.title')">
    <div class="grid">
      <AppCard v-for="item in [
        { t: 'CPU', p: cpu.percent, d: t('system_resources.cores', { n: cpu.count }) },
        { t: t('system_resources.memory'), p: memory.percent, d: t('system_resources.memory_detail', { total: formatBytes(memory.total), available: formatBytes(memory.available) }) },
        { t: t('system_resources.disk'), p: disk.percent, d: t('system_resources.disk_detail', { free: formatBytes(disk.free) }) },
      ]" :key="item.t">
        <template #content>
          <h3>{{ item.t }}</h3>
          <ProgressBar :value="item.p" :show-value="true" :dt="{ height: 'var(--size-24)' }" />
          <p class="detail">{{ item.d }}</p>
        </template>
      </AppCard>
    </div>
  </PageContainer>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--space-16); }
h3 { margin: 0 0 var(--space-12); font-size: var(--font-size-15); }
.detail { margin-top: var(--space-8); font-size: var(--font-size-13); color: var(--text-secondary); }
</style>
