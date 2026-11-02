# “等回家”验证清单（2026-10-31 建）

> 办公室：纯代码/文档/测试，`192.168.1.18` 不可达。
> 完成项标 ✅ + 证据，不清空、不删除。

| 项 | 做什么 | 需要条件 | 验收标准 | 办公室可做部分 |
|---|---|---|---|---|
| **A-6 429 基线** | 按渠道统计 total/failed/429 | 验证环境可达 | 输出各渠道占比与时间窗 | 统计脚本（本地库仅称“参考”） |
| **D-14 耗时分布** | P50/P90/P99 | A-30 部署 + API | 走 API 的 `task_context`，与用户所见同口径 | 取数 SQL/脚本 |
| **A-30 线上验证** | 部署最新版后验 `notify_event`、`task_context` 白名单、诊断端点仅 admin | 部署 | 三项接口实测 | 代码/测试已完成 |
| **阶段六 真隔离构建** | `192.168.1.18` 上 `docker build --build-arg APP_VERSION=$(git rev-parse --short HEAD)` + health | 验证机 | 构建成功 + health 版本匹配 | 本地干净 clone 已做（非真隔离） |
| **A-28 阶段二部署验证** | 设置页静音显示一致；`/test-event` 系统/用户关响应；`--rollback` 实跑 | 部署 | 三项人工/接口实测 | 代码+全量已完成 |
| **A-27 P1 真实验证** | 真实菜单点击报文、企微凭证、公网回调地址 | 企微后台 + 公网 | `EventKey/FromUserName/AgentID` 校准 | mock 测试/代码 |

## 2026-11-01 部署执行记录（A-21 3b-4 后）

> 顺序固定：备份 → 部署 `0788b09c` → version 变化 → v71 迁移验证 → A-30/A-28 → A-35 多用户隔离 → A-6/D-14 → 阶段六。
> 每项完成标 ✅ + 证据；v71 失败立即停：回滚备份、报现象，不重试不猜。

| # | 项 | 状态 | 证据 |
|---|---|---|---|
| 0 | 部署前备份 DB | ✅ | `pilotstd_manual_20261101_215239.bak`（264.45 MB，/api/backup/list） |
| 1 | 部署 `0788b09c`（/api/system/update 或 compose pull） | ✅ | 用户已在局域网更新；`/api/system/version` = **0.168.0 / v0.168.0**，`/api/health` build = `41143728`（2026-11-02 18:50） |
| 2 | `/api/health` / `/api/system/version` 版本变化 | ✅ | build `41143728`；version `0.168.0`（部署前 `0.156.0 / 12bcb0b2`） |
| 3 | **v71 首次真实迁移**（schema 70→71、user_id 回填、索引耗时、可回滚） | ✅ | `_schema_version` MAX=**71**；`notification_log.user_id`/`notification_queue.user_id` 存在；索引 `idx_nl_user_sent`、`idx_nq_user_status` 存在；回填 `notification_log` user1=568、user0=2，queue user1=26；启动重启 18:34:31 后服务正常 |
| 4 | A-30 线上验证（notify_event/task_context/诊断 admin） | ✅ | `GET /api/notification/logs?limit=1` 返回 `notify_event`/`task_context`；admin 访问 `/logs/2483/diagnostics` 200；user2 访问同端点 403 |
| 5 | A-28 阶段二验证（静音显示、test-event、rollback） | ⚠️ 部分 | `/api/notification/config` quiet_hours enabled=true 22:00-07:00 与设置页一致；user2 `/test-event` 返回 `ok=true`（但日志 `user_id=0`，见 A-35）；未执行 `--rollback`（会改静音配置，未获批） |
| 6 | A-35 多用户隔离（见下） | ⏳ 待新镜像 | 已修：`/test-event` 写 `user_id/delivery_user_id` 并按 `channels_for(user_id)` 校验；收藏通知增加 `manager.notification_mgr is None` 告警与 send_event 单测（commit `95e7ae68`）。已建 `a35_user2`（id=3），待部署后重跑收藏与日志验证 |
| 7 | A-6 429 基线（线上口径） | ✅ | `/api/notification/logs` 全量 SQL：telegram 399 total / 14 failed / 10 429（2.51%）；wechat 141 total / 141 failed / 0 429（已配置但 100% 失败，token tunnel，待查）；feishu 16/16/0、dingtalk 16/16/0（**未配置渠道，失败是预期**，不计入渠道健康度）。2026-11-02 18:58 取数 |
| 8 | D-14 耗时分布（A-30 后） | ⬜ | |
| 9 | 阶段六真隔离构建 + health | ⬜ | |

