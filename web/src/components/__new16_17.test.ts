// tests for NEW-16 / NEW-17（方向 C 批次 6）
// NEW-16：3 个组件的用户操作失败分支必须弹提示（不能静默）
// NEW-17：stores/app 的系统主题监听器必须可 dispose
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SRC = resolve(__dirname, '..')

// ── NEW-16：源码级断言「用户操作失败分支有 appToast.error」──
// 用源码断言而非组件测试：这 3 个组件分别是 Options API / 依赖大量 http mock，
// 单测成本高；而「失败分支有没有提示」是纯结构性问题，源码断言更直接且不易误判。
describe('NEW-16 用户操作失败必须有反馈', () => {
  const cases: Array<[string, string]> = [
    ['components/FileMonitor.vue', 'startMonitor'],
    ['components/FileMonitor.vue', 'stopMonitor'],
    ['components/CacheManager.vue', 'saveConfig'],
    ['components/CacheManager.vue', 'triggerCleanup'],
    ['components/TaskManager.vue', 'retryTask'],
    ['components/TaskManager.vue', 'cancelTask'],
  ]

  it.each(cases)('%s 的 %s 失败分支调用了 appToast.error', (file, fnName) => {
    const text = readFileSync(resolve(SRC, file), 'utf8')
    // 该函数体范围内必须有 appToast.error
    const fnIdx = text.indexOf(fnName)
    expect(fnIdx, `${file} 找不到 ${fnName}`).toBeGreaterThan(-1)
    // 取函数名后 800 字符窗口（足够覆盖函数体）
    const window = text.slice(fnIdx, fnIdx + 800)
    expect(window, `${fnName} 失败分支缺少 appToast.error`).toContain('appToast.error')
  })

  it('3 个组件都导入了 appToast（不是 useAppToast，避免 inject 依赖）', () => {
    for (const file of ['components/FileMonitor.vue', 'components/CacheManager.vue', 'components/TaskManager.vue']) {
      const text = readFileSync(resolve(SRC, file), 'utf8')
      expect(text, `${file} 应导入 appToast 全局单例`).toContain("import { appToast }")
      // 注意：import 的路径字符串本身含 "useAppToast"，故先剔除 import 行再断言
      const body = text
        .split('\n')
        .filter((ln) => !ln.trimStart().startsWith('import '))
        .join('\n')
      expect(body, `${file} 不应调用 useAppToast()（会要求 PrimeVue 插件）`).not.toContain('useAppToast()')
    }
  })
})

// ── NEW-17：监听器可 dispose ──
describe('NEW-17 系统主题监听器可 dispose', () => {
  it('stores/app.ts 导出 disposeSystemThemeListener 且成对注册/注销', () => {
    const text = readFileSync(resolve(SRC, 'stores/app.ts'), 'utf8')
    expect(text).toContain('disposeSystemThemeListener')
    expect(text).toContain('addEventListener')
    expect(text).toContain('removeEventListener')
    // 必须保留引用（否则无法 remove）
    expect(text).toContain('_mediaQueryList')
    expect(text).toContain('_mediaHandler')
  })
})
