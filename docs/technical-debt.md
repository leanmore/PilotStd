# 技术债登记

> 版本：v1.3.5
> 更新日期：2026-09-25
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)
> 2026-09-25 登记规则修正（用户指令，本轮起生效）：**每笔技术债必须写全四项 —— 根因 / 现状 / 偿还窗口 / 不还的代价**；偿还窗口必须是具体轮次（或"最迟第 N 轮"），**不接受"等复评条件"这种无期限写法**，也**不接受**"无用户投诉就不修"作为理由。本轮据此为 #11/#13/#14/#15/#17 补窗口、新增 **#20**（偿还窗口 = 下一轮），并复核 #16/#18/#19 的残留。
> 2026-09-25 第四轮（现场验证 + #19 方案②）：**#18 已处置**（数据修复现场执行成功 + 显示层改文案 + 导出 `COALESCE` 兜底，并补记 v57 只加列不回填导致的 36 行 `standard_number` NULL）；**#19 已处置**（用户选定方案②：保留 `/status`，新增 `favorited: bool` + `[STATUS_API]` 防御性日志）。
> 2026-09-25 第三轮（清理与还债）：**#16 已清理**（`/status` 旧键 + 前端 `getFavoriteStatus`，见第一节 TD-16）；新增 **#18**（8 条无队列行的历史收藏：B 显示层已改"未加入队列"，A 数据修复 SQL 已备好待容器执行）与 **#19**（`/status` 对"无队列行"与"未收藏"返回同一份 null 体，语义不可区分）。
> 2026-09-23 追加：#17 Qt 线程"只能保活、不可安全终止"的边界——`terminate()` 已在 7 处取消/关闭路径全部移除（改用 `stop_worker_gracefully()`），代价是线程超时未退出时只能保活等待；已加计数与 `error` 级升级作为发现手段，本条登记边界与复评条件。
> 2026-09-21 追加：#16 `/status` 旧键兼容层未清理——下载状态改造后前端已统一取标准键，旧键（`local_path`/`error_message`/`in_cooldown`/`abandoned`/`archive_retry_count`）经用户确认**本轮保留**，待 grep 复核无消费方后单独清理。
> 2026-09-21 追加：#15 通知聚合器实例不共享（聚合对"每次新建门面"的路径失效）——经用户确认本轮**不做单例化**，改用链路源头按批汇总（`1dd48f66`/`71ecaea0`），本条登记为暂缓项与复评条件。
> 2026-09-13 追加：#13、#14 两条 G-031 文档联动缺口（`pilotstd/core/`、`pilotstd/announcement/` 无映射 → 代码变更不触发文档同步），来源为 G-031 按"事实归属"判据的体检结果（commit `6539dbe8`）。
> 2026-08-25 全库审计：原待处理台账 12 条中 8 条（#1~#8）确认已解决并移入第一节（附 fix commit 证据），4 条（#9~#12）仍存在、描述已同步现状；第三/四节过时内容一并修正。同日 TD-9（#9，`bd34a226`）、TD-10（#10，P0 `07786678` + P1+P2 `acf2a7fd`）修复完成；TD-12（G-012 LANG）全量清零（`1d06e0d2`）后关闭（Won't Fix），剩余 1 条（#11）继续观察。

---

## 〇、登记规则（2026-09-25 起生效）

每笔技术债**必须写全四项**，缺一项视为登记无效：

| 字段 | 要求 |
|---|---|
| **根因** | 为什么会变成这样（可追溯到代码/数据/流程），不接受"历史遗留"这类空话 |
| **现状** | 今天实测到什么（附证据/命令/行号），影响面到哪里 |
| **偿还窗口** | **具体轮次**或"最迟第 N 轮"；触发式提前条件（如门禁阻断、error 级告警）可另附 |
| **不还的代价** | 用户/项目会具体损失什么（中断、脏数据、无法运维、返工成本） |

配套约束：

