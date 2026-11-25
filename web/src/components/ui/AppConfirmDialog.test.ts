// AppConfirmDialog：ConfirmationService 渲染宿主的真实链路 —— require → 渲染 → accept/reject 回调
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import { useConfirm } from 'primevue/useconfirm'
import AppConfirmDialog from './AppConfirmDialog.vue'

let wrappers: VueWrapper[] = []
let confirm: ReturnType<typeof useConfirm>

function mountHost(): VueWrapper {
  const Host = defineComponent({
    setup() {
      confirm = useConfirm()
      return () => h(AppConfirmDialog)
    },
  })
  const wrapper = mount(Host, {
    attachTo: document.body,
    global: { plugins: [PrimeVue, ConfirmationService] },
  })
  wrappers.push(wrapper)
  return wrapper
}

/** ConfirmDialog 经 Portal 渲染到 body，断言必须查 document.body */
const dialogEl = () => document.body.querySelector('.app-confirm-dialog') as HTMLElement | null
const buttons = () => Array.from(document.body.querySelectorAll<HTMLButtonElement>('.app-btn'))

async function requireConfirm(options: Record<string, unknown>) {
  mountHost()
  confirm.require(options)
  await nextTick()
  await nextTick()
}

describe('AppConfirmDialog', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    for (const w of wrappers) w.unmount()
    wrappers = []
    document.body.innerHTML = ''
  })

  it('require 后渲染 header/message/icon 与 alertdialog 语义', async () => {
    await requireConfirm({
      header: '删除确认',
      message: '确定删除该记录？',
      icon: 'pi pi-exclamation-triangle',
      accept: vi.fn(),
      reject: vi.fn(),
    })

    const el = dialogEl()
    expect(el).not.toBeNull()
    expect(el!.getAttribute('role')).toBe('alertdialog')
    expect(el!.getAttribute('aria-modal')).toBe('true')
    expect(el!.querySelector('.app-confirm-dialog__title')?.textContent).toBe('删除确认')
    expect(el!.querySelector('.app-confirm-dialog__message')?.textContent).toBe('确定删除该记录？')
    expect(el!.querySelector('.app-confirm-dialog__header i')?.className).toContain('pi-exclamation-triangle')
  })

  it('接受/拒绝按钮的文案来自调用方的 acceptProps/rejectProps', async () => {
    await requireConfirm({
      header: '确认', message: '继续？',
      acceptProps: { label: '确定执行' }, rejectProps: { label: '再想想' },
      accept: vi.fn(), reject: vi.fn(),
    })

    const labels = buttons().map((b) => b.textContent?.trim())
    expect(labels).toEqual(['再想想', '确定执行'])
  })

  it('点击接受按钮：执行 accept 回调一次，默认按钮层级为 primary', async () => {
    const accept = vi.fn()
    const reject = vi.fn()
    await requireConfirm({
      header: '确认', message: '继续？',
      accept, reject,
      acceptProps: { label: '确定' }, rejectProps: { label: '取消' },
    })

    const acceptBtn = buttons().find((b) => b.textContent?.trim() === '确定')!
    expect(acceptBtn.classList.contains('app-btn--primary')).toBe(true)
    acceptBtn.click()
    await flushPromises()

    expect(accept).toHaveBeenCalledTimes(1)
    expect(reject).not.toHaveBeenCalled()
  })

  it('点击拒绝按钮：执行 reject 回调，不触发 accept', async () => {
    const accept = vi.fn()
    const reject = vi.fn()
    await requireConfirm({
      header: '确认', message: '继续？', accept, reject,
      acceptProps: { label: '确定' }, rejectProps: { label: '取消' },
    })

    const rejectBtn = buttons().find((b) => b.textContent?.trim() === '取消')!
    expect(rejectBtn.classList.contains('app-btn--ghost')).toBe(true)
    rejectBtn.click()
    await flushPromises()

    expect(reject).toHaveBeenCalledTimes(1)
    expect(accept).not.toHaveBeenCalled()
  })

  it('acceptProps.severity=danger 时接受按钮用 danger 层级（危险操作语义）', async () => {
    await requireConfirm({
      header: '危险操作', message: '不可撤销',
      acceptProps: { label: '删除', severity: 'danger' }, rejectProps: { label: '取消' },
      accept: vi.fn(), reject: vi.fn(),
    })

    const acceptBtn = buttons().find((b) => b.textContent?.trim() === '删除')!
    expect(acceptBtn.classList.contains('app-btn--danger')).toBe(true)
  })

  it('未提供 icon 时不渲染图标节点（避免空占位）', async () => {
    await requireConfirm({ header: '确认', message: '继续？', accept: vi.fn(), reject: vi.fn() })
    expect(dialogEl()!.querySelector('.app-confirm-dialog__header i')).toBeNull()
  })
})
