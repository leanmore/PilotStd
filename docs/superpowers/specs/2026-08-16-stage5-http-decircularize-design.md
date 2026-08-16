# 阶段5 HTTP 循环依赖解耦 + 偏好收编 + 环境变量修正 — 设计文档

> 日期：2026-08-16
> 类型：架构变更（跨模块重构 + 接口变更）
> 关联计划：`docs/superpowers/plans/2026-08-16-stage5-http-decircularize-plan.md`

## 一、背景与目标

阶段5 一并解决三个问题：

- **A**：`VITE_SUPERUSER_ROLE` 环境变量警告（本地 dev 恒缺该变量）
- **B**：偏好系统请求未完全收编（`useDashboard` 绕过 store 直调 http）+ store 内死代码
- **C**：`http.ts` 循环依赖，导致 `router.ts` / `stores/app.ts` 无法使用 http 实例，只能用原生 axios

## 二、调查结论（关键事实）

### A 项根因
`VITE_SUPERUSER_ROLE` 仅 CI 构建时注入（`.github/workflows/ci.yml:835`）。本地无任何 `.env` 文件定义，`vite.config.ts` 无 `define` 兜底，故 `import.meta.env.VITE_SUPERUSER_ROLE` 恒 `undefined` → `SUPERUSER_USERNAME = null` → `main.ts` 警告。
变量名 misnomer：存的是**用户名**（superadmin），却叫 `ROLE`；后端已区分 `SUPERUSER_USERNAME`（用户名）与 `ADMIN_ROLE`（角色）。

### B 项现状
`stores/preferences.ts` **已迁移到 `@/api/http`**（非 axios 直调）。10 个请求 = `getAll()` 的并行 GET。但 `useDashboard.ts` 仍绕过 store 直调 http（`layout:dashboard` 的 get/put）。`remove()`/`resetAll()` 无调用方（死代码）。
**后端已存在批量 GET**：`GET /api/user/preferences` 返回 `{"preferences": {key: value}}`（`user_service.get_preferences`）。故 getAll 可纯前端优化为 1 个请求。

### C 项依赖链路
`http.ts` 401 拦截器静态 `import { useAppStore }`（唯一静态业务耦合）+ 动态 `import('../router')`。`router.ts` 静态 import `cancelByRouteTag`（http 工具函数）+ 用原生 axios 做守卫检查。`stores/app.ts` 用原生 axios 做 `auth/me`。三处原生 axios 均有注释说明是刻意规避循环依赖。

## 三、设计决策

| 决策 | 方案 | 说明 |
| :--- | :--- | :--- |
| A 改名对齐 | `VITE_SUPERUSER_ROLE` → `VITE_SUPERUSER_USERNAME` | 消除语义 misnomer，与后端 `SUPERUSER_USERNAME` 对齐 |
| B 收编+清理+优化 | ① useDashboard 直调收编进 store ② 删 remove/resetAll 死代码 ③ getAll 改 1 个批量 GET | 批量 GET 后端已存在，纯前端 |
| C 依赖注入回调 | `setUnauthorizedHandler(fn)`，http.ts 归零业务依赖 | 由 bootstrap 模块注册 401 处理器 |

### C 项解耦方案（依赖注入）

`http.ts` 不再静态 import `useAppStore`、不再动态 import `router`，改为暴露：

```typescript
type UnauthorizedHandler = () => void | Promise<void>
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void
```

401 拦截器命中时调用已注册的 `unauthorizedHandler`（若已注册）。由新建的 `src/bootstrap/registerHttpHandlers.ts` 在 `main.ts` 启动时注册处理器，处理器内部才引用 `useAppStore` + `router`（此时 http.ts 已归零业务依赖，可安全静态 import）。

## 四、技术修正（对执行方案模板的审查结论）

1. **registerHttpHandlers 模板 bug**：`typeof router === 'function' ? router() : router` 是死逻辑——`router` 是 `createRouter()` 返回的实例对象，`typeof` 恒 `'object'`。解耦后可直接静态 import 并 `router.push('/login')`，删除死逻辑与错误注释。
2. **logout 双重跳转**：`http.post('/logout')` 需带 `skipGlobalAuthRedirect: true`，否则 token 失效时 401 触发 handler 与 logout 函数自身双重 `clearUser` + push。
3. **router.ts 守卫请求**：`http.get('/stats', { skipGlobalAuthRedirect: true })`，避免 401 拦截器与守卫双重跳转循环。
4. **`web/.env.example` 为新建文件**（web/ 下当前无任何 .env）；本地用 `web/.env.local`（被 `.gitignore` 忽略）。
5. **AppLayout 路径**：`src/components/AppLayout.vue`。
6. **测试路径**：对齐现有约定 `src/api/__tests__/`、`src/stores/app.test.ts`（同目录）。

## 五、风险

| 风险 | 等级 | 缓解 |
| :--- | :--- | :--- |
| 401 拦截器行为变化 | 高 | 手动回归清单（清 cookie 触发 401、登出、未登录访问受保护路由）+ 新增单测 |
| router 守卫冲突 | 中 | `/stats` 带 `skipGlobalAuthRedirect` |
| useDashboard 收编后时序 | 中 | 对比收编前后 Dashboard 布局读写 |
| CI 变量名变更 | 低 | 本地 build 验证后 push |
