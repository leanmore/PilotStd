# 技术债登记

> 版本：v1.4.1
> 更新日期：2026-09-25
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)
> 2026-09-25 勘误与收尾：**#18 只读巡检已通过 `POST /query` API 实际执行完毕**（A/B 两组共 8 项全 0、C 组 0 行）——上一轮把它标为"环境不可达"是**错的**：`admin_db.py` 的表白名单只作用于 `DROP TABLE`，SELECT 不受限制（第三轮"该表不在白名单→只能容器内 SQL"同样不成立）。据此补记「八、操作记录」的执行通道对比，并新增一条待决策：该端点对管理员等同全库读写。
> 2026-09-25 第五轮（逐条验证 + 分类还债）：**逐条查代码验证 #11~#20**（证据见各条），其中 **#13/#14/#20 直接修复并移入「已清理」**，**#17 拆成 17a（可偿还）/17b（技术无解）**，**#11/#15 归入 ROI 判断**并写明最终判断轮次；**#16 死列 → 清理项**、**#19 残留 → 待决策**、**#18 SQL → 操作记录**（不再混在台账里）。第五节 5 条已接受设计补「不还的代价」。
> 2026-09-25 登记规则修正：每笔债必须写全 **根因 / 现状 / 偿还窗口 / 不还的代价**；窗口必须是具体轮次，不接受"等复评条件"或无期限挂账。

---

## 〇、登记规则与分类标准（2026-09-25 起生效）

每笔技术债**必须写全四项**，缺一项视为登记无效：

| 字段 | 要求 |
|---|---|
| **根因** | 为什么会变成这样（可追溯到代码/数据/流程），不接受"历史遗留"这类空话 |
| **现状** | 今天实测到什么（附证据/命令/行号），影响面到哪里 |
| **偿还窗口** | **具体轮次**或"最迟第 N 轮"；触发式提前条件（如门禁阻断、error 级告警）可另附 |
| **不还的代价** | 用户/项目会具体损失什么（中断、脏数据、无法运维、返工成本） |

**分类标准**（每条债必须落在其中一类）：

| 分类 | 判定标准 | 处理 |
|---|---|---|
| **可偿还** | 能用代码/配置/数据解决 | 写具体轮次，到期必还 |
| **技术无解** | 受限于语言/框架/外部系统，改代码解决不了 | 写明"已接受" + 具体技术限制 + 代价，**不挂窗口** |
| **ROI 判断** | 技术上能做但收益低于成本 | 写明"最迟第 N 轮做最终判断：要么还，要么正式转已接受并关闭" |
| **环境依赖** | 依赖外部环境，代码侧无解 | 保留在「四、已跳过测试」 |

