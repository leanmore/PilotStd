# ADR-013: 健康检查与业务任务解耦轮询机制

> 日期：2026-08-21（决策于 2026-08-15 会话 F145）
> 状态：✅ Accepted（已实施，commit `1b2c2a1f`）
> 来源：A4 会话转录提炼（`~/.claude/projects/d--PilotStd/` F145）
> 关联：[[ADR-012]]

---

## 背景

两类适配器（查询适配器 / 公告抓取适配器）没有单独的健康检查自动轮询机制，状态数据完全依赖业务操作触发更新——"查询适配器卡片状态永远显示正常"的回归 Bug 暴露了该架构缺陷。同时 `adapter_state` 表使用 `INSERT OR REPLACE` 写入，存在适配器名称重叠时互相清零的隐患。

## 决策

1. **健康检查（探活）与业务任务（查询/抓取）彻底分离**：新建 `docker/health_check_service.py`，注册 `auto_health_check` 定时任务（cron 每小时）；探活为非侵入式 HTTP GET（首页或 ping 端点，超时 10s），严禁触发完整业务查询或公告抓取流程、不消耗目标站点配额。
2. **状态写入改 UPSERT**：`adapter_state` 从 `INSERT OR REPLACE` 改为 `INSERT ... ON CONFLICT(adapter_name) DO UPDATE SET ...`，每个写入方只更新自己负责的字段组（rotator 更新查询侧、circuit_breaker 更新公告侧）。
3. **health_status 默认值用 NULL**（表示"从未检查过"），不用 'unknown'，减少状态枚举处理复杂度。
4. **v51 迁移**独立文件（遵循 v50 拆分的 G-010 合规先例）。

## 核心约束

- 探活必须复用 `adapter_manager.get_adapter_status(name)`（读 rotator 内存态），不能直接读表——表里的 `cooldown_until` 在冷却退出时不回写，直接读表字段会让卡片卡在"冷却中"
- 公告三站探活 URL 从共用首页改为各自实际列表端点（nocGBPage/nocHBPage/nocDBPage）——首页探活无法反映搜索端点真实可用性
- 新增配置项必须同步三处：settings_schema.py 定义、get_settings() 返回、put_settings 调度同步

## 实施证据

- `docker/health_check_service.py`（存在）
- commit `1b2c2a1f`（19 文件 +429 行：v51 迁移两列 + 服务 + 调度 + API 新字段 + 前端 1h 轮询 + cooldown 橙点）
- 相关修复：`518e5b06`（API 字段错位）、`df182a3d`（UPSERT 改造）、`317f6975`（CircuitBreaker key 改 standard_type + 三站探活 URL 各归其端点）