### A-35 部署验证项

- [ ] 两个用户各触发一次事件，`notification_log.user_id` 各归各；
- [ ] 投递各收各：user2 未绑定渠道 ⇒ 跳过，不发给 user1；
- [ ] 无串号：user2 日志不出现在 user1 普通视角；
- [ ] system 事件投递所有 admin，日志 `user_id=0`。


### A-6 渠道健康度口径（2026-11-02 修正）

- **已配置渠道**（wechat/telegram）才计入健康度；
- **未配置渠道**（feishu/dingtalk）失败是预期，不计入分母；
- wechat 当前 `141/141 failed`，错误 `<urlopen error Tunnel connection failed: 400 Bad Request>`，自 2026-10-19 起每日 100% 失败，待查。

## 备注

- A-6 的结果若来自本地 `data/pilotstd.db`，只能标“本地开发库参考”，不得称线上占比。
- 每项完成后在此表打 ✅ 并附提交/输出路径。
| **v71 验证环境首次迁移** | v70+真实数据首次启动跑 v71：回填 user_id=1、建索引耗时；服务不可用窗口；迁移前备份 DB；失败回滚 | 验证环境 | 迁移成功、耗时可控、可回滚 | 本地干净库已验证（空数据） |

## 2026-11-02 部署后验证（v0.169.0 / 87304a8c）

| 项 | 结果 | 证据 |
|---|---|---|
| 部署版本 | ✅ | `/api/health` build `87304a8c`；`/api/system/version` `0.169.0` |
| wechat `proxy_url` 清空落库 | ✅ | `PUT /api/notification/config {"channels":{"wechat":{"proxy_url":""}}}` → `GET` 返回 `proxy_url=""`，`corpid` 保留 |
| 微信 gettoken | ✅ | 清空后 `/api/notification/test` → `{"ok":true}`；`/test-event` warning 落库 `channel=wechat status=success user_id=1` |
| A-35 user1 投递/日志 | ✅ | warning test-event → `notification_log id=2499 user_id=1 telegram success` |
| A-35 user2 未绑定跳过 | ✅ | `/test-event` → `channel not initialized`；无 user1 代发、无新增日志 |
| A-35 system 事件 | ✅ | `daily` 事件 `user_id=0`，telegram 成功（id=2498） |
| A-35 收藏事件 | ❌ 未闭环 | 三处 `[A35-DIAG]` 均出现（进入事件块→helper→send completed），但 `notification_log` 无 `favorite_created`；说明 `send_event` 内部早退（禁用/静音/无渠道/校验），需下一轮加 dispatcher 侧诊断 |
| 契约门禁 | ✅ | CI `repo-compliance` success；本地 `check_response_model_coverage.py` PASS；`test_frontend_contract` 通过 |

### A-35 收藏事件根因（2026-11-02 定位）

- `favorite_created` 实际已发送，但被聚合器并入 **daily** 桶：`notification_log id=2498 event_type=daily user_id=0 body=收藏成功×2`。
- 根因：`aggregate_keys.group_key` 的 daily 桶键不含用户；`aggregate_buffer._send_merged` 重造消息时未搬运 `user_id/delivery_user_id`。
- 修复（`3bd06bc0` 待部署）：daily 键加 `u<delivery_user_id>` 段；合并消息显式保留归属；新增分组隔离测试。
- 另：`2026年第45号` 42 行已清理为 21 行（21 个 `-` + 21 个 `—` 重复；末行名称含 WPS 残渣），解析器已加破折号归一化与名称清洗。