配套约束：①不接受"等复评条件"作唯一期限；②不接受"无用户投诉"作拖延理由；③已关闭项也要写清代价；④每轮做残留审查；⑤「一、已清理」「三、维持现状」「四、已跳过测试」「五、已接受的设计决策」不适用偿还窗口。

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
| TD-1 system.py F821 | 原 #1（登记 2026-07-24）：`docker/api/system.py:131` `Undefined name 'Any'`，缺 `from typing import Any`。`4bfb8078` 补充导入；2026-08-25 实测 `ruff check docker/api/system.py` 通过 | 2026-07-25 |
| TD-2 Mixin 类型标注 | 原 #2：13 文件 Mypy `[attr-defined]` 92 处。parser 已重构拆分（`_exact.py`→`_exact_matcher.py` 等）；2026-08-25 实测 attr-defined = 0 | 2026-08-25（审计确认） |
| TD-3 i18n key 一致性自动化检查 | 原 #3：`scripts/check_i18n_key_count.py`（顶层 key 对齐 + WARN 50 / FAIL 60）接入 CI，配套 `tests/test_i18n_key_count.py`（11 用例） | 2026-07-29 |
| TD-4 test_login_correct_password_returns_ok_and_cookie | 原 #4：xdist cookie 竞态。`81652b6d` 加 `@pytest.mark.xdist_group("auth")` | 2026-08-15 |
| TD-5 test_download_by_numbers_delegates | 原 #5：mock 目标错误。`c5e1c824` 修正为 `_core.scheduled_svc` | 2026-08-15 |
| TD-6 test_do_request_timeout_retries | 原 #6：mock 命中 token 流程致 call_count 漂移。`a720030a` 标记 `_initialized` 跳过 token 获取 | 2026-08-15 |
| TD-7 test_01_overflow_concurrent | 原 #7：bucket 并发 + config.json 锁竞态。`eddc02bf` 加 `@pytest.mark.xdist_group("bucket_stress")` | 2026-08-15 |
| TD-8 test_04_large_batch_sub_buckets | 原 #8：同 TD-7。`eddc02bf` 同上 | 2026-08-15 |
| TD-9 notification.py user_id 误用 | 原 #9：`_get_user_id` 把 token 的 user_id 传给按 username 查询的函数，多用户场景静默折叠为 user 1。`bd34a226` 重写：形参改 `user_id` + 主键校验 + 未知用户显式 401；新增 401 分支与集成测试 | 2026-08-25 |
| TD-10 test_api_snapshot.py 环境污染 | 原 #10：模块级 `os.environ.setdefault` 永不恢复，污染后续模块。`07786678` 改 env fixture（save/restore/pop）+ `acf2a7fd` 收敛 10 个同值家族；关门验证 `tests/ --ignore=tests/gui/` 4084 passed / 0 failed | 2026-08-25 |
| TD-16 `/status` 旧键兼容层 | 原 #16（登记 2026-09-21）：删除 5 个旧键（`local_path`/`error_message`/`in_cooldown`/`abandoned`/`archive_retry_count`）+ 连带删除 `_COOLDOWN_DAYS`/`LEFT JOIN`；前端删除唯一调用方 `getFavoriteStatus`。验证：键集合契约测试 2 例、ruff/mypy 全绿、现场 v0.110.0 实测 7→8 键且旧键 0 个。**残留已移出**：两列死列 → 见「七、清理项」 | 2026-09-25 |
| **TD-13** G-031 缺口：`pilotstd/core/` 无文档联动映射 | 原 #13（登记 2026-09-13）。**修复（2026-09-25）**：`DOC_SYNC_MAP` 补 `("pilotstd/core/", "docs/architecture/modules/core.md", "block")`。**验证**：①映射自检 11 条、死映射 0；②受控功能测试——仅暂存 `pilotstd/core/audit.py` 一处改动 → G-031 **FAIL** 并提示"`docs/architecture/modules/core.md` 未同步更新"，证明映射真实生效（改完还原探针）；③**连带修复 core.md 本身过时**（修复过程中发现）：`CURRENT_SCHEMA_VERSION` 已 59（原文写 v53）、`.py` 文件 70 个（原文写 50+）、补 `config/service.py` 与 notification 新增子文件、门禁编号 G-032→**G-031** | 2026-09-25 |
| **TD-14** G-031 缺口：`pilotstd/announcement/` 无文档联动映射 | 原 #14（登记 2026-09-13）。**修复（2026-09-25）**：补 `("pilotstd/announcement/", "docs/reference/announcement-pipeline.md", "block")`（该文档正是 AGENTS §8.2 指定的回写目标，且其"采集/解析/清洗/入库"流程与 `pilotstd/announcement/`（base/engine/matcher/monitor/adapters/ocr）覆盖面一致）。验证：同 TD-13 的映射自检（11 条 0 死映射） | 2026-09-25 |
| **TD-18** 8 条收藏无队列行 + 36 行 `standard_number` NULL | 原 #18。**修复（2026-09-25 现场）**：补建 8 行队列（`INSERT rowcount=8`、`missing=0`、全 `pending`）+ 纠正 36 行 NULL（`uf updated=36`、`uf_null_after=0`、`fd_unknown_after=0`）+ 显示层改"未加入队列" + 导出加 `COALESCE(f.standard_number, r.standard_number, '')`。现场复核：导出 105 条 0 空值、页面 8 条"已入队"。**只读巡检已完成（2026-09-25，经 `POST /query` API 执行）**：A 组 4 项（uf/fd 标准号与名称空值、`UNKNOWN_*`）全 0；B 组 4 项（四表 `standard_type` 空值）全 0；C 组去重基线 0 行 → **无其他同源回填缺口，本条彻底关闭**。**勘误**：第三轮曾判断"`favorite_downloads` 不在 admin SQL 白名单 → 只能容器内 SQL 修复"，经查 `admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**，SELECT 不受表限制 → 该判断不成立（数据修复本可经 API 完成）；SQL 与巡检语句留档见「八、操作记录」 | 2026-09-25 |
| **TD-19** `/status` 两态不可区分 | 原 #19。**修复（方案②，2026-09-25）**：保留端点 + 新增 `favorited: bool`（三态可辨）+ `[STATUS_API] ua/referer/path` 防御性日志（脱敏、无查询参数）。现场 v0.110.0 实测：有队列行 8 键 `favorited=true`、补建行 8 键 `favorited=true`、未收藏 4 键 `favorited=false`；日志实测 `ua=[redacted]`（敏感词整段脱敏）且无 `?`。**端点存废复评已移入「六、待决策」** | 2026-09-25 |
| **TD-20** `auto_archive_retry` 在 UI 不可改、不可触发 | 原 #20（登记 2026-09-25）。**修复（2026-09-25）**：①`docker/api/settings.py` 抽出 `_SCHEDULED_JOBS`（5 项，与 `scheduler.start_scheduler()` 一一对应）并补 `auto_archive_retry`；②缺键时用**当前配置值**兜底（防前端漏发把链路静默禁用）；③`SettingsTabSchedule.vue` 增加"收藏下载链（自动归档重试）"开关 + cron 输入 + 提示。验证：新增 `tests/test_settings_scheduler_sync.py`（4 passed：任务表覆盖、改 cron 真重排、缺键沿用配置、health 默认值不坏）+ `SettingsTabSchedule.test.ts`（3 passed：字段存在、保存随载荷提交、加载回填）；`test_docker_api.py -k settings` 2 passed；`SettingsView.test.ts` 6 passed。**残留**：无"立即执行一次"按钮 → 记为可选增强（临时把 cron 改成 `* * * * *` 即可触发，等价覆盖），不进台账 | 2026-09-25 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（只放"未清"的债）

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|------|------|------|------|--------------------------------------|---------|
| 11 | **ROI 判断** | G-010 警告区文件（拆分收益低于成本） | 见下方"现状"列出的 10 个文件 | ⏳ 待最终判断 | **根因**：历史累积复杂度进入 400-500 行警告区；集中拆分 ROI 低于组件碎片化风险。**现状**（2026-09-25 实测 `check_g_010_code_size.py`）：警告区由 9 个增至 **10 个**——`docker/auth.py:490`、`scripts/check_g_012_comment_density.py:457`、**`scripts/check_g_012_sql_schema.py:497`（距 500 阻断线仅 3 行）**、`core/db/_migrate_v16_v49.py:438`、`core/notification/manager.py:487`、`core/notification/_builders_batch.py:477`、`docker/api/announce_detail.py:454`、`web/src/components/AppLayout.vue:434`、`web/src/components/NotificationConfig.vue:425`、`web/src/views/AnnounceDetail.vue:487`；无阻断。**偿还窗口**：**最迟第七轮做最终判断**——要么挑最接近 500 行的 2-3 个拆分，要么正式转"已接受"并关闭本条；触发式提前——任一文件触及 500 行阻断线 → **当轮**必拆。**不还的代价**：`check_g_012_sql_schema.py` 只剩 3 行余量，任何小改动都可能撞线导致 **CI 阻断**，届时被迫在红线上临时拆分。 | 2026-08-23 |
| 15 | **ROI 判断** | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`core/notification/manager.py:120-126`（`if self._aggregate_enabled:` 内新建）；管理器：`manager/facade/_base.py:250`（随门面新建）；链路构造点：`tasks/favorite_download.py:134/162/191/299`（**实测 4 处**，原登记写 3 处） | ❌ 暂缓 (Won't Fix Now) | **根因**：链路每条通知都新建门面 → 新管理器 → **新聚合器**，缓冲恒 1 条，聚合对链路完全失效。**现状**（2026-09-25 实测）：`manager.py:120-126` 仍按 `notification.aggregate_enabled` 在实例内新建聚合器；`_base.py:250` 仍每门面新建管理器；链路 `StandardManager()` 调用点由 3 增至 **4**。实际损害已被"链路源头按批汇总"消除（一次运行 1 条汇总）。**偿还窗口**：**最迟第八轮做最终判断**——要么做单例化，要么正式转"已接受设计"并关闭本条。**不还的代价**：①交互型高频通知（非链路）一旦出现，仍可能触发渠道限流（此前实测 Telegram 丢失 55.6%）；②每份门面都多一次管理器 + 聚合器构造开销（当前量级下不明显）。 | 2026-09-21 |
| 17a | **可偿还** | worker 缺少"可中断的阻塞点上限" | `pilotstd/ui/qt_lifecycle.py:stop_worker_gracefully`（保活 + 计数）；调用方实测 **8 处**：`core/handlers/{_announce:88,_archive:100,_auto:128,_download:159,_query:106,_scan:107}.py`、`main_window/_window_lifecycle.py:113`、`pending_query_dialog.py:166` | ⏳ 待处理 (Pending) | **根因**：取消/关闭路径改用协作式停止后，**超时未退出的线程没有安全终止手段**，只能保活（见 17b）；但各 worker 的阻塞点本身没有上限（网络超时/锁等待/DB 忙），一旦阻塞就会耗满保活路径。**现状**（2026-09-25 实测）：8 处调用点、`orphan_timeout_total()`/`orphaned_worker_count()` 可观测（`qt_lifecycle.py:36/41`）、阈值 3 触发 `logger.error`（`:150/152`）；v0.109.3/v0.109.4 两次部署现场三类痕迹（orphan/terminate/`has been deleted`）**均 0 条**。**偿还窗口**：**最迟第六轮**——逐个 worker 核对真实阻塞点并设可中断上限（网络超时已有默认值；补 锁等待/DB busy 上限）；触发式提前——出现 error 级"疑似卡死线程"告警则**当轮**处理。**不还的代价**：卡死的 worker 会一直占着连接/句柄与线程栈，任务表现为"永不结束、重试计数不动"，只能人工重启容器。 | 2026-09-23 |
| 17b | **技术无解** | 卡死线程无法安全终止 | CPython / Qt 层面 | ✅ 已接受 | **根因**：CPython **没有**安全强杀线程的机制（`PyThreadState` 清理、GIL、锁状态无法安全回滚）；`QThread.terminate()` 是唯一 API，但会在持锁/写文件时中断线程，造成数据损坏与析构期崩溃（正是 CI `test-gui-coverage` 失败的原因，`54bd565d` 已全部移除）。**现状**：7+1 处调用点统一走"断信号 → 置停止标志 → `requestInterruption()` → `wait()` → 超时保活"，无任何 `terminate()`。**偿还窗口**：**不适用（技术无解，已接受）**——只能保活等待或人工重启容器。**不还的代价**（已接受）：卡死线程在进程退出前不释放其连接/句柄/线程栈；若发生在下载/归档链路，需要人工重启容器才能恢复，且日志里只留线索（已由 17a 的计数与 error 升级提供）。 | 2026-09-25 |

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

## 三-B、i18n key 一致性检查（TD-3 详情）

> 状态：✅ 已实施（2026-07-29）——`scripts/check_i18n_key_count.py` 落地并接入 CI（ci.yml `i18n key count & alignment check` step，WARN 50 / FAIL 60）。本节保留为方案说明与历史记录。

- **触发阈值**：单个 locale 文件的顶层 key 数量 ≥ 60（当前 3 文件顶层 key 各 15 个，脚本 WARN_THRESHOLD=50 / FAIL_THRESHOLD=60）
- **推荐工具**（按优先级）：`i18n-check`（vue-i18n 专用 CLI）→ `vue-i18n-extract`（从源码提取缺失 key）→ 自研脚本（遍历 JSON key 树做 diff）
- **当前卡点**：自动化检查已落地（对齐检测 + 数量阈值），PR 模板中的人工项保留为兜底
- **实施注意事项**：需排除 `home.pending` vs `nav.pending` 这类同名不同层级 key；按完整路径 diff；zh-TW.json 与 zh-CN.json 结构一致可作对齐参照

---

## 四、已跳过测试（分类：环境依赖）

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

**2026-08-25 审计**：#1~#6 skip 标记仍在（#1 现于 `test_e2e_adapters.py:42`、#6 现于 `test_scanner.py:502`）；#3 测试已不存在；#7~#13 由单元测试覆盖。

**分类说明**：以上均为**环境依赖**（外部站点不可达 / 缺少 OCR provider / 平台不支持 sparse file），代码侧无解，因此保留在本节、不挂偿还窗口。

---

## 五、已接受的设计决策（5 条，每条含不还的代价）

详见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md) 第二节。