1. **不接受"等复评条件"** 作为唯一期限 —— 复评条件可以写，但必须同时给出最迟轮次。
2. **不接受"无用户投诉"** 作为拖延理由（个人项目以"状态是否干净可控"为准）。
3. 已关闭（Won't Fix）条目同样要写清 **不还的代价**，并把处置写成"已接受"而不是留空。
4. 每轮结束前复核：本轮涉及的债是否真的还清（**残留审查**），未清则顺延并重述窗口。
5. **适用范围**：本规则适用于「二、剩余台账」（待偿还项）。「一、已清理」记录已还清项、「四、已跳过测试」记录环境依赖跳过、「五、已接受的设计决策」每行已写明接受理由（等效于"不还的代价"且已决定不还），这三节不适用"偿还窗口"。

---

## 一、已清理

| 项目 | 说明 | 修复日期 |
|------|------|---------|
| DriveEnumerator 死代码 | `_file_tree.py` 内联副本删除，统一引用 `pilotstd/ui/drive_enumerator.py` 正本 | 2026-07-16 |
| LogHandler atexit 冲突 | `flush_logs()` + `app.aboutToQuit` 注册，Qt 析构前安全关闭 logging | 2026-07-16 |
| 跨 Handler 回调升级事件总线 | EventBus 单例 + 5 Handler 迁移（scan/query/download/archive/auto），13 个集成测试 | 2026-07-16 |
| 剩余 Handler 纯逻辑提取 | AutoFlowEngine（build_summary_stats）+ ScanFlowEngine（5 方法）+ AnnounceFlowEngine（3 方法），65 测试 | 2026-07-16 |
| _auto.py 全链路阶段验证 | test_auto_pipeline.py 补充 query/download/archive 阶段字段存在性断言 | 2026-07-16 |
| PriorityConfigManager 死代码（O-6） | `pilotstd/core/config/priority.py` 零生产引用（仅测试），删除模块 + 测试；`STANDARD_ROOT` 环境变量能力已由 `ConfigManager.__init__` 原生覆盖，不丢功能 | 2026-08-24 |
| TD-1 system.py F821 | 原 #1（登记 2026-07-24）：`docker/api/system.py:131` `Undefined name 'Any'`，缺 `from typing import Any`。`4bfb8078`（2026-07-25）补充导入；2026-08-25 审计实测 `ruff check docker/api/system.py` 通过 | 2026-07-25 |
| TD-2 Mixin 类型标注 | 原 #2（登记 2026-07-24）：`pilotstd/scan/parser/_exact.py` 等 13 文件 Mypy `[attr-defined]` 92 处。parser 已重构拆分为多模块（`_exact.py`→`_exact_matcher.py` 等，f6c6b4de/bddc6943）；2026-08-25 审计实测 `mypy pilotstd docker`：attr-defined = 0（剩余错误为 arg-type 等其他类型，见登记簿第四节） | 2026-08-25（审计确认） |
| TD-3 i18n key 一致性自动化检查 | 原 #3（登记 2026-07-29）：locale 键名未对齐时 vue-i18n 静默降级。`scripts/check_i18n_key_count.py` 已实现（顶层 key 对齐检测 + 50 警告 / 60 阻断阈值）并接入 CI（ci.yml `i18n key count & alignment check` step），配套 `tests/test_i18n_key_count.py`（11 用例）；当前 3 locale 文件顶层 key 各 15 个 | 2026-07-29 |
| TD-4 test_login_correct_password_returns_ok_and_cookie | 原 #4（登记 2026-08-15）：xdist cookie 竞态。`81652b6d` 添加 `@pytest.mark.xdist_group("auth")`（`tests/test_docker_auth.py:97`） | 2026-08-15 |
| TD-5 test_download_by_numbers_delegates | 原 #5（登记 2026-08-15）：mock 目标错误，mock 未生效触发真实查询超时。`c5e1c824` 修正为 `_core.scheduled_svc`（`tests/test_manager.py:369`） | 2026-08-15 |
| TD-6 test_do_request_timeout_retries | 原 #6（登记 2026-08-15）：mock 命中 token 获取流程致 call_count 漂移。`a720030a` 标记 `_session_mgr._initialized` 跳过 token 获取，断言 3 成立（`tests/test_query.py:743-754`） | 2026-08-15 |
| TD-7 test_01_overflow_concurrent | 原 #7（登记 2026-08-15）：bucket 并发 + config.json 文件锁竞态。`eddc02bf` 添加 `@pytest.mark.xdist_group("bucket_stress")`（`tests/test_query.py:970`） | 2026-08-15 |
| TD-8 test_04_large_batch_sub_buckets | 原 #8（登记 2026-08-15）：同上（bucket 并发 + config.json 锁）。`eddc02bf` 添加 `@pytest.mark.xdist_group("bucket_stress")`（`tests/test_query.py:1002`） | 2026-08-15 |
| TD-9 notification.py user_id 误用 | 原 #9（登记 2026-08-20，2026-08-25 审计升 🔴 高）：`_get_user_id` 把 token 的 user_id 传给按 username 查询的 `get_user_id()`（`WHERE username = ?`），多用户场景静默折叠为 user 1。`bd34a226`（2026-08-25）重写：形参 `username`→`user_id`，改用按主键 `get_user_by_id()` 校验，未知用户显式 401（删除兜底 1）；新增单元 401 分支 + 真实登录 + SQLite 集成测试（`tests/test_notification_api.py`，12 passed；联动 4 文件 28 passed） | 2026-08-25 |
| TD-10 test_api_snapshot.py 环境污染 | 原 #10（登记 2026-08-20）：模块级 `os.environ.setdefault` 注入独有 env 值（snapshot_*/admin_db_*）且永不恢复，污染后导入的 test_docker_auth 等模块（SUPERUSER 错值 → 登录 401，串行确定性失败 / xdist 下 flaky）。P0 `07786678`（2026-08-25）：test_api_snapshot/test_admin_db 改模块级 autouse env fixture（save/restore/pop 标准模式，同 test_api_favorites_auth.py:25-38）；P1+P2 `acf2a7fd`：4 个守卫式 `SUPERUSER` 注入清理（test_announce_detail 等）+ 10 个同值家族模块级 setdefault 收敛为 conftest 共享 fixture + 薄 wrapper。关门验证：全量串行 `tests/ --ignore=tests/gui/` 4084 passed / **0 failed**（基线 2 failed），14 skipped 不变 | 2026-08-25 |

