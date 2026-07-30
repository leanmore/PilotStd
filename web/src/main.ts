import './style.css'
import './theme.css'
import 'primeicons/primeicons.css'
import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { createI18n } from 'vue-i18n'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import Toast from 'primevue/toast'
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import ConfirmDialog from 'primevue/confirmdialog'
import DataTable from 'primevue/datatable'
import DataView from 'primevue/dataview'
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Paginator from 'primevue/paginator'
import Password from 'primevue/password'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Badge from 'primevue/badge'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import ToggleSwitch from 'primevue/toggleswitch'
import App from './App.vue'
import router from './router'
import zhCN from './locales/zh-CN.json'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import { isDarkTheme } from '@/config/themes'
import { SUPERUSER_USERNAME } from './config'
import { getItem } from '@/lib/storage'

import { primevueLocales } from '@/lib/primevueLocale'

const savedLocale = (getItem('locale') || 'zh-CN') as 'zh-CN' | 'en' | 'zh-TW'

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
const savedTheme = getItem('theme') || 'light'
const initialDark = isDarkTheme(savedTheme)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: { dark: initialDark },
  },
  locale: primevueLocales[savedLocale] || primevueLocales['en'],
  ripple: true,
})
app.use(ConfirmationService)
app.use(ToastService)
app.use(i18n)

// 语言切换时同步更新 PrimeVue 日历本地化
watch(() => i18n.global.locale.value, (newLocale: string) => {
  const cfg = app.config.globalProperties.$primevue?.config
  if (cfg) {
    cfg.locale = primevueLocales[newLocale] || primevueLocales['en']
  }
})
app.component('Accordion', Accordion)
app.component('AccordionTab', AccordionTab)
app.component('Button', Button)
app.component('DatePicker', DatePicker)
app.component('Card', Card)
app.component('Checkbox', Checkbox)
app.component('Column', Column)
app.component('ConfirmDialog', ConfirmDialog)
app.component('DataTable', DataTable)
app.component('DataView', DataView)
app.component('Dialog', Dialog)
app.component('Dropdown', Dropdown)
app.component('InputNumber', InputNumber)
app.component('InputText', InputText)
app.component('Message', Message)
app.component('Paginator', Paginator)
app.component('Password', Password)
app.component('ProgressBar', ProgressBar)
app.component('Select', Select)
app.component('SelectButton', SelectButton)
app.component('Tag', Tag)
app.component('Textarea', Textarea)
app.component('ToggleSwitch', ToggleSwitch)
app.component('Toast', Toast)
app.component('Tabs', Tabs)
app.component('TabList', TabList)
app.component('Tab', Tab)
app.component('TabPanels', TabPanels)
app.component('TabPanel', TabPanel)
app.component('Badge', Badge)

// G-028 启动校验：生产环境缺少 SUPERUSER 配置时阻止挂载
if (!SUPERUSER_USERNAME) {
  console.error('❌ VITE_SUPERUSER_ROLE 未设置，前端超管功能不可用')
  if (import.meta.env.PROD) {
    throw new Error('VITE_SUPERUSER_ROLE 环境变量未设置，无法启动生产环境')
  }
}

app.mount('#app')
