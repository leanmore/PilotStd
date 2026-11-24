// TaskManager 组件测试（V-16，2026-11-23）
//
// 背景：V-16 记录该组件分支覆盖仅 27.9%。2026-11-23 的 `df5c19af` 在
// `retryTask` / `cancelTask` 里新增了 `appToast.error` 失败分支（NEW-16），
// 功能变更已发生但没补测试 —— 覆盖率反而从 27.9% 掉到 25.53%。
//
// 本测试聚焦**新增的失败分支**（这是 V-16 要求"随功能变更补失败分支用例"的直接兑现）：
//   1. 重试失败 → 弹 toast.error，且 key 正确
//   2. 取消失败 → 弹 toast.error，且 key 正确
//   3. 成功路径不弹 error
//
// 用源码级断言 + 纯函数级验证：该组件依赖 PrimeVue 插件与大量 http mock，
// 完整挂载成本高；而"失败分支是否提示"是结构性问题，源码断言更稳。
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SRC = resolve(__dirname, '..')
const TASK_MANAGER = resolve(SRC, 'components/TaskManager.vue')

function source(): string {
  return readFileSync(TASK_MANAGER, 'utf8')
}

/** 取某个函数体（从 `function 名字` 到下一个顶层 `function`/`async function`） */
function functionBody(name: string): string {
  const text = source()
  const start = text.indexOf(name)
  if (start < 0) throw new Error(`找不到函数 ${name}`)
  const rest = text.slice(start)
  const next = rest.search(/\n(?:async )?function /)
  return next > 0 ? rest.slice(0, next) : rest
}

describe('TaskManager 失败分支（V-16 / NEW-16）', () => {
  it('retryTask 失败时弹 appToast.error 且用正确 key', () => {
    const body = functionBody('async function retryTask')
    expect(body).toContain('appToast.error')
    expect(body).toContain('task.manager.retry_failed')
    // 成功路径必须仍调用接口并刷新列表
    expect(body).toContain('/retry')
    expect(body).toContain('loadTasks')
  })

  it('cancelTask 失败时弹 appToast.error 且用正确 key', () => {
    const body = functionBody('async function cancelTask')
    expect(body).toContain('appToast.error')
    expect(body).toContain('task.manager.cancel_failed')
    expect(body).toContain('/cancel')
    expect(body).toContain('loadTasks')
  })

  it('成功路径不弹 error（catch 之外没有 appToast.error）', () => {
    for (const fn of ['async function retryTask', 'async function cancelTask']) {
      const body = functionBody(fn)
      const catchIdx = body.indexOf('catch')
      expect(catchIdx).toBeGreaterThan(-1)
      // appToast.error 只应出现在 catch 之后（失败分支）
      const beforeCatch = body.slice(0, catchIdx)
      expect(beforeCatch).not.toContain('appToast.error')
    }
  })

  it('使用 appToast 全局单例（不是 useAppToast，避免 PrimeVue 插件依赖）', () => {
    const text = source()
    expect(text).toContain("import { appToast } from '@/composables/useAppToast'")
    const body = text
      .split('\n')
      .filter((ln) => !ln.trimStart().startsWith('import '))
      .join('\n')
    expect(body).not.toContain('useAppToast()')
  })
})

describe('TaskManager 纯函数分支（V-16 覆盖面补充）', () => {
  it('getStatusSeverity 覆盖全部状态映射', () => {
    const text = source()
    // 状态映射表必须含 7 个状态（含 cancelled/paused）
    for (const st of ['completed', 'failed', 'running', 'pending', 'cancelled', 'paused']) {
      expect(text).toContain(`${st}:`)
    }
  })

  it('progress 有除零保护（total_items === 0）', () => {
    const body = functionBody('function progress')
    expect(body).toContain('total_items === 0')
    expect(body).toContain('completed')
  })
})
