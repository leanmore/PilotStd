<!--
  为什么封装这个组件？
  PrimeVue 4.x 的全局 locale 配置对 Calendar 组件存在 Bug，
  必须显式传入 :locale 才能正确汉化。使用此组件可自动注入
  中文语言包，业务页面无需手动传参，也不会遗漏。
  如果 PrimeVue 未来修复了此问题，只需改这一个文件即可。
-->
<script setup lang="ts">
import Calendar from 'primevue/calendar'
import { primevueLocales } from '@/lib/primevueLocale'
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

const { locale } = useI18n()
const calendarLocale = computed(() => primevueLocales[locale.value] || primevueLocales['zh-CN'])
</script>

<template>
  <Calendar v-bind="$attrs" :locale="calendarLocale" />
</template>
