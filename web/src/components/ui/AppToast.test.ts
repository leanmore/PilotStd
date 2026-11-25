/**
 * `AppToast` 宿主单测（NEW-44 / 方向 A 闭环，2026-11-24）。
 *
 * 测的是**我们自己的渲染契约**（不是 PrimeVue 本身）：
 * - 四类 severity → 语义图标映射（`severityIcon` 纯函数）
 * - 自定义 `#message` 插槽：图标 + summary + 可选 detail
 * - `role="status"` 无障碍声明
 * - `severity` 作为 body 的 BEM 修饰类（语义底色的选择器挂点）
 * - 未知 severity 回退到 info 图标（不自创第五种）
 *
 * ── 两个必须注意的点（初版踩过）──
 * 1. `useToast()` 是 `inject`，**必须在组件 setup 里调用**；在测试文件顶层调用会
 *    `No PrimeVue Toast provided!` → 用一个 harness 组件在 setup 里取服务并 expose。
 * 2. Toast 经 Portal 渲染到 body 下，断言查 `document.body` 而非 wrapper。
 */
import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import { useToast } from 'primevue/usetoast'

import AppToast from './AppToast.vue'

const Harness = defineComponent({
  name: 'ToastHarness',
  setup(_, { expose }) {
    expose({ toast: useToast() })
    return () => h(AppToast)
  },
})

let wrappers: VueWrapper[] = []

afterEach(() => {
  for (const w of wrappers) w.unmount()
  wrappers = []
  document.body.innerHTML = ''
})

function mountHarness(): VueWrapper {
  const w = mount(Harness, {
    attachTo: document.body,
    global: { plugins: [PrimeVue, ToastService] },
  })
  wrappers.push(w)
  return w
}

async function addToast(w: VueWrapper, options: Record<string, unknown>): Promise<void> {
  ;(w.vm as unknown as { toast: { add: (o: Record<string, unknown>) => void } }).toast.add(options)
  await nextTick()
  await nextTick()
}

describe('AppToast 渲染契约', () => {
  it('默认挂载不渲染任何消息', async () => {
    mountHarness()
    await nextTick()
    expect(document.body.querySelectorAll('.app-toast__body').length).toBe(0)
  })

  it('success / info / warn / error 各自渲染对应语义图标', async () => {
    const w = mountHarness()
    const expected: Record<string, string> = {
      success: 'pi pi-check-circle',
      info: 'pi pi-info-circle',
      warn: 'pi pi-exclamation-triangle',
      error: 'pi pi-times-circle',
    }
    for (const [severity, icon] of Object.entries(expected)) {
      await addToast(w, { severity, summary: `s-${severity}`, life: 5000 })
      const bodies = document.body.querySelectorAll('.app-toast__body')
      const body = bodies[bodies.length - 1] as HTMLElement
      expect(body.className).toContain(`app-toast__body--${severity}`)
      const iconEl = body.querySelector('i.app-toast__icon') as HTMLElement
      expect(iconEl.className).toContain(icon)
    }
  })

  it('未知 severity 回退到 info 图标（不自创第五种）', async () => {
    const w = mountHarness()
    await addToast(w, { severity: 'unknown-sev', summary: 'x', life: 5000 })
    const body = document.body.querySelector('.app-toast__body') as HTMLElement
    const iconEl = body.querySelector('i.app-toast__icon') as HTMLElement
    expect(iconEl.className).toContain('pi pi-info-circle')
  })

  it('渲染 summary，detail 可选', async () => {
    const w = mountHarness()
    await addToast(w, { severity: 'error', summary: '主标题', detail: '明细说明', life: 5000 })
    const body = document.body.querySelector('.app-toast__body') as HTMLElement
    expect(body.querySelector('.app-toast__summary')!.textContent).toBe('主标题')
    expect(body.querySelector('.app-toast__detail')!.textContent).toBe('明细说明')
  })

  it('无 detail 时不渲染 detail 节点', async () => {
    const w = mountHarness()
    await addToast(w, { severity: 'info', summary: '只有标题', life: 5000 })
    const body = document.body.querySelector('.app-toast__body') as HTMLElement
    expect(body.querySelector('.app-toast__summary')!.textContent).toBe('只有标题')
    expect(body.querySelector('.app-toast__detail')).toBeNull()
  })

  it('body 带 role="status"（无障碍：变化需被读屏感知）', async () => {
    const w = mountHarness()
    await addToast(w, { severity: 'success', summary: 'ok', life: 5000 })
    const body = document.body.querySelector('.app-toast__body') as HTMLElement
    expect(body.getAttribute('role')).toBe('status')
  })
})