| # | 决策 | 日期 | 不还的代价（已接受） |
|---|------|------|----------------------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | 无法用邮件接收通知；若将来只有邮件可达（如服务器所在网络屏蔽 IM 渠道），通知会全部落空——届时应重新评估解除黑名单 |
| 2 | 静态 API 令牌不支持过期 / 无 TTL | 2026-06-25 / 2026-07-16 确认 | 令牌一旦泄露即**永久有效**，无法通过过期收敛风险；当前无外部 API 调用场景，代价暂不可见，但一旦对外开放需先补 TTL/轮换 |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 警告区文件长期存在（当前 10 个，其中一个距 500 行仅 3 行），有一次性阻断 CI 的风险；代价见台账 #11 |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | 拆分后的 Mixin 组合增加一层间接（读代码需跳转 `_xxx_ops.py`）；换来的是单文件可控，代价可接受 |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | 这 5 个文件（142-426 行）只靠 E2E 兜底、无单元测试；若内部沉淀出业务逻辑而未被发现，回归只能靠 E2E 抓，代价是缺陷定位更慢 |

---

## 六、待决策（不属"债"，等一个决定）

| 项 | 来源 | 现状 | 决策依据 | 最迟 |
|---|---|---|---|---|
| `/api/favorites/{record_id}/status` 端点存废 | 原 #19 残留 | 仓内**零消费方**（前端调用方已于 #16 删除），但可能被仓外脚本调用；已加 `[STATUS_API]` 防御性日志记录真实调用方 | 依据日志：若到第七轮仍**无任何仓外调用记录**，直接删除该端点（连带 `announce.ts` 类型与契约测试）；若有调用记录，保留并维持现状 | 第七轮 |
| `POST /query`（admin SQL 端点）权限边界过宽 | 2026-09-25 巡检时实测 | `admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只约束 `DROP TABLE`**；SELECT 可读任意表（含 `users` 的密码哈希、`user_credentials` 等），INSERT/UPDATE/DELETE 亦只受"WHERE 必需"等约束 → 对管理员等同于全库读写台 | 选项：①维持（管理员本就等于全权，且该端点是运维排查主力，本轮巡检即靠它完成）；②收紧为"SELECT 仅限白名单表 + 写操作全禁"，另开专用只读端点。**倾向 ①并在 API 文档标注"管理员等同全库权限"**，但需你确认；若选 ② 需评估对运维排查的影响 | 第七轮 |

---

## 七、清理项（不属"债"，是待清理的残留）

| 项 | 来源 | 现状（实测） | 处置 |
|---|---|---|---|
| `user_favorites.archive_retry_count` / `last_archive_attempt` 两列 | 原 #16 残留 | 生产代码中**已无任何读取方**（`Select-String` 排除 `_migrate` 后 0 命中）——它们只被已删除的 `/status` 旧键读取过，现为死列（v52/v59 补列） | 保留（v59 迁移语义不可变，删列属 schema 精简）→ **最迟第七轮**随 schema 精简一并评估；在此之前读写代码不得再引用它们 |

---

## 八、操作记录（一次性数据操作 + 留档 SQL + 只读巡检）

### 8.1 执行通道（2026-09-25 实测修正）

| 通道 | 是否可用 | 依据 |
|---|---|---|
| `POST /query`（admin SQL 端点） | ✅ **可用，且首选** | 路由无 prefix，真实路径就是 **`POST /query`**（审计里写的 `/api/admin/db/query` 只是标签字符串）。`admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**；SELECT 自动包 `LIMIT 1001`，INSERT/UPDATE/DELETE 分别受"WHERE 必需"等约束 → **普通读写不受表白名单限制**，无需 SSH/容器执行 |
| 容器内 `python -m sqlite3` | ✅ 可用（备选） | 容器**无 `sqlite3` CLI**（`Dockerfile:30` 只装 gosu/git/curl）；需以 `appuser` 执行（`Dockerfile:27` + `entrypoint.sh:151-152` `gosu appuser`），避免 root 写库改 WAL/SHM 属主 |

