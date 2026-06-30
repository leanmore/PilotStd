import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SystemResources from './SystemResources.vue'
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import axios from 'axios'

vi.mock('axios')
const mockedAxios = vi.mocked(axios)

const StubCard = {
  name: 'Card',
  template: '<div class="card-stub"><slot name="content" /></div>',
}

function mountComponent() {
  return shallowMount(SystemResources, {
    global: {
      stubs: { Card: StubCard, ProgressBar },
    },
  })
}

describe('SystemResources', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders page title 系统资源', () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { cpu: { percent: 10, count: 8 }, memory: { percent: 50, total: 16 * 1024**3, available: 8 * 1024**3 }, disk: { percent: 30, total: 256 * 1024**3, free: 180 * 1024**3 } },
    })
    const wrapper = mountComponent()
    expect(wrapper.find('.page-title').text()).toBe('系统资源')
  })

  it('renders 3 resource cards for CPU, memory, and disk', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { cpu: { percent: 25, count: 4 }, memory: { percent: 60, total: 8 * 1024**3, available: 3 * 1024**3 }, disk: { percent: 45, total: 512 * 1024**3, free: 280 * 1024**3 } },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    const cards = wrapper.findAllComponents(StubCard)
    expect(cards.length).toBe(3)
  })

  it('renders CPU card with correct title and detail', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { cpu: { percent: 40, count: 8 }, memory: { percent: 0, total: 0, available: 0 }, disk: { percent: 0, total: 0, free: 0 } },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.html()).toContain('8 核')
  })

  it('renders memory card with GB formatting', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { cpu: { percent: 0, count: 0 }, memory: { percent: 75, total: 16 * 1024**3, available: 4 * 1024**3 }, disk: { percent: 0, total: 0, free: 0 } },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.html()).toContain('16.0 GB')
    expect(wrapper.html()).toContain('4.0 GB')
  })

  it('renders disk card with free space detail', async () => {
    mockedAxios.get.mockResolvedValueOnce({
      data: { cpu: { percent: 0, count: 0 }, memory: { percent: 0, total: 0, available: 0 }, disk: { percent: 10, total: 1000 * 1024**3, free: 900 * 1024**3 } },
    })
    const wrapper = mountComponent()
    await nextTick()
    await nextTick()
    expect(wrapper.html()).toContain('900.0 GB 剩余')
  })
})
