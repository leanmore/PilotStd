// useUserPreferences：localStorage 启动读取（含旧 key 迁移/坏 JSON 回退）、变更写回、
// 后端覆盖与失败降级、初始化标记幂等、初始化后 500ms 防抖同步、legacy key 清理
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mocks = vi.hoisted(() => ({ getAll: vi.fn(), setAll: vi.fn() }))
vi.mock('@/stores/preferences', () => ({
  usePreferencesStore: () => ({ getAll: mocks.getAll, setAll: mocks.setAll }),
}))

/** 每次重新加载模块：composable 的状态是模块级单例，只有 resetModules 才能测"启动读取" */
async function load() {
  vi.resetModules()
  return (await import('./useUserPreferences')).useUserPreferences()
}
const raw = (key: string) => localStorage.getItem(`pilotstd_${key}`)
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0))

describe('useUserPreferences', () => {
  beforeEach(() => {
    localStorage.clear()
    mocks.getAll.mockReset().mockResolvedValue({})
    mocks.setAll.mockReset().mockResolvedValue(undefined)
  })
  afterEach(() => { vi.useRealTimers() })

  it('启动读取：JSON 字段反序列化、带引号 locale 兼容、旧无前缀 key 迁移', async () => {
    localStorage.setItem('theme', '"dark"') // 旧 key（无前缀）→ getItem 迁移到 pilotstd_theme
    localStorage.setItem('pilotstd_locale', '"en"') // 旧版 JSON.stringify 写入的带引号值
    localStorage.setItem('pilotstd_task_path', '"/settings"')
    localStorage.setItem('pilotstd_notification_quiet_hours', JSON.stringify({ enabled: true, start: '23:00', end: '07:00' }))
    const p = await load()

    expect([p.theme.value, p.locale.value, p.taskPath.value]).toEqual(['dark', 'en', '/settings'])
    expect(p.quietHours.value).toEqual({ enabled: true, start: '23:00', end: '07:00' })
    expect(localStorage.getItem('theme')).toBeNull()
    expect(raw('theme')).toBe('"dark"')
  })

  it('空存储 / 坏 JSON：回退默认值且不抛错', async () => {
    localStorage.setItem('pilotstd_theme', '{bad json')
    const p = await load()

    expect([p.theme.value, p.locale.value, p.taskPath.value]).toEqual(['', 'zh-CN', '/inbox'])
    expect(p.quietHours.value).toEqual({ enabled: false, start: '22:00', end: '07:00' })
  })

  it('变更即写回 localStorage；字符串字段不 JSON 包装；未初始化不同步后端', async () => {
    const p = await load()
    p.theme.value = 'green'
    p.locale.value = 'en'
    p.taskPath.value = '/task'
    p.quietHours.value = { enabled: true, start: '01:00', end: '02:00' }
    await tick()

    expect([raw('theme'), raw('locale'), raw('task_path')]).toEqual(['"green"', 'en', '"/task"'])
    expect(JSON.parse(raw('notification_quiet_hours')!)).toEqual({ enabled: true, start: '01:00', end: '02:00' })
    expect(mocks.setAll).not.toHaveBeenCalled()
  })

  it('loadFromBackend：后端值覆盖本地并写回 localStorage、清理 legacy key；重复调用早退', async () => {
    localStorage.setItem('dashboard_widgets_visibility', '1')
    mocks.getAll.mockResolvedValue({
      ui: { theme: 'blue', language: 'zh-TW' },
      task_path: '/settings',
      notification_quiet_hours: { enabled: true, start: '21:00', end: '06:00' },
    })
    const p = await load()
    await p.loadFromBackend()

    expect([p.theme.value, p.locale.value, p.taskPath.value]).toEqual(['blue', 'zh-TW', '/settings'])
    expect(p.quietHours.value).toEqual({ enabled: true, start: '21:00', end: '06:00' })
    expect([raw('theme'), raw('locale')]).toEqual(['"blue"', 'zh-TW'])
    expect(localStorage.getItem('dashboard_widgets_visibility')).toBeNull()

    await p.loadFromBackend()
    expect(mocks.getAll).toHaveBeenCalledTimes(1)
  })

  it('loadFromBackend 失败：保留本地值，仍置初始化标记（避免反复打爆后端）', async () => {
    localStorage.setItem('pilotstd_theme', '"light"')
    mocks.getAll.mockRejectedValue(new Error('offline'))
    const p = await load()
    await p.loadFromBackend()

    expect([p.theme.value, p.locale.value]).toEqual(['light', 'zh-CN'])
    await p.loadFromBackend()
    expect(mocks.getAll).toHaveBeenCalledTimes(1)
  })

  it('初始化后变更：500ms 防抖后按完整快照同步 setAll', async () => {
    vi.useFakeTimers()
    const p = await load()
    await p.loadFromBackend()
    mocks.setAll.mockClear()

    p.theme.value = 'dark'
    await Promise.resolve()
    expect(mocks.setAll).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(500)
    await Promise.resolve()
    expect(mocks.setAll).toHaveBeenCalledWith({
      ui: { theme: 'dark', language: 'zh-CN' },
      task_path: '/inbox',
      notification_quiet_hours: { enabled: false, start: '22:00', end: '07:00' },
    })
  })

  it('cleanupLegacy 只清理遗留 key，不碰 pilotstd_ 命名空间', async () => {
    const p = await load()
    localStorage.setItem('dashboard_widgets_visibility', '1')
    localStorage.setItem('pilotstd_theme', '"x"')

    p.cleanupLegacy()
    expect(localStorage.getItem('dashboard_widgets_visibility')).toBeNull()
    expect(raw('theme')).toBe('"x"')
  })

  it('localStorage 读/写抛错（被禁用/配额满）：模块导入与变更写回都不崩（D-4 回归）', async () => {
    // 读：getItem 抛 SecurityError 时，locale 等字段必须回退默认值而不是让模块导入失败
    const getSpy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError')
    })
    vi.resetModules()
    const mod = await import('./useUserPreferences')
    const p = mod.useUserPreferences()
    expect(p.locale.value).toBe('zh-CN')
    expect(p.taskPath.value).toBe('/inbox')
    getSpy.mockRestore()

    // 写：setItem 抛 QuotaExceededError 时，watch 回调不得把异常抛给调用方
    const setSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    expect(() => { p.theme.value = 'dark' }).not.toThrow()
    await tick()
    setSpy.mockRestore()
  })
})