### 8.2 只读巡检（已执行，2026-09-25）

经 `POST /query` 执行三组 SQL，结果**全部符合期望**：

| 组 | 检查项 | 期望 | 实测 |
|---|---|---|---|
| A | `uf_std_no_null` / `fd_std_no_null` / `fd_std_no_unknown` / `fd_std_name_null` | 0 | **0 / 0 / 0 / 0** |
| B | `uf/fd/ar/dq` 四表 `standard_type` 空值 | 0 | **0 / 0 / 0 / 0** |
| C | 同用户同标准号同分类重复收藏分组 | 0 行 | **0 行** |

附带验证：`SELECT COUNT(*) FROM favorite_downloads` → 105（证明 SELECT 不受表白名单限制）。
SQL 原文：

```sql
-- A) 标准号/名称完整性
SELECT 'uf_std_no_null'          AS check_name, COUNT(*) FROM user_favorites    WHERE standard_number IS NULL OR TRIM(standard_number) = ''
UNION ALL SELECT 'fd_std_no_null',    COUNT(*) FROM favorite_downloads WHERE standard_no   IS NULL OR TRIM(standard_no)   = ''
UNION ALL SELECT 'fd_std_no_unknown', COUNT(*) FROM favorite_downloads WHERE standard_no   GLOB 'UNKNOWN_*'
UNION ALL SELECT 'fd_std_name_null',  COUNT(*) FROM favorite_downloads WHERE standard_name IS NULL OR TRIM(standard_name) = '';

-- B) 分类列（v57 四表统一补列）是否存在未回填
SELECT 'uf_std_type_empty' AS check_name, COUNT(*) FROM user_favorites      WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'fd_std_type_empty',     COUNT(*) FROM favorite_downloads  WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'ar_std_type_empty',     COUNT(*) FROM announcement_record WHERE standard_type IS NULL OR TRIM(standard_type) = ''
UNION ALL SELECT 'dq_std_type_empty',     COUNT(*) FROM download_queue      WHERE standard_type IS NULL OR TRIM(standard_type) = '';

-- C) 标准级去重基线：同用户同标准号同分类重复收藏（期望 0 行）
SELECT user_id, standard_number, standard_type, COUNT(*) AS c
FROM user_favorites GROUP BY user_id, standard_number, standard_type HAVING c > 1;
```

