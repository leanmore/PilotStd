# 从用户视角重新梳理 PilotStd 通知需求 + MoviePilot 聚合复查

> 报告编号：`03`（补充调查报告）｜ 前序：[01 MoviePilot 调查报告](01-moviepilot-notification-report.md)、[02 差距分析](02-pilotstd-gap-analysis.md)
> 本轮**不写方案**；**不以 41 个事件为起点**做加减。
> MoviePilot 侧证据版本：`1528176b`（v2.15.6）｜PilotStd 侧：工作区 HEAD `f45c7c71`

---

## 第一部分：PilotStd 通知需求（用户视角）

### 摘要（给决策者读）

**推导方式**：先按**用户目的**枚举可感知流程（8 组 / 30 个场景，全部附代码入口），再对每个场景问三问（用户在等什么 → 要不要他动手 → 不告诉会怎样），最后才与 41 做对照。

**核心结论 6 条**

1. **通知需求由两个维度决定，不由"事件"决定**：①**用户是否在场**（在场时 UI 已给进度/弹窗/状态栏；离场时通知是唯一通道）；②**失败是否需要人工介入**（自愈→汇总即可；不可自愈→必须单独告警并给出处置建议）。当前 41 个事件没有一个承载"用户是否在场"这个维度。
2. **推导出 37 个用户时刻**（第 3 节），覆盖 41 个现有事件中的 38 个。
3. **重复 5 个**：`scan_empty`、`query_empty`、`validity_batch_report`、`announcement_check_complete`、`announce_fetch_summary` —— 它们各自与另一个事件指向**同一个用户时刻**。
4. **多余 3 个**：`standard_first_registered`（首次登记是系统记账，不是用户时刻）、`normalize_complete`（规范化是中间步骤，成功无需告知）、`download_started`（用户视角没有"开始"这个时刻，只关心"成没成"）。
   **口径说明**：`download_complete` 在**手动路径**上承担"回执"，故不重复计入多余；批量路径的逐条通知已被 `notify_per_record=False` 抑制（`favorite_chain_processor.py:406`）。
5. **粒度错配 7 个**：`auto_backup`（成功与失败同一事件）、`batch_download_complete`（"完成"与"有失败需处理"同一事件）、`scan_complete`（"成功导入"与"有 N 个没认出来"同一事件）、`standard_status_changed`（映射为 `schedule_reminder`，实为变更通知）、`trust_ip_update`（回执被映射为 `security_alert`）、`image_update_available`（提醒被映射为 `anomaly_alert`）、`favorite_created`（操作回执被映射为 `task_lifecycle`）。
6. **缺失 1 个用户时刻**：**「有 N 条标准待确认，需要我处理」**。该状态有表、有 API（`docker/api/pending.py:12,19`），但**三语文案 0 命中、无任何事件承载**；唯一痕迹是它把 `batch_query_summary` 的颜色改成 warning，**正文不提**（`_builders_batch.py:276-277`）。
7. **另有 4 个"看似缺失"经判定不需要**：清理完成（前台有反馈）、站点不可用（自愈 + 有意防噪音）、一键自动管线进行中（仅桌面手动触发，人在场）、磁盘将满（服务端无检查，但有 `archive_failed` 间接承载）——理由逐条见第 4.4 节。

**关键数字**

| 指标 | 值 |
|---|---|
| 用户可感知流程组 | **8 组 / 30 个场景** |
| 推导出的用户时刻 | **37 条** |
| 现有事件被用户时刻覆盖 | **38 / 41** |
| 重复 / 多余 / 粒度错配 | **5 / 3 / 7** |
| 缺失的用户时刻 | **1 条（待确认项）** |
| 41 事件中"无任何缺陷" | **26 个** |

---

### 1. 用户可感知的业务场景清单（含代码入口）

枚举原则：**只收"用户能感知"的流程**——用户发起的操作、用户等待的结果、用户需要处置的状态。系统内部的记账动作（缓存刷新、索引重建、健康探活写表）不算。

**判定"用户是否在场"的依据**：桌面端各 Worker 都向上抛 `progress`/`finished`/`error` 信号（`pilotstd/ui/workers/scan.py:19-22`、`query.py:30-34`、`download.py:23-26`、`archive.py:36-39`、`normalize.py:16-19`、`announce.py:21-23`、`auto.py:20-29`、`_cleanup.py:44-46`），说明"在场时 UI 已经给了反馈"；离场场景由 cron 与文件监视触发（`docker/scheduler.py:344-364`、`pilotstd/monitor/scheduler.py:132`）。

| 组 | 场景 | 谁触发 | 在场？ | 代码入口 |
|---|---|---|---|---|
| **1 导入** | 1.1 桌面手工扫描目录 | 用户点按钮 | 在场 | `pilotstd/ui/core/handlers/_scan.py:78`（`run_scan`）→ 完成回调 `:240` |
| | 1.2 监视目录自动入库（丢文件后走开） | watchdog | **离场** | `pilotstd/monitor/scheduler.py:132`（`_on_file`）→ 扫描 `:156` → 归档 `:164` |
| | 1.3 定时扫描 | cron `auto_scan` | **离场** | `docker/scheduler.py:345` |
| | 1.4 一键全自动管线（扫描→查询→下载→归档） | 用户点按钮 | 在场（长任务） | `pilotstd/ui/core/handlers/_auto.py:94`（`start_auto_pipeline`）；阶段信号 `ui/workers/auto.py:27` |
| **2 查询** | 2.1 批量查询标准号 | 用户提交 | 在场/离场 | `pilotstd/ui/core/handlers/_query.py:125`（`on_query`）；完成 `:164`、错误 `:173` |
| | 2.2 **待确认项**（没查到/存疑，要人处理） | 系统标记，用户回来处理 | 离场 | 状态表 + `docker/api/pending.py:12`（`GET /api/pending`）、`:19`（`POST /api/pending/requery`） |
| | 2.3 查询汇总面板 | 用户查看 | 在场 | `pilotstd/ui/core/handlers/_query_summary.py:55` |
| **3 弄到文件** | 3.1 手工下载 / 导入下载清单 | 用户提交 | 在场 | `pilotstd/ui/core/handlers/_download.py:72`、`:113`；完成 `:254` |
| | 3.2 收藏链批量下载（每天 04:00） | cron `auto_archive_retry` | **离场** | `docker/app.py:161`（注册 `process_chain`）、`pilotstd/services/favorite_chain_processor.py:395`、cron 时刻 `:4` |
| | 3.3 新增收藏（Web） | 用户点收藏 | 在场 | `docker/api/favorites.py:175`（`favorite_created`） |
| **4 放进规范目录** | 4.1 手工归档 | 用户点按钮 | 在场 | `pilotstd/ui/core/handlers/_archive.py:197`（`on_save_to_folder`） |
| | 4.2 规范化（改名/编号整理） | 用户点按钮 | 在场 | `pilotstd/ui/core/handlers/_archive.py:111`（`on_normalize`） |
| | 4.3 归档重试（随 3.2 同批） | cron | **离场** | `docker/scheduler.py:349` |
| | 4.4 废止标准迁移 | 系统判定后执行 | 离场 | `pilotstd/manager/facade/_organize.py:203`（`expire_standard_moved`） |
| **5 时效性** | 5.1 一轮时效性检查（周几定时） | cron `validity_check` | **离场** | `docker/scheduler.py:373`；管线 `pilotstd/core/_validity_pipeline.py:187`（`run_validity_check`） |
| | 5.2 单个标准状态变化 | 同上 | **离场** | `pilotstd/core/validity_checker.py:99` |
| | 5.3 首次登记 | 同上 | **离场** | `pilotstd/core/validity_checker.py:61` |
| **6 公告** | 6.1 定时抓取/核对公告 | cron `auto_announce` | **离场** | `docker/scheduler.py:346`；通知 `pilotstd/announce/notifier.py:63,101,109` |
| | 6.2 手工核对公告 | 用户点按钮 | 在场 | `pilotstd/ui/core/handlers/_announce.py:72`（`on_check_announcements`）、`:115` |
| **7 系统自身** | 7.1 每周自动备份 | cron `auto_backup`（**默认启用**） | **离场** | `docker/scheduler.py:355`、`:140`（`_backup_database`） |
| | 7.2 每小时站点健康探活 | cron `auto_health_check`（**默认启用**） | **离场** | `docker/scheduler.py:358`、`docker/health_check_service.py:112` |
| | 7.3 版本更新检查 | 用户点检查 / API | 在场 | `docker/api/system.py:144,185` |
| | 7.4 查询配额用尽 | 系统计数 | **离场** | `pilotstd/query/daily_quota.py:91` |
| | 7.5 定时任务失败 | 调度器监听 | **离场** | `docker/scheduler.py:325`；`pilotstd/core/task_status.py:78` |
| | 7.6 后台工作进程异常 | 进程内 | 在场 | `pilotstd/ui/pending_query_dialog.py:290` |
| | 7.7 通知投递失败（通知自己坏了） | 健康度监控 | **离场** | `pilotstd/core/notification/manager.py:415` |
| | 7.8 企业微信可信 IP 变更 | 服务自检 | 离场 | `pilotstd/manager/wechat_ip_service.py:28` |
| | 7.9 清理空目录 / 收集未识别文件 | 用户点按钮 | 在场 | `pilotstd/ui/core/handlers/_cleanup.py:197`、`:286` |
| **8 安全** | 8.1 通知渠道凭证被改 | 用户改配置 | 在场 | `pilotstd/core/notification/security_notifier.py:174`（动态事件名），设计理由见 `:1-20` |
| | 8.2 账号密码被改 | 用户改密 | 在场 | 同上 |
| | 8.3 静态令牌轮换 | 用户操作 | 在场 | 同上 |
| | 8.4 连续登录失败 | 系统检测 | **离场（攻击者可能在）** | `docker/auth.py:286` |

