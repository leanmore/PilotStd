# 全局问题总表（唯一问题基线）

> 维护规则：每批收口只改状态/增删条目，不重列全表；状态仅三种：待做 / 等触发 / 已闭合。
> 闭合判据必须可复核（测试、数据核对、日志行、部署确认）。

## 一、本轮新产生（2026-11-17 批）

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| G-01 | csres 日志把 not-found 写成“找到 评分=100” | 已闭合 | 2026-11-18 v0.195.2 复跑 GB 50016-2014：日志 状态=未找到、stats.found=0、结果行 未找到匹配结果；csres_state_text + 	est_csres_state.py 锁定 |
| G-02 | 61 条重查可信度 | 已闭合 | 2026-11-17 23:04 低峰重跑（298s）：found=3、not_found=58；SHB 日志 	ried=gongbiaoku→hbba→ahbz→njbz365（4 站真查），NB 单站为能力模型配置 |
| G-03 | 健康检查探针 11 站 `probe_pending` | 等触发 | 触发：对应站点出现 `exact` 缓存；判据：自动纳入并输出 found/no_result |
| G-04 | 健康检查生产首轮 | 已闭合 | 2026-11-17 23:04 POST /api/adapters/health/run：found=3/no_result=7/error=0/probe_pending=11；日志 dapter_health site=... 可见 |
| G-05 | 30 个 62 批副本（/app/data/_quarantine/__replay_b62） | 已闭合 | 均为 standards 副本；保留隔离区（持久卷、不监控）；28 条对应 pending 已标 copy_quarantined，无悬空 |
| G-06 | 28 条空分类 pending 回填 | 已闭合 | 已回填 `chain_exhausted` + `reason=copy_quarantined`；manifest/rollback 见 `C:\Temp\pending28_*` |
| G-07 | `health_probe.json` 轮转/上限 | 已闭合 | 单文件每次覆盖写，不增长；无需轮转（2026-11-17 确认） |
| G-08 | v0.192.1 审计 patch 是否含在 v0.194.1 | 已闭合 | `git merge-base --is-ancestor 2986acde 5e43c66b` 通过 |
| G-09 | Web 通知铃铛把渠道副本当独立消息（同一收藏成功出现 2 条） | 已修（待部署 v0.195.3） | 根因：`notification_log` 按渠道各一行（wechat/telegram），铃铛直接渲染；已在前端 `dedupeMessages` 按 `(event_type,title,body,分钟)` 去重（未读优先），日志页仍保留渠道行；`useNotification.test` 全绿（367 例） |
| G-10 | Web 铃铛“标记已读”后弹层偏到页面左侧 | 已修（待部署 v0.195.3） | 根因：标记后 badge/按钮状态变化，PrimeVue Popover 未按新坐标重排；已加 `nextTick` + `alignOverlay()`，`NotificationBell.test` 断言调用；08 #18 同步 |

## 二、之前悬着未闭合

| ID | 事项 | 状态 | 判据/触发 |
|---|---|---|---|
| A-44 | monitor 实时：新目录半残，必须 restart | 等触发 | 触发：有人依赖实时触发或换 PollingObserver；规则已写入 08 + 用户帮助 |
| A-45 | 无 dry-run/站内通知渠道 | 等触发 | 触发：新增渠道系统或 AC-6 复验触发链路 |
| A-46 | 33 个 file_missing 文件重取 | 等触发 | 触发：公告记录/下载链可重取；取到后归档并核销 |
| P3-16 多站链 | NB 单站为能力模型配置；SHB 部署后 4 站真查 | 已闭合 | 2026-11-17 61 重查日志 SHB tried=gongbiaoku→hbba→ahbz→njbz365；NB energy→energy 属配置 |
| P2-08 | Organize/Pending 失败/恢复分支 | 已闭合 | 既有测试覆盖（见 27 #63）；后续为覆盖率棘轮 |
| A-40 | 旧数据 user_id 归属 | 已闭合（部分记录） | 452+67 行订正；残余 89→0（除用户动作 22 行）；queue 未改 |

## 三、定触发

| ID | 事项 | 触发 |
|---|---|---|
| A-44 | 实时缺陷修复 | 依赖实时/换 PollingObserver |
| A-45 | dry-run 渠道 | 新增渠道或 AC-6 复验触发 |
| V-16 / V-17 / A-5 / A-32 / T-42 / A-43 | 见 03-open | 各自触发（改 TaskManager、G-012 第 3 次红、脚手架频繁、升级 cookiecutter、官方限流码、表数质疑） |
| P2-08 转阻断 | diff coverage 1~2 个月数据后 |

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
| T-42 | 渠道限流未逐家实现 | 等触发 | 触发：取到官方限流码或限流实际发生 |
| A-22 | Windows 15 个共享事件托盘验收 | 等触发 | 触发：Windows 实机有人使用 |
| A-27 | 自定义菜单（企微/飞书/TG/钉钉） | 等触发 | 触发：菜单需求排期 |
| A-43 | SQLite 表数机械核对 | 等触发 | 触发：表数被质疑或动迁移链 |
| A-40 | 旧数据归属 | 已闭合（部分记录） | 452+67 行订正；queue 例外；残余 0 |
| D-2/D-3 | 通知阶段 2 启动 / 主题判定观察 | 等触发 | 触发：业务排期/设计改进 |
| V-16/V-17/A-5/A-32/P2-08 | 见 04-watch | 等触发 | 各条触发条件 |
