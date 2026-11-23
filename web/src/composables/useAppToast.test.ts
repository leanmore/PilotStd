// useAppToast 单测（DS 阶段三 · 模块四）
import { describe, expect, it, vi, beforeEach } from 'vitest'

// 用可控的假 toast 服务替换 PrimeVue 的 useToast，避免依赖 PrimeVue 插件
const addMock = vi.fn()
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: addMock }),
}))

// i18n 全局实例打桩：key 原样返回带标记的字符串，便于断言"确实走了 key 路径"
vi.mock('@/i18n', () => ({
  i18n: {
    global: {
      t: (k: string, n?: Record<string, unknown>) => (n ? `${k}|${JSON.stringify(n)}` : k),
    },
  },
}))

import { appToast, bindAppToast, useAppToast } from './useAppToast'

describe('useAppToast', () => {
  beforeEach(() => {
    addMock.mockClear()
  })

  it('四种 severity 分别映射，默认 life 正确（success/info 2000、warn/error 3000）', () => {
    const notify = useAppToast()
    notify.success('ok')
    notify.info('i')
    notify.warn('w')
    notify.error('e')

    expect(addMock).toHaveBeenCalledTimes(4)
    expect(addMock.mock.calls[0][0]).toMatchObject({ severity: 'success', summary: 'ok', life: 2000 })
    expect(addMock.mock.calls[1][0]).toMatchObject({ severity: 'info', summary: 'i', life: 2000 })
    expect(addMock.mock.calls[2][0]).toMatchObject({ severity: 'warn', summary: 'w', life: 3000 })
    expect(addMock.mock.calls[3][0]).toMatchObject({ severity: 'error', summary: 'e', life: 3000 })
  })

  it('支持裸字符串入参（等价于 { summary }）', () => {
    useAppToast().success('已保存')
    expect(addMock.mock.calls[0][0].summary).toBe('已保存')
  })

  it('key 优先于 summary，并支持 named 插值', () => {
    const notify = useAppToast()
    notify.success({ key: 'a.b', summary: '不该用这个' })
    expect(addMock.mock.calls[0][0].summary).toBe('a.b')

    notify.success({ key: 'a.b', named: { n: 3 } })
    expect(addMock.mock.calls[1][0].summary).toBe('a.b|{"n":3}')
  })

  it('detail / detailKey 二选一，key 优先；无 detail 时不传该字段', () => {
    const notify = useAppToast()
    notify.error({ summary: 'S', detail: 'D' })
    expect(addMock.mock.calls[0][0].detail).toBe('D')

    notify.error({ summary: 'S' })
    expect('detail' in addMock.mock.calls[1][0]).toBe(false)

    notify.error({ summary: 'S', detailKey: 'k.d' })
    expect(addMock.mock.calls[2][0].detail).toBe('k.d')
  })

  it('自定义 life 覆盖默认值', () => {
    useAppToast().error({ summary: 'x', life: 8000 })
    expect(addMock.mock.calls[0][0].life).toBe(8000)
  })

  it('统一 closable:false（提示自动消失）', () => {
    useAppToast().success('x')
    expect(addMock.mock.calls[0][0].closable).toBe(false)
  })

  it('group 只有显式传时才下发（避免误用导致互相覆盖）', () => {
    const notify = useAppToast()
    notify.error({ summary: 'x' })
    expect('group' in addMock.mock.calls[0][0]).toBe(false)

    notify.error({ summary: 'x', group: 'site-a' })
    expect(addMock.mock.calls[1][0].group).toBe('site-a')
  })

  it('summary 为空时跳过并 warn，不抛错（提示失败不拖垮业务）', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    useAppToast().success('')
    expect(addMock).not.toHaveBeenCalled()
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
  })

  it('appToast 全局单例：未绑定时静默丢弃并 warn，不抛错', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    // 注意：模块级 boundToast 是共享状态，这里先确保未绑定（首次调用前）
    appToast.success('x')
    expect(addMock).not.toHaveBeenCalled()
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('尚未绑定'))
    warnSpy.mockRestore()
  })

  it('appToast 全局单例：bindAppToast 后可用', () => {
    const svc = { add: vi.fn() }
    bindAppToast(svc)
    appToast.warn({ summary: 'w' })
    expect(svc.add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'warn', summary: 'w' }))
  })
})