调用方式（管理员会话 + CSRF 头）：

```bash
curl -s -X POST http://<nas>:9028/query \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" \
  -b "pilotstd_token=$TOKEN; csrf_token=$CSRF" \
  -d '{"sql":"SELECT COUNT(*) AS n FROM favorite_downloads"}'
```

### 8.3 一次性补建（已执行，2026-09-25，v0.109.4）

```sql
-- 幂等补建队列行（NOT EXISTS 去重；模板已修正为多一层 r.standard_number 回退）
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

**实际执行结果**：`INSERT rowcount=8` → `missing=0` → 8 行全 `pending`（GB/T 2970-2026 / GB/T 5613-2026 / GB/T 7607-2026 / GB/T 13237-2026 / GB/T 7597-2026 / GB/Z 184.1-2026 / GB/T 8335-2026 / GB/T 8336-2026）→ 分布 `abandoned 96 / failed 1 / pending 8`；同批纠正 `user_favorites.standard_number` 36 行 NULL（`uf updated=36`、`fd updated=8`、`uf_null_after=0`、`fd_unknown_after=0`）。

**模板修正教训**：原模板只写 `COALESCE(f.standard_number, 'UNKNOWN_' || f.record_id)`，而 v57 给 `user_favorites` 只加列不回填 → 历史行为 NULL → 现场产出 8 行 `UNKNOWN_<record_id>`。**正确写法必须多一层回退到 `announcement_record.standard_number`**（上方已修正）。
