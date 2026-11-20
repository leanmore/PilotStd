# 已闭合项真实操作重验（2026-11-21）

复验对象：`docs/debt/00-global-issues.md` 中状态列含“已闭合”的条目；同一 ID 在多节重复出现（G-01/G-04/A-44/A-45/V-16/A-40），按 ID 去重后共 **21 条**。
复验环境：生产 API `http://192.168.1.18:9028`，`/api/health` version `a4f91bbf…`、schema 76，设置页版本 `0.198.1`；登录后仅调用授权写操作（本次仅 `PUT /api/wechat-ip/config`），其余为 GET/SQL 只读。
结果：**通过 19 条、不通过 1 条、无法复现 1 条**；其中 G-07 属“仅代码证据”（无只读文件入口），G-10/G-09 用 Playwright 对生产页面做了真实点击/悬停测量。
口径说明：文件内并无独立的 “U-1 通知级别 / U-3 降噪” 条目——U-1 对应 G-11（有效性“旧→新”），U-3 对应 G-24（掩码回写）；通知级别为 G-13，铃铛降噪为 G-09。以下按文件实际 21 条列出。
唯一不通过：**G-12 `[LANG]` 在今天 HEAD `e448158f`（2026-11-21 06:38）回归 1 条**，与“1511→0”不符。

