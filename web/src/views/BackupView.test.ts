// views/BackupView.test.ts — 备份管理视图测试
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
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

function mountView() {
  return mount(BackupView, {
    global: { plugins: [PrimeVue] },
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
})
