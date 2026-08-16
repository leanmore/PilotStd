// web/src/types/route-tag.ts
// ⚠️ 手动维护，与 router.ts 同步：仅列走共享 http.ts 的页面级路由。
export type RouteTag =
  | '/'
  | '/task'
  | '/organize'
  | '/pending'
  | '/announce'
  | '/notification-logs'
  | '/standards-status'
  | '/login'
  | '/settings'
  | '/scheduler'
  | '/backup'
  | '/query-history'
  | '/download-queue'
  | '/resources'
  // 显式降级标记：请求不归属任何路由，等价于不传 routeTag（走 globalPool）
  | 'global'
