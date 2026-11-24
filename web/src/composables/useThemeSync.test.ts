// web/src/composables/useThemeSync.test.ts — 主题同步 composable 单元测试
//
// NEW-44 补齐：此前 `useThemeSync.ts` 无任何测试。本文件锁定对外可观察契约：
//   · 挂载即立即同步一次（watch immediate）：data-p-theme 明暗属性 + Aura surface 色板 + text token
//   · 亮/暗主题切换时属性、updateSurfacePalette 入参、:root 内联 token 同步更新
//   · 清理只作用于映射表管理范围内的 token，严禁触碰 --p-surface-* 等非映射 token
//   · 未知主题 id 安全降级：不调用色板更新、移除映射 token（防残留）
//   · 卸载后 watch 停用，主题再变化不再写 DOM（无泄漏）
// 依赖 @primeuix/themes 与 app store 替身；THEMES / token 映射用真实模块，断言与生产配置不脱节。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  store: { theme: 'light' } as { theme: string },
  updateSurfacePalette: vi.fn(),
}))

vi.mock('@/stores/app', () => ({ useAppStore: () => mocks.store }))
vi.mock('@primeuix/themes', () => ({ updateSurfacePalette: mocks.updateSurfacePalette }))

import { useThemeSync } from './useThemeSync'
import { THEMES } from '@/config/themes'
import { AURA_TEXT_DIM_MAP, AURA_TOKEN_MAP } from '@/theme/aura-token-map'

let wrapper: ReturnType<typeof mount> | undefined

function mountSync(theme: string) {
  mocks.store.theme = theme
  wrapper = mount(defineComponent({ setup() { useThemeSync() }, render: () => h('div') }))
}

/** 源码 syncSurfacePalette 的入参形状（dark/light 同时注入，防亮暗泄漏） */
function expectedPalette(themeId: string) {
  const c = THEMES[themeId].colors
  return {
    dark: { 900: c.surface, 800: c.surfaceRaised, 950: c.bg, 700: c.disabledBg },
    light: { 0: c.surface, 50: c.surfaceRaised, 100: c.bg },
  }
}

const root = () => document.documentElement
const cssVar = (name: string) => root().style.getPropertyValue(name)
const lastPalette = () => mocks.updateSurfacePalette.mock.calls.at(-1)?.[0]

describe('useThemeSync', () => {
  beforeEach(() => {
    root().removeAttribute('style')
    root().removeAttribute('data-p-theme')
    mocks.updateSurfacePalette.mockReset()
    mocks.store = reactive({ theme: 'light' })
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.restoreAllMocks()
  })

  it('暗色主题：挂载即写 data-p-theme=dark、注入暗/亮两套 surface、写入暗色 text token', () => {
    mountSync('dark')

    expect(root().getAttribute('data-p-theme')).toBe('dark')
    expect(mocks.updateSurfacePalette).toHaveBeenCalledTimes(1)
    expect(lastPalette()).toEqual(expectedPalette('dark'))
    expect(cssVar('--p-content-color')).toBe(AURA_TOKEN_MAP.dark['--p-content-color'])
    expect(cssVar('--p-button-primary-background')).toBe(AURA_TOKEN_MAP.dark['--p-button-primary-background'])
    expect(cssVar('--text-dim')).toBe(AURA_TEXT_DIM_MAP.dark)
  })

  it('亮色主题：挂载即移除残留 data-p-theme，并用亮色值覆盖旧的暗色内联 token', () => {
    root().setAttribute('data-p-theme', 'dark')
    root().style.setProperty('--p-content-color', '#ffffff') // 模拟旧主题残留
    mountSync('light')

    expect(root().hasAttribute('data-p-theme')).toBe(false)
    expect(lastPalette()).toEqual(expectedPalette('light'))
    expect(cssVar('--p-content-color')).toBe(AURA_TOKEN_MAP.light['--p-content-color'])
    expect(cssVar('--text-dim')).toBe(AURA_TEXT_DIM_MAP.light)
  })

  it('响应式切换：dark → blue 时重新注入蓝色 surface 与 token，属性维持 dark', async () => {
    mountSync('dark')
    mocks.updateSurfacePalette.mockClear()

    mocks.store.theme = 'blue'
    await nextTick()

    expect(mocks.updateSurfacePalette).toHaveBeenCalledTimes(1)
    expect(lastPalette()).toEqual(expectedPalette('blue'))
    expect(root().getAttribute('data-p-theme')).toBe('dark')
    expect(cssVar('--p-content-color')).toBe(AURA_TOKEN_MAP.blue['--p-content-color'])
    expect(cssVar('--text-dim')).toBe(AURA_TEXT_DIM_MAP.blue)
  })

  it('响应式切换：dark → green 时暗色属性被移除，token 换成浅色主题值', async () => {
    mountSync('dark')
    mocks.updateSurfacePalette.mockClear()

    mocks.store.theme = 'green'
    await nextTick()

    expect(root().hasAttribute('data-p-theme')).toBe(false)
    expect(lastPalette()).toEqual(expectedPalette('green'))
    expect(cssVar('--p-content-color')).toBe(AURA_TOKEN_MAP.green['--p-content-color'])
    expect(cssVar('--text-dim')).toBe(AURA_TEXT_DIM_MAP.green)
  })

  it('清理边界：不动 --p-surface-* 等非映射 token，只覆盖映射表内的 token', async () => {
    mountSync('dark')
    root().style.setProperty('--p-surface-900', '#123456') // updateSurfacePalette 注入的 token，非映射范围

    mocks.store.theme = 'green'
    await nextTick()

    expect(cssVar('--p-surface-900')).toBe('#123456')
    expect(cssVar('--p-content-color')).toBe(AURA_TOKEN_MAP.green['--p-content-color'])
  })

  it('未知主题 id：不调用 updateSurfacePalette，移除全部映射 token 防残留', async () => {
    mountSync('dark')
    mocks.updateSurfacePalette.mockClear()

    mocks.store.theme = 'mystery'
    await nextTick()

    expect(mocks.updateSurfacePalette).not.toHaveBeenCalled()
    expect(root().hasAttribute('data-p-theme')).toBe(false)
    expect(cssVar('--p-content-color')).toBe('')
    expect(cssVar('--p-button-primary-background')).toBe('')
    // --text-dim 无映射时保留当前值（?? 兜底分支）
    expect(cssVar('--text-dim')).toBe(AURA_TEXT_DIM_MAP.dark)
  })

  it('卸载后停止监听：主题再变化不再写 DOM', async () => {
    mountSync('dark')
    wrapper!.unmount()
    wrapper = undefined
    mocks.updateSurfacePalette.mockClear()

    mocks.store.theme = 'light'
    await nextTick()

    expect(mocks.updateSurfacePalette).not.toHaveBeenCalled()
    expect(root().getAttribute('data-p-theme')).toBe('dark')
  })
})
