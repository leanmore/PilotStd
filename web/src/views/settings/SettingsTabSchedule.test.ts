// web/src/views/settings/SettingsTabSchedule.test.ts
// 回归守卫（技术债 #20）：收藏标准下载归档的 cron 必须出现在设置页，且保存时随载荷提交。
// 修复前该任务既不在设置页、也不在 put_settings 的重排列表，用户既看不到也改不了。
// 另加 i18n 守卫：文案必须来自 locales（张成 key 会直接断言失败），切语言后任务名随之变化。

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { createI18n } from 'vue-i18n'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import ToggleSwitch from 'primevue/toggleswitch'
import SettingsTabSchedule from './SettingsTabSchedule.vue'
import { getSettings, putSettings } from '@/api'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'

vi.mock('@/api', () => ({
  getSettings: vi.fn().mockResolvedValue({ tasks: {} }),
  putSettings: vi.fn().mockResolvedValue({ ok: true }),
}))

/** 用真实 locale 文件挂载（空 messages 会让 t() 直接回显 key，断言就失去意义）。 */
async function mountTab(locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN') {
  const i18n = createI18n({
    legacy: false,
    locale,
    messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en },
  })
  const wrapper = mount(SettingsTabSchedule, {
    global: {
      plugins: [PrimeVue, ToastService, i18n],
      components: { Button, InputText, Message, ToggleSwitch },
      stubs: { FileMonitor: true },
    },
  })
  await flushPromises()
  return wrapper
}

function cronInput(wrapper: ReturnType<typeof mount>, placeholder: string) {
  return wrapper.findAll('input').find((i) => i.attributes('placeholder') === placeholder)
}

describe('SettingsTabSchedule 定时任务', () => {
  beforeEach(() => {
    vi.mocked(getSettings).mockResolvedValue({ tasks: {} } as never)
    vi.mocked(putSettings).mockResolvedValue({ ok: true } as never)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('渲染收藏标准下载归档的 cron 输入框（#20 回归守卫）', async () => {
    const wrapper = await mountTab()

    expect(wrapper.text()).toContain('收藏标准下载归档')
    expect(cronInput(wrapper, '0 4 * * *'), '缺少 auto_archive_retry 的 cron 输入框').toBeTruthy()
  })

  it('保存时把 auto_archive_retry_cron 一并提交（否则改了也不生效）', async () => {
    const wrapper = await mountTab()
    const input = cronInput(wrapper, '0 4 * * *')!
    await input.setValue('* * * * *')

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存配置'))!
    await saveBtn.trigger('click')
    await flushPromises()

    expect(putSettings).toHaveBeenCalledWith(
      expect.objectContaining({
        tasks: expect.objectContaining({
          auto_archive_retry_cron: '* * * * *',
          auto_archive_retry_enabled: true,
        }),
      }),
    )
  })

  it('加载已有配置时回填该任务（不覆盖成默认值）', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      tasks: { auto_archive_retry_cron: '0 6 * * *', auto_archive_retry_enabled: true },
    } as never)

    const wrapper = await mountTab()
    const values = wrapper.findAll('input').map((i) => (i.element as HTMLInputElement).value)

    expect(values, '应从后端配置回填 cron 值').toContain('0 6 * * *')
  })

  // ── i18n 守卫：文案必须来自 locales，且随语言切换而变化 ──

  it('五个任务名与卡片标题来自 i18n（zh-CN）', async () => {
    const wrapper = await mountTab('zh-CN')
    const text = wrapper.text()

    for (const label of [
      '自动扫描标准库',
      '公告自动检查',
      '实施日期到期提醒',
      '适配器健康检查',
      '收藏标准下载归档',
      'Cron 表达式',
      '保存配置',
    ]) {
      expect(text, `zh-CN 缺文案: ${label}`).toContain(label)
    }
    expect(text).toContain('定时任务')
  })

  it('切换语言后任务名与卡片标题随之变化（en）', async () => {
    const wrapper = await mountTab('en')
    const text = wrapper.text()

    expect(text).toContain('Scheduled Tasks')
    expect(text).toContain('Favorite Standard Download & Archive')
    expect(text).toContain('Adapter Health Check')
    expect(text).toContain('Cron Expression')
    expect(text).toContain('Save Config')
    // 反向断言：英文界面不得再出现中文任务名
    expect(text, 'en 下仍出现中文任务名').not.toContain('收藏标准下载归档')
    expect(text).not.toContain('自动扫描标准库')
  })

  it('切换语言后任务名随之变化（zh-TW）', async () => {
    const wrapper = await mountTab('zh-TW')
    const text = wrapper.text()

    expect(text).toContain('定時任務')
    expect(text).toContain('收藏標準下載歸檔')
    expect(text).toContain('自動掃描標準庫')
  })
})
