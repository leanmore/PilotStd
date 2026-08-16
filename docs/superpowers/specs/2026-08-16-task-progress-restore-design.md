# 任务页面进度丢失修复 — spec-lite

## 用户指令摘要

Web 任务页执行任务后退出再进入，进度不显示。根因：runId 及全部进度均为组件内 ref，App.vue 无 KeepAlive 且 :key 强制重建，卸载即销毁；onMounted 未恢复。要求前端持久化 runId + onMounted 恢复，后端补全 step_results 使详情卡片可恢复。

## 采纳的关键设计决策

1. 前端 runId 持久化到 `task_active_run`（复用 `@/lib/storage`），onMounted 读回后调 `getPipelineRun` 恢复 steps/progress 并续轮询。
2. 终态（completed/failed）在轮询回调识别，清除 `task_active_run`，避免任务完成后重进仍显示旧进度。
3. 后端各步 update_step 的 step_results 补全 files/results 数组（scan/query/download/normalize/archive），使前端详情卡片可重建。
4. tasks.py get_pipeline_run 将 step_results 由 JSON 字符串改为 `json.loads` 返回对象，对齐前端 `Record<string, unknown>` 类型。
5. 前端恢复函数对旧数据做防御：step_results 可能为字符串或缺失字段，解析失败/缺失时回退空值不报错。

## 识别到的风险点及与现有架构的冲突

1. step_results 为按步骤嵌套结构（`{"scan": {...}, "query": {...}}`），前端恢复需按步骤名映射回 ref 结构。
2. 体积风险：query/download 的 results 数组可能较大，单次轮询响应可能超 50KB（软约束，SQLite TEXT 可承载）。
3. 历史已完成任务 step_results 缺新字段，前端需防御性兜底（`|| 0` / `|| []`）。
4. 终态清理时序：runPipeline finally 有 5 秒延迟 stopPolling，清理须放在轮询回调的终态分支而非 finally，确保可靠。

## 验证方式

- 后端 pytest：新增/扩展测试验证 step_results 含 files/results、get_pipeline_run 返回 dict。
- 前端 `npm run test`：新增测试验证恢复逻辑（有 runId 恢复轮询、无 runId 不请求、终态清除、缺失字段不报错）。
- 手动：执行任务→退出→重进，进度条+步骤状态+详情卡片恢复；完成后重进不再显示旧进度。
