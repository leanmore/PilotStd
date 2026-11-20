# 全局问题总表（唯一问题基线）

> 维护规则：每批收口只改状态/增删条目，不重列全表；状态仅三种：待做 / 等触发 / 已闭合。
> 闭合判据必须可复核（测试、数据核对、日志行、部署确认）。
> **用户可感知项（UI 定位/渲染、通知内容、行为结果）必须真实操作复验通过；“仅测试断言”只能标“已修复（待真实验证）”。**

## 一、本轮新产生（2026-11-17 批）

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| G-01 | csres 日志把 not-found 写成“找到 评分=100” | 已闭合 | 2026-11-18 v0.195.2 复跑 GB 50016-2014：日志 状态=未找到、stats.found=0、结果行 未找到匹配结果；csres_state_text + 	est_csres_state.py 锁定 |
| G-02 | 61 条重查可信度 | 已闭合 | 2026-11-17 23:04 低峰重跑（298s）：found=3、not_found=58；SHB 日志 	ried=gongbiaoku→hbba→ahbz→njbz365（4 站真查），NB 单站为能力模型配置 |
| G-03 | 健康检查探针 11 站 probe_pending | 已修复（已随 v0.196.1 部署，待生产复跑） | 每次运行前从 standard_info_cache 的 exact 记录补齐探针；剩余无缓存站点仍标 probe_pending；单测 	est_discover_probes_fills_pending |
| G-04 | 健康检查生产首轮 | 已闭合 | 2026-11-17 23:04 POST /api/adapters/health/run：found=3/no_result=7/error=0/probe_pending=11；日志 dapter_health site=... 可见 |
| G-05 | 30 个 62 批副本（/app/data/_quarantine/__replay_b62） | 已闭合 | 均为 standards 副本；保留隔离区（持久卷、不监控）；28 条对应 pending 已标 copy_quarantined，无悬空 |
| G-06 | 28 条空分类 pending 回填 | 已闭合 | 已回填 `chain_exhausted` + `reason=copy_quarantined`；manifest/rollback 见 `C:\Temp\pending28_*` |
| G-07 | `health_probe.json` 轮转/上限 | 已闭合 | 单文件每次覆盖写，不增长；无需轮转（2026-11-17 确认） |
| G-08 | v0.192.1 审计 patch 是否含在 v0.194.1 | 已闭合 | `git merge-base --is-ancestor 2986acde 5e43c66b` 通过 |
| G-09 | Web 通知铃铛把渠道副本当独立消息 | 已闭合 | 2026-11-20 生产 v0.196.3 端到端：接口精确 `sent_at` 统计 100 条→同分钟双渠道重复 81 组→去重后 45 条；铃铛实际渲染 10 条，与“接口按同键去重后的前 10”逐条一致（10/10） |
| G-10 | Web 铃铛“标记已读”后弹层偏左 | 已闭合 | 2026-11-20 生产 v0.196.3 Playwright：鼠标移入弹层（原触发路径）后铃铛盒与打开前完全一致（x=1119.97,y=14.5），弹层右缘与铃铛右缘差 **0px**，无左跳；`bee0add4` 另修掉 `.topbar.collapsed` 在弹层打开时仍收缩造成的 8/10px 位移 |
| G-11 | CI `test-backend` 红（状态字面量守卫 + 过期断言） | 已闭合 | `_validity_pipeline.py:102` 用裸 `'未知'` 字面量、`test_status_changed` 未随 `4003372e` 同步 reason 契约；改为 `Status.UNKNOWN.value` + 新断言；受影响 4 文件 159 例、全量 6371 passed（CI 等价命令 EXIT=0）；见 `27` #80 |
| G-12 | G-012 `[LANG]` 注释语言警告 1511 条长期挂着 | 已闭合 | 规则改按词判定（工具指令/反引号/文件名/代码标识符豁免）1511→504，504 行分 6 批改写（叙事词译中文、裸标识符加反引号）→0；200 个改动 `.py` 做 AST 归一化比对，除检查器外 198 个文件 AST 完全一致；见 `27` #81、`gates.md` v2.55 |
| G-13 | 通知日志 `level` 假闭合（铃铛告警着色不生效） | 已闭合 | `NotificationLogItem` 漏声明 `level`，FastAPI 按 response_model 过滤；修复 `d9a29db1` 后**生产 v0.196.3 实证**：`GET /api/notification/logs` 返回 level，100 条 info 68 / warning 32；见 `27` #83 |
| G-14 | 配置多实例整文件覆盖写（IP 失败重复通知根因） | 已修复（待部署） | `save()` 写整份快照，长任务收尾覆盖他方键；新增 `update()/update_many()` 并改造 `docker/scheduler`、`_validity_pipeline._finalize_validity_round`；`test_manager_update.py` 4 例；AST 扫描确认“同函数构造+save”仅 1 处（毫秒级）、保存入参的 7 处中跨长任务的 `wechat_ip/scheduler.run_check` 也已改造，同类风险收口；见 `27` #86 |

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
| R-3 U-1/U-3 | 有效性“旧 → 新”与 U-3 保存链路真实操作复验 | 需生产写窗口（跑一次时效检查 / 保存一次 CookieCloud 配置） |
| superseded_by 迁移 | 49,306 行方向纠正 | 需授权 + 备份 + 维护窗口，方案见 `docs/analysis/superseded-by-migration-plan.md` |

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
| A-27 | 自定义菜单（企微/飞书/TG/钉钉） | 等触发 | **代码已落地** `8dc5393a`（v0.196.1 起在线）：企微/飞书 create+delete 真实接口、Telegram setMyCommands、钉钉显式 `unsupported`；21 例单测。剩余触发条件改为：各平台后台权限下的真实联调 |
| A-43 | SQLite 表数机械核对 | 已闭合 | 2026-11-19 生产表数与迁移链一致；check_schema_consistency.py 汇总 0 处不一致，文档未声明固定表数 |
| A-40 | 旧数据归属 | 已闭合（部分记录） | 452+67 行订正；queue 例外；残余 0 |
| D-2/D-3 | 通知阶段 2 启动 / 主题判定观察 | 等触发 | **D-3 已落地**：`topic_of()` 事件键优先、关键词兜底，`tests/test_notification_topic_event_first.py` 3 例锁定；D-2 仍等业务排期 |
| V-16 | TaskManager 失败分支覆盖 | 已闭合 | 	ests/test_core_task_manager.py：
ailed 归一（3）、终态词表 completed/cancelled/failed、result_json 防御、两种 result 形状均覆盖；TaskManager 为只读门面，执行失败落库在任务运行时 |
