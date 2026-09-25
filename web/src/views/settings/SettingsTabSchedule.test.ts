// web/src/views/settings/SettingsTabSchedule.test.ts
// 回归守卫（技术债 #20）：收藏下载链的 cron 必须出现在设置页，且保存时随载荷提交。
// 修复前该任务既不在设置页、也不在 put_settings 的重排列表，用户既看不到也改不了。

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

vi.mock('@/api', () => ({
  getSettings: vi.fn().mockResolvedValue({ tasks: {} }),
  putSettings: vi.fn().mockResolvedValue({ ok: true }),
}))

async function mountTab() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': {} } })
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

  it('渲染收藏下载链的 cron 输入框（#20 回归守卫）', async () => {
    const wrapper = await mountTab()

    expect(wrapper.text()).toContain('收藏下载链')
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
})
