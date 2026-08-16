# 工作台悬浮按钮自定义拖拽位置 — spec-lite

## 用户指令摘要

现有唯一悬浮图标为 AppLayout.vue 的「工作台悬浮按钮」（固定右下角、无拖拽、无持久化）。要求支持拖拽移动 + localStorage 持久化，仅改造现有按钮，不新增其他悬浮按钮，不改变点击展开菜单等现有功能。

## 采纳的关键设计决策

1. 手写 Pointer Events（非 mousedown/touchstart 双绑），统一覆盖鼠标+触摸+触控笔，用 `setPointerCapture` 免全局监听。
2. 5px 移动阈值区分点击/拖拽，拖拽释放后吞掉紧随的 click，避免误触菜单。
3. 拖拽逻辑抽独立 composable `useFloatingDrag.ts`，避免 AppLayout.vue（已 519 行）继续膨胀，且可独立单测。
4. 位置复用 `@/lib/storage` 的 getItem/setItem（自动 `pilotstd_` 前缀），key=`floating_workspace_pos`，默认右下角。
5. 释放时 clamp 吸附可视区 + window resize 150ms 防抖重新校验并写回。

## 识别到的风险点及与现有架构的冲突

1. 触摸设备滚动冲突：必须给按钮加 `touch-action: none`，否则触摸拖拽触发页面滚动。
2. 与全局 click-outside 冲突：AppLayout.vue:132 有 document 级点击关闭菜单监听，拖拽释放的 click 需被抑制。
3. 现有 i18n 硬编码：按钮 aria-label 及菜单文案未走 i18n（不在本次范围，新增文案需走 i18n）。
4. 位置由 bottom/right 改 left/top 后，下拉菜单绝对定位（right:0）需验证跟随正确。

## 验证方式

- `npm run test`：新增 useFloatingDrag.test.ts 覆盖默认坐标、阈值内不拖拽、超阈值拖拽、释放 clamp、storage 读写、resize 校验。
- 手动：拖拽到任意位置刷新后位置保持；拖出屏幕释放后吸附回可视区；非拖拽点击菜单正常弹出。
