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
import Accordion from 'primevue/accordion'
import AccordionTab from 'primevue/accordiontab'
import Button from 'primevue/button'
import Calendar from 'primevue/calendar'
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
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import Toast from 'primevue/toast'
import ToggleSwitch from 'primevue/toggleswitch'
import App from './App.vue'
import router from './router'
import zhCN from './locales/zh-CN.json'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'
import { isDarkTheme } from '@/config/themes'
import { getItem } from '@/lib/storage'

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

// PrimeVue 日历本地化（与 Vue I18n 联动）
const primevueLocales: Record<string, any> = {
  'zh-CN': {
    firstDayOfWeek: 1,
    dayNames: ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'],
    dayNamesShort: ['周日', '周一', '周二', '周三', '周四', '周五', '周六'],
    dayNamesMin: ['日', '一', '二', '三', '四', '五', '六'],
    monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'],
    monthNamesShort: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
  },
  en: {
    firstDayOfWeek: 0,
    dayNames: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    dayNamesShort: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    dayNamesMin: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
    monthNames: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    monthNamesShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  },
  'zh-TW': {
    firstDayOfWeek: 1,
    dayNames: ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'],
    dayNamesShort: ['週日', '週一', '週二', '週三', '週四', '週五', '週六'],
    dayNamesMin: ['日', '一', '二', '三', '四', '五', '六'],
    monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'],
    monthNamesShort: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
  },
}

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
app.component('Calendar', Calendar)
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
app.component('Toast', Toast)
app.component('ToggleSwitch', ToggleSwitch)
app.mount('#app')
