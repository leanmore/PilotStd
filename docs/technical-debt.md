# 技术债登记

> 版本：v1.3.3
> 更新日期：2026-09-25
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)
> 2026-09-25 第三轮（清理与还债）：**#16 已清理**（`/status` 旧键 + 前端 `getFavoriteStatus`，见第一节 TD-16）；新增 **#18**（8 条无队列行的历史收藏：B 显示层已改"未加入队列"，A 数据修复 SQL 已备好待容器执行）与 **#19**（`/status` 对"无队列行"与"未收藏"返回同一份 null 体，语义不可区分）。
> 2026-09-23 追加：#17 Qt 线程"只能保活、不可安全终止"的边界——`terminate()` 已在 7 处取消/关闭路径全部移除（改用 `stop_worker_gracefully()`），代价是线程超时未退出时只能保活等待；已加计数与 `error` 级升级作为发现手段，本条登记边界与复评条件。
> 2026-09-21 追加：#16 `/status` 旧键兼容层未清理——下载状态改造后前端已统一取标准键，旧键（`local_path`/`error_message`/`in_cooldown`/`abandoned`/`archive_retry_count`）经用户确认**本轮保留**，待 grep 复核无消费方后单独清理。
> 2026-09-21 追加：#15 通知聚合器实例不共享（聚合对"每次新建门面"的路径失效）——经用户确认本轮**不做单例化**，改用链路源头按批汇总（`1dd48f66`/`71ecaea0`），本条登记为暂缓项与复评条件。
> 2026-09-13 追加：#13、#14 两条 G-031 文档联动缺口（`pilotstd/core/`、`pilotstd/announcement/` 无映射 → 代码变更不触发文档同步），来源为 G-031 按"事实归属"判据的体检结果（commit `6539dbe8`）。
> 2026-08-25 全库审计：原待处理台账 12 条中 8 条（#1~#8）确认已解决并移入第一节（附 fix commit 证据），4 条（#9~#12）仍存在、描述已同步现状；第三/四节过时内容一并修正。同日 TD-9（#9，`bd34a226`）、TD-10（#10，P0 `07786678` + P1+P2 `acf2a7fd`）修复完成；TD-12（G-012 LANG）全量清零（`1d06e0d2`）后关闭（Won't Fix），剩余 1 条（#11）继续观察。

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

| TD-16 `/status` 旧键兼容层 | 原 #16（登记 2026-09-21）：`get_favorite_status` 曾同时返回旧键 `local_path`/`error_message`/`in_cooldown`/`abandoned`/`archive_retry_count`。第三轮清理：删除 5 个旧键 + 连带删除仅供 `in_cooldown` 使用的 `_COOLDOWN_DAYS`/`LEFT JOIN announcement_record`；前端删除唯一调用方 `getFavoriteStatus`（全库零消费方）。验证：新增键集合契约测试 2 例（含"旧键不得回流"断言）、ruff/mypy 全绿、现场 `verify_api.py` 8/8 | 2026-09-25 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（#11 继续观察 / #12 已关闭 / #13、#14 待补 / #15 暂缓 / #17 边界观察 / #18 A 待执行 / #19 待处置；#16 已清理，见第一节）

