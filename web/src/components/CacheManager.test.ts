// CacheManager：统计汇总（表行数/状态计数）、容量百分比、配置保存与清理链路的成功/失败分支
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ProgressBar from 'primevue/progressbar'
import { createI18n } from 'vue-i18n'
import CacheManager from './CacheManager.vue'
import zhCN from '@/locales/zh-CN.json'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  post: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('@/api/http', () => ({ default: { get: mocks.get, put: mocks.put, post: mocks.post } }))
vi.mock('@/composables/useAppToast', () => ({ appToast: { error: mocks.toastError } }))

const STATS = {
  total_size_mb: 12.5,
  max_size_mb: 100,
  auto_cleanup: true,
  cleanup_ratio: 0.1,
  tables: {
    standard_info_cache: { valid: 10, stale: 2 },
    standard_validity: { valid: 3 },
    announcement_record: { refresh_pending: 1, stale: 4 },
  },
}

async function mountManager() {
  const i18n = createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
  const wrapper = mount(CacheManager, { global: { plugins: [PrimeVue, i18n] } })
  await flushPromises()
  return wrapper
}

describe('CacheManager', () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue({ data: STATS })
    mocks.put.mockReset().mockResolvedValue({ data: {} })
    mocks.post.mockReset().mockResolvedValue({ data: {} })
    mocks.toastError.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('挂载即加载统计：容量、状态计数、各表行数与待刷新数都来自后端', async () => {
    const w = await mountManager()

    expect(mocks.get).toHaveBeenCalledWith('/cache/stats', { routeTag: '/settings' })
    expect(w.find('.stat-value').text()).toBe('12.5 / 100 MB')
    const text = w.text()
    expect(text).toContain('有效 13')      // 10 + 3（跨表汇总）
    expect(text).toContain('失效 6')       // 2 + 4
    expect(text).toContain('刷新中 1')
    expect(text).toContain('12 条')        // standard_info_cache 行数
    expect(text).toContain('2 条待刷新')
    expect(w.findComponent(ProgressBar).props('value')).toBe(13) // 12.5/100 取整
  })

  it('加载统计失败时静默回退初始值，不抛错也不暂停渲染', async () => {
    mocks.get.mockRejectedValueOnce(new Error('boom'))
    const w = await mountManager()
    expect(w.find('.stat-value').text()).toBe('0.0 / 50 MB')
    expect(w.findComponent(ProgressBar).props('value')).toBe(0)
  })

  it('max_size_mb=0 时百分比守卫为 0（不出现 NaN/Infinity）', async () => {
    mocks.get.mockResolvedValueOnce({ data: { ...STATS, max_size_mb: 0, total_size_mb: 5 } })
    const w = await mountManager()
    expect(w.findComponent(ProgressBar).props('value')).toBe(0)
  })

  it('选择 200 MB：PUT 数字型配置并重新拉统计', async () => {
    const w = await mountManager()
    const radios = w.findAll('input[type="radio"]')
    expect(radios).toHaveLength(3)
    await radios[2].setValue()

    expect(mocks.put).toHaveBeenCalledWith('/cache/config', { max_size_mb: 200 })
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })

  it('保存配置失败：必须弹错误提示（NEW-16：不允许静默）', async () => {
    mocks.put.mockRejectedValueOnce(new Error('save boom'))
    const w = await mountManager()
    await w.findAll('input[type="radio"]')[0].setValue() // 50 MB（与当前 100 MB 不同，确保 change 触发）
    await flushPromises()

    expect(mocks.toastError).toHaveBeenCalledWith({ key: 'settings.cache.save_failed', detail: 'save boom' })
  })

  it('立即清理成功：POST 后显示"清理完成"，3 秒后自动复位', async () => {
    vi.useFakeTimers()
    const w = await mountManager()
    const cleanupBtn = w.findAll('.app-btn').find((b) => b.text().includes('立即清理'))!
    await cleanupBtn.trigger('click')
    await flushPromises()

    expect(mocks.post).toHaveBeenCalledWith('/cache/cleanup')
    expect(w.text()).toContain('清理完成')

    await vi.advanceTimersByTimeAsync(3000)
    expect(w.text()).not.toContain('清理完成')
  })

  it('清理失败：弹错误提示且不显示"清理完成"假象', async () => {
    mocks.post.mockRejectedValueOnce(new Error('cleanup boom'))
    const w = await mountManager()
    const cleanupBtn = w.findAll('.app-btn').find((b) => b.text().includes('立即清理'))!
    await cleanupBtn.trigger('click')
    await flushPromises()

    expect(mocks.toastError).toHaveBeenCalledWith({ key: 'settings.cache.cleanup_failed', detail: 'cleanup boom' })
    expect(w.text()).not.toContain('清理完成')
  })
})