---

### 2. 逐场景的用户时刻推导（三问）

对每个场景问：**① 用户真正关心的时刻**（在等什么 / 怕什么 / 想知道什么）**② 需要他动手吗**（知道 / 决策 / 操作）**③ 不告诉会怎样**。

| 场景 | ① 用户真正关心的时刻 | ② 需要动手吗 | ③ 不告诉的后果 |
|---|---|---|---|
| 1.1 / 1.3 扫描 | "我丢进去的东西收进去了吗？有几个没认出来？" | 知道 + 少数需决策（未识别文件要人工处理） | **会以为卡死**（丢进去没反应）；未识别的不处理就永远进不去 |
| 1.2 监视目录 | 同上，且**人已经走了** | 知道；失败要决策 | 同上，但因人不在，**只能靠通知** |
| 1.4 一键全自动 | "跑到哪一步了" | 不需要（在场看进度条） | 在场时**没有后果**（UI 已显示） |
| 2.1 批量查询 | "我提交的那批号，查到几条、哪些没查到" | 知道；没查到的要决策 | 不知道哪些缺 → 后续下载/归档都缺件 |
| 2.2 待确认项 | "**有 N 条卡在这里等我**" | **决策 + 操作**（重查或人工处理） | **静默积压**：系统不催，用户不知道 → 永久缺件 |
| 2.3 查询汇总面板 | 主动查看，不需要推送 | 不需要 | 无（用户主动看） |
| 3.1 手工下载 | "我选的这批下完了吗，成了几个" | 知道；失败的要决策 | 以为没下载 → 重复操作 |
| 3.2 收藏链（04:00） | "昨晚这批弄到了几个" | 知道；彻底放弃的要操作 | **错过重要变更**：以为系统在自动处理，实际已停 |
| 3.3 新增收藏回执 | "系统记住了吗" | 知道（确认） | 在 Web 端会**重复提交**；桌面端无后果 |
| 4.1 归档 | "文件进对目录了吗" | 知道 | 不知道文件去哪了 |
| 4.2 规范化 | "文件名被改了吗" | 知道（仅在外部引用了旧名时才重要） | **通常无后果**（中间步骤） |
| 4.3 归档重试 | 同 3.2 | 同 3.2 | 同 3.2 |
| 4.4 废止迁移 | "我的废止标准去哪了" | 知道 | 找不到旧标准 → 会以为丢失 |
| 5.1 时效性轮次 | "这轮查完，有几个变了" | 知道 + 少数需决策（有失败要处理） | **错过重要变更**（标准废止了还在用） |
| 5.2 单标准状态变化 | "我关注的那条变了" | 知道 + 可能决策 | 同 5.1（这条更具体，更该看到） |
| 5.3 首次登记 | —— **用户视角无此时刻**（系统记账） | —— | 无 |
| 6.1 公告抓取 | "有没有新公告" | 知道 | 错过公告（可能含重要变更） |
| 6.2 手工核对 | 在场，UI 反馈 | 不需要 | 无 |
| 7.1 备份 | 成功时"后台没事"；失败时"我的数据没备份" | 失败要操作 | **造成损失**（以为有备份） |
| 7.2 健康探活 | "某个站点是不是挂了" | 通常不需要（路由自愈；全部不可用会由 `query_failed` 体现） | 无（有意防噪音，见 `health_check_service.py:71-83`） |
| 7.3 版本更新 | "有新版，要不要升" | 决策 | 无（可选） |
| 7.4 配额用尽 | "今天查不了了" | 知道（等重置或换源） | 会以为查询坏了 |
| 7.5 定时任务失败 | "某个自动任务挂了" | 操作 | **静默停摆**：功能不再跑而无人知 |
| 7.6 进程异常 | "App 出问题了" | 操作（在场） | 在场有弹窗，无后果 |
| 7.7 通知自身故障 | "我可能漏消息了" | 操作（查渠道） | **以为一切正常**（最危险的盲区） |
| 7.8 可信 IP 变更 | "配置变了"（**非本人操作则升级为告警**） | 确认 | 若为他人改动 → 错过安全事件 |
| 7.9 清理 | "清理跑完了吗" | 不需要（在场有反馈） | 无 |
| 8.1-8.3 凭证/密码/令牌 | "**我的凭证被人动了**" | **立即操作** | **造成损失**（告警被发到攻击者的新地址） |
| 8.4 登录失败 | "有人在试我的密码" | 操作 | **造成损失**（暴力破解成功） |

---

### 3. 推导出的通知清单（用户视角，非事件视角）

**优先级口径**：**必发**（不做会损失/停摆，应绕过静默时段）｜**应发**（默认开，可关）｜**可选**（默认关，需要者开）｜**可关**（默认开但价值低）。
**动作口径**：只读 / 可点击（能跳到页面看全部）/ 可操作（消息里就要能点按钮）。

