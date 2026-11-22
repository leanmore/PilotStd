// AppDialog 单测（DS 阶段二 · 模块二）
//
// 两个必须注意的点（本文件初版都踩过，别再踩）：
//   1. Dialog 的内容经 <Portal> teleport 到 document.body，所以断言要查 body 而不是 wrapper；
//   2. Portal 的 `mounted` 标志在 mounted() 钩子里才置 true，**首帧不渲染内容** ——
//      挂载后必须 `await nextTick()`，否则 body 上还什么都没有（表现为"visible=true 但查不到 .p-dialog"）。
//   另外每个用例前清空 body 并销毁上一个 wrapper，避免残留节点被 querySelector 先命中。
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import PrimeVue from 'primevue/config'

import AppDialog from './AppDialog.vue'

let wrappers: VueWrapper[] = []

async function mountDialog(
  props: Record<string, unknown> = {},
  attrs: Record<string, unknown> = {},
  slots: Record<string, string> = {},
): Promise<VueWrapper> {
  const w = mount(AppDialog, {
    props,
    attrs,
    slots,
    attachTo: document.body,
    global: { plugins: [PrimeVue] },
  })
  wrappers.push(w)
  // Portal 在 mounted() 里才把 mounted 置 true，等一拍内容才会真正 teleport 出来
  await nextTick()
  return w
}

/** 取 body 上的弹窗根节点（清空策略保证只有一个） */
function dialogEl(): HTMLElement | null {
  return document.body.querySelector('.p-dialog')
}

beforeEach(() => {
  document.body.innerHTML = ''
})

afterEach(() => {
  for (const w of wrappers) w.unmount()
  wrappers = []
  document.body.innerHTML = ''
})

describe('AppDialog', () => {
  it('visible=false 时不渲染 .p-dialog', async () => {
    await mountDialog({ visible: false })
    expect(dialogEl()).toBeNull()
  })

  it('visible=true 时渲染 .p-dialog，并带 DS 根类', async () => {
    await mountDialog({ visible: true, header: '详情' })
    const el = dialogEl()
    expect(el).not.toBeNull()
    expect(el?.classList.contains('app-dialog')).toBe(true)
    expect(el?.textContent).toContain('详情')
  })

  it('header 透传到标题区', async () => {
    await mountDialog({ visible: true, header: '任务详情' })
    expect(dialogEl()?.querySelector('.p-dialog-title')?.textContent).toBe('任务详情')
  })

  it('#header 插槽接管标题区（覆盖 header prop）', async () => {
    await mountDialog({ visible: true, header: '被替换' }, {}, { header: '<div class="my-title">自定义标题</div>' })
    expect(document.body.querySelector('.my-title')?.textContent).toBe('自定义标题')
  })

  it('默认插槽渲染内容', async () => {
    await mountDialog({ visible: true }, {}, { default: '<div class="dlg-body">弹窗正文</div>' })
    expect(document.body.querySelector('.dlg-body')?.textContent).toBe('弹窗正文')
  })

  it('#footer 插槽透传（有 footer 才渲染 .p-dialog-footer）', async () => {
    await mountDialog({ visible: true }, {}, { footer: '<button class="dlg-ok">确定</button>' })
    expect(document.body.querySelector('.p-dialog-footer')).not.toBeNull()
    expect(document.body.querySelector('.dlg-ok')?.textContent).toBe('确定')
  })

  it('#container 插槽透传（接管整个弹窗壳，含 closeCallback）', async () => {
    await mountDialog({ visible: true }, {}, { container: '<div class="my-container">自定义容器</div>' })
    expect(document.body.querySelector('.my-container')?.textContent).toBe('自定义容器')
  })

  it('modal 透传：渲染遮罩 .p-overlay-mask', async () => {
    await mountDialog({ visible: true, modal: true })
    expect(document.body.querySelector('.p-overlay-mask')).not.toBeNull()
  })

  it('非 modal 不渲染遮罩类', async () => {
    await mountDialog({ visible: true, modal: false })
    expect(document.body.querySelector('.p-overlay-mask')).toBeNull()
  })

  it('closable / draggable 透传到内部 Dialog', async () => {
    const w = await mountDialog({ visible: true, closable: false, draggable: false })
    const dlg = w.findComponent({ name: 'Dialog' })
    expect(dlg.props('closable')).toBe(false)
    expect(dlg.props('draggable')).toBe(false)
    // closable=false 时右上角关闭按钮不渲染
    expect(document.body.querySelector('.p-dialog-close-button')).toBeNull()
  })

  it('dismissableMask 透传到内部 Dialog', async () => {
    const w = await mountDialog({ visible: true, modal: true, dismissableMask: true })
    expect(w.findComponent({ name: 'Dialog' }).props('dismissableMask')).toBe(true)
  })

  it('style / class 透传（业务代码大量使用 :style="{width:\'360px\'}"）', async () => {
    await mountDialog({ visible: true }, { style: 'width: 360px;', class: 'task-detail' })
    const el = dialogEl() as HTMLElement
    expect(el.style.width).toBe('360px')
    expect(el.classList.contains('task-detail')).toBe(true)
    // DS 根类不被业务 class 覆盖
    expect(el.classList.contains('app-dialog')).toBe(true)
  })

  it('v-model:visible：内部 Dialog 关闭时回流 update:visible', async () => {
    const w = await mountDialog({ visible: true })
    w.findComponent({ name: 'Dialog' }).vm.$emit('update:visible', false)
    await nextTick()
    expect(w.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('@show / @hide 由内部 Dialog 事件转发', async () => {
    const w = await mountDialog({ visible: true })
    const dlg = w.findComponent({ name: 'Dialog' })
    dlg.vm.$emit('show')
    dlg.vm.$emit('hide')
    await nextTick()
    expect(w.emitted('show')).toHaveLength(1)
    expect(w.emitted('hide')).toHaveLength(1)
  })

  it('其余事件继续走 $attrs 透传（after-hide）', async () => {
    const seen: string[] = []
    const w = await mountDialog({ visible: true }, { onAfterHide: () => seen.push('after-hide') })
    w.findComponent({ name: 'Dialog' }).vm.$emit('after-hide')
    await nextTick()
    expect(seen).toEqual(['after-hide'])
  })

  it('bare 时不施加基础 class，只留 bare 标记，并走 unstyled', async () => {
    const w = await mountDialog({ visible: true, bare: true })
    expect(w.findComponent({ name: 'Dialog' }).props('unstyled')).toBe(true)
    // unstyled 下 PrimeVue 不生成 p-dialog 类名，只剩 DS 的 bare 标记
    const el = document.body.querySelector('.app-dialog--bare')
    expect(el).not.toBeNull()
    expect(el?.classList.contains('p-dialog')).toBe(false)
    expect(el?.classList.contains('app-dialog')).toBe(false)
  })

  it('$attrs 透传 data-* 到 .p-dialog 根节点', async () => {
    await mountDialog({ visible: true }, { 'data-testid': 'detail-dialog' })
    expect(dialogEl()?.getAttribute('data-testid')).toBe('detail-dialog')
  })
})

describe('AppDialog · 组件身份', () => {
  it('显式声明组件名（G-027：防生产构建压缩后组件名丢失）', () => {
    expect(AppDialog.name ?? (AppDialog as unknown as { __name?: string }).__name).toBe('AppDialog')
  })
})
