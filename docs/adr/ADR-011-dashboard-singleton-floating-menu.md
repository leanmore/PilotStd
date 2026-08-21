# ADR-011: 首页仪表盘状态集中化与悬浮工作台菜单（A2 迁移）

> 日期：2026-08-21
> 状态：✅ Accepted（已实施，归档）
> 关联：[[ADR-003]]（模块级单例模式沿用 `useUserPreferences` 惯例）
> 来源：迁移自 Claude Code 计划 `~/.claude/plans/fluttering-soaring-minsky.md`（2026-07）

---

## 背景

HomeView 顶部存在 `.dashboard-header` 操作栏（"工作台"标题 + 添加卡片下拉 + 锁定布局按钮），占用垂直空间，且功能与右上角悬浮工作台按钮重复。

## 决策

1. **删除顶部操作栏**，将"添加卡片"与"锁定/解锁布局"功能整合进悬浮按钮的下拉菜单。
2. **状态集中化**：新建 `web/src/composables/useDashboard.ts`，采用模块级单例 composable（`layout`/`isLocked` 在模块顶层声明 `ref`，所有调用者共享同一实例），遵循项目既有 `useUserPreferences` 模式。

## 核心约束与设计点

- **三阶段加载**：`fetchLayout()` 按 localStorage → API → 默认 顺序加载
- **竞态防护**：模块级 `fetchVersion` 版本号标记，每个 `await` 后校验，避免路由快速切换时旧异步回调写入脏数据
- **可访问性**：`role="menu"`/`role="menuitem"`、`aria-labelledby` 关联、Esc 关闭并归还焦点、Tab 焦点循环
- **路由联动**：`watch(route.path)` 在浏览器前进/后退、侧边栏跳转时自动关闭菜单
- **移动端**：悬浮按钮不渲染，底部导航正常工作

## 实施证据

- `web/src/composables/useDashboard.ts`（存在）
- `web/src/views/HomeView.vue`：`.dashboard-header` 已删除（0 处残留）
- `web/src/components/AppLayout.vue`：`floating-workspace-menu` 已实现
- 后续演进：仪表盘布局迁移至 preferences API（见 git log `9243c599`），悬浮按钮位置记忆升级为百分比坐标持久化（`6ff1f20a`）
