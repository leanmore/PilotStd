// components/dashboard/widgets/AdapterStatusQueryCard.test.ts — 适配器名称映射 + healthText i18n 测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import AdapterStatusQueryCard from './AdapterStatusQueryCard.vue'
import http from '@/api/http'
import zhCN from '@/locales/zh-CN.json'
import en from '@/locales/en.json'

vi.mock('@/api/http', () => ({
  default: { get: vi.fn() },
}))

function makeAdapter(overrides: Record<string, unknown> = {}) {
  return {
    name: 'hbba',
    display_name: '行业标准',
    status: 'normal',
    frozen_until: null,
    remaining_seconds: 0,
    freeze_count: 0,
    fail_streak: 0,
    last_health_check: null,
    health_status: null,
    ...overrides,
  }
}

describe('AdapterStatusQueryCard 名称映射', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function mountCard(locale = 'zh-CN') {
    const i18n = createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, en } })
    return mount(AdapterStatusQueryCard, {
      global: { plugins: [PrimeVue, i18n] },
    })
  }

  async function waitForLoad(wrapper: ReturnType<typeof mount>) {
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
  }

  it('hbba 显示"行业标准"而非"湖北标准"', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: { adapters: [makeAdapter({ display_name: '行业标准' })] },
    })
    const wrapper = mountCard()
    await waitForLoad(wrapper)

    expect(wrapper.text()).toContain('行业标准')
    expect(wrapper.text()).not.toContain('湖北标准')
  })

  it('csres 显示"工标网"而非"CSRES"', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: { adapters: [makeAdapter({ name: 'csres', display_name: '工标网' })] },
    })
    const wrapper = mountCard()
    await waitForLoad(wrapper)

    expect(wrapper.text()).toContain('工标网')
    expect(wrapper.text()).not.toContain('CSRES')
  })

  it('healthText 未检查时中文显示"尚未检查"', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: { adapters: [makeAdapter({ last_health_check: null, health_status: null })] },
    })
    const wrapper = mountCard('zh-CN')
    await waitForLoad(wrapper)

    expect(wrapper.text()).toContain('尚未检查')
  })

  it('healthText 英文下显示"Not checked yet"', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: { adapters: [makeAdapter({ last_health_check: null, health_status: null })] },
    })
    const wrapper = mountCard('en')
    await waitForLoad(wrapper)

    expect(wrapper.text()).toContain('Not checked yet')
  })
})
