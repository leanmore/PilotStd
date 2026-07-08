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
import { computed } from 'vue'

const { locale } = useI18n()
const calendarLocale = computed(() => primevueLocales[locale.value] || primevueLocales['zh-CN'])
</script>

<template>
  <DatePicker v-bind="$attrs" :locale="calendarLocale" />
</template>