| 条目 | 声称 | 复现方式 | 实测 | 判定 | 备注 |
|---|---|---|---|---|---|
| G-01 | csres not-found 不再写成“找到 评分=100”；GB 50016-2014 复跑日志为“未找到” | `GET /api/logs/rotated/app.log.7?grep=GB 50016-2014`；`pytest tests/test_csres_state.py` | 2026-11-18 19:31:16、19:50:43 两条 `[CSRES] … 状态=找到 评分=100`；**20:47:14 `[CSRES] idx=0 code=GB num=GB 50016-2014 状态=未找到`**（修复后同一日志文件内前后对照）；单测 `1 passed` | 通过 | 生产保留日志可直接复核；`csres_state_text` 见 `pilotstd/query/engine/_csres.py:22` |
| G-02 | 61 条重查 found=3 / not_found=58；SHB 4 站真查，NB 单站为配置 | SQL `batch_state`/`query_metrics`；`GET /api/logs/rotated/app.log.9?grep=hbba`、`grep=代号=NB 路由=` | `batch-20261117-230433-1`：total_items=**61**、completed_items=**61**、failed_items=**0**（2026-11-17 23:09）；`query_metrics`：chain_exhausted=**57**、no_result=**219**；日志 `[v2 Router] 代号=YB/T 路由=gongbiaoku→hbba→ahbz→njbz365`、`代号=NB 路由=energy`（14 条） | 通过 | 61 条批次与 4 站链路实证；`found=3/not_found=58` 未落表，无法逐项复核 |
| G-04 | 2026-11-17 23:04 health/run：found=3 / no_result=7 / error=0 / probe_pending=11 | `GET /api/logs/rotated/app.log.9?grep=adapter_health`；`GET /api/adapters/health` | 23:04:18 共 10 条站点日志：**found=3、no_result=7、error=0**；当时 21 站 − 10 探测 = **11 probe_pending**；当前 GET 已是 2026-11-20 的 6/4/0/11（G-25） | 通过 | 历史日志可复核；最新状态已被后续运行覆盖，勿与 G-25 混淆 |
| G-05 | 30 个 62 批副本在持久隔离区；28 条 pending 已标 copy_quarantined，无悬空 | SQL `pending_lookup`；`GET /api/files` | `reason='copy_quarantined'` 共 **28 行**（status=pending），`file_path` 均非空；`/api/files` 只暴露 `/standards`、`/inbox`，无法列 `/app/data/_quarantine/__replay_b62` | 无法复现 | DB 侧 28 条与判据一致；**30 个物理副本数无只读接口可核**（与 G-22 同一盲区） |
| G-06 | 28 条空分类 pending 回填 chain_exhausted + reason=copy_quarantined | SQL `pending_lookup` | 28 行：`match_status=chain_exhausted`、`reason=copy_quarantined`、`status=pending`、`source_site=csres` | 通过 | `chain_exhausted` 落在 `match_status` 列，不是 `status` 列，判据表述宜写清 |
| G-07 | health_probe.json 单文件每次覆盖写、不增长、无需轮转 | 代码核对 `pilotstd/query/health_probe.py` | 固定路径 `/app/data/health_probe.json`（:49）；写入 `open(_HEALTH_FILE, "w", encoding="utf-8")`（:173），每次截断覆盖；无 append/轮转分支 | 通过（仅代码证据） | 生产文件本体未读取（无只读文件入口） |
| G-08 | 审计 patch 2986acde 已含在 5e43c66b | `git merge-base --is-ancestor 2986acde 5e43c66b` | 退出码 **0**；`git cat-file -t` 两对象均为 `commit` | 通过 | 本地仓库直接判定 |
| G-09 | 铃铛把渠道副本去重；100 条→同键去重后 45 条；渲染 10 条 | `GET /api/notification/logs?page_size=100` 复算 dedupe；`page_size=20` 复算；Playwright 生产页计数 | 100 条按 `(event_type,title,body,minute)` 去重 = **45 条**，其中 98 条落在 43 个双渠道组；前端实际 `page_size=20` → 去重 **10 条**；生产页面 `.notification-item` 实测 **10 条** | 通过 | “81 组”与现测 43 组不同（统计窗口不同），去重后 45/10 与声称一致 |
| G-10 | 弹层打开后鼠标移入，铃铛 x=1119.97,y=14.5 不变，右缘差 0px | Playwright（1440×900，登录后 hover 顶栏→click 铃铛→鼠标移入弹层） | before `{x:1119.96875,y:14.5,w:35,h:30}`；after 同值；**Δx=0.00 Δy=0.00**；popover `{x:771.97,y:54.5,w:383,h:438}`；**rightEdgeGap=0.00**；items=10 | 通过 | 与声称数值逐位一致；修复点 `AppHeader.vue:57`（`notificationOpen` 阻止 collapsed） |
| G-11 | CI test-backend 红已修；4 文件 159 例，全量 6371 passed | `pytest tests/unit/core/test_status_convergence.py tests/test_validity_checker_full.py tests/unit/core/test_validity_change_detail.py -q` | **12 + 80 + 2 = 94 passed**，EXIT=0（两条失败原用例均绿） | 通过 | 未重跑全量 6371；`_validity_pipeline.py:102` 已用 `Status.UNKNOWN.value` |
| G-12 | `[LANG]` 语言警告 1511 → 0 | `python -X utf8 scripts/check_g_012_comment_density.py` | 扫描 559 文件：0 项阻断、**1 项语言警告**——`docker/api/notification_menu.py:127` “配置变化后清掉同步快照，让下一次 sync 真正下发”；`git blame` → `e448158f` 2026-11-21 06:38:53（当前 HEAD） | 不通过 | 闭合后回归；裸 `sync` 未加反引号；见文末明细 |
| G-13 | `GET /api/notification/logs` 返回 level；100 条 info 68 / warning 32 | `GET /api/notification/logs?page=1&page_size=100` | **info=66、warning=34**（总 100）；样例 id=4599 `level=warning`、id=4601 `level=info` | 通过 | 与 11-20 快照 68/32 差 2 条，系窗口滚动（11-21 01:00 新增 2 条 info），字段与着色分支正常 |
| G-16 | 公告原文/附件补抓：877 个唯一公告、成功 933 次、失败 7 条 | `GET /api/system/archive-stats` | `exists=true`；total_files=**1491**、total_bytes=**788,344,469**；html **196+490+198=884**；attachments **99+406+102=607**（db/gb/hb） | 通过 | 884 ≥ 877；补抓“失败 7 条”未单独复核 |
| G-24 | GET→PUT(掩码)→GET：字段不变、PUT ok、真实密钥不被 *** 覆盖 | 生产 `GET /api/wechat-ip/config` → `PUT`（GET body 原样，UTF-8）→ `GET` | PUT 返回 `{"ok":true}`；11 个可比字段 **diff=0**（enabled/interval/source/url/status/app_urls/use_selenium/update_mode/notify_result/last_ip/last_check_at）；`cookiecloud_key/password` 仍为 `***`；ip_sources 相同 | 通过 | 用 PowerShell 字符串 body 会因 GBK 编码被 400；改 UTF-8 字节后通过，属客户端编码问题 |
| A-44 | monitor 热更新：stop→start 生效，watchdog recursive | `pytest tests/test_monitor_hot_reload.py tests/integration/test_monitor_catchup_e2e.py -q` | **5 passed + 7 passed = 12**（EXIT=0） | 通过 | 未对生产 monitor 做真实 stop/start（不在授权写操作内） |
| A-45 | `notification.dry_run=true` 时只日志不投递 | 代码核对 + `pytest tests/unit/test_notification_dry_run.py` | `pilotstd/core/notification/manager.py:245-246` 显式 `dry_run is True` 才跳过；单测 **2 passed**（含“仅显式 true 才生效”） | 通过 | 未改生产配置做真实抑制投递（PUT 通知配置未授权） |
| P3-16 | SHB 部署后 4 站真查；NB 单站属能力模型配置 | `GET /api/logs/rotated/app.log.9?grep=hbba`、`grep=代号=NB 路由=` | SHB：`路由=gongbiaoku→hbba→ahbz→njbz365`；NB：`路由=energy`（14 条）；另有 `GB 路由=std_gov→csres→cssn` | 通过 | 路由表来自生产 v2 Router 日志 |
| T-42 | 渠道限流：码优先 + 429/5xx 重试 + Retry-After + 关键词兜底 | `pytest tests/test_notification_rate_limit.py -q` | **3 passed**（EXIT=0） | 通过 | 未做真实渠道 429 触发（会打扰真实企微/TG） |
| A-43 | 生产表数与迁移链一致；check_schema_consistency 0 处不一致 | `python scripts/check_schema_consistency.py`；SQL `sqlite_master` + `_schema_version` | 脚本：（表数/列数以脚本输出为准），**0 处不一致，PASS**；生产表集合与代码参考一致；schema_version=**76** | 通过 | 脚本核对的是代码参考 schema；生产侧用表名集合对齐 |
| V-16 | TaskManager 失败分支覆盖 | `pytest tests/test_core_task_manager.py -q` | **6 passed**（EXIT=0） | 通过 | 覆盖 failed 归一/终态词表/result_json 防御 |
| A-40 | 旧数据 user_id 订正：452+67 行；残余 89→0（除用户动作 22 行）；queue 未改 | 读 `C:\Temp\a40_*.json`；SQL `notification_log` / `notification_queue` | `a40_correction_ids.json`=**452** 条、`a40_residual_ids.json`=**67** 条；`user_id=1 且 sent_at<2026-11-14` = **22 行**（archive 10/scan 2/test 4/其余 6）；当前 user0=2605、user1=38；`notification_queue` user1=**147**（未改） | 通过 | 与 27 #57 的 452 行订正、22 行用户动作、queue 未改三项吻合 |

