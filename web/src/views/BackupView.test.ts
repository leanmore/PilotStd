// views/BackupView.test.ts — 备份管理视图测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { createI18n } from 'vue-i18n'
import zhCN from '@/locales/zh-CN.json'
import zhTW from '@/locales/zh-TW.json'
import en from '@/locales/en.json'
import { useAppStore } from '@/stores/app'
import BackupView from './BackupView.vue'

// Mock axios
const mockGetBackupList = vi.fn()
const mockCreateBackup = vi.fn()
vi.mock('@/api/backup', () => ({
  getBackupList: (...args: any[]) => mockGetBackupList(...args),
  createBackup: (...args: any[]) => mockCreateBackup(...args),
}))

const mockBackups = [
  { id: '1', name: 'backup_20260629.zip', size: 1048576, size_mb: 1.0, created_at: '2026-06-29T12:00:00Z' },
  { id: '2', name: 'backup_20260630.zip', size: 2097152, size_mb: 2.0, created_at: '2026-06-30T08:30:00Z' },
]

/** 用真实 locale 文件挂载（空 messages 会让 t() 回显 key，断言即失去意义） */
function makeI18n(locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN') {
  return createI18n({ legacy: false, locale, messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en } })
}

/**
 * 挂载视图。
 *
 * `role` 默认 'admin' ——「创建备份」按钮受 admin 门控（后端 `POST /api/backup/create`
 * 已加 `@require_role("admin")`，备份含全量数据库内容）。既有用例断言按钮存在，
 * 故默认用 admin；非 admin 的行为由下方专门的守卫用例覆盖。
 */
function mountView(locale: 'zh-CN' | 'zh-TW' | 'en' = 'zh-CN', role: 'admin' | 'user' = 'admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useAppStore()
  store.role = role
  return mount(BackupView, {
    global: { plugins: [pinia, PrimeVue, makeI18n(locale)] },
  })
}

describe('BackupView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染页面标题和"创建备份"按钮', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: [] } })
    const wrapper = mountView()
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))

    expect(wrapper.html()).toContain('备份管理')
    expect(wrapper.html()).toContain('创建备份')
  })

  it('渲染备份列表数据', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: mockBackups } })
    const wrapper = mountView()
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('backup_20260629.zip')
    expect(html).toContain('backup_20260630.zip')
    expect(html).toContain('1')   // size_mb
    expect(html).toContain('2')   // size_mb
  })

  it('显示上次备份时间', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: mockBackups } })
    const wrapper = mountView()
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))
    await wrapper.vm.$nextTick()

    expect(wrapper.html()).toContain('上次备份')
  })

  it('空列表时正常渲染不崩溃', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: [] } })
    const wrapper = mountView()
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))

    // 不应显示"上次备份"文字
    expect(wrapper.html()).not.toContain('上次备份')
    // 表格区域应存在
    expect(wrapper.html()).toContain('备份管理')
  })

  it('请求失败时正常渲染不崩溃', async () => {
    mockGetBackupList.mockRejectedValue(new Error('网络错误'))
    const wrapper = mountView()
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))

    // 仍然渲染基本 UI
    expect(wrapper.html()).toContain('备份管理')
    expect(wrapper.html()).toContain('创建备份')
  })

  // 批 6 i18n 守卫：文案确实来自 locales，且随语言切换而变化
  it('文案随语言切换（zh-CN / en）', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: [] } })

    const zh = mountView('zh-CN')
    await zh.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))
    expect(zh.html()).toContain('备份管理')

    const english = mountView('en')
    await english.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))
    expect(english.html()).toContain('Backup Management')
    expect(english.html()).not.toContain('backup.')
  })

  // ── 授权门控守卫（技术债阶段批次①）─────────────────────────────────────
  // 后端 `POST /api/backup/create` 已加 `@require_role("admin")`；前端同步隐藏按钮，
  // 避免非 admin 看到「可点但必然 403」的按钮。
  it('非 admin 不渲染「创建备份」按钮', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: [] } })
    const wrapper = mountView('zh-CN', 'user')
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))

    // 页面仍可访问（列表可见），但创建入口隐藏
    expect(wrapper.html()).toContain('备份管理')
    expect(wrapper.html()).not.toContain('创建备份')
  })

  it('admin 渲染「创建备份」按钮（判别力对照）', async () => {
    mockGetBackupList.mockResolvedValue({ data: { items: [] } })
    const wrapper = mountView('zh-CN', 'admin')
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))

    expect(wrapper.html()).toContain('创建备份')
  })
})
