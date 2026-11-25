// SettingsTabUsers 测试（用户管理）：挂载加载列表；删除按钮只对「管理员 + 非当前登录用户」可见；
// 添加用户拦截保留名 admin；改密有必填/长度/一致性三道校验；删除前必须 confirm.require 二次确认。
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import zhCN from '@/locales/zh-CN.json'
import { getUsers, addUser, deleteUser, changePassword } from '@/api'
import SettingsTabUsers from './SettingsTabUsers.vue'

const store = vi.hoisted(() => ({ role: 'admin', username: 'alice' }))
const confirmRequire = vi.hoisted(() => vi.fn())

vi.mock('@/stores/app', () => ({ useAppStore: () => store }))
vi.mock('primevue/useconfirm', () => ({ useConfirm: () => ({ require: confirmRequire }) }))
vi.mock('@/api', () => ({ getUsers: vi.fn(), addUser: vi.fn(), deleteUser: vi.fn(), changePassword: vi.fn() }))
vi.mock('@/api/http', () => ({ getApiErrorMessage: vi.fn(() => '操作失败') }))

const AppDialog = {
  name: 'AppDialog', props: ['visible', 'header', 'modal', 'style'], emits: ['update:visible'],
  template: '<div class="dlg" v-if="visible"><slot /></div>',
}
const DataView = { name: 'DataView', props: ['value'], template: '<div class="dv"><slot name="list" :items="value" /></div>' }
const USERS = [
  { id: 1, username: 'alice', role: 'admin', created_at: '2026-01-01' },
  { id: 2, username: 'bob', role: 'user', created_at: '2026-02-02' },
]

type TabVM = {
  newUser: { username: string; password: string; role: string }
  pwdForm: { old: string; new: string; confirm: string }
  doAdd: () => Promise<void>
  doChangePwd: () => Promise<void>
}

function mountTab() {
  return mount(SettingsTabUsers, {
    global: {
      plugins: [PrimeVue, createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })],
      stubs: { AppDialog, DataView },
    },
  })
}
const buttons = (w: ReturnType<typeof mount>) => w.findAll('button')
const vmOf = (w: ReturnType<typeof mount>) => w.vm as unknown as TabVM

describe('SettingsTabUsers 用户管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.role = 'admin'
    store.username = 'alice'
    vi.mocked(getUsers).mockResolvedValue({ users: USERS } as never)
    vi.mocked(addUser).mockResolvedValue({ ok: true } as never)
    vi.mocked(deleteUser).mockResolvedValue({ ok: true } as never)
    vi.mocked(changePassword).mockResolvedValue({ ok: true } as never)
    vi.stubGlobal('alert', vi.fn())
  })

  it('加载列表；删除按钮只在非当前用户行显示，普通用户一个都没有', async () => {
    const wrapper = mountTab()
    await flushPromises()
    expect(getUsers).toHaveBeenCalledWith('/settings')
    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('bob')
    expect(buttons(wrapper).filter((b) => b.text().includes('删除')).length).toBe(1)

    store.role = 'user'
    const userView = mountTab()
    await flushPromises()
    expect(buttons(userView).filter((b) => b.text().includes('删除')).length).toBe(0)
  })

  it('添加用户：addUser 收到用户名/密码/角色，成功后刷新列表', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await buttons(wrapper).find((b) => b.text().trim() === '添加')!.trigger('click')
    const vm = vmOf(wrapper)
    vm.newUser = { username: 'carol', password: 'pw123456', role: 'admin' }
    await vm.doAdd()
    await flushPromises()
    expect(addUser).toHaveBeenCalledWith('carol', 'pw123456', 'admin')
    expect(getUsers).toHaveBeenCalledTimes(2)
  })

  it('保留用户名 admin 被拦截，不发请求', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await buttons(wrapper).find((b) => b.text().trim() === '添加')!.trigger('click')
    const vm = vmOf(wrapper)
    vm.newUser = { username: 'ADMIN', password: 'pw123456', role: 'user' }
    await vm.doAdd()
    await flushPromises()
    expect(wrapper.text()).toContain('为保留用户名')
    expect(addUser).not.toHaveBeenCalled()
  })

  it('改密三道校验：必填 → 长度 → 两次不一致', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await buttons(wrapper).find((b) => b.text().trim() === '修改密码')!.trigger('click')
    const vm = vmOf(wrapper)

    await vm.doChangePwd()
    expect(wrapper.text()).toContain('请填写旧密码和新密码')
    vm.pwdForm = { old: 'old', new: 'abc', confirm: 'abc' }
    await vm.doChangePwd()
    expect(wrapper.text()).toContain('新密码至少')
    vm.pwdForm = { old: 'old', new: 'newpass', confirm: 'different' }
    await vm.doChangePwd()
    expect(wrapper.text()).toContain('两次输入的新密码不一致')
    expect(changePassword).not.toHaveBeenCalled()
  })

  it('改密成功：changePassword(old,new) 严格传参并提示已修改', async () => {
    const wrapper = mountTab()
    await flushPromises()
    const vm = vmOf(wrapper)
    vm.pwdForm = { old: 'oldpass', new: 'newpass1', confirm: 'newpass1' }
    await vm.doChangePwd()
    await flushPromises()
    expect(changePassword).toHaveBeenCalledWith('oldpass', 'newpass1')
    expect(alert).toHaveBeenCalled()
  })

  it('删除需二次确认：确认后才按 id 调 deleteUser', async () => {
    const wrapper = mountTab()
    await flushPromises()
    await buttons(wrapper).filter((b) => b.text().includes('删除'))[0].trigger('click')

    expect(confirmRequire).toHaveBeenCalledTimes(1)
    const cfg = confirmRequire.mock.calls[0][0] as { message: string; accept: () => void }
    expect(cfg.message).toContain('bob')
    expect(deleteUser).not.toHaveBeenCalled()
    cfg.accept()
    await flushPromises()
    expect(deleteUser).toHaveBeenCalledWith(2)
  })

  it('加载用户列表失败时显示错误文案', async () => {
    vi.mocked(getUsers).mockRejectedValue(new Error('boom'))
    const wrapper = mountTab()
    await flushPromises()
    expect(wrapper.text()).toContain('加载用户列表失败')
  })

  it('删除失败：展示后端错误文案，不静默（D-7 回归）', async () => {
    vi.mocked(deleteUser).mockRejectedValue(new Error('403'))
    const wrapper = mountTab()
    await flushPromises()

    await (wrapper.vm as unknown as { doDelete: (id: number) => Promise<void> }).doDelete(2)
    await flushPromises()
    // 组件通过 getApiErrorMessage 统一取文案（本测试 mock 为「操作失败」）
    expect(wrapper.text()).toContain('操作失败')
    // 失败后不得刷新列表（原实现无论如何都会 loadUsers()）
    expect(getUsers).toHaveBeenCalledTimes(1)
  })
})