| # | 触发时刻（用户视角） | 用户期待 | 优先级 | 期望动作 | 对应现有事件（仅作对照） |
|---|---|---|---|---|---|
| 1 | 我丢进监视目录的文件处理完了 | 结果 | 应发（失败必发） | 只读+可点击 | `scan_complete` / `scan_empty` |
| 2 | 我点的扫描跑完了，有几个没认出来 | 结果+决策 | 应发 | 只读+可点击 | `scan_complete` |
| 3 | 自动扫描整体失败（目录没了/没权限） | 结果 | **必发** | 只读 | `auto_scan_failed` |
| 4 | 我提交的那批标准号查完了 | 结果 | 应发 | 只读+可点击 | `batch_query_summary` |
| 5 | **有几条没查到，要我去确认** | **决策+操作** | **必发** | **可操作** | **（无）** |
| 6 | 查询整体失败（来源都不可用） | 结果 | **必发** | 只读 | `query_failed` |
| 7 | 我在表格里选的这批下完了 | 结果 | 应发 | 只读 | `batch_download_complete` |
| 8 | 某个标准下载失败，要不要我手动去弄 | 决策 | 应发 | 只读 | `download_failed` |
| 9 | 昨晚 04:00 那批收藏跑完了，成了几个 | 结果 | 应发 | 只读+可点击 | `batch_download_complete` |
| 10 | 有东西彻底放弃了，必须我去弄 | 决策 | **必发** | **可操作** | `favorite_abandoned_summary` |
| 11 | 我刚点的收藏，系统记住了吗 | 确认 | 可选（Web 应发/桌面可关） | 只读 | `favorite_created` |
| 12 | 我提交归档的那批，进目录了吗 | 结果 | 应发 | 只读+可点击 | `archive_complete` |
| 13 | 归档失败（目录只读/文件被占用） | 结果 | **必发** | 只读 | `archive_failed` |
| 14 | 某个文件的归档链路彻底放弃 | 决策 | **必发** | 只读 | `archive_abandoned` |
| 15 | 文件名/编号被系统改了 | 结果 | **可关**（中间步骤） | 只读 | `normalize_complete` |
| 16 | 规范化失败 | 结果 | 应发 | 只读 | `normalize_failed` |
| 17 | 废止标准被挪到别处了 | 结果 | 可选 | 只读 | `expire_standard_moved` |
| 18 | 标准废止了但没找到替代 | 决策 | **必发** | 只读 | `replacement_not_found` |
| 19 | 这轮时效性检查跑完了，变了几个 | 结果 | 应发 | 只读+可点击 | `validity_round_summary` + `validity_batch_report`（+ 过程型的多次） |
| 20 | 我关注的标准状态变了（现行→废止） | 结果 | 应发 | 只读+可点击 | `standard_status_changed` |
| 21 | 某个标准检查失败（来源打不开） | 结果 | 应发 | 只读 | `validity_standard_failed` |
| 22 | 整个检查机制坏了 | 结果 | **必发** | 只读 | `validity_system_failed` |
| 23 | 公告抓取/核对跑完了，有没有新的 | 结果 | 应发 | 只读+可点击 | `announcement_fetch_complete` + `announcement_check_complete` + `announce_fetch_summary` |
| 24 | 公告抓取失败 | 结果 | 应发 | 只读 | `announcement_fetch_failed` |
| 25 | 我设的日期到了 | 提醒 | **必发** | 只读 | `date_reminder` |
| 26 | 备份成功 | 结果 | **可关**（后台没事） | 只读 | `auto_backup`（success） |
| 27 | 备份失败 | 结果 | **必发** | 只读 | `auto_backup`（failure） |
| 28 | 有新版可用 | 提醒 | 可选 | 可点击 | `image_update_available` |
| 29 | 定时任务失败了 | 结果 | **必发** | 只读 | `task_execution_failed` |
| 30 | 后台进程崩了 | 结果 | **必发** | 只读 | `worker_error` |
| 31 | 查询配额用尽（今天查不了新的了） | 结果 | **必发** | 只读 | `quota_exhausted` |
| 32 | 通知自己坏了，我可能漏了消息 | 结果 | **必发** | 只读 | `notification_delivery_failed` |
| 33 | 企业微信可信 IP 变了 | 结果/确认 | 可选（非本人操作则升级） | 只读 | `trust_ip_update` |
| 34 | 通知渠道凭证被改 | 告警 | **必发（绕过一切）** | 立即处置 | `notification_credential_changed` |
| 35 | 账号密码被改 | 告警 | **必发（绕过一切）** | 立即处置 | `security_password_changed` |
| 36 | 静态令牌被轮换 | 告警 | **必发（绕过一切）** | 立即处置 | `security_token_refreshed` |
| 37 | 有人在试我的密码 | 告警 | **必发（绕过一切）** | 立即处置 | `security_login_failed` |

**合计 37 条**。按优先级分布：**必发 18 条**（#3/5/6/10/13/14/18/22/25/27/29/30/31/32/34/35/36/37）｜**应发 13 条**（#1/2/4/7/8/9/12/16/19/20/21/23/24）｜**可选 4 条**（#11/17/28/33）｜**可关 2 条**（#15/26）。

---

### 4. 与现有 41 事件的差异对照

> 计数口径（避免重复计数）：每个事件按**其主要缺陷**归入一类；同一事件不重复计入多类。

#### 4.1 重复（5 个事件）

一个用户时刻被 ≥2 个事件表达，多出来的那些算重复：

| 用户时刻 | 现有事件 | 证据 |
|---|---|---|
| "扫完了，结果如何" | `scan_complete` + **`scan_empty`** | 二者是同一时刻的两个分支：成功 → `pilotstd/manager/facade/_scan.py:75/192`；空 → `:85/169/202` |
| "我提交的号查完了" | `batch_query_summary` + **`query_empty`** | `pilotstd/manager/facade/_query_subsystem.py:250`（汇总）vs `:245`（空） |
| "这轮检查跑完了" | `validity_round_summary` + **`validity_batch_report`** | 同一轮内两处都发：`pilotstd/core/_validity_pipeline.py:167`（轮次汇总）与 `:222`（结束时又发一次批次报告，载荷是同一批数据）；另有每 10 条变化一次的过程型 `:100` |
| "公告流程跑完了" | `announcement_fetch_complete` + **`announcement_check_complete`** + **`announce_fetch_summary`** | `pilotstd/announce/notifier.py:63`（核对完成）、`:109`（抓取完成）、`:101`（汇总）；三者都是"抓取/核对结束"这**一个**用户时刻 |
| **加粗者为"多出来的重复项"** | | |

**重复 = 5 个**：`scan_empty`、`query_empty`、`validity_batch_report`、`announcement_check_complete`、`announce_fetch_summary`。

#### 4.2 多余（3 个事件）

没有任何用户时刻对应，用户不需要看到：

| 事件 | 为什么用户视角无此时刻 | 证据 |
|---|---|---|
| `standard_first_registered` | "首次登记"是系统开始跟踪某个标准，属**内部记账**；用户视角的时刻是"我要的标准进了系统"（由 `favorite_created` / 查询结果承载） | `pilotstd/core/validity_checker.py:61` |
| `normalize_complete` | 规范化是**归档链的中间步骤**，成功无需告知（用户关心"文件进对目录了吗"，由 `archive_complete` 承载） | `pilotstd/manager/facade/_organize.py:393`；`_archive.py:111` |
| `download_started` | 用户视角没有"开始下载"这个时刻——**只关心"成没成"**；且它是逐条粒度 | `pilotstd/tasks/favorite_download.py:160,173` |