| TD-16 `/status` 旧键兼容层 | 原 #16（登记 2026-09-21）：`get_favorite_status` 曾同时返回旧键 `local_path`/`error_message`/`in_cooldown`/`abandoned`/`archive_retry_count`。第三轮清理：删除 5 个旧键 + 连带删除仅供 `in_cooldown` 使用的 `_COOLDOWN_DAYS`/`LEFT JOIN announcement_record`；前端删除唯一调用方 `getFavoriteStatus`（全库零消费方）。验证：新增键集合契约测试 2 例（含"旧键不得回流"断言）、ruff/mypy 全绿、现场 v0.110.0 实测 `/status` 恰 8 键且旧键 0 个。**残留审查（2026-09-25）**：API 与前端侧**无残留**（`grep getFavoriteStatus` 仅命中文档/注释）；`in_cooldown` 剩余命中属路由评分与 rotator 方法（与 `/status` 无关）、`archive_retry_count` 剩余命中全在迁移/DB 列定义。⚠️ **唯一残留**：`user_favorites.archive_retry_count` / `last_archive_attempt` 两列（v52/v59 补列）在生产代码中**已无任何读取方**（`Select-String` 排除迁移后 0 命中），成为死列；处置：**保留**（v59 迁移语义不可变，删列属 schema 精简），偿还窗口 = **最迟第七轮**随 schema 精简一并评估；不还的代价：库结构里长期挂着两列"看起来重要"的字段，后续读库者会误以为归档重试逻辑仍在按它们运行。 | 2026-09-25 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（#11 观察中 / #12 已关闭 / #13、#14 待处理 / #15 暂缓 / #17 观察中 / #20 待处理；#16、#18、#19 已处置，见本节条目与第一节）

> 每行必须含四项：**根因 / 现状 / 偿还窗口 / 不还的代价**（规则见第〇节）。

