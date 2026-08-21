# 登录页背景图请求时机修复 spec-lite

## 用户指令摘要

- 现象：打开登录页 URL 时，背景图网络请求延迟到"进入项目"（登录成功后）才发起，甚至缺失，影响首屏视觉。
- 目标：背景图两阶段请求（获取 URL → 加载图片）应在登录页组件创建时立即发起，不依赖全局 store、不等待认证。
- 来源：登录页背景图请求时机调查与修复方案（完整版）。

## 采纳的关键设计决策

1. **新增公开接口 `GET /api/login-background`**（白名单放行），仅返回 `appearance.login_bg` 单字段；替代 admin-only 的 `GET /api/settings`（未登录 401 / 非 admin 403），实现"解耦鉴权"。
2. **前端请求提前到 `<script setup>` 顶层**（早于 onMounted），并保持两阶段：`getLoginBackground()` 取 URL → `new Image()` 预加载 → onload 后写 `bgUrl` 应用 CSS background-image。
3. **`/login` 路由改为静态导入**（取消懒加载），消除路由懒加载对首屏组件挂载的额外延迟。
4. **降级策略**：API 失败 / 图片加载失败 / `file://` 本地路径（桌面端遗留值）→ 默认渐变背景，`console.warn` 记录，无未捕获异常。
5. **前端类型同步**：新增 `LoginBackgroundResponse` 写入 `src/types/api.ts`（符合 ui-components.md 接口类型约束）。

## 识别到的风险点及与现有架构的冲突

1. 不可将 `/api/settings` 重新加入白名单（SEC-001 已移除，会泄露存储路径/站点配置等系统信息）；必须用最小字段公开接口，测试断言响应仅含 `url` 字段。
2. `/api/login-background` 前缀已被 `("/api/login", set())` 白名单前缀命中，显式新增条目仅为意图明确 + 防未来将 `/api/login` 收窄为 POST 时回归。
3. 路由静态导入会增加主包体积（LoginView 依赖均为已入主包的模块，增量可忽略）；`manualChunks` 不受影响。
4. 桌面端 `file://` 背景图值在浏览器不可用，必须在前端过滤（后端原样返回配置值，不做展示层判断）。
5. jsdom 测试环境无真实图片加载，需 stub `window.Image` 手动触发 onload/onerror 保证确定性。

## 验证方式

- 后端：`tests/test_login_background_api.py`（无 token 200 / 配置回显 / 仅 url 字段 / 伪造 token 仍公开 / 非字符串防御）；`test_settings_auth.py` 确认 `/api/settings` 仍 401/403。
- 前端：`web/src/views/LoginView.test.ts`（挂载即请求 / 两阶段预加载 / API 失败降级 / 图片 onerror 降级 / file:// 跳过）。
- 门禁：`scripts/check_all.sh --fast` + ruff + mypy（改动文件）+ `vue-tsc`。
- 手动：DevTools Network 清缓存刷新登录页，确认 `GET /api/login-background` 与背景图请求在 DOMContentLoaded 前后出现、无 token 时均 200。
