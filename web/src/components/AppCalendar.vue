<!--
  为什么封装这个组件？
  PrimeVue 4.x 中 Calendar 已废弃，迁移到 DatePicker。
  语言联动：PrimeVue 4.5 DatePicker 的月份/星期名**硬读 `$primevue.config.locale`**，
  它没有 `locale` prop（传 `:locale` 只会落到 $attrs 变成非法 DOM 属性）
  → 本组件在挂载时**并监听界面语言变化**更新全局 locale，业务代码无需关心。
-->
<script setup lang="ts">
defineOptions({ name: 'AppCalendar' })
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import { primevueLocales } from '@/lib/primevueLocale'
import { useI18n } from 'vue-i18n'
import { computed, onMounted, watch, getCurrentInstance } from 'vue'

const { locale } = useI18n()
const calendarLocale = computed(() => primevueLocales[locale.value] || primevueLocales['zh-CN'])

/** 把当前语言包写进 PrimeVue 全局配置（DatePicker 面板只认这里）。 */
// 注意：`getCurrentInstance()` 只在 setup 期有效；在 watch 回调里调用会拿到 null
// → 必须在此处（setup 期）先捕获 app 引用（2026-11-25 实测）。
const app = getCurrentInstance()?.appContext.app

function applyLocale(): void {
  const cfg = app?.config.globalProperties.$primevue?.config
  if (cfg) cfg.locale = calendarLocale.value
}

// 2026-11-25 修复（D-3）：原实现只在 onMounted 设置一次 → 运行中切换语言（不重挂载）
// 面板月份/星期名不更新；且模板给 AppDatePicker 传了它没有的 `:locale` prop。
onMounted(applyLocale)
watch(calendarLocale, applyLocale)
</script>

<template>
  <AppDatePicker v-bind="$attrs" />
</template>
