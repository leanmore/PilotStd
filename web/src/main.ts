import './style.css'
import './theme.css'
import 'primeicons/primeicons.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createI18n } from 'vue-i18n'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import App from './App.vue'
import router from './router'
import zhCN from './locales/zh-CN.json'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import { isDarkTheme } from '@/config/themes'

const savedLocale = (localStorage.getItem('locale') || 'zh-CN') as 'zh-CN' | 'en' | 'zh-TW'

const messages = {
  'zh-CN': zhCN,
  en,
  'zh-TW': zhTW,
}

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'zh-CN',
  messages,
})

// 检测初始主题的明暗类型
const savedTheme = localStorage.getItem('theme') || 'light'
const initialDark = isDarkTheme(savedTheme)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: { dark: initialDark },
  },
  ripple: true,
})
app.use(ConfirmationService)
app.use(ToastService)
app.use(i18n)
app.mount('#app')