| # | 项目 | 位置 | 状态 | 说明 | 登记日期 |
|---|------|------|------|------|---------|
| 11 | G-010 警告基线 9 文件 | 9 文件（400–500 有效代码行，详见 [登记簿](architecture/technical-debt-registry.md) 第六节） | ⏳ 继续观察 (Monitoring) | **根因**：9 个文件的历史累积复杂度落在 G-010 警告区，集中拆分 ROI 低于引入组件碎片化的风险，故一直未动。**现状**（2026-08-25 复核）：9/9 仍在 400-500 行警告区（3 升/6 平/0 降），无一触及 500 行阻断线；策略为"仅在业务需求触及时顺手局部重构"。**偿还窗口**：**最迟第七轮**做一次全量复查（行数趋势 + 是否需专项拆分）；触发式提前——任一文件触及 500 行阻断线、或连续 3 个批次行数单调上升 → **当轮**启动拆分评估。**不还的代价**：任一行数越过 500 行会直接**阻断 CI**（G-010 阻断模式），届时被迫在红线上临时拆分；这 9 个文件又是热点改动区，复杂度继续聚合会让后续每次修改更贵。 | 2026-08-23 |
| 12 | G-012 LANG 历史警告 + 白名单子串匹配机制 | `pilotstd/core/notification/`、`docker/api/announce_detail.py`、`scripts/` 等 | ✅ 已关闭 (Won't Fix) | **根因**：G-012 注释语言检查用子串白名单放行英文标识符（理论上匹配过宽），且历史注释混有英文术语。**现状**：核心目标已达成——白名单 58 词 + 11 处中文改写，LANG 告警 50→0（`1d06e0d2`）；白名单内无超短泛词，不存在隐蔽漏检。**偿还窗口**：不适用（**已接受，不再偿还**）——处置为"维持子串匹配"：正则边界匹配需重写解析逻辑 + 大量边界测试，而它只影响"多放行"，不会误杀或阻断。**不还的代价**（已接受）：若未来白名单里加入超短泛词，可能漏统计某条注释（最多少报一条警告，不影响 CI 正确性）。 | 2026-08-24 |
| 13 | G-031 缺口：`pilotstd/core/` 无文档联动映射 | 映射表 `scripts/check_g_031_docs_sync.py`；事实载体 [architecture/modules/core.md](architecture/modules/core.md) | ⏳ 待处理 (Pending) | **根因**：`DOC_SYNC_MAP` 里没有 `pilotstd/core/` → `core.md` 这条，改任何 core 文件都不触发文档同步。**现状**：缺口仍在；未立即补是因为要先核定 `core.md` 粒度（config/db/notification/i18n 子域），否则会退化成形式联动。**偿还窗口**：**最迟第五轮** —— 核定 `core.md` 覆盖面 → 落地"整包映射或按子域映射" → 补一个验证场景。**不还的代价**：`pilotstd/core/` 的变更可让 `core.md` 静默过期，读者（含未来的自己）按文档读到错误事实，且**没有任何门禁会拦住**这类漂移。 | 2026-09-13 |
| 14 | G-031 缺口：`pilotstd/announcement/` 无文档联动映射 | 映射表 `scripts/check_g_031_docs_sync.py`；事实载体 [reference/announcement-pipeline.md](reference/announcement-pipeline.md) | ⏳ 待处理 (Pending) | **根因**：AGENTS.md §8.2 已把 `docs/reference/announcement-pipeline.md` 定为 `pilotstd/announcement/` 的回写目标，但 G-031 未落地该映射（该点曾被误配到描述 `pilotstd/scan/parser/` 的 parser.md，已于 `6539dbe8` 修正）。**现状**：改公告解析/入库流程不触发任何文档同步；需先核定该文档是否覆盖 parser 层变更。**偿还窗口**：**最迟第五轮**（与 #13 同批落地）。**不还的代价**：公告解析是问题排查的高频入口，文档静默过期后，"流程在哪一步写库/去重/匹配"得靠读代码重新推导，重复消耗时间。 | 2026-09-13 |
| 15 | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`pilotstd/core/notification/manager.py:119-132`（随管理器新建）；管理器：`pilotstd/manager/facade/_base.py:250`（随门面新建）；触发点：`pilotstd/tasks/favorite_download.py:130/156/181` 每条通知都 `StandardManager()` | ❌ 暂缓 (Won't Fix Now) | **根因**：链路每条通知都新建门面 → 新管理器 → **新聚合器**，缓冲恒为 1 条，聚合对链路完全失效；对照收藏接口走依赖注入的长期存活管理器，同一聚合器故能合并（实测 50+17 两条）。**现状**：单例化未做；已用侵入性更低的"链路源头按批汇总"根治实际损害（一次运行只发 1 条汇总，`1dd48f66`/`71ecaea0`），聚合器继续服务交互型通知（5s 窗口）。**偿还窗口**：**最迟第八轮**评估是否做单例化；若届时判定无收益，正式转"已接受设计"并关闭本条（不再挂账）。**不还的代价**：①交互型高频通知（非链路）仍可能触发渠道限流（本轮之前实测 Telegram 丢失 55.6%）；②每条通知多一次管理器构造开销（当前量级下不明显）。 | 2026-09-21 |
| 17 | Qt 线程"只能保活、不可安全终止"的边界 | `pilotstd/ui/qt_lifecycle.py:stop_worker_gracefully`（保活列表 + 计数）；调用方 7 处：`core/handlers/{_scan,_download,_archive,_announce,_auto,_query}.py`、`main_window/_window_lifecycle.py`、`pending_query_dialog.py` | ⏸️ 边界观察 (Monitoring) | **根因**：取消/关闭路径原用 `QThread.terminate()` 强杀线程（与"控件已析构、排队信号仍投递"形成竞态，CI `test-gui-coverage` 因它失败）；改协作式停止后，**超时未退出的线程没有安全终止手段**，只能保活。**现状**：7 处已统一走 `stop_worker_gracefully()`；`orphan_timeout_total()`/`orphaned_worker_count()` 可观测、累计 ≥3 升级 `logger.error`；两次部署现场（v0.109.3/v0.109.4）`orphan`/`terminate`/`has been deleted` 三类痕迹**均 0 条**——从未触发，属预防性边界。**偿还窗口**：**最迟第六轮**——逐个 worker 核对真实阻塞点（网络超时/锁/DB 忙）并设可中断上限，把"被动保活"升级为"可中断的阻塞点治理"；触发式提前——一旦出现 error 级"疑似卡死线程"告警，**当轮**处理。**不还的代价**：线程真卡死时只能保活等待，进程退出前其连接/文件句柄/线程栈不释放且无法自动恢复；若卡在下载/归档链路，表现为"任务永不结束、重试计数不动"，只能人工重启容器。 | 2026-09-23 |
| 18 | 8 条收藏没有 `favorite_downloads` 队列行（显示"未加入队列"） | 数据：`user_favorites` favorite_id 1..8；代码：`docker/api/favorites.py`（只有**新建**收藏才建队列行）；`pilotstd/core/db/_migrate_v54.py`（v54 只补列 + 回填**已有行**，不建缺失行）；`_migrate_v57.py:38-43`（`user_favorites.standard_number` 只加列不回填） | ✅ 已处置 (Resolved) | **根因**：收藏创建路径在 2026-08-23 前不建 `favorite_downloads` 行（v54「断链修复」是分界线）；同源问题：v57 给 `user_favorites` 只加列不回填 → 36 行 `standard_number` 为 NULL。**现状**：8 条已补建（`INSERT rowcount=8`、`missing=0`、全 `pending`）；36 行 NULL 已纠正（`uf updated=36`、`uf_null_after=0`、`fd_unknown_after=0`）；导出 105 条 **0 空值**；显示层改"未加入队列"；导出代码加 `COALESCE(f.standard_number, r.standard_number, '')` 兜底。**偿还窗口**：**最迟第五轮**完成一次只读巡检（其他表是否有同源回填缺口，SQL 见本节末尾）；若巡检发现残留即并入该轮修复。**不还的代价**（若跳过巡检）：其他表的 v57 式缺口会继续以"导出空白/去重失效/显示 Unknown"存在——这类脏数据"看得见却查不出为什么"，每次都要重新排查一遍。**残留审查（2026-09-25）**：API/数据侧已核对通过；仅余上述只读巡检一项。 | 2026-09-25 |
| 19 | `/status` 对"无队列行的收藏"与"未收藏"返回同一份 null 体 | `docker/api/favorites.py`（`get_favorite_status` 无行分支） | ✅ 已处置 (Resolved，方案②) | **根因**：该端点按 `favorite_downloads` 取数，而"是否收藏"的信息在 `user_favorites`，两态因此返回完全相同的 null 体。**现状**：已按用户选定方案②保留端点并新增 `favorited: bool`（三态可辨：`true+null`=收藏但无队列行 / `false+null`=未收藏 / `true+abandoned`=收藏且已放弃），现场 v0.110.0 实测 8 键且三态正确；附带 `[STATUS_API] ua/referer/path` 防御性日志（脱敏、无查询参数，现场已验）。**偿还窗口**：**最迟第七轮**复评"该端点是否还有真实调用方"——依据就是 `[STATUS_API]` 日志；若届时仍无仓外调用记录，再决定是否删除该端点。**不还的代价**：一个仓内零消费方的端点会持续消耗契约测试与文档同步成本；且"是否收藏"存在两个来源（列表/批量接口 与 /status），长期容易再次分叉。**残留审查（2026-09-25）**：无队列行分支返回 4 键、有队列行返回 8 键——属**设计如此**（本轮只新增 `favorited`，不改分支形状），两条路径各有契约断言。 | 2026-09-25 |
| 20 | `auto_archive_retry`（收藏→下载链路唯一入口）在 UI 不可改、不可手动触发 | `web/src/views/settings/SettingsTabSchedule.vue:16-25`（只暴露 4 个任务）；`docker/api/settings.py:186-195`（重排列表只含 4 个 job）；`web/src/api/scheduler.ts` + `docker/api/scheduler.py`（只有 GET，无 run-now） | ⏳ 待处理 (Pending) | **根因**：链路任务上线时只挂了 cron，三处接入面同时缺席——①"定时任务"设置页没有 `auto_archive_retry_cron/enabled` 字段；②`put_settings` 的调度重排列表只重排 scan/announce/reminder/health，写配置**不会**重排该 job（要重启容器才生效）；③`/api/scheduler/*` 全是 GET，没有任何"立即执行一次"的入口，前端也没有按钮。**现状**（2026-09-25 现场）：为触发 8 条补建记录的下载，用户在 UI 里**找不到**该任务，只能等 04:00；`PUT /api/settings` 虽能持久化该键但不重排，等于"改了也不生效"。**偿还窗口**：**第五轮（下一轮，最迟）**——①`SettingsTabSchedule` 增加 `auto_archive_retry_cron/enabled`（含校验）；②`put_settings` 重排列表补该 job；③（可选）加"立即执行一次"接口 + 按钮；若你要求可作为本轮追加提交。**不还的代价**：①任何"立刻验证下载链"的需求都要改配置 + 重启两次、或等一整天（本轮已实际付出该代价）；②5 个定时任务里唯独链路任务不可运维，用户"以为能改却找不到入口"；③链路出问题时无法用 UI 触发一次来复现或止损，只能等下一个 04:00。 | 2026-09-25 |

### #18 A SQL 留档（容器内执行，不入代码库）

执行前先备份（宿主机 compose 目录内，`./data/pilotstd.db` 即容器 `/app/data/pilotstd.db`）：

```bash
cp ./data/pilotstd.db ./data/pilotstd.db.bak-$(date +%Y%m%d-%H%M%S)
docker compose exec pilotstd sqlite3 /app/data/pilotstd.db
```

补建 SQL（幂等：`NOT EXISTS` 去重，`UNIQUE(favorite_id, record_id)` 兜底，可重复执行）

> ⚠️ **模板修正（2026-09-25 实测教训）**：原模板只写 `COALESCE(f.standard_number, 'UNKNOWN_' || f.record_id)`，而 v57 给 `user_favorites` 只加列不回填 → 历史行该列为 NULL → 落到兜底，现场产出 8 行 `UNKNOWN_<record_id>`。**正确写法必须多一层回退到公告记录**（下表已修正）：

```sql
INSERT INTO favorite_downloads
  (favorite_id, user_id, record_id, status, standard_no, standard_name, standard_type,
   retry_count, created_at, updated_at)
SELECT f.id, f.user_id, f.record_id, 'pending',
       COALESCE(NULLIF(TRIM(f.standard_number), ''), r.standard_number, 'UNKNOWN_' || f.record_id),
       COALESCE(r.std_name, '未知标准'),
       COALESCE(f.standard_type, 'Unknown'),
       0, datetime('now'), datetime('now')
FROM user_favorites f
LEFT JOIN announcement_record r ON r.id = f.record_id
WHERE NOT EXISTS (SELECT 1 FROM favorite_downloads fd WHERE fd.favorite_id = f.id);
```

执行后验证（三条都跑）：

```sql
-- 1) 期望 0：不再存在缺队列行的收藏
SELECT COUNT(*) AS missing FROM user_favorites f
WHERE NOT EXISTS (SELECT 1 FROM favorite_downloads fd WHERE fd.favorite_id = f.id);

-- 2) 期望 8 行 pending，编号 1..8
SELECT favorite_id, status, standard_no, standard_type, created_at
FROM favorite_downloads WHERE favorite_id BETWEEN 1 AND 8 ORDER BY favorite_id;

-- 3) 队列状态分布（pending 应 +8）
SELECT status, COUNT(*) FROM favorite_downloads GROUP BY status;
```

**执行后的预期副作用（需知情）**：这 8 条属 GB/T 且发布时间在 2026-07/08，早已过 28 天冷却期 → 下一次 `auto_archive_retry`（每日 04:00）会把它们纳入下载链，可能出现 `failed`/`abandoned`（取链失败或采标跳过）。这正是"回到正常队列语义"的表现；若你希望它们**不**被下载，把 SQL 里的 `'pending'` 改为 `'abandoned'`（终态，可解释为"历史遗留不再重试"）。

**实际执行记录（2026-09-25 现场，v0.109.4）**：`INSERT rowcount=8` → `missing=0` → 8 行全 `pending`（编号 1..8，标准号分别 GB/T 2970-2026 / GB/T 5613-2026 / GB/T 7607-2026 / GB/T 13237-2026 / GB/T 7597-2026 / GB/Z 184.1-2026 / GB/T 8335-2026 / GB/T 8336-2026）→ 分布 `abandoned 96 / failed 1 / pending 8`。同批纠正 `user_favorites.standard_number` 36 行 NULL：`uf updated=36`、`fd updated=8`、`uf_null_after=0`、`fd_unknown_after=0`；导出复核 105 条 0 空值。

### #18 残留巡检 SQL（只读，最迟第五轮执行）

用于确认"其他表是否也存在 v57 式只加列不回填的缺口"（#18 的残留审查项）：

```sql
-- A) 标准号/名称完整性
SELECT 'uf_std_no_null'              AS check_name, COUNT(*) FROM user_favorites    WHERE standard_number IS NULL OR TRIM(standard_number) = ''
UNION ALL SELECT 'fd_std_no_null',        COUNT(*) FROM favorite_downloads WHERE standard_no   IS NULL OR TRIM(standard_no)   = ''
UNION ALL SELECT 'fd_std_no_unknown',     COUNT(*) FROM favorite_downloads WHERE standard_no   GLOB 'UNKNOWN_*'
UNION ALL SELECT 'fd_std_name_null',      COUNT(*) FROM favorite_downloads WHERE standard_name IS NULL OR TRIM(standard_name) = '';

-- B) 分类列（v57 四表统一补列）是否存在未回填
SELECT 'uf_std_type_empty'  AS check_name, COUNT(*) FROM user_favorites      WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'fd_std_type_empty',      COUNT(*) FROM favorite_downloads  WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'ar_std_type_empty',      COUNT(*) FROM announcement_record WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'dq_std_type_empty',      COUNT(*) FROM download_queue      WHERE standard_type IS NULL OR TRIM(standard_type) = '';

-- C) 标准级去重基线：同用户同标准号同分类出现重复收藏（期望 0 行）
SELECT user_id, standard_number, standard_type, COUNT(*) AS c
FROM user_favorites
GROUP BY user_id, standard_number, standard_type
HAVING c > 1;
```

判定：A/B 全部期望 0（若 `ar_std_type_empty` > 0 属公告记录未回填，需单独评估）；C 期望 0 行。

---

## 三、维持现状（E2E 兜底，不再拆解）

以下文件经审查为纯 Qt 控件构建，无可提取业务逻辑。**停止底层拆解**，仅通过 E2E 测试覆盖：

| 文件 | 行数 | 内容特征 | 策略 |
|------|------|---------|------|
| `pilotstd/ui/core/handlers/_settings.py` | 426 | QTabWidget/QGroupBox/QFormLayout 构建 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_theme_ops.py` | 142 | QIcon/QTranslator/QStyleSheet 管理 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py` | 263 | QTreeWidget+QMenu+QThread 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_export_ops.py` | 143 | QFileDialog+QTextEdit+QTableWidget 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_dialog_ops.py` | 51 | QFileDialog 封装，零业务逻辑 | E2E 兜底 |

**策略**：关注增量——未来若沉淀复杂业务逻辑（如动态对比度计算、复杂联动校验），再考虑局部提取。

**2026-08-25 审计**：原 `_theme.py`/`_file_tree.py`/`_export.py`/`_file_dialog.py` 已随 Handler 重构删除（`d1c12253` 创建 `main_window/parts/*_ops.py` 等价物，`cfb166fe` 清理旧文件），`_settings.py` 361→426 行；策略不变。

---

## 三-B、i18n key 一致性检查（#3 详情）

> 状态：✅ 已实施（2026-07-29）——`scripts/check_i18n_key_count.py` 落地并接入 CI（ci.yml `i18n key count & alignment check` step，WARN 50 / FAIL 60）。本节保留为方案说明与历史记录。

- **触发阈值**：单个 locale 文件的顶层 key 数量 ≥ 60（当前 3 文件顶层 key 各 15 个、叶子 key 各 88 个，脚本 WARN_THRESHOLD=50 / FAIL_THRESHOLD=60）
- **推荐工具**（按优先级）：
  1. `i18n-check` — 专为 vue-i18n 设计，CLI 对比各 locale 文件键名并支持 CI 集成
  2. `vue-i18n-extract` — 可从源码自动提取缺失 key 并生成报告
  3. 自研脚本 — 遍历 JSON key 树做 diff，适合不想引入新依赖的场景
- **当前卡点**：自动化检查已落地（对齐检测 + 数量阈值），PR 模板中的 `☑️ 已确认新增 i18n key 在所有 locale 文件中存在` 人工项保留为兜底
- **实施时注意事项**：
  - 需排除 `home.pending` vs `nav.pending` 这种同名不同层级的 key（它们合法共存，不应报错）
  - 建议按完整路径（如 `nav.download_import`）做 diff，而非仅比较叶子 key 名
  - zh-TW.json 当前与 zh-CN.json 结构一致，可作为对齐参照

---

## 四、已跳过测试（历史 13 条，现存 6 条）

详见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md) 第一节。

| # | 测试 | 原因 | 分类 |
|---|------|------|------|
| 1 | `test_gb_exact_match` | 外部 API 返回空 | E2E 网络依赖 |
| 2 | `test_hg_exact_match` | hbba 无响应 | E2E 网络依赖 |
| 3 | `test_cold_start_pending` | ahbz 未登录（测试已删除，见登记簿） | E2E 认证依赖 |
| 4 | `test_sh_exact_match` | hbba 无响应 | E2E 网络依赖 |
| 5 | `test_split_pdf_pages` | 无可用 OCR provider | 环境依赖 |
| 6 | (sparse file) | 系统不支持 | 平台依赖 |
| 7~13 | 7 个 Handler E2E | 测试文件已删除（`cfb166fe`，tests/gui/） | 已删除（由单元测试覆盖） |

**2026-08-25 审计**：#1~#6 skip 标记仍在（行号随文件重构漂移：#1 现于 `test_e2e_adapters.py:42`、#6 现于 `test_scanner.py:502`）；#3 测试已不存在；#7~#13 对应 `tests/gui/test_e2e_*.py` 文件已于 `cfb166fe`（Handler/Mixin dual-track 清理）删除，功能由对应单元测试覆盖。

---

## 五、已接受的设计决策（5）

详见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md) 第二节。

| # | 决策 | 日期 | 影响范围 |
|---|------|------|---------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | `notification/manager.py` |
| 2 | 静态 API 令牌不支持过期/无 TTL | 低 | 令牌永不过期，泄露后风险无限期存在。决策：保持现状。理由：当前无外部 API 调用场景，实现 TTL 需增加刷新/轮换逻辑，投入产出比不高。未来若有外部集成需求可重新评估 | 2026-06-25 / 2026-07-16 确认 | `docker/auth.py` |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 全项目 |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | `engine/`, `notification/` |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | `ui/core/handlers/` 5 文件 |
