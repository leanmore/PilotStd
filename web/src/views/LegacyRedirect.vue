<template>
  <div class="flex justify-content-center align-items-center" style="min-height: 400px">
    <div class="text-center">
      <AppLoading variant="spinner" size="l" :label="t('legacy.redirecting')" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LegacyRedirect' })

import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getAnnouncementByNo } from '@/api/announce'
import { SOURCE_TO_URL } from '@/constants/sourceMapping'
import AppLoading from '@/components/ui/AppLoading.vue'

const { t } = useI18n()
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