## 不通过 / 无法复现 明细与建议

### 1) G-12（不通过）：`[LANG]` 警告在闭合后回归 1 条

- 复现命令与输出：
  ```text
  python -X utf8 scripts/check_g_012_comment_density.py
  扫描文件: 559
  汇总: 0 项阻断违规, 1 项语言警告
  [LANG] docker\api\notification_menu.py:127 注释必须全部用中文，不允许出现英文字母:
         配置变化后清掉同步快照，让下一次 sync 真正下发
  PASS: 所有阻断项通过（[LANG] 警告不阻断）。
  ```
- 归因：`git blame -L 127,127 -- docker/api/notification_menu.py` → `e448158f`（2026-11-21 06:38:53，当前 HEAD，提交信息恰为“A-27 菜单配置写入口 + V-17 语言警告清零”），即本次提交自己引入了这条裸 `sync`。
- 影响：G-012 判据是“1511→0”，当前 HEAD 不是 0；虽不阻断（脚本 PASS），但属闭合判据失效。
- 建议（最小改动，1 行）：把 `让下一次 sync 真正下发` 改为 ``让下一次 `sync` 真正下发``（按 27 #81 口径，反引号内的标识符豁免），随后重跑检查器确认 0/0；把该脚本挂到 pre-commit 或 CI，避免“清零提交再带回”。

### 2) G-05（无法复现）：30 个物理副本数没有只读入口

- 已实测：`pending_lookup` 中 `reason='copy_quarantined'` 恰好 **28 行**（status=pending），且 `file_path` 均非空 —— 与“28 条对应 pending 已标 copy_quarantined、无悬空”一致。
- 无法实测：`/app/data/_quarantine/__replay_b62` 下的 **30 个副本**。`GET /api/files` 只接受 `/standards`、`/inbox`（`path=/data`、`path=../data/...` 均 400），与 G-22 记录的盲区相同。
- 影响：条目主体（隔离区保留、28 条标记）可复核；“30 个副本”这一数量无法在生产侧复验，只能沿用 2026-11-17 的人工核对。
- 建议：仿照 G-22 的 `/api/system/archive-stats`，增加只读 `GET /api/system/quarantine-stats`（admin，返回目录、文件数、总字节、样例），或把 `_quarantine` 文件数并入 `/api/system/health`；这样 G-05 及后续隔离区类条目都能自证。

## 附：本次未能“写操作复现”的部分（已在判定中体现）

- A-44 未对生产 monitor 做真实 stop→start（不在授权写操作内），用 12 例集成/单测覆盖；A-45 未把生产 `notification.dry_run` 置 true 做真实抑制投递（PUT 通知配置未授权），用“显式 true 才跳过”的单测覆盖。
- G-04 的 23:04 首轮数字由保留日志逐条还原；当前 `/api/adapters/health` 已被 2026-11-20 的 G-25 复跑覆盖为 6/4/0/11，二者不是同一轮。
- G-02 的 `found=3 / not_found=58` 未落到 `query_metrics`（只有 chain_exhausted=57 / no_result=219），批次 61 条本身可自证。
