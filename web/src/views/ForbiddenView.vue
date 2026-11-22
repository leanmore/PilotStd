<script setup lang="ts">
/**
 * 403 页面：普通用户访问 admin-only 路由时由 router.beforeEach 重定向至此。
 * 不请求任何后端接口，避免二次 403。
 */
defineOptions({ name: 'ForbiddenView' })
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/ui/AppButton.vue'

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="forbidden">
    <div class="code">403</div>
    <h1>{{ t('nav.forbidden') }}</h1>
    <p class="desc">{{ t('nav.forbidden_desc') }}</p>
<AppButton
      :label="t('nav.back_home')"
      icon="pi pi-home"
      @click="router.push('/')"
      size="m"
      type="secondary"
    />
  </div>
</template>

<style scoped>
.forbidden {
  max-width: 560px;
  /* TODO: [Design Debt] 12vh auto 0 无精确令牌，暂不替换，待定令牌后统一处理 */
  margin: 12vh auto 0;
  text-align: center;
  padding: var(--space-32);
}
.code {
  font-size: var(--font-size-72);
  font-weight: var(--font-weight-bold);
  color: var(--primary);
  line-height: var(--line-height-none);
}
h1 {
  margin: var(--space-16) 0 var(--space-8);
}
.desc {
  color: var(--text-dim);
  margin-bottom: var(--space-24);
}
</style>