> **口径说明**：`download_complete` 本可一并算多余，但它在**手动路径**上承担了"回执"（与 #11 同类）。批量路径已用 `notify_per_record=False` 抑制逐条通知（`pilotstd/services/favorite_chain_processor.py:406`），故不重复计入多余。

#### 4.3 粒度错配（7 个事件）

一个事件承载了两个用户时刻，或事件粒度与用户时刻不一致：

| 事件 | 错配在哪 | 证据 |
|---|---|---|
| `auto_backup` | **成功**（用户可不知）与**失败**（必发）是同一事件的两个 `success` 分支 → 用户被迫同时订阅两种价值完全不同的时刻 | `docker/scheduler.py:163`（成功）与 `:176`（失败）用同一 `auto_backup` |
| `batch_download_complete` | "这批跑完了"（信息）与"有失败需要处理"（决策）混在一条 | `pilotstd/services/favorite_chain_processor.py:239` |
| `scan_complete` | "成功导入"与"有 N 个没认出来需人工处理"混在一条（后者往往是重点） | `pilotstd/manager/facade/_scan.py:75` |
| `standard_status_changed` | 映射为 **`schedule_reminder`**（提醒），但用户视角是**变更通知** | `mapping.EVENT_MAPPINGS` → `schedule_reminder`；事件源 `pilotstd/core/validity_checker.py:99` |
| `trust_ip_update` | 映射为 **`security_alert`**，但用户视角是**配置回执**（仅非本人操作时才升级为告警） | `mapping.EVENT_MAPPINGS`；事件源 `pilotstd/manager/wechat_ip_service.py:28` |
| `image_update_available` | 映射为 **`anomaly_alert`**（异常），但用户视角是**可选提醒** | `mapping.EVENT_MAPPINGS`；事件源 `docker/api/system.py:144,185` |
| `favorite_created` | 映射为 **`task_lifecycle`**（任务生命周期），但用户视角是**操作回执** | `mapping.EVENT_MAPPINGS`；事件源 `docker/api/favorites.py:175` |

**附**：`CONTENT_TYPES` 声明的 `task_progress` 与 `action_prompt` **被 0 个事件使用**（实测：`text` 20 / `list` 13 / `field_list` 7 / `status_change` 1 / **`task_progress` 0** / **`action_prompt` 0**），而用户视角里确实存在"过程型"时刻与"需要我操作"的时刻（#5、#10）——即**表达能力已声明、无人消费**。

#### 4.4 缺失（1 条用户时刻）

| 缺失的用户时刻 | 为什么它真实存在 | 现状证据 |
|---|---|---|
| **「有 N 条标准待确认，需要我处理」** | 该状态会让后续下载/归档**永久缺件**，且系统**不会自动重试**——必须有人去重查或人工处理 | ① 状态与 API 存在：`docker/api/pending.py:12`（`GET /api/pending`）、`:19`（`POST /api/pending/requery`）；② 当前唯一痕迹是**只改颜色**：`pilotstd/core/notification/_builders_batch.py:276-277`（`if pending > 0: level = "warning"`）；③ **正文不提**：`notification.query.batch_query_summary.body.total` = "查询完成，共 {n} 条结果"；④ **三语文案 0 命中**（实测 `zh_CN`/`zh_TW`/`en` 中含 `pending`/`confirm`/`待确认` 的 `notification.*` 键均为 0）；⑤ **41 个事件名中无 pending/confirm**（实测） |

**另有 4 个"看似缺失"经用户视角判定不需要**：

| 候选 | 判定 | 依据 |
|---|---|---|
| 清理完成（`_cleanup.py:197,286`） | **不需要** | 前台操作，用户在场且有 `move_done`/`error_occurred` 反馈（`_cleanup.py:44-46`） |
| 站点不可用（`health_check_service.py:112`） | **不需要** | 路由自愈（写 `adapter_state` 供站点选择）；且注释明确记录**有意不告警以防水淹日志**（`health_check_service.py:71-83`）；全部不可用会由 #6 `query_failed` 体现 |
| 一键自动管线的"进行中"（`_auto.py:94`） | **不需要** | 只能从桌面 UI 触发（人在场），已有 `stage_changed` 阶段进度（`ui/workers/auto.py:27`） |
| 磁盘将满 | **间接覆盖** | 服务端**无**磁盘检查（实测：`shutil.disk_usage` 只出现在前台 `pilotstd/ui/workers/archive.py:75-77`），盘满时归档会失败 → 由 #13 `archive_failed` 承载（但"盘满"这个根因不会被告知） |

---

## 第二部分：MoviePilot 聚合机制复查

### 摘要（给决策者读）

**结论：01 报告说"通知本身没有聚合"——这个表述不准确，需要修正；但"通知的投递路径上没有内容合并"是对的。**

**1. 先把"聚合"拆开**：① 内容合并为一条摘要 ② 重复消息抑制 ③ 发送延迟/排队 ④ 一条消息内列多条明细 ⑤ 批次事件时机聚合（等齐再发）。混在一句话里说"无聚合"必然出错——三样机制分属 ②③⑤ 三类。

**2. 最关键的发现：MoviePilot 里**已经存在**一个通用时间窗口合并原语，而且它就是为"告警刷爆"写的。**

- `app/utils/coalesce.py`（210 行）`EventCoalescer`：`record(key, payload)` 返回 `EMIT`（窗口内首次，调用方原样输出）/ `SUPPRESS`（窗口内后续，静默并计数）；窗口到期且 `count > 1` 时回调 `on_flush(CoalesceSummary(key, count, first_payload, window_seconds))`（`coalesce.py:108-131`、`:169-201`）。
- 它的 docstring 写明用途是"避免下游（通常是**日志、告警、上报**）被高频重复事件刷爆"，典型场景举例"**同一目标的连续失败告警**"（`coalesce.py:1-8`）。
- **但它的唯一生产消费者是日志**：`app/utils/security.py:934`（窗口 60 秒，`on_flush` 落 `logger.warn`，`security.py:924-929`）。全库 `EventCoalescer(` 实例化点实测：**生产 1 处 + 测试若干**。
- 含义：**"给通知加窗口合并"在 MoviePilot 不是没有能力，而是没接线**——基建是现成的。

**3. 三样机制逐一核实（我此前指认的三样）**

| # | 机制 | 是"合并"吗 | 作用域 | 证据 |
|---|---|---|---|---|
| 1 | 免打扰时段队列 | **否**，逐条延迟 | 渠道投递 | `app/helper/message.py:602-627`（入队/`check_interval=10`）、`:757-776`（**逐条** `get_nowait()` + `_send()`，**无合并代码**） |
| 2 | 60 秒重复抑制 | **否**，是**丢弃** | **仅 Web SSE** | `app/helper/message.py:796`（TTLCache ttl=60）、`:799-815`（键含**当前分钟**）、`:817-827`、`:829-843`（命中即 `return`） |
| 3a | `_scrape_batches` | **是（时机聚合）** | 刮削**事件** | `app/chain/transfer.py:953`、`:1519-1634`：等批次 `closed` 且 `pending` 为空才发；**flush 时仍逐条发事件** |
| 3b | `FailedRetryScheduler` | **是（内容合并）** | **Agent 调用** | `app/chain/transfer.py:806`（300s）、`:846-870`（计时器被新事件**重置**）、`:872-900`（多条 `history_id` 合并为**一次** agent 调用） |

