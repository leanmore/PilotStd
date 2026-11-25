// LegacyRedirect 测试（旧 `/announce/:announceNo` 链接 → 新详情路由）
//
// 契约（见组件 onMounted）：
//   1 条结果 → `/announce/<URL 侧 source>/<announceNo>`（source_site 需经 SOURCE_TO_URL 映射）；
//   0 条 → NotFound；多条冲突 → 列表页并带 conflict=true&no=...；
//   接口异常同样降级到 NotFound，绝不把用户留在空白跳转页。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import zhCN from '@/locales/zh-CN.json'
import { getAnnouncementByNo } from '@/api/announce'
import LegacyRedirect from './LegacyRedirect.vue'

vi.mock('@/api/announce', () => ({ getAnnouncementByNo: vi.fn() }))

const Blank = { template: '<div />' }

async function mountAt(path = '/legacy/A-1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/legacy/:announceNo', component: LegacyRedirect },
      { path: '/announce', component: Blank },
      { path: '/announce/:source/:announceNo', component: Blank },
      { path: '/:pathMatch(.*)*', name: 'NotFound', component: Blank },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(LegacyRedirect, {
    global: {
      plugins: [router, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
    },
  })
  return { wrapper, router }
}

describe('LegacyRedirect 旧链接重定向', () => {
  beforeEach(() => vi.clearAllMocks())

  it('单条结果：按 SOURCE_TO_URL 映射 source_site 后跳详情，并带上原始 announceNo', async () => {
    vi.mocked(getAnnouncementByNo).mockResolvedValue([{ source_site: 'announcement_gb', announce_no: 'A-1', title: 'T' }])
    const { router } = await mountAt()
    await flushPromises()

    expect(getAnnouncementByNo).toHaveBeenCalledWith('A-1', '/announce')
    expect(router.currentRoute.value.fullPath).toBe('/announce/annc_gb/A-1')
  })

  it('source_site 不在映射表时原样作为 URL 段，不做静默丢弃', async () => {
    vi.mocked(getAnnouncementByNo).mockResolvedValue([{ source_site: 'announcement_xx', announce_no: 'A-1', title: 'T' }])
    const { router } = await mountAt()
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/announce/announcement_xx/A-1')
  })

  it('零条结果：跳 NotFound', async () => {
    vi.mocked(getAnnouncementByNo).mockResolvedValue([])
    const { router } = await mountAt()
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('NotFound')
  })

  it('多条冲突：跳列表页并带 conflict=true 与 no 参数', async () => {
    vi.mocked(getAnnouncementByNo).mockResolvedValue([
      { source_site: 'announcement_gb', announce_no: 'A-1', title: 'a' },
      { source_site: 'announcement_hb', announce_no: 'A-1', title: 'b' },
    ])
    const { router } = await mountAt()
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/announce')
    expect(router.currentRoute.value.query).toEqual({ conflict: 'true', no: 'A-1' })
  })

  it('接口异常：降级 NotFound，不抛未捕获异常', async () => {
    vi.mocked(getAnnouncementByNo).mockRejectedValue(new Error('network down'))
    const { router } = await mountAt()
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('NotFound')
  })

  it('跳转期间渲染「正在跳转...」过渡态', async () => {
    // 接口挂起不返回：只验证跳转前的过渡 UI（成功跳转已由第 1 例覆盖）
    vi.mocked(getAnnouncementByNo).mockReturnValue(new Promise(() => {}) as never)
    const { wrapper } = await mountAt()
    expect(wrapper.text()).toContain('正在跳转...')
  })
})
