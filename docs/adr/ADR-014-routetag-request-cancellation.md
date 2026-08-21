# ADR-014: 前端 HTTP 请求取消 routeTag 三层机制

> 日期：2026-08-21（决策于 2026-08-16 会话 F147）
> 状态：✅ Accepted（已实施）
> 来源：A4 会话转录提炼（`~/.claude/projects/d--PilotStd/` F147）
> 关联：[[ADR-013]]

---

## 背景

`cancelAllRequests()` 在每次路由切换时无差别取消所有 pending 请求，误杀新路由组件 `onMounted` 刚发出的初始化请求（NS_BINDING_ABORTED 红字），且 `router.beforeEach` 无条件触发导致 SettingsView Tab 切换（`router.replace({query})`，path 不变）也误杀新 Tab 请求。这是系统性设计缺陷——"取消粒度太粗，不知道该取消谁只能全杀"。

## 决策：三层架构

1. **路由级隔离**：双池结构 `pendingPools(routeTag → reqKey → controller)` + `globalPool`（降级池）；三函数 `registerRequest` / `removeRequest`（池空自动删除防内存泄漏）/ `cancelByRouteTag`（abort 后删池）；`cancelAllRequests` 保留作降级。
2. **守卫级防误杀**：仅跨路由 path 变化时触发取消（`from.path !== to.path`），同路由 Tab 切换绝不触发全局取消。
3. **组件级自治**：同路由内请求取消由组件自身 watch/onUnmounted 管理；定时器轮询统一带 routeTag（防 flight 中的轮询请求在离开路由后更新已卸载组件）。

## 核心约束

- **routeTag 必须从真实路由表生成**（`web/src/types/route-tag.ts`，注释"⚠️ 手动维护，与 router.ts 同步"）——硬编码会引入幽灵标签
- `/settings` 用粗粒度 routeTag：`from.path !== to.path` 已保证同路由不误杀；细粒度引入 KeepAlive 生命周期问题（onUnmounted 不触发）+ 切回数据为空的副作用
- preferences store 全局共享（10 key 并发拉取、跨页面缓存）不迁移；写操作（保存/刷新令牌）不加 routeTag
- 严禁组件内裸调 http，所有请求收敛至 `src/api/`
- 3 处原生 axios 保留（router 登录检查、stores/app auth/me、AppLayout logout）是有意的循环依赖规避，补架构注释

## 实施证据

- `web/src/api/http.ts`（双池 + registerRequest/removeRequest/cancelByRouteTag）
- `web/src/router.ts`（from.path !== to.path 守卫）
- Playwright E2E：`route-cancellation.spec.ts`

## 后续演进

- 阶段 4：7 个绕过 http.ts 的原生 axios view 迁移到统一实例（纳入 CSRF/401 降级/取消池）
- 阶段 5：preferences 10 并行 GET → 1 批量 GET、循环依赖解耦（setUnauthorizedHandler 回调）