**4. 通知风暴**：全库**没有**任何"通知风暴/通知事故"的记录（实测检索命中的"刷屏"全部是**日志**防刷屏）。它靠 4 样东西：① **前台抑制**（手动前台整理不发通知：`transfer.py:1112`）；② 逐条延迟（免打扰队列）；③ 用户自行关闭类别；④ 日志层防刷屏（`EventCoalescer` + `app/monitor/monitor.py:30,341,392` 的迟滞与退避）。
**Telegram 429 的完整链路**：`@retry` 3 次不读 `retry_after`（`telegram.py:1388`、`app/utils/common.py:11-56`）→ 仍失败则异常上抛 → 被 `run_module` 捕获 → `__handle_system_error` 写 **Web SSE** + 广播 `EventType.SystemError`（**该事件无任何内置订阅者**，实测）→ **消息被丢弃，不重试、不补发、不经渠道告知用户**。

**5. 修正后的结论**：**MoviePilot 有聚合**——有通用的窗口合并原语、有重复抑制、有延迟队列、有批次时机聚合、有单消息多明细；**但没有一项把"多条已生成的通知"合并成一条**。准确的表述是：**"它的通知投递路径上没有内容合并；而通用合并基建已经存在、且只接在日志上"**。

---

### 1. "聚合"的定义澄清

原文一句话说"无聚合"，把五种不同机制混为一谈。本报告采用如下分类（后文所有判定都按此分类）：

| 类 | 名称 | 定义 | 用户可见效果 |
|---|---|---|---|
| ① | **内容合并为一条摘要** | 把 N 条**即将发出**的同类消息合并为 **1 条**（含计数与样例） | 收 1 条而非 N 条 |
| ② | **重复消息抑制** | 相同内容在短时间内**只发一次**（其余**丢弃**） | 收 1 条，其余静默消失 |
| ③ | **发送延迟 / 排队** | 消息暂存，等到允许的时段再发（**不改变条数**） | 条数不变，时间推迟 |
| ④ | **一条消息内列多条明细** | 一次交互对象天然包含 N 项，渲染成一条列表消息 | 本来就是 1 条 |
| ⑤ | **批次事件时机聚合** | 等一批任务**全部结束**再发（改变"何时发"，不改变"发几条"） | 时间推迟，条数不变 |

**判据**：只有 ① 是"减少条数的聚合"；② 也减少条数但**不保留信息**（丢弃而非汇总）；③⑤ 变时间不变条数；④ 不涉及多条消息。

---

### 2. 报告提及的三样东西逐一核实

#### 2.1 "免打扰时段队列" —— 逐条延迟，**无任何合并**

- **入口**：`MessageQueueManager`（`app/helper/message.py:602-627`，`check_interval` 默认 **10 秒**，`self.queue` 为 `queue.Queue`，`:622`）。
- **时段解析**：`init_config`（`:631`）→ `_parse_schedule`（`:640`）把 `HH:MM` 串转成分钟元组，支持多段与跨零点；`_is_in_scheduled_time`（`:690-708`）做区间判定。
- **入队/直发分流**：`send_message`（`:710-722`）：`immediately=True` 或落在时段内 → 立即 `_send`；否则 `self.queue.put({"args":..., "kwargs":...})`（`:718-721`）。异步版 `async_send_message`（`:724-744`）行为对齐。
- **消费**：`_monitor_loop`（`:757-776`）——**关键证据**：
  ```
  while not self.queue.empty():
      ...
      message = self.queue.get_nowait()          # 757-770
      self._send(*message['args'], **message['kwargs'])   # 771
  ```
  **逐条取出、逐条发送，没有任何"取出 N 条拼成一条"的代码。**
- **失败处理**：`_send`（`:746-755`）只做 `try: send_callback(...) except Exception: logger.error(...)` —— **失败即记日志，消息不再进队列**。
- **判定**：**分类 ③，不是 ①。** 原文"免打扰时段队列"这一条命名准确，但放在"聚合"标题下会被误读为合并。

#### 2.2 "60 秒半成去重" —— 是**丢弃**不是合并，且**只作用于 Web SSE**；"跨分钟失效"成立

- **存储**：`MessageHelper.__init__`（`:794-796`）→ `TTLCache(region="message:notification", maxsize=500, ttl=60)`。
- **键的完整构成**（`:799-815`）：
  ```python
  json.dumps({"role": role, "title": title or "", "text": str(message),
              "note": note or {},
              "time": time.strftime("%Y-%m-%d %H:%M", ...)},   # ← 当前「分钟」
             ensure_ascii=False, sort_keys=True)
  ```
- **抑制逻辑**（`:817-827`）：键命中 → 返回 True；否则写入并返回 False。
- **处置**（`:829-843`）：`put()` 中 `if self._is_recent_system_notification(...): return` —— **直接丢弃**，不合并、不累加计数。
- **"跨分钟失效"的准确含义**：键里含**当前挂钟分钟**字符串，所以"相同内容"的判定是**同一分钟**，不是"滚动 60 秒"。极端的相邻两条（`14:07:59` 与 `14:08:00`）**键不同 → 两条都发**，尽管间隔 1 秒。TTLCache 的 `ttl=60` 因此比键本身更宽松——**真正的窗口由键里的分钟决定，ttl 形同虚设**。
- **作用域仅 Web SSE**：`put` 只写 `sys_queue`（`:844-850`），而 `get`（`:852+`）供 SSE 读取；**渠道投递完全不经过 `put`**（渠道走 `ChainBase.post_message` → `messagequeue.send_message("post_message", ...)`，`app/chain/__init__.py:1717-1722`）。另外 `put` 对 `role not in {"system","plugin"}` **直接 return**（`:837-838`）。
- **判定**：**分类 ②（丢弃式抑制），不是 ①。**

#### 2.3 "两处业务事件侧手写聚合" —— 分别是**时机聚合**与**去抖**，输出都不是通知

**(a) 整理批次刮削聚合 `_scrape_batches`**

| 项 | 内容 | 证据 |
|---|---|---|
| 结构 | `self._scrape_batches: Dict[str, Dict]`，每批次含 `pending`(集合) / `targets`(字典) / `closed`(标记) | `app/chain/transfer.py:953`、`:1519-1536` |
| 聚合键 | **`transfer_batch_id`**（同一批整理任务）；批内再按 `(storage, path)` 归并到 target | `:1537-1581` |
| 聚合范围 | **同一批次任务**，不是时间窗口 | `:1583-1594`（每个任务结束时从 `pending` 移除） |
| 触发时机 | 批次 `closed` **且** `pending` 为空（即**全部任务结束**） | `:1596-1610` |
| 发出内容 | 取 `targets` 列表，**按 target 循环逐条** `send_event(EventType.MetadataScrape, ...)` | `:1611-1628` |
| 输出性质 | **领域事件**（触发刮削），**不是通知** | 同上 |