| # | 项目 | 位置 | 状态 | 说明 | 登记日期 |
|---|------|------|------|------|---------|
| 11 | G-010 警告基线 9 文件 | 9 文件（400–500 有效代码行，详见 [登记簿](architecture/technical-debt-registry.md) 第六节） | ⏳ 继续观察 (Monitoring) | 复核结论（2026-08-25）：9/9 文件仍处于 400-500 行警告区间（3 升/6 平/0 降），无一降至阈值以下，但均未触及 500 行阻断线。处置策略：①拒绝集中拆分——当前行数处于安全警告区，强制拆分 ROI 极低，易引入不必要的组件碎片化与认知负载；②维持 Boy Scout 原则——不设立专项拆分计划，仅在后续业务需求涉及这些文件时顺手局部重构；③观察触发条件——若任一文件触及 500 行阻断线，或出现连续 3 个批次行数单调上升，则立即升级为"需处理（Pending）"并启动拆分评估 | 2026-08-23 |
| 12 | G-012 LANG 历史警告 + 白名单子串匹配机制 | `pilotstd/core/notification/`、`docker/api/announce_detail.py`、`scripts/` 等 | ✅ 已关闭 (Won't Fix) | 关闭理由（2026-08-25）：①风险可控——当前子串匹配仅用于白名单放行，只会多放、不会误杀；即使匹配过宽，最多导致某条注释未被统计，不会产生阻断级误报，不影响 CI 流水线的正确性；②无实际损害——经全量审计，当前白名单中无超短泛词（如 id、v 等），不存在因前缀/后缀重叠导致的隐蔽漏检案例；③ROI 极低——升级为正则边界匹配（\b...\b）需重写解析逻辑并补充大量边界测试用例，投入产出比远低于收益；④G-012 已清零——核心目标（消除 LANG 警告）已达成（`1d06e0d2`：白名单 58 词 + 11 处中文改写，50→0），实现细节的"完美"不应成为持续挂账的理由 | 2026-08-24 |
| 13 | G-031 缺口：`pilotstd/core/` 无文档联动映射 | 映射表 `scripts/check_g_031_docs_sync.py`；事实载体 [architecture/modules/core.md](architecture/modules/core.md) | ⏳ 待处理 (Pending) | 判据（2026-09-13 确认）：文档要与代码一致，承载事实的文档存在就该联动。实测 `core.md` 自述模块路径 `pilotstd/core/` 且文件存在，但 G-031 的 `DOC_SYNC_MAP` 里没有 `pilotstd/core/` → `core.md` 这条，因此改任何 core 文件都不会触发文档同步，`core.md` 可静默过期。未立即补的原因：`pilotstd/core/` 覆盖面很大（config/db/notification/i18n 等子域），需先核定 `core.md` 的粒度是否足以承载"任意 core 文件变更"，否则会退化成形式联动（这正是本次刚消除的问题）。待办：核定 `core.md` 实际覆盖面 → 决定整包映射还是按子域映射 → 落地并加验证场景 | 2026-09-13 |
| 14 | G-031 缺口：`pilotstd/announcement/` 无文档联动映射 | 映射表 `scripts/check_g_031_docs_sync.py`；事实载体 [reference/announcement-pipeline.md](reference/announcement-pipeline.md) | ⏳ 待处理 (Pending) | AGENTS.md §八 8.2 已把 `docs/reference/announcement-pipeline.md` 定为 `pilotstd/announcement/` 状态机/流程变更的回写目标，但 G-031 未落地该映射，改公告解析（如 `pilotstd/announcement/parser.py`）不触发任何文档同步。另注：该点曾被误配为 `pilotstd/announcement/parser.py` → `docs/architecture/modules/parser.md`（`c27c6c85` 引入），而 parser.md 实际描述的是 `pilotstd/scan/parser/`，已于 `6539dbe8` 修正。待办：把 `pilotstd/announcement/` → `announcement-pipeline.md` 纳入映射，并先核定该文档是否覆盖 parser 层变更 | 2026-09-13 |
| 15 | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`pilotstd/core/notification/manager.py:119-132`（随管理器新建）；管理器：`pilotstd/manager/facade/_base.py:250`（随门面新建）；触发点：`pilotstd/tasks/favorite_download.py:130/156/181` 每条通知都 `StandardManager()` | ❌ 暂缓 (Won't Fix Now) | 实测（2026-09-21，1119 条通知日志）：仅 `favorite_created` 出现过聚合消息（2/3），`download_failed`(509)/`download_started`(437)/`archive_abandoned`(68) **聚合占比 0%**。根因：链路每条通知都新建门面 → 新管理器 → **新聚合器**，缓冲区恒为 1 条，等于未聚合；对照收藏接口走 FastAPI 依赖注入的长期存活管理器，同一聚合器故能合并（50+17 两条）。决策（用户确认）：本轮**不做单例化**——属高风险架构变更，会牵动大量测试，且可能在多 Worker / 异步混合运行时引入状态竞争；改用侵入性更低的"链路源头按批汇总"（一次运行 1 条，已落地 `1dd48f66`/`71ecaea0`），聚合器继续服务交互型通知（5s 窗口）。复评条件：有专门重构窗口 + 测试覆盖率进一步提升后再议 | 2026-09-21 |
| 17 | Qt 线程"只能保活、不可安全终止"的边界 | `pilotstd/ui/qt_lifecycle.py:stop_worker_gracefully`（保活列表 + 计数）；调用方 7 处：`core/handlers/{_scan,_download,_archive,_announce,_auto,_query}.py`、`main_window/_window_lifecycle.py`、`pending_query_dialog.py` | ⏸️ 边界观察 (Monitoring) | 背景：`test-gui-coverage` 因"取消后 worker 信号触达已析构控件"失败（commit `54bd565d`），修复时把 7 处 `QThread.terminate()` 全部移除——强杀可能让线程在持锁/写文件时中断，风险高于收益。代价（本条登记项）：线程若因 bug 永不退出，只能脱离父对象后保活等待自然结束，进程退出前其资源不释放，且没有安全手段中断它。已有发现手段：`orphan_timeout_total()` 累计次数、`orphaned_worker_count()` 当前滞留数、累计 ≥3 时 `logger.error` 列出滞留线程的类名与时长（测试见 `tests/gui/test_worker_lifecycle.py`）。复评条件：一旦出现 error 级"疑似卡死线程"告警，立即定位该 worker 的阻塞点（网络 / 锁 / DB），把超时从"被动保活"升级为"可中断的阻塞点治理" | 2026-09-23 |
| 18 | 8 条收藏没有 `favorite_downloads` 队列行（显示"未加入队列"） | 数据：`user_favorites` favorite_id 1..8；代码：`docker/api/favorites.py:151-165`（只有**新建**收藏才建队列行）；`pilotstd/core/db/_migrate_v54.py`（v54 只补列 + 回填**已有行**，不建缺失行） | ⏳ A 待执行 (Pending，B 已完成) | 根因确认（2026-09-25 实测）：收藏创建路径在 2026-08-23 前不建 `favorite_downloads` 行（v54「断链修复」是分界线）；现场 8 条 `favorite_id 1..8` 创建于 2026-07-20（5 条）/ 2026-08-22（3 条），而 2026-08-23 起的 97 条全部有队列行 → **新增为 0，属历史遗留**。**自动补建确认：不会**——`add_favorite` 命中 `already_exists` 时直接返回、不补行；全库唯一的 `INSERT INTO favorite_downloads` 在 `favorites.py:155`（仅新建路径）；`favorite_downloads` 不在 admin SQL 白名单（`docker/api/admin_db.py:25-34`）→ 只能容器内 SQL 修复。**B 已完成**：前端 null 显示由"待下载"改为"未加入队列"（`download.status.notQueued`）。**A 待执行**：容器内一次性幂等 SQL（原文见本节末尾「#18 A SQL 留档」），需在 NAS 上由用户执行（本机无 docker/SSH）。 | 2026-09-25 |
| 19 | `/status` 对"无队列行的收藏"与"未收藏"返回同一份 null 体 | `docker/api/favorites.py:196-247`（`get_favorite_status` 无行分支 `{"status": None, "favorite_id": None, "download_status": None}`） | ⏳ 待处置 (Pending) | 问题：该端点按 `favorite_downloads` 取数，因此"收藏存在但无队列行"（如 #18 那 8 条）与"从未收藏"返回**完全相同**的 JSON，调用方无法区分两种业务状态。现状影响：第三轮 #16 已删除前端唯一调用方 `getFavoriteStatus`，仓内**零消费方**（`Select-String` 全库仅剩定义处与文档），当前无实际损失，属 API 语义缺口。**处置方案（二选一，需用户确认外部是否有仓外调用方）**：①**删除该端点**（零消费方，最干净）；②保留但加 `favorited: bool`（取自 `user_favorites`）使两态可区分。默认倾向 ①。 | 2026-09-25 |

### #18 A SQL 留档（容器内执行，不入代码库）

执行前先备份（宿主机 compose 目录内，`./data/pilotstd.db` 即容器 `/app/data/pilotstd.db`）：

```bash
cp ./data/pilotstd.db ./data/pilotstd.db.bak-$(date +%Y%m%d-%H%M%S)
docker compose exec pilotstd sqlite3 /app/data/pilotstd.db
```

补建 SQL（幂等：`NOT EXISTS` 去重，`UNIQUE(favorite_id, record_id)` 兜底，可重复执行）：

```sql
INSERT INTO favorite_downloads
  (favorite_id, user_id, record_id, status, standard_no, standard_name, standard_type,
   retry_count, created_at, updated_at)
SELECT f.id, f.user_id, f.record_id, 'pending',
       COALESCE(f.standard_number, 'UNKNOWN_' || f.record_id),
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
