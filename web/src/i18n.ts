// web/src/i18n.ts — 全局 i18n 实例（从 main.ts 抽出，供**非组件模块**调用）
//
// 组件内一律用 `useI18n()` 解构的 t；composable / 工具模块没有组件上下文，
// 只能用这里的 `i18n.global.t`。实例仍由 main.ts `app.use(i18n)` 注册，语言切换逻辑不变。
import { createI18n } from 'vue-i18n'
import { getItem } from '@/lib/storage'
import zhCN from './locales/zh-CN.json'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'

const rawLocale = getItem('locale')
// 兼容旧版 JSON.stringify 写入的带引号值（如 "\"zh-CN\""）
export const savedLocale = (rawLocale ? rawLocale.replace(/^"|"$/g, '') : 'zh-CN') as 'zh-CN' | 'en' | 'zh-TW'

export const messages = {
  'zh-CN': zhCN,
  en,
  'zh-TW': zhTW,
}

export const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'zh-CN',
  messages,
})