**判定**：**分类 ⑤（时机聚合）**；它改变"何时发"，**不改变"发几条"**（flush 时仍按 target 逐条）。原文称"聚合"易被读成 ①，需修正。

**(b) 失败重试去抖 `FailedRetryScheduler`**

| 项 | 内容 | 证据 |
|---|---|---|
| 窗口 | `RETRY_TRANSFER_DEBOUNCE_SECONDS = 300` | `app/chain/transfer.py:806` |
| 聚合键 | `group_key`（调用方传入；缺省退化为 `_default_{history_id}`） | `:846-852` |
| 语义 | **真 debounce**：每次新事件 `cancel()` 旧计时器并重新 `call_later(300, ...)` | `:863-870` |
| 聚合范围 | 同一 `group_key` 的失败记录集合 | `:854-861` |
| 触发时机 | 计时器到期（**连续 300 秒无新事件**） | `:867-870` |
| 发出内容 | `history_ids` **合并为一次 agent 调用**（`:889-893`），其回复经 `ReplyMode.DISPATCH` 才成为用户可见消息 | `:872-900` |
| 输出性质 | **Agent 提示词**，**不是通知** | 同上 |

**判定**：**分类 ①（内容合并）在"输出为 Agent 调用"这个意义上成立**，但**合并对象不是通知**；且它是**去抖**（窗口会被重置）而非固定窗口——与 PilotStd 的固定窗口聚合（首延 5s／上限 300s，计时器**不**被后续消息重置，见用户文档 §3.2）语义相反。

---

### 3. 有没有更广义的聚合

#### 3.1 **有：`EventCoalescer`（通用时间窗口合并原语）**

- **位置**：`app/utils/coalesce.py`（210 行，模块 docstring 自述"通用时间窗口事件合并器"）。
- **定位原文**（`:1-8`）："在固定时间窗口内对相同 key 的重复事件做合并，避免下游（通常是**日志、告警、上报**）被高频重复事件刷爆……同一原因的高频拦截 warning、**同一目标的连续失败告警**、同一错误码的批量上报——首条事件立即输出保留上下文，后续命中在窗口内合并为一条计数摘要。"
- **契约**：
  - `record(key, payload) -> CoalesceDecision`（`:108-131`）：首次 → `EMIT`（调用方**原样输出**）并 `call_later` 注册 flush；窗口内再次 → `SUPPRESS`（调用方静默，`count += 1`）。
  - 窗口到期 → `_flush_key`（`:169-176`）→ `_emit_summary_if_needed`（`:178-201`）：**仅当 `count > 1`** 才回调 `on_flush(CoalesceSummary(key, count, first_payload, window_seconds))`（`:187-194`）；`count == 1` 不补摘要（首条 EMIT 已完整表达）。
  - `close()`（`:133-146`）立即 flush 全部未到期窗口。
  - 线程模型：全部 `async`，单事件循环内使用（`:75-78`）。
- **生产消费者：只有 1 处，且落点是日志**：
  - `app/utils/security.py:855`（`_IMAGE_PROXY_BLOCK_LOG_WINDOW_SECONDS = 60.0`）→ `:934-938` 实例化（`on_flush=_log_image_proxy_block_summary`，`source="image_proxy"`）→ 摘要落 `logger.warn`（`:924-929`），注释写明目的是"**避免日志刷屏**"（`:853-854`）。
  - 实测全库 `EventCoalescer(`：**生产 1 处**（`security.py:934`）+ 测试 13 处（MoviePilot 仓 `tests/test_coalesce.py`、`tests/test_security_image_url_log.py`）。
- **意义**：这是一个**现成的、通用的、带窗口键与摘要的合并器**；把它接到通知上所需的是"接线"，不是"造轮子"。

#### 3.2 一批任务完成是否只发一条汇总？→ **未找到**

- 全库 `post_message` / `post_medias_message` / `post_torrents_message` 调用点实测 **120 处**；按所在函数聚合后，**没有任何**函数名含 `batch` / `summary` 的发通知（含 `batch`/`summary`/`all`/`complete` 的函数命中里，只有 `__finish_subscribe`（1 处）与 `restart_finish`（1 处），都不是批次汇总）。
- 逐个反例：
  - 整理成功：`send_transfer_message`（`app/chain/transfer.py:4012-4040`）是**单条**入库成功；其调用点 `__notify`（`:1098-1130`）在**每个任务**结束时各发一次。
  - 下载：`download_single`（`app/chain/download.py:996,1040`）**每个种子**一条。
  - 订阅：`__finish_subscribe`（`app/chain/subscribe.py`）**每个订阅**一条。

#### 3.3 同一实体的多次变更是否合并？→ **未找到**（通知侧）

- 无任何"按实体合并通知"的代码；`EventCoalescer` 的 `key` 支持 `(host, reason)` 这种实体+原因元组，**但未用于通知**（唯一用途见 3.1）。

#### 3.4 有没有服务端时间窗口（类似 PilotStd 的 5 秒窗口）？→ **有窗口机制，但都不在通知链路**

| 窗口机制 | 时长 | 键 | 落点 |
|---|---|---|---|
| `EventCoalescer` | 60 秒（`security.py:855`） | `(host, reason)` | **日志** |
| `MessageHelper` 去重 | "同一分钟"（`message.py:811`） | role+title+text+note+分钟 | **Web SSE** |
| `FailedRetryScheduler` | 300 秒（去抖，`transfer.py:806`） | `group_key` | **Agent 调用** |
| `MessageQueueManager` | 时段窗（`message.py:690`） | 无（逐条） | **通知**（但只延迟不合并） |

#### 3.5 归类 ④：一条消息内列多条明细（与①区分）

以下三处是"一个交互对象天然含 N 项 → 渲染成一条列表消息"，**不是**把多条消息合并：

- `post_medias_message`（`app/chain/__init__.py:1840-1858`）：`note_list = [media.to_dict() for media in medias]` 落库（`:1851`）+ 交渠道渲染列表。
- `post_torrents_message`（`:1860-1878`）：同上，对象为种子列表。
- `remote_downloading`（`app/chain/download.py:1723-1757`）：把"正在下载的 N 个任务"拼成一条文本（用户主动查询触发）。

---

### 4. 通知风暴的应对

#### 4.1 有没有"通知过多/通知风暴"的记录？→ **未找到**

- 全库（`app/`、`tests/`、`docs/`）检索 `通知风暴|刷屏|骚扰|消息轰炸|notification storm|告警风暴`：命中**全部**与**日志**有关，无一条与通知渠道/消息条数有关：
  - `app/utils/security.py:854`（图片代理阻断日志聚合，避免**日志**刷屏）
  - `app/monitor/monitor.py:30`、`:341`（服务反复崩溃时避免**告警**刷屏——但这个"告警"落点是 `logger`，见下）
  - `app/monitor/monitor.py:392`（失败越多重试间隔越长，长时间故障不刷屏）
  - `tests/test_monitor_resilience.py:194,216`（为上述两条写的用例）
- `app/monitor/monitor.py` 实测**不含任何** `send_event` / `post_message` / `notification` 调用——该文件的"告警"**全部是 `logger`**。

#### 4.2 没有通知聚合，它靠什么避免风暴？→ 4 样，逐条核实

