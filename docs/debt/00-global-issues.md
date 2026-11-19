# 全局问题总表（唯一问题基线）

> 维护规则：每批收口只改状态/增删条目，不重列全表；状态仅三种：待做 / 等触发 / 已闭合。
> 闭合判据必须可复核（测试、数据核对、日志行、部署确认）。
> **用户可感知项（UI 定位/渲染、通知内容、行为结果）必须真实操作复验通过；“仅测试断言”只能标“已修复（待真实验证）”。**

## 一、本轮新产生（2026-11-17 批）

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| G-01 | csres 日志把 not-found 写成“找到 评分=100” | 已闭合 | 2026-11-18 v0.195.2 复跑 GB 50016-2014：日志 状态=未找到、stats.found=0、结果行 未找到匹配结果；csres_state_text + 	est_csres_state.py 锁定 |
| G-02 | 61 条重查可信度 | 已闭合 | 2026-11-17 23:04 低峰重跑（298s）：found=3、not_found=58；SHB 日志 	ried=gongbiaoku→hbba→ahbz→njbz365（4 站真查），NB 单站为能力模型配置 |
| G-03 | 健康检查探针 11 站 probe_pending | 已修复（自动发现，待部署） | 每次运行前从 standard_info_cache 的 exact 记录补齐探针；剩余无缓存站点仍标 probe_pending；单测 	est_discover_probes_fills_pending |
| G-04 | 健康检查生产首轮 | 已闭合 | 2026-11-17 23:04 POST /api/adapters/health/run：found=3/no_result=7/error=0/probe_pending=11；日志 dapter_health site=... 可见 |
| G-05 | 30 个 62 批副本（/app/data/_quarantine/__replay_b62） | 已闭合 | 均为 standards 副本；保留隔离区（持久卷、不监控）；28 条对应 pending 已标 copy_quarantined，无悬空 |
| G-06 | 28 条空分类 pending 回填 | 已闭合 | 已回填 `chain_exhausted` + `reason=copy_quarantined`；manifest/rollback 见 `C:\Temp\pending28_*` |
| G-07 | `health_probe.json` 轮转/上限 | 已闭合 | 单文件每次覆盖写，不增长；无需轮转（2026-11-17 确认） |
| G-08 | v0.192.1 审计 patch 是否含在 v0.194.1 | 已闭合 | `git merge-base --is-ancestor 2986acde 5e43c66b` 通过 |
| G-09 | Web 通知铃铛把渠道副本当独立消息 | 已修复（真实 UI 验证通过；生产待部署复验） | Playwright（dev 构建 + 生产 API）2 条渠道行 → 铃铛只显示 1 条；`useNotification` 按内容+分钟去重 |
| G-10 | Web 铃铛“标记已读”后弹层偏左 | 已修复（真实 UI 验证通过；生产待部署复验） | 根因非“未重排”，而是 `topbar-right v-show=isHovered` 在鼠标移入弹层后隐藏铃铛，锚点变 0；已让 Popover 打开期间保持顶栏显示；Playwright 实测点击前后 delta 8px（弹层右缘距铃铛右缘 3.5px） |
| G-11 | CI `test-backend` 红（状态字面量守卫 + 过期断言） | 已闭合 | `_validity_pipeline.py:102` 用裸 `'未知'` 字面量、`test_status_changed` 未随 `4003372e` 同步 reason 契约；改为 `Status.UNKNOWN.value` + 新断言；受影响 4 文件 159 例、全量 6371 passed（CI 等价命令 EXIT=0）；见 `27` #80 |

## 二、之前悬着未闭合

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| A-44 | monitor 实时：新目录半残，必须 restart | 已闭合 | 2026-11-19 	ests/test_monitor_hot_reload.py 5 例（PUT stop→start）+ 	ests/integration/test_monitor_catchup_e2e.py 7 例通过；watchdog recursive 覆盖子目录 |
| A-45 | 无 dry-run/站内通知渠道 | 已闭合（dry-run） | `notification.dry_run=true` 时 `send_event` 只日志不投递；`test_notification_dry_run.py`；站内渠道仍属新增功能，不在本条范围 |
| A-46 | 33 个 file_missing 文件重取 | 等触发 | 触发：公告记录/下载链可重取；取到后归档并核销 |
| P3-16 多站链 | NB 单站为能力模型配置；SHB 部署后 4 站真查 | 已闭合 | 2026-11-17 61 重查日志 SHB tried=gongbiaoku→hbba→ahbz→njbz365；NB energy→energy 属配置 |
| P2-08 | diff coverage 转阻断 | 等触发（数据不足，继续收集） | 全仓无 diff-cover 工具/历史数据，仅 PR 模板说明“只报告”；待积累 1~2 个月数据再定阈值 |
| A-40 | 旧数据 user_id 归属 | 已闭合（部分记录） | 452+67 行订正；残余 89→0（除用户动作 22 行）；queue 未改 |

