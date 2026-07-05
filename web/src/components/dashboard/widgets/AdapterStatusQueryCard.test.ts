// components/dashboard/widgets/AdapterStatusQueryCard.test.ts — 适配器名称映射测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import AdapterStatusQueryCard from './AdapterStatusQueryCard.vue'
import http from '@/api/http'

vi.mock('@/api/http', () => ({
  default: { get: vi.fn() },
}))

describe('AdapterStatusQueryCard 名称映射', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function mountCard() {
    return mount(AdapterStatusQueryCard, {
      global: { plugins: [PrimeVue] },
    })
  }

  async function waitForLoad(wrapper: ReturnType<typeof mount>) {
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()
  }

  it('hbba 显示"行业标准"而非"湖北标准"', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: {
        adapters: [{
          name: 'hbba',
          status: 'normal',
          frozen_until: null,
          remaining_seconds: 0,
          freeze_count: 0,
          fail_streak: 0,
        }],
      },
    })
    const wrapper = mountCard()
    await waitForLoad(wrapper)

    expect(wrapper.text()).toContain('行业标准')
    expect(wrapper.text()).not.toContain('湖北标准')
  })

  it('csres 显示"工标网"而非"CSRES"', async () => {
    vi.mocked(http.get).mockResolvedValueOnce({
      data: {
        adapters: [{
          name: 'csres',
          status: 'normal',
          frozen_until: null,
          remaining_seconds: 0,
          freeze_count: 0,
          fail_streak: 0,
        }],
      },
    })
    const wrapper = mountCard()
    await waitForLoad(wrapper)

    expect(wrapper.text()).toContain('工标网')
    expect(wrapper.text()).not.toContain('CSRES')
  })
})