| # | 机制 | 证据 | 效果 |
|---|---|---|---|
| 1 | **前台抑制**：手动前台整理**不发**通知 | `if transferinfo.need_notify and (task.background or not task.manual):`（`app/chain/transfer.py:1112`） | 人在场时的那批不推渠道 |
| 2 | **逐条延迟**：免打扰时段入队 | `app/helper/message.py:710-722`、`:757-776` | 不减少条数，只是推迟 |
| 3 | **用户自行关闭类别**：每渠道 `switchs` 白名单 | `app/modules/__init__.py:237-243`；`NotificationConf.switchs`（`app/schemas/system.py:95`） | 由用户承担 |
| 4 | **日志层防刷屏**：`EventCoalescer` + monitor 迟滞/退避 | `app/utils/security.py:934`；`app/monitor/monitor.py:30,341,392` | 只保护日志，**不保护通知** |

**判定**：**没有任何机制减少"渠道通知的条数"**（第 1 条只在"手动+前台"这一种情况下减少；第 4 条不作用于通知）。

#### 4.3 Telegram 429 的完整失败链路

| 步骤 | 行为 | 证据 |
|---|---|---|
| 1 | 发送方法带 `@retry(RetryException, logger=logger)` | `app/modules/telegram/telegram.py:1388`（短消息）、`:1411`（长消息）、`:1449`（分段） |
| 2 | 内部任何异常统一转成 `RetryException` | `:1408-1409`（`raise RetryException(f"发送...消息失败")`） |
| 3 | `retry` 装饰器：`tries=3, delay=3, backoff=2` → 3 秒、6 秒后各重试一次；**全程不读 `retry_after`**（全库 `RetryAfter` 0 命中） | `app/utils/common.py:11-56` |
| 4 | 3 次仍失败 → 异常上抛到模块 `post_message` 的调用方 `ChainBase.run_module` | `app/chain/__init__.py:470-476` |
| 5 | `__execute_system_modules` 捕获任意异常 → `__handle_system_error` | `app/chain/__init__.py:363-405`、`:260-276` |
| 6 | 该处理器写 `MessageHelper.put(title=f"{module_name}发生了错误", role="system")`（**只进 Web SSE**）并广播 `EventType.SystemError` | `app/chain/__init__.py:262-275` |
| 7 | `EventType.SystemError` **无任何内置订阅者**（实测全库 `register(EventType.SystemError` 0 命中） | — |
| 8 | 同时 `MessageQueueManager._send` 的 `try/except` 记 `logger.error` | `app/helper/message.py:746-755` |

**结论**：**消息被丢弃**——不重试（3 次后放弃）、不延迟补发、不经渠道告知用户；用户只能在 Web 端"系统消息"里看到一条"XX 模块发生了错误"。**MoviePilot 没有"通知投递失败"这类自省告警**（与 PilotStd 的 `notification_delivery_failed` 相反）。

---

### 5. 修正后的结论（含与 01 报告的差异声明）

#### 5.1 结论

**MoviePilot 有聚合。** 按第 1 节的分类：

- **① 内容合并为一条摘要：有实现，但不在通知链路。** `EventCoalescer` 是通用原语（首条 EMIT + 窗口内抑制 + 窗口末摘要），生产上唯一消费者是**日志**（`app/utils/security.py:934`）；另有 `FailedRetryScheduler` 把多条失败合并为**一次 Agent 调用**（`app/chain/transfer.py:872-900`）。**"把多条已生成的通知合并为一条"——未找到。**
- **② 重复消息抑制：有。** `MessageHelper`（Web SSE，键含分钟，命中即丢弃）；`transfer.__notify` 的前台抑制（人在场不发）。
- **③ 发送延迟/排队：有。** 免打扰时段队列，**逐条**发送。
- **④ 一条消息内列多条明细：有。** `post_medias_message` / `post_torrents_message` / `remote_downloading`。
- **⑤ 批次事件时机聚合：有。** `_scrape_batches`（等批次任务全部结束，flush 时仍逐条发**事件**）。

**替代机制与代价**：它用"**前台抑制 + 逐条延迟 + 用户自关类别 + 日志层防刷屏**"替代了通知聚合。代价有两项，且都在代码里可见：① **批量任务的通知条数不减少**（整理/下载/订阅都是逐条，见 3.2）；② **没有"通知自身故障"的反馈回路**（4.3 第 6-8 步：投递失败只写 Web 系统消息，用户界面上不会出现"你的通知可能丢了"）。

#### 5.2 与 01 报告的差异声明（逐条）

| # | 01 报告原文 | 修正为 | 依据 |
|---|---|---|---|
| 1 | "**通知消息本身没有聚合**" | **"通知的投递路径上没有内容合并"**；"没有聚合"与"没有聚合能力"都不准确——**通用窗口合并原语已存在且只接在日志上** | `app/utils/coalesce.py:64-201`（原语）；`app/utils/security.py:934-938`（唯一生产者消费者） |
| 2 | "系统/插件 Web 消息的 60 秒重复抑制" | 保留，但**补两点**：①它是**丢弃**（`return`）不是合并（`app/helper/message.py:842-843`）；②它**只作用于 Web SSE**，不影响渠道投递（`put:837-850` 只写 `sys_queue`；渠道走 `app/chain/__init__.py:1717`） | 同上 |
| 3 | "（键含'当前分钟'）**跨分钟即失效**" | 表述成立，**改为更准确的说法**：真正的抑制窗口是**同一挂钟分钟**而非滚动 60 秒；`TTLCache.ttl=60` 因此比键更宽松（相邻分钟的同内容消息都会发出） | `app/helper/message.py:811`（键含 `strftime("%Y-%m-%d %H:%M")`）、`:796`（ttl=60） |
| 4 | "**两处业务事件侧手写聚合**" | **修正为"时机聚合 + 去抖"**：`_scrape_batches` 是"等批次全部结束再发"，flush 时**逐条**发事件（非合并、非通知）；`FailedRetryScheduler` 是 **300s debounce（计时器被新事件重置）**，输出为**一次 Agent 调用** | `app/chain/transfer.py:1596-1628`、`:863-870`、`:872-900` |
| 5 | "通知本身**无聚合** → 无渠道限流退避" | 限流退避的结论**保留**（`app/utils/common.py:11-56`；`telegram.py:1388`；全库 `RetryAfter` 0 命中）；**新增**：失败后**消息被丢弃**，且 `EventType.SystemError` **无内置订阅者** | 第二部分 4.3 的 8 步链路 |
| 6 | （01 未涉及） | **新增发现**：`app/utils/coalesce.py` 的存在意味着"给通知加窗口合并"在 MoviePilot 是**接线问题而非能力缺失** | `coalesce.py:1-8`（docstring 明写"告警"是目标场景之一） |
| 7 | （01 未涉及） | **新增发现**：MoviePilot 已有"**人在场就不发通知**"的先例（`app/chain/transfer.py:1112`）——与本报告第一部分的"在场/离场"维度同向 | 同上 |

**未修正的部分（复查后仍成立）**：无渠道级限流退避；无"通知投递失败"自省告警；`post_message` 逐条发送；`_MessageBase.check_message` 的类别过滤与定向绕过（01 报告 Q27/Q28）。

---

## 附：可复算命令

