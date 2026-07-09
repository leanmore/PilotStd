<!--
  为什么封装这个组件？
  PrimeVue 4.x 中 Calendar 已废弃，迁移到 DatePicker。
  显式传入 :locale 确保与界面语言联动，业务代码无需关心。
-->
<script setup lang="ts">
defineOptions({ name: 'AppCalendar' })
import DatePicker from 'primevue/datepicker'
import { primevueLocales } from '@/lib/primevueLocale'
import { useI18n } from 'vue-i18n'
import { computed, onMounted, getCurrentInstance } from 'vue'

const { locale } = useI18n()
const calendarLocale = computed(() => primevueLocales[locale.value] || primevueLocales['zh-CN'])

// PrimeVue 4.5 DatePicker 月份/星期名硬读 $primevue.config.locale，
// :locale prop 对月份面板无效，需直接更新全局 locale。
onMounted(() => {
  const app = getCurrentInstance()?.appContext.app
  if (app?.config.globalProperties.$primevue?.config) {
    app.config.globalProperties.$primevue.config.locale = calendarLocale.value
  }
})
</script>

<template>
  <DatePicker v-bind="$attrs" :locale="calendarLocale" />
</template>
