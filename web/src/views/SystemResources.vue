<script setup lang="ts">
defineOptions({ name: 'SystemResources' })
import { ref, onMounted, onUnmounted } from 'vue'
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import axios from 'axios'

const cpu = ref({ percent: 0, count: 0 })
const memory = ref({ percent: 0, total: 0, available: 0 })
const disk = ref({ percent: 0, total: 0, free: 0 })
let timer: ReturnType<typeof setInterval> | null = null

const formatBytes = (b: number) => (b / (1024 * 1024 * 1024)).toFixed(1) + ' GB'

const fetchResources = async () => {
  try {
    const resp = await axios.get('/api/system/resources')
    if (resp.data.cpu) cpu.value = resp.data.cpu
    if (resp.data.memory) memory.value = resp.data.memory
    if (resp.data.disk) disk.value = resp.data.disk
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchResources()
  timer = setInterval(fetchResources, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">系统资源</h2>
    <div class="grid">
      <Card v-for="item in [
        { t: 'CPU', p: cpu.percent, d: `${cpu.count} 核` },
        { t: '内存', p: memory.percent, d: `${formatBytes(memory.total)} / ${formatBytes(memory.available)} 可用` },
        { t: '磁盘', p: disk.percent, d: `${formatBytes(disk.free)} 剩余` },
      ]" :key="item.t">
        <template #content>
          <h3>{{ item.t }}</h3>
          <ProgressBar :value="item.p" :show-value="true" style="height: 24px" />
          <p class="detail">{{ item.d }}</p>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 900px; }
.page-title { margin: 0 0 20px; font-size: 20px; font-weight: 600; color: var(--text-heading); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
h3 { margin: 0 0 12px; font-size: 15px; }
.detail { margin-top: 8px; font-size: 13px; color: var(--text-color-secondary); }
</style>