## 三、定触发

| ID | 事项 | 触发 |
|---|---|---|
| A-44 | monitor 实时：新目录半残，必须 restart | 已闭合 | 2026-11-19 	ests/test_monitor_hot_reload.py 5 例（PUT stop→start）+ 	ests/integration/test_monitor_catchup_e2e.py 7 例通过；watchdog recursive 覆盖子目录 |
| A-45 | 无 dry-run/站内通知渠道 | 已闭合（dry-run） | `notification.dry_run=true` 时 `send_event` 只日志不投递；`test_notification_dry_run.py`；站内渠道仍属新增功能，不在本条范围 |
| V-16 | TaskManager 失败分支覆盖 | 已闭合 | 	ests/test_core_task_manager.py：
ailed 归一（3）、终态词表 completed/cancelled/failed、result_json 防御、两种 result 形状均覆盖；TaskManager 为只读门面，执行失败落库在任务运行时 |
| P2-08 | diff coverage 转阻断 | 等触发（数据不足，继续收集） | 全仓无 diff-cover 工具/历史数据，仅 PR 模板说明“只报告”；待积累 1~2 个月数据再定阈值 |

## 四、明确不做

| ID | 事项 | 理由 |
|---|---|---|
| FK×4 | `favorite_downloads`/`user_favorites` → `announcement_record` 4 条既有违规 | 与当前功能无关、无用户反馈；文档“已知不修” |

## 五、等外部条件

| ID | 事项 | 条件 |
|---|---|---|
| G-04 | 健康检查生产首轮 | 已闭合 | 2026-11-17 23:04 POST /api/adapters/health/run：found=3/no_result=7/error=0/probe_pending=11；日志 dapter_health site=... 可见 |
| G-01 | csres 日志把 not-found 写成“找到 评分=100” | 已闭合 | 2026-11-18 v0.195.2 复跑 GB 50016-2014：日志 状态=未找到、stats.found=0、结果行 未找到匹配结果；csres_state_text + 	est_csres_state.py 锁定 |
| AC-6 触发链路 | 真实触发验证 | 需第二真实 admin 或 dry-run 渠道 |

## 六、已闭合（累计）

- M1（11 项）、M2（A-40 订正 + P2 双用户隔离）、M3（AC-6 读隔离、quarantine 路径、62 批演练、A1/A2/A3/B）；
- 62 批缩小版（10 目录/202 文件）；825 不做；
- 33 文件扫 API 可见根 0 命中（`/inbox`、`/standards`）；30 副本留隔离区；
- user5 2 条通知、a35_user2（测试账号）已清理。


## 七、从 03-open/04-watch 映射的未闭合项（2026-11-17 梳理）

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| T-40 | V6 wechat 真发未取证 | 等触发 | 触发：需要取证真实企微发送 |
| T-42 | 渠道限流未逐家实现 | 已闭合 | channels/base.py 已实现：码优先（wechat 45009、feishu 99991400）、429/5xx 重试、Retry-After、关键词兜底；	ests/test_notification_rate_limit.py 3 例通过 |
| A-22 | Windows 15 个共享事件托盘验收 | 等触发 | 触发：Windows 实机有人使用 |
| A-27 | 自定义菜单（企微/飞书/TG/钉钉） | 等触发 | 触发：菜单需求排期 |
| A-43 | SQLite 表数机械核对 | 已闭合 | 2026-11-19 生产表数与迁移链一致；check_schema_consistency.py 汇总 0 处不一致，文档未声明固定表数 |
| A-40 | 旧数据归属 | 已闭合（部分记录） | 452+67 行订正；queue 例外；残余 0 |
| D-2/D-3 | 通知阶段 2 启动 / 主题判定观察 | 等触发 | 触发：业务排期/设计改进 |
| V-16 | TaskManager 失败分支覆盖 | 已闭合 | 	ests/test_core_task_manager.py：
ailed 归一（3）、终态词表 completed/cancelled/failed、result_json 防御、两种 result 形状均覆盖；TaskManager 为只读门面，执行失败落库在任务运行时 |