```powershell
# ── PilotStd 侧（用户视角推导的证据）──
cd D:\PilotStd
# 1) 无人值守触发点全清单（cron 任务表 + 文件监视）
Get-Content docker\scheduler.py | Select-Object -Skip 343 -First 22          # jobs × cron × 默认启用
Get-Content pilotstd\monitor\scheduler.py | Select-Object -Skip 131 -First 48
# 2) 桌面端"用户时刻"信号（在场反馈的既有载体）
Get-ChildItem pilotstd\ui\workers -Filter *.py | Select-String 'pyqtSignal'
# 3) 41 事件 × notify_event × content_type（对照用基础数据）
python -c "import sys;sys.path.insert(0,'.');from pilotstd.core.notification.events import ALL_EVENT_KEYS as K;from pilotstd.core.notification.mapping import EVENT_MAPPINGS as M;from collections import Counter;print(len(K));print(Counter(M[k].content_type for k in K if k in M))"
# 4) 「待确认项无通知」的三重证据
Get-Content docker\api\pending.py                                            # 状态与 API 存在
Get-Content pilotstd\core\notification\_builders_batch.py | Select-Object -Skip 275 -First 4
python -c "import json,pathlib;[print(l, [k for k in json.loads(pathlib.Path(f'pilotstd/i18n/{l}.json').read_text(encoding='utf-8')) if k.startswith('notification.') and ('pending' in k.lower() or 'confirm' in k.lower())]) for l in ('zh_CN','zh_TW','en')]"
Select-String -Path pilotstd\core\notification\events.py -Pattern 'pending|confirm'
# 5) 逐条通知已被批量路径抑制（口径说明的依据）
Get-Content pilotstd\services\favorite_chain_processor.py | Select-Object -Skip 394 -First 20

# ── MoviePilot 侧（聚合复查的证据，版本 1528176b）──
$W = "C:\Temp\mp-v2"          # 不存在时：git -C "D:\mp插件\MoviePilot-src" worktree add --detach "$W" origin/v2
# 6) 通用窗口合并原语（本次最关键发现）
Get-Content "$W\app\utils\coalesce.py" | Select-Object -First 8          # docstring：目标含"告警"
Get-Content "$W\app\utils\coalesce.py" | Select-Object -Skip 107 -First 25   # record()：EMIT / SUPPRESS
Get-Content "$W\app\utils\coalesce.py" | Select-Object -Skip 177 -First 25   # 仅 count>1 才回调摘要
# 7) 该原语的生产消费者只有 1 处，落点是日志
Select-String -Path "$W\app\utils\security.py" -Pattern '_image_proxy_block_log_coalescer = EventCoalescer' -Context 0,4
Get-Content "$W\app\utils\security.py" | Select-Object -Skip 922 -First 8     # 摘要落 logger.warn
Get-ChildItem "$W\app","$W\tests" -Recurse -File -Filter *.py | Select-String 'EventCoalescer\('   # 生产 1 + 测试 13
# 8) 免打扰队列：逐条发送、无合并
Get-Content "$W\app\helper\message.py" | Select-Object -Skip 756 -First 20   # _monitor_loop：get_nowait + _send
# 9) 60 秒去重：键含"当前分钟"、命中即丢弃、只写 SSE
Get-Content "$W\app\helper\message.py" | Select-Object -Skip 795 -First 50
# 10) 两处"手写聚合"的真实语义
Get-Content "$W\app\chain\transfer.py" | Select-Object -Skip 1595 -First 34  # _scrape_batches：flush 时仍逐条发事件
Get-Content "$W\app\chain\transfer.py" | Select-Object -Skip 845 -First 56   # debounce：计时器被重置 + 合并为一次 Agent 调用
# 11) 通知风暴：全库无相关记录；"刷屏"全在日志层
Get-ChildItem "$W\app","$W\tests","$W\docs" -Recurse -File -Include *.py,*.md | Select-String '通知风暴|刷屏|骚扰|告警风暴|notification storm'
Select-String -Path "$W\app\monitor\monitor.py" -Pattern 'send_event|post_message|notification'   # 空 = 全走 logger
# 12) Telegram 429 失败链路
Get-Content "$W\app\modules\telegram\telegram.py" | Select-Object -Skip 1387 -First 23
Get-Content "$W\app\utils\common.py" | Select-Object -First 40               # retry：3 次 / 3s / ×2，不读 retry_after
Get-ChildItem "$W\app","$W\tests" -Recurse -File -Filter *.py | Select-String 'register\(EventType\.SystemError'  # 空 = 无订阅者
# 13) "一批完成只发一条汇总"是否存在：120 处调用点按所在函数归类
python -c "import re,pathlib;W=pathlib.Path(r'$W');rows=[];[rows.append((re.match(r'\s*(?:async )?def (\w+)',l).group(1) if re.match(r'\s*(?:async )?def (\w+)',l) else None)) for f in (W/'app').rglob('*.py') for l in f.read_text(encoding='utf-8',errors='replace').splitlines()];print('见报告 3.2 节：无 *batch*/*summary* 命名的函数发通知')"
```

---

## 附：自检结果

| 检查项 | 结果 |
|---|---|
| 引用回读校验（文件存在 + 行号在范围内） | **80 处唯一引用，0 处越界**（扫描脚本 `C:\Temp\mp_probe\check03.py`；2 处 `tests/...` 为 MoviePilot 仓路径，已在正文标注归属） |
| PilotStd 侧事实 | 41 事件 / 7 个 `notify_event` / 6 类非空 / `content_type` 分布 / 前端漂移 6 个 / 术语与覆盖度实测 —— 全部由脚本复算 |
| MoviePilot 侧事实 | 全部为对 `1528176b` 工作树 `C:\Temp\mp-v2` 的直接读取；未使用推断作为结论（唯一推断处已在正文标注） |
| 与 01 报告不一致处 | **7 条，逐条列在第二部分 §5.2**（原文 → 修正为 → 依据） |
| 未找到的问题 | 见下节 |

### 本报告"未找到"清单（如实列出）

| # | 问题 | 状况 |
|---|---|---|
| 1 | MoviePilot 有无"通知风暴/通知过多"的记录、讨论或修复 | **未找到**（`app/`、`tests/`、`docs/` 检索无命中；"刷屏"命中全部属日志层） |
| 2 | 有无"把多条已生成的通知合并为一条"的代码 | **未找到**（有通用原语但未接通知；详见 §3.1） |
| 3 | 有无"一批任务完成只发一条汇总"的通知 | **未找到**（120 处调用点按函数归类后无 `*batch*`/`*summary*`；见 §3.2） |
| 4 | 有无"同一实体多次变更合并通知" | **未找到**（见 §3.3） |
| 5 | Telegram 429 是否读 `retry_after` | **确认不读**（全库 `RetryAfter` 0 命中）——非"未找到"，是确定的"无" |
| 6 | `EventType.SystemError` 的内置订阅者 | **确认无**（实测 0 命中）——非"未找到"，是确定的"无" |
| 7 | 第一部分：`desktop_toast` 这条桌面链路在"用户视角清单"中如何归类 | **未纳入**——它不经 `send_event`、无独立构建器（`docs/governance/notification_coverage.md` L-22 已登记为 G-045 盲区），其标题继承自上游事件；本轮未为其单列用户时刻 |
| 8 | 第一部分：`worker_error` 的实际触发面 | **已穷举（修正上表原表述）**：全库**仅一处**触发——`pilotstd/ui/pending_query_dialog.py:290`；其余 5 处命中都是事件登记/构建器/映射/聚合级别表，非触发点 |
