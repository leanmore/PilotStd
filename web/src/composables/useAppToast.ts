// web/src/composables/useAppToast.ts
/**
 * useAppToast — 跨端设计系统（DS）统一 Toast 提示（阶段三 · 模块四）。
 *
 * ── 为什么不是「一个 .vue 组件」而是一个 composable ──
 * PrimeVue 的 Toast 是**运行时服务**：`<Toast />` 只是渲染宿主，真正的 API 是
 * `useToast()` 返回的 `toast.add({...})`。而 `useToast()` 必须在 `setup()` 同步调用
 * （它内部 `inject(PrimeVueToastSymbol)`），**不能在异步回调/普通函数里临时调**。
 * 所以「统一 Toast」的正确形态是：
 *   1. 一个 composable 收口 add() 的调用口径（severity 白名单 / 默认 life / 文案参数）；
 *   2. 一个宿主组件收口渲染样式（AppToast.vue，内部就是配置好的 <Toast />）。
 *
 * ── 两种消费方式，都支持 ──
 *   A. 组件内（有 setup 上下文）：`const notify = useAppToast()` → `notify.success('已保存')`
 *   B. 非组件模块（composables / api 层）：`appToast.success(...)`（全局单例，见下）
 *      全局单例在 App.vue 挂载时通过 `bindAppToast(toast)` 注入，
 *      未绑定前调用会走 `console.warn` 并静默丢弃（**不抛错**，避免提示失败拖垮业务）。
 *
 * ── 与直接 `toast.add()` 的差异（这是收口的意义） ──
 *   - severity 只允许 `success | info | warn | error`（与 DS 语义色一一对应，杜绝自创）；
 *   - 默认 `life`：success/info 2000ms、warn/error 3000ms（错误看得更久）；
 *   - `summary` 必填、`detail` 可选；支持 `{ named }` 插值直接传给 i18n；
 *   - 统一 `closable: false`（提示自动消失，不占用户注意力）；
 *   - **禁止 group 分组的随意使用**：只有「同一实体反复失败」场景才传 group（如按站点分组），
 *     否则多条同类提示会互相覆盖（PrimeVue 的 group 语义是"替换同组"）。
 *
 * 门禁：业务代码禁止直接 `import { useToast } from 'primevue/usetoast'`
 * 或直接写 `<Toast />`（custom/no-raw-toast）。
 */
import { useToast } from 'primevue/usetoast'
import { i18n } from '@/i18n'

/** DS 语义色一一对应的四种提示级别（不提供第五种） */
export type ToastSeverity = 'success' | 'info' | 'warn' | 'error'

export interface ToastOptions {
  /** 主文案（已是最终字符串，或配合 key 由本函数翻译） */
  summary?: string
  /** i18n key；给了 key 就由本函数翻译，与 summary 二选一（key 优先） */
  key?: string
  /** 明细文案（可选，已是最终字符串） */
  detail?: string
  /** 明细的 i18n key（与 detail 二选一，key 优先） */
  detailKey?: string
  /** i18n 插值参数 */
  named?: Record<string, unknown>
  /** 停留毫秒；不传按 severity 取默认 */
  life?: number
  /** 同组提示互相替换（仅"同一实体反复失败"场景用，见文件头） */
  group?: string
}

/** severity → 默认停留时长（错误/警告停留更久，让用户看清） */
const DEFAULT_LIFE: Record<ToastSeverity, number> = {
  success: 2000,
  info: 2000,
  warn: 3000,
  error: 3000,
}

/** 把 key / summary 归一成最终字符串（key 优先，交给全局 i18n 实例翻译） */
function resolveText(key: string | undefined, text: string | undefined, named?: Record<string, unknown>): string {
  if (key) {
    return named
      ? (i18n.global.t as (k: string, n: Record<string, unknown>) => string)(key, named)
      : (i18n.global.t as (k: string) => string)(key)
  }
  return text ?? ''
}

