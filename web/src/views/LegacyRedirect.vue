<template>
  <div class="flex justify-content-center align-items-center" style="min-height: 400px">
    <div class="text-center">
      <ProgressSpinner />
      <p class="mt-3 text-color-secondary">正在跳转...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LegacyRedirect' })
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProgressSpinner from 'primevue/progressspinner'
import { getAnnouncementByNo } from '@/api/announce'
import { SOURCE_TO_URL } from '@/constants/sourceMapping'

const route = useRoute()
const router = useRouter()
const announceNo = route.params.announceNo as string

onMounted(async () => {
  try {
    const result = await getAnnouncementByNo(announceNo, '/announce')

    if (!Array.isArray(result) || result.length === 0) {
      router.replace({ name: 'NotFound', query: {} })
      return
    }

    if (result.length === 1) {
      const item = result[0]
      const urlSource = SOURCE_TO_URL[item.source_site] || item.source_site
      router.replace(`/announce/${urlSource}/${encodeURIComponent(announceNo)}`)
      return
    }

    // 多条冲突 → 跳转到列表页并提示用户选择
    router.replace(`/announce?conflict=true&no=${encodeURIComponent(announceNo)}`)
  } catch {
    router.replace({ name: 'NotFound', query: {} })
  }
})
</script>
