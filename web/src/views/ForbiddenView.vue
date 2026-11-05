<script setup lang="ts">
/**
 * 403 页面：普通用户访问 admin-only 路由时由 router.beforeEach 重定向至此。
 * 不请求任何后端接口，避免二次 403。
 */
defineOptions({ name: 'ForbiddenView' })
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="forbidden">
    <div class="code">403</div>
    <h1>{{ t('nav.forbidden') }}</h1>
    <p class="desc">{{ t('nav.forbidden_desc') }}</p>
    <Button :label="t('nav.back_home')" icon="pi pi-home" @click="router.push('/')" />
  </div>
</template>

<style scoped>
.forbidden {
  max-width: 560px;
  margin: 12vh auto 0;
  text-align: center;
  padding: 32px;
}
.code {
  font-size: 72px;
  font-weight: 700;
  color: var(--primary);
  line-height: 1;
}
h1 {
  margin: 16px 0 8px;
}
.desc {
  color: var(--text-dim);
  margin-bottom: 24px;
}
</style>