/** PrimeVue Toast 服务的最小接口（不 import 它的类型，避免与运行时耦合） */
interface ToastServiceLike {
  add(message: {
    severity: ToastSeverity
    summary: string
    detail?: string
    life: number
    closable?: boolean
    group?: string
  }): void
  /** 清空指定分组的所有提示（仅 group 场景需要，如"某站点重试前先清掉旧错误"） */
  removeGroup?(group: string): void
}

/** 全局单例：供非组件模块（composables / api 层）使用 */
let boundToast: ToastServiceLike | null = null

/**
 * 绑定全局 toast 实例（在 App.vue 的 setup 里调用一次）。
 * 单独抽出来是为了让 `useAppToast()` 之外的地方也能提示 —— 那些地方没有 setup 上下文，
 * 拿不到 `useToast()`。
 */
export function bindAppToast(toast: ToastServiceLike): void {
  boundToast = toast
}

/** 内部：统一的 add 实现，组件内与全局单例共用 */
function addToast(service: ToastServiceLike, severity: ToastSeverity, opts: ToastOptions): void {
  const summary = resolveText(opts.key, opts.summary, opts.named)
  // 空文案是调用方的 bug：留一条 warn 便于排查，但不抛错（提示失败不该拖垮业务）
  if (!summary) {
    console.warn('[useAppToast] summary 为空，已跳过该提示') // i18n-allow: 开发者日志
    return
  }
  const detail = resolveText(opts.detailKey, opts.detail, opts.named)
  service.add({
    severity,
    summary,
    ...(detail ? { detail } : {}),
    life: opts.life ?? DEFAULT_LIFE[severity],
    // 提示自动消失，不给用户额外的关闭负担
    closable: false,
    ...(opts.group ? { group: opts.group } : {}),
  })
}

export interface AppToastApi {
  success(opts: ToastOptions | string): void
  info(opts: ToastOptions | string): void
  warn(opts: ToastOptions | string): void
  error(opts: ToastOptions | string): void
  /**
   * 清空指定分组的提示。
   * 只在 group 场景用（"同一实体反复失败"），如某站点重试前先清掉旧错误，
   * 避免旧错误与新结果同时挂在屏幕上互相矛盾。
   */
  removeGroup(group: string): void
}

function normalize(opts: ToastOptions | string): ToastOptions {
  return typeof opts === 'string' ? { summary: opts } : opts
}

function makeApi(getService: () => ToastServiceLike | null): AppToastApi {
  const fire = (severity: ToastSeverity) => (opts: ToastOptions | string) => {
    const service = getService()
    if (!service) {
      // 未绑定（如在挂载前的模块初始化阶段调用）：明确记录但不抛错
      console.warn('[useAppToast] toast 服务尚未绑定，提示被丢弃') // i18n-allow: 开发者日志
      return
    }
    addToast(service, severity, normalize(opts))
  }
  return {
    success: fire('success'),
    info: fire('info'),
    warn: fire('warn'),
    error: fire('error'),
    removeGroup(group: string) {
      const service = getService()
      if (!service?.removeGroup) {
        console.warn('[useAppToast] toast 服务不支持 removeGroup，已跳过') // i18n-allow: 开发者日志
        return
      }
      service.removeGroup(group)
    },
  }
}

/**
 * 组件内使用：必须在 `setup()` 同步调用（PrimeVue 的 `useToast()` 限制）。
 * 返回的四个方法签名一致，都接受 `{ summary }` 或 `{ key, named }` 或裸字符串。
 */
export function useAppToast(): AppToastApi {
  const toast = useToast()
  return makeApi(() => toast as unknown as ToastServiceLike)
}

/**
 * 非组件模块使用：走全局单例（App.vue 挂载时 `bindAppToast` 注入）。
 * 未绑定时静默丢弃并 warn，不抛错。
 */
export const appToast: AppToastApi = makeApi(() => boundToast)
