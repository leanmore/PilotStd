# 阶段5 HTTP 循环依赖解耦 + 偏好收编 + 环境变量修正 — 实现计划

> **Goal:** 解决 VITE_SUPERUSER_ROLE 警告（改名对齐）、偏好请求收编（store 收编 + 删死代码 + 批量 GET）、http.ts 循环依赖解耦（依赖注入回调），并补全单测。
> **Architecture:** 依赖注入回调解耦 http.ts；`registerHttpHandlers` bootstrap 注册 401 处理器；preferences store 收编 useDashboard 直调 + getAll 改批量。
> **Tech Stack:** TypeScript + Vue 3 + Pinia + axios + vitest
> **Design Doc:** `docs/superpowers/specs/2026-08-16-stage5-http-decircularize-design.md`

---

## 批次A：环境变量改名对齐（低风险）

**Files:**
- Modify: `web/src/config/index.ts`
- Modify: `web/src/main.ts`
- Create: `web/.env.example`
- Create: `web/.env.local`（本地，不入库）
- Modify: `.github/workflows/ci.yml`

- [ ] `VITE_SUPERUSER_ROLE` → `VITE_SUPERUSER_USERNAME`（config/index.ts 1 处 + main.ts 2 处）
- [ ] ci.yml:835 `VITE_SUPERUSER_ROLE: superadmin` → `VITE_SUPERUSER_USERNAME: superadmin`
- [ ] 新建 `web/.env.example`（`VITE_SUPERUSER_USERNAME=superadmin`）
- [ ] 新建 `web/.env.local`（同上，gitignore）
- [ ] 验证：`pnpm build` 成功 + `vue-tsc --noEmit` 零错误

---

## 批次B：Preferences 收编 + 清理 + 优化（中风险）

**Files:**
- Modify: `web/src/stores/preferences.ts`
- Modify: `web/src/composables/useDashboard.ts`

- [ ] 删除 `remove()` / `resetAll()` 死代码（-11 个 DELETE）
- [ ] `getAll()` 从 10 个并行 GET 改为 1 个 `http.get('/user/preferences')`（返回 `{preferences: {...}}`）
- [ ] 新增 `getDashboardLayout()` / `setDashboardLayout()` action
- [ ] `useDashboard.ts` 移除直调 http 的 2 处，改为调用 store action
- [ ] 验证：`vue-tsc --noEmit` 零错误 + `vitest run` 全绿

---

## 批次C：循环依赖解耦（高风险）

**Files:**
- Modify: `web/src/api/http.ts`
- Create: `web/src/bootstrap/registerHttpHandlers.ts`
- Modify: `web/src/main.ts`
- Modify: `web/src/stores/app.ts`
- Modify: `web/src/router.ts`
- Modify: `web/src/components/AppLayout.vue`

- [ ] http.ts：移除 `import { useAppStore }` 与动态 `import('../router')`，新增 `setUnauthorizedHandler(fn)`
- [ ] 401 拦截器：命中 401 且未 `skipGlobalAuthRedirect` 时调用注册的 handler
- [ ] 新建 `registerHttpHandlers.ts`：静态 import http/useAppStore/router，注册 401 处理器（`clearUser` + `router.push('/login')`）
- [ ] `main.ts`：调用 `registerHttpHandlers()`
- [ ] `stores/app.ts`：`axios.get('/api/auth/me')` → `http.get('/auth/me')`；移除 `import axios`
- [ ] `router.ts`：`axios.get('/api/stats')` → `http.get('/stats', { skipGlobalAuthRedirect: true })`；移除 `import axios`
- [ ] `AppLayout.vue`：`axios.post('/api/logout')` → `http.post('/logout', undefined, { skipGlobalAuthRedirect: true })`；移除 `import axios`
- [ ] 移除三处"刻意使用原生 axios"的架构注释
- [ ] 验证：手动回归清单（登录刷新、清 cookie 触发 401、登出、未登录访问受保护路由）+ Playwright E2E

---

## 批次D：测试补全（中风险）

**Files:**
- Create: `web/src/api/__tests__/http.test.ts`
- Create: `web/src/stores/preferences.test.ts`
- Create: `web/src/stores/app-auth.test.ts`

- [ ] `http.test.ts`：setUnauthorizedHandler 注册与触发；401 调用 handler；skipGlobalAuthRedirect 不触发
- [ ] `preferences.test.ts`：getAll 批量拉取；setDashboardLayout 读写；remove/resetAll 已删除
- [ ] `app-auth.test.ts`：loadPreferences 用 http 实例；401 后状态清空
- [ ] 验证：新增测试全绿 + 总测试数 ≥ 124

---

## 执行顺序与提交

```
批次A → 批次B → 批次C → 批次D（各批次独立验证 + 独立提交）
```

| 批次 | 提交信息 |
| :--- | :--- |
| A | `fix(config): rename VITE_SUPERUSER_ROLE to VITE_SUPERUSER_USERNAME` |
| B | `refactor(preferences): consolidate store requests and remove dead code` |
| C | `refactor(http): decouple circular dependency via setUnauthorizedHandler` |
| D | `test(http): add unit tests for unauthorized handler and preferences` |
