# 技术债登记

> 版本：v1.6.0
> 更新日期：2026-09-26
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)
> 2026-09-26 收尾轮（monitor 计数误导）：**TD-30（原 #30）已清理**——`pilotstd/monitor/scheduler.py::_on_file` 此前只调 `scan_directory`（仅解析文件名、不搬文件、不写 `file_index`）却照记 `success`：`monitor.auto_archive` 开关与「文件就绪后触发自动归档」的注释**从未有过实现**（`git log -S 'archive_standards' -- pilotstd/monitor/scheduler.py` 为空）。现补上归档（复用统一入口 `archive_standards`，非第二套实现）并改按**真实归档结果**计数（`moved>0` 才记成功；解析不出或归档报错记失败；一条没搬不计成败）；与 TD-28 零重叠（延迟回调先判 `os.path.exists`，链路已搬走的文件根本不会触发回调）。验证：单元 6 例 + 集成真跑 4 例，`git stash` 反证 **8 failed**；至此「一、已清理」共 15 行。
> 2026-09-26 第八轮（四线并行）：① **#11 G-010 警告区治理执行完毕**——警告区 **8 → 3**、最高有效行 **487 → 438**（拆 5 个文件，见本条台账）；② **#15 通知聚合器实例不共享** 转最终判断；③ **#16 两个死列** 删除（新增 v60 迁移）；④ **#19 `/api/favorites/{id}/status` 端点存废** 按 `[STATUS_API]` 日志实测 UA 分布定案。各线独立分支、独立提交、独立验证。
> 2026-09-26 第七轮（两条线并行：前端 CI 缺陷 + #17a 到期偿还）：
> ① **前端 CI 缺陷已修**（非"偶发"）：`primevue/tablist/index.mjs:48-53` 在 `mounted()` 排的 150ms ink-bar 定时器无句柄、`unmounted` 不清理，测试文件在 150ms 内结束时回调落在 jsdom 全局被摘除之后 → `ReferenceError: HTMLElement is not defined`（unhandled → `Tests 230 passed` + `Errors 1 error` + exit 1）。修法：`web/src/test-setup.ts` 接管 `setTimeout` 登记未触发句柄，文件级 `afterAll` 清理；连跑 10 次 `Errors 0 / exit 0`。详见「八、操作记录 8.6」。
> ② **#17a 已偿还并移入「一、已清理」**（TD-23）：8 处停止入口对应 7 类 worker 全部加中断检查点（抛 `WorkerAborted` 终止底层流，而非仅跳过信号发射）；中断延迟实测 scan 14ms / query 6ms / 暂停中 query 60ms / DriveEnumerator 54ms（修复前四者均 ~5s 超时 + 保活计数 +1）。残留的单条网络阻塞窗口登记为「六-B 观察项」。
> 2026-09-26 第六轮（技术债收尾：验证 → 消除 → 记录）：① **#18 巡检改走公开 API 复核**——`GET /api/favorites/export?format=json` 无分页截断（导出行数 105 == 库内行数 105），A/B/C 三组的 `user_favorites` 维度可本地算得全 0；`favorite_downloads`/`announcement_record`/`download_queue` 三表列**未在任何公开端点暴露**（`favorites.py:341-346` 只给 4 个下载字段），其维度仍经 `POST /query` 取证，结果同为 0。② **#11 紧急项已还**：`scripts/check_g_012_sql_schema.py` 有效行 **497 → 139**（拆出 `scripts/_sql_schema_parser.py`），`docker/auth.py` **490 → 394**（拆出 `docker/_static_token.py`）；G-010 警告区 **10 → 8**，最高 487。③ **#15 现状更新**（`StandardManager()` 构造点实测 **9 处**）。④ **#21 新登记**；`docs/deployment/README.md` 过时内容已更新。⑤ 第五节 5 条已接受设计补齐审计轨迹。
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
| **TD-18** 8 条收藏无队列行 + 36 行 `standard_number` NULL | 原 #18。**修复（2026-09-25 现场）**：补建 8 行队列（`INSERT rowcount=8`、`missing=0`、全 `pending`）+ 纠正 36 行 NULL（`uf updated=36`、`uf_null_after=0`、`fd_unknown_after=0`）+ 显示层改"未加入队列" + 导出加 `COALESCE(f.standard_number, r.standard_number, '')`。现场复核：导出 105 条 0 空值、页面 8 条"已入队"。**只读巡检已完成（2026-09-25，经 `POST /query` API 执行）**：A 组 4 项（uf/fd 标准号与名称空值、`UNKNOWN_*`）全 0；B 组 4 项（四表 `standard_type` 空值）全 0；C 组去重基线 0 行 → **无其他同源回填缺口，本条彻底关闭**。**勘误**：第三轮曾判断"`favorite_downloads` 不在 admin SQL 白名单 → 只能容器内 SQL 修复"，经查 `admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**，SELECT 不受表限制 → 该判断不成立（数据修复本可经 API 完成）；SQL 与巡检语句留档见「八、操作记录」。**2026-09-26 公开端点复核（第六轮）**：`GET /api/favorites/export?format=json` 返回 **105 行 == 库内 `user_favorites` 行数**（接口 SQL 无 LIMIT/分页，`favorites.py:453-470`）→ 全量性成立；本地分组算得 A 组 `uf_std_no_null/empty = 0`、`uf_std_name_null/empty = 0`（键名 `std_name`，来自 `announcement_record`）、`uf_std_no_UNKNOWN_ = 0`；B 组 `uf_std_type_empty = 0`（105 条全 `NationalStd`）；C 组 105 组、**重复组 0**。`favorite_downloads`/`announcement_record`/`download_queue` 三表列**未在任何公开端点暴露**（`_DOWNLOAD_FIELDS` 只有 status/error/last_attempt/updated_at），其维度仍经 `POST /query` 取证：fd 标准号/名称空值、`UNKNOWN_*`、fd/ar/dq 分类空值**全 0** | 2026-09-25 |
| **TD-23** 原 #17a —— worker 阻塞点可中断上限 | 原 #17a（登记 2026-09-23，偿还窗口"最迟第六轮"，第七轮补还）。**根因**：停止信号只让回调"闭嘴"（`if self._stopped: return`），底层 `manager.*_stream()` 循环并不知道要停，仍会跑完全部条目 → `stop_worker_gracefully()` 等满 timeout → 只能保活（#17b 已接受的代价）。**改动**：① `pilotstd/ui/workers/_common.py` 新增 `WorkerAborted` + `check_stop()`（`stop()` 或 `requestInterruption()` 置位即抛）+ `wait_pause_or_abort()`（暂停等待改 200ms 切片，原无超时 `wait()` 在暂停中必然卡死）；② 7 类 worker 的逐条回调（scan/query/download/archive/normalize/announce/auto）全部改为"在检查点抛异常终止流"，而非仅跳过发射；`AutoWorker` 四阶段回调共用同一组检查点（原为无任何停止检查的 lambda）；`ArchiveWorker` 的磁盘预扫描循环、`DriveEnumerator` 的逐盘循环也加检查点；③ 各 worker 增加 `except WorkerAborted` 分支（不误报 error 信号），`finally` 的收尾信号加 `isInterruptionRequested()` 守卫；④ `WorkerAborted` **刻意继承 `BaseException`**——服务层有"单条失败继续跑"的兜底（`manager/facade/_organize.py:106-123` 把 `on_result` 包在 `try/except Exception` 内），继承 `Exception` 会被吞掉导致中断失效；已加专门回归用例（`_ExceptionSwallowingMgr` + `test_abort_survives_service_layer_except_exception`）。`AutoWorker._emit_scan_batch` 同步改为"停止即抛"契约，`tests/gui/test_coverage_workers.py::test_emit_scan_batch_when_stopped` 由"断言不发射"更新为"断言抛 WorkerAborted"（删方法时漏扫测试导致全量 GUI 首轮 2 failed，已修）。<br>**验证（量化验收）**：假 stream（20000 条 × 10ms，不中断需 200s）逐条回调，中途 `stop_worker_gracefully(timeout_ms=5000)`——**修复后**：scan **14ms**（0.3% 预算）、query **6ms**（0.1%）、暂停中 query **60ms**（1.2%）、DriveEnumerator **54ms**（1.1%），四者 `退出=True`、保活计数增量 **0**、残留 **0**；**修复前对照**（`git stash` 掉改动）：四者分别 **5035 / 5009 / 5010 / 5055ms**、`退出=False`、保活计数各 **+1**，并触发 error 级"疑似卡死线程"告警（累计超时 4）。单测：`tests/gui/test_worker_lifecycle.py` 新增 4 例（scan/query 参数化、暂停可中断、盘符枚举）→ 该文件 10 passed。窗口达标情况见「六-B 观察项」（单条网络请求/大文件 IO 内部仍不可中断，受既有 timeout 约束）。 | 2026-09-26 |
| **TD-22** G-010 高危文件拆解（#11 紧急项） | 编号说明：台账 **#21** 已占给"下载链验证码"，故本条取 TD-22。<br>**A**：`scripts/check_g_012_sql_schema.py` 有效行 **497 → 139**——SQL 文本解析层（`SQL_KEYWORDS`/`PYTHON_BUILTINS`/`_SQL_FUNCTIONS` + 13 个纯函数）整体搬到新模块 `scripts/_sql_schema_parser.py`（470 行 / 370 有效行），脚本以 `from _sql_schema_parser import ...` 复用。<br>**B**：`docker/auth.py` 有效行 **490 → 394**——静态令牌管理（`_STATIC_API_TOKEN`/`_STATIC_TOKEN_INITIALIZED` + `_ensure_static_token_in_db`/`get_static_token`/`refresh_static_token`）搬到 `docker/_static_token.py`（125 行 / 105 有效行）。调用方：auth.py 只 import 其仍内部使用的 `_ensure_static_token_in_db`；唯一外部调用方 `docker/api/settings.py:13` 改为直接 `from .._static_token import get_static_token, refresh_static_token`（**仓内全量 grep 确认无第二处引用**）。曾试"在 auth.py 冗余别名再导出"，但 ruff isort 会把纯再导出拆成 3 条 import（+2 行、且更难看），故改为直接引用新模块。<br>**搬移方式**：程序化按行区间提取（`C:\Temp\pilotstd-probe\split_g012.py` / `split_auth.py`），函数体逐字节未改，仅新增模块 docstring 与 4 条中文说明注释。<br>**验证**：①`python scripts/check_g_012_sql_schema.py` 前后自身输出**逐行一致**（清洗 shell 噪声后各 36 行，diff 为空）且 PASS（0 处不一致 / 73 条 SQL）；②G-010 警告区 **10 → 8**，最高 487，无文件 ≥490（auth.py 已退出警告区）；③ruff 全绿；④mypy `docker/` 单目录错误数前后同为 5（源文件 47→48）——注意 G-038 的**合并口径**（`pilotstd/ docker/` 一起跑）实测 `Success: no issues found in 385 source files`；⑤`tests/test_core.py` 107 passed、auth 相关 6 文件 **73 passed**；⑥`check_all.sh --fast --guards --local` EXIT=0 / 0 FAIL。（过程中唯一回归：新模块注释密度 1.9% < 3% 触发 G-012 注释密度 FAIL → 补"为什么"注释后 PASS） | 2026-09-26 |
| **TD-16 残留** `user_favorites` 两列死列 | 原 #16 残留（登记 2026-09-25）：`archive_retry_count` / `last_archive_attempt` 的唯一读取方是 `/api/favorites/{record_id}/status` 的 5 个旧响应键，随 #16 删除后零读取（`pilotstd/` + `docker/` grep 排除 `_migrate_*` 后 0 命中），但受 P-106（已执行迁移源码不可变）约束不能改 v52/v59 就地删列，故挂到清理项。**修复（2026-09-26）**：新增 v60 迁移 `pilotstd/core/db/_migrate_v60_drop_favorite_retry_columns.py` 幂等 `ALTER TABLE user_favorites DROP COLUMN`（先读 `PRAGMA table_info`，表不存在/列不存在均安全跳过；删列本身失败时降级为 WARNING——两列零读取方，留下的代价只是 schema 未收敛，而抛异常会让 `_run_migrations()` 直接阻断应用启动），`CURRENT_SCHEMA_VERSION` 59 → 60。**验证**：①**真库级**（`sqlite 3.50.4`，脚本 `C:\Temp\td16_v60_verify\verify_v60_real_sqlite.py`，4 段全 PASS）——v59 形态库（2 行数据 + `idx_user_favorites_user_id/status/record_id`）迁移后两列消失、行数与其余列值**逐值不变**、三索引保留；二次打开 + 直接重复调用迁移函数零副作用；无 `user_favorites` 表的库打开不抛异常；全新建库跑完 v0→v60 链无两列；②`tests/test_migrate_v60.py` **10 passed**（含"生产代码零引用"回归护栏与降级路径用例），`tests/test_migrate_v59.py`+`tests/test_migrations_full.py` **101 passed**（v59 语义不变）；③`check_schema_consistency` **EXTRA=0 / MISSING=0**（同步清理 3 处镜像生产的测试 fixture，两处历史 fixture 改由等价 `ALTER` 构造）；④`ruff` / `mypy` 全绿 | 2026-09-26 |
| **TD-19** `/status` 两态不可区分 | 原 #19。**修复（方案②，2026-09-25）**：保留端点 + 新增 `favorited: bool`（三态可辨）+ `[STATUS_API] ua/referer/path` 防御性日志（脱敏、无查询参数）。现场 v0.110.0 实测：有队列行 8 键 `favorited=true`、补建行 8 键 `favorited=true`、未收藏 4 键 `favorited=false`；日志实测 `ua=[redacted]`（敏感词整段脱敏）且无 `?`。**端点存废复评已移入「六、待决策」**（最终决定见 **TD-24**，端点已删除） | 2026-09-25 |
| **TD-24** `/api/favorites/{record_id}/status` 端点删除（#19 最终决定） | 原 #19 残留（「六、待决策」第一行，最迟第七轮）。**决定：删除**——现场日志实测**零仓外调用方**。**取证**（只读，2026-09-26）：镜像 v0.110.2；`GET /api/admin/logs/app`（admin，`docker/api/logs.py:106-122`）+ `GET /api/logs/rotated/{f}`（admin，`docker/api/logs.py:284-298`，分页读全）共读 **48428 行**，覆盖 `app.log.10` 起 **2026-09-02 11:00 → 2026-09-26 15:36**（连续无空洞）；`[STATUS_API]` 命中 **7 次**，全部落在 **2026-09-25 21:48:46～21:49:23** 同一窗口 → **UA 分布：`python-requests/2.34.0` 3、`PilotStdProbe/1.0` 2、`[redacted]` 2；referer：`http://192.168.1.18:9028/favorites` 4、`-` 3；path 全为 `/api/favorites/*/status`**。三类 UA 全为本项目自己的排查探针（`[redacted]` 是 2026-09-25 脱敏验证用 curl 探针，命中 `_SENSITIVE_MARKERS` 被整段替换），**无 curl（非探针）/扫描器/未知 UA**。**对照实证**：现场对该端点发 **1 次只读 GET**（UA `TD19-Control-Probe/1.0`）→ 200 且 app.log 中 `[STATUS_API]` 计数 7 → **8**，证明"日志机制真的生效"，即上述零命中不是日志失效造成的假阴性。**改动**：删路由 `docker/api/favorites.py`（原 222 行）+ 防御性日志辅助代码（`_log_status_api_call`/`_sanitize_header`/`_SENSITIVE_MARKERS`）+ 未再使用的 `Request` 导入；删契约测试 3 类 12 例与仅其使用的 `_FakeRequest`/`_fakeURL`/`_fake_request` 替身；`web/src/api/announce.ts` 清掉 #16 遗留的说明注释；`docs/architecture.md` 端点表删该行、v59 注记标注端点已删；`docs/testing/known-issues.md` #6 状态改「已关闭」。**证据局限**：轮转上限 10 个文件，`2026-09-02` 之前的日志已轮转丢失；窗口内有 11 天空档（`app.log.8` 起于 09-10 11:26，前一段未覆盖）——但 `[STATUS_API]` 日志自 2026-09-25 才随 v0.110.0 上线，窗口完整覆盖其全部存在期，故空档不影响结论。**残留（不擅自改，单独报告）**：`pilotstd/core/db/_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 仍称"两列的读取方是收藏状态接口"——该 docstring **在 `norm_checksum` 覆盖范围内**（实测 `raw != norm`），改动会触发 `DatabaseError: 迁移 v59 的脚本逻辑已变更`（`_migration_checksum.py:109-115`），受 P-106 约束不可改 | 2026-09-26 |
| **TD-25** 查询适配器重复加载证书包（原 #22） | **修复（2026-09-26）**：新增 `pilotstd/query/adapters/_shared_ssl.py`（进程级单例 `default_ssl_context()`，加锁保证首次只加载一次）；9 个默认校验的适配器改为 `httpx.Client(verify=default_ssl_context(), ...)`；`energy` / `sppt` / `sppt_local` 三处自签名站点**保持 `verify=False`** 不动。**根因**：httpx 对 `verify=True`（默认）的**每个** Client 都调 `ssl.create_default_context()` → `load_verify_locations()` 重新解析加载整份证书包（本机单次 ≈1.3s，cProfile 占 96.5%）。**验证**：`StandardManager()` 构造中位 **6.742s → 0.036s**（各 5 次；改后 min 0.035s，首次 0.233s 为一次性证书包加载，目标 <1.0s 达成）；查询适配器相关 8 个测试文件 **270 passed**；ruff/mypy（390 files）全绿；`check_all.sh --fast --guards --local` EXIT=0；文档同步：`docs/architecture/modules/query.md` 新增「HTTP 客户端与 SSL 复用」节（G-031 block 映射） | 2026-09-26 |
| **TD-26** 下载链无读者文档 + G-031 缺口（原 #24） | 原 #24（登记 2026-09-26，偿还窗口"最迟第十轮"）。**根因**：① `docs/` 下无描述 openstd 下载流程的现行文档——#21 修复（`532d994f` + `62fba6ef`）的三个变化点（hcno 权威来源＝openstd 搜索页、端点族 `/bzgk/std/*`、新增「全文下载页」`showGb?type=download`）只存在于代码 docstring 与台账 #21 行；② G-031 的 `DOC_SYNC_MAP` 不含 `pilotstd/download/`，该目录改动**不触发**文档同步检查。<br>**修复（2026-09-26）**：① 新建 `docs/reference/download-pipeline.md`——hcno 权威来源（搜索页逐行 `showInfo('<hcno>')`；**禁用 std_gov 的 pid**，实测 `newGbInfo?hcno=<pid>` 与空/损坏 hcno 响应**逐字节相同**，sha1 `b93e289a82d884a4`、18610 字节）、端点族 `/bzgk/std/*`（旧路径 301 → `requests` 对 POST 的 301 **退化为 GET、body 丢失** → `verifyCode` 恒被拒）、完整步骤链（详情页 → 全文下载页 → `gc` → OCR → `verifyCode` → `viewGb`，含代码行号）、`_VIEW_ROUNDS = 2` 的轮次语义（只在"验证码通过但 viewGb 取到 0 字节"时用第二轮；OCR 失败不消耗轮次）、历史事故与防回归测试清单；② `DOC_SYNC_MAP` 补 `("pilotstd/download/", "docs/reference/download-pipeline.md", "block")`（映射 11 → 12，无死映射）；③ 更正三处陈旧描述——`docs/testing/下载适配器测试方案.md`（头改 openstd + `/bzgk/std/*`；删掉**不存在**的 `tests/manual_test_download.py`（`Test-Path` = False，随 `3d16d662` 删除）改为 `pytest tests/download/adapters/test_openstd_download.py` + 手工核对清单）、`docs/testing/testing-baseline.md:37/59`（"待 P4 步骤1 / 方案锁定（待实现）"→ 已实现，依据 `openstd_download.py:175-256`）、`docs/guides/人工测试方案.md:127`（"日志为 `viewGb`（非旧 `showGb`）"→ 先走 `showGb` 全文下载页再 `viewGb` 取文件）。<br>**验证**：① **受控功能测试**（TD-13 同款）——仅暂存 `pilotstd/download/adapters/openstd_download.py` 末尾一行临时注释 → `python scripts/check_g_031_docs_sync.py` **FAIL**：`[G-031] FAIL: pilotstd/download/ 已变更，但 docs/reference/download-pipeline.md 未同步更新`、`EXIT=1`；`git restore --staged` + 还原文件后 `git status` 干净、脚本回到 `PASS: 无变更文件` / `EXIT=0`；② `python -m pytest tests/download/adapters/test_openstd_download.py -q` = **43 passed**（含 `test_query_result_pid_is_not_used_as_hcno` / `test_search_row_number_must_match` / `TestEndpointPathGuard` 三个契约测试）；③ 连带同步 `docs/governance/gates.md`（新增 v1.19 版本行 + G-031 映射条目 + 11→12 计数）与 `docs/governance/README.md`（gates.md 状态 v1.18→v1.19），并重跑 `scripts/generate_capabilities.py`；④ `ruff` / `mypy` / `check_all.sh --fast --guards --local` 全绿。**残留（不擅自改）**：`docs/governance/gates.md:234` 的 v1.16/v1.15 两行版本历史挤在同一行（缺一个行首 `|`，属既有格式缺陷，与本次改动无关） | 2026-09-26 |
| **TD-27** 迁移 checksum 自愈判定使 P-106 失效（原 #28） | **修复（2026-09-26）**：`pilotstd/core/db/_migration_checksum.py` 的自愈判定由「**当前源码** `raw != norm`」改为「**存储值 == 当前 raw**」——只有库内存的正是当前 raw 哈希（历史 raw 口径、源码未变）才 WARNING + 自愈为标准值，其余一律视为真实源码变更 → `DatabaseError` 阻断启动。**改前行为**：`norm_source()` 去缩进使任何带缩进函数恒有 `raw != norm`（实测 **59/59**）→ **任何**不匹配（含真实逻辑改动）都静默自愈、只记 WARNING，抛错分支不可达（P-106 名义生效、实际失效）。**改后行为**：① 存储值 == 标准化值 → 通过（注释/空行变化不改变标准化值——实测对注入 `#` 注释不敏感）；② 存储值 == 当前 raw → 自愈（WARNING + UPDATE）；③ 其余 → **DatabaseError 阻断启动**。**可达性证据（永久保留）**：新增 `tests/test_migration_checksum_guard.py` **6 例**，其中 `test_logic_change_raises_database_error` 断言「库内是旧逻辑的标准化哈希 + 当前源码逻辑已变」必抛错；实测原始 traceback：`DatabaseError: 迁移 v1 的脚本逻辑已变更，checksum 不匹配` @ `_migration_checksum.py:121`。`tests/test_core.py` 两条旧测试同步改写（`test_checksum_mismatch_auto_heals` → `test_checksum_legacy_raw_hash_auto_heals`，因为旧断言固化的正是本债的错误行为；`test_checksum_real_change_raises` **去掉 mock**，改用真实迁移直接触发）。**验证**：迁移+守卫相关 5 个测试文件 **222 passed**；ruff 全绿；mypy `Success: 390 files`；门禁 EXIT=0。 | 2026-09-26 |
| **TD-28** 收藏链归档期依赖周期机制 → 必然「归档超时」（原 #29） | **修复（2026-09-26）**：`pilotstd/tasks/favorite_download.py` 新增 `_archive_inbox_file()`——下载落 inbox 后**由链路自己**按**规范标准号**解析 → 交给 `archive_standards`（organizer 搬文件进标准库并 upsert `file_index`）→ 再走原有索引轮询复核；超时文案改为「文件未被归档器登记进索引（+ 归档错误原文）」。**根因（比登记时更严重）**：**没有任何调度会归档 inbox**——`auto_scan` 只 UPDATE `standards` 表（不碰 inbox）；monitor 的 `_on_file` 只调 `scan_directory`（仅解析文件名、不搬文件、不写 `file_index`，却照计 success 计数，现场 `processed_today=6 / success_today=6` 即由此而来；该计数误导与缺失归档已由 **TD-30** 修复）→ 因此等多久都不可能成功（候选「延长窗口/调调度顺序」均被证伪）。**关键口径坑**：不能用被 `_safe_filename` 转义过的 inbox 文件名解析——实测 `GB_T 5613-2026_x.pdf` → `logical_code='GB'`，而规范口径是 `'GB/T'`；用错会让「归档写入口径」与「链路查询口径」不一致、永远查不到。**改前行为**：下载成功也必然在 +60 秒判 failed（现场 6/6 复现：`收藏归档超时: favorite_id=2/1/4/3/5/106`，各在对应下载时刻 +60s）。**改后行为**：归档同步完成 → 索引命中即 `done`（不再依赖周期机制）。**验证**：① 单元 4 例（归档被调用且 `source_path` 指向 inbox 文件 / 归档异常与标准号不可解析时原因进 `error_message` / 索引已有则跳过下载与归档）；② **集成真跑端到端**（真实下载引擎 → 真 inbox → 真归档搬库 → 真 `FileIndexRepository` → 真 `_find_in_file_index` 命中 → `done`、`local_path` 指向库内、inbox 清空）；③ 契约测试固定解析口径（含「用转义文件名会退化成 GB」的反证）；④ 相关 5 个测试文件 **101 passed**；ruff/mypy 全绿；门禁 EXIT=0。**现场闭环待下次部署**（本轮按指示只做本地验证）。 | 2026-09-26 |
| **TD-29** 收藏下载链 GB 类成功率 0（`verifyCode` 恒被拒，原 #21） | **修复（2026-09-26）**：① 下载链三处流程修正（`532d994f` + `62fba6ef`）——hcno 权威来源改为从 openstd **搜索页**按标准号逐行解析（**禁用** `std_gov` 的 pid）、端点族 `/bzgk/gb/*` → `/bzgk/std/*`（旧路径 301 使 POST 退化 GET、body 丢失）、新增「全文下载页」步骤（`showGb?type=download`；缺该步时 `viewGb` 返回 200 但 0 字节）；② 归档环节见 **TD-28**。**现场验证（v0.111.2 / `ba3cb65b`，解冻后临时以 `* * * * *` 触发一轮）**：下载 **6/6 成功**——`verifyCode 结果: success` ×6（另 1 次 error 后第 2 次尝试成功）、`viewGb 第1轮取到全文` ×6、字节数 251074 / 528280 / 483415 / 470971 / 381418 / 376488、hcno 全为**搜索页实时解析值**（如 GB/T 2970-2026 `44C04018C3C0E40BE28E19DA0510F24B`，与 09-26 04:00 失败时不同）；全日志 **0 次** `301` / 缺 `showGb` / `0 字节` 痕迹 → 本条原始症状「`verifyCode` 恒被拒、成功率 0」**不再成立**。**遗留**：当时 6/6 在 +60 秒归档超时（已由 TD-28 修复并本地真跑验证；其**现场闭环待下次部署后确认**）。 | 2026-09-26 |
| **TD-30** monitor `_on_file` 从不归档却照记「成功」（原 #30） | **修复（2026-09-26）**：`pilotstd/monitor/scheduler.py::_on_file` 补上归档并改按**真实归档结果**计数——解析（`scan_directory`）→ 交**统一归档入口** `archive_standards(scanned, word_source_root=<inbox 目录>)` → `moved>0` 才记 `success`；解析不出标准号或归档器报 `failed>0` 记 `failed`；一条都没搬（源已不在/目标已存在/条目待确认）**不计成败**；`success` 不再是"文件名解析出来了"。<br>**根因（两条并存，代码实测）**：① **归档从未实现**——配置项 `monitor.auto_archive`（默认 `true`，`monitor/config.py:15` 且 `set_config` 可写）、类注释「文件就绪后触发自动归档」（`scheduler.py:54`）、日志「自动归档已禁用，跳过」三处都在描述归档，但函数体只调 `scan_directory`（**仅解析文件名**：`manager/facade/_scan.py:31-96` 不搬文件、不写 `file_index`）；`git log -S 'archive_standards' -- pilotstd/monitor/scheduler.py` **输出为空** → 自模块引入（`a11a23c7`）起从未调用过归档。② **计数语义错**——`success` 在"解析到 ≥1 条"时 +1，而前端把它显示为「成功」（`web/src/components/FileMonitor.vue:153` `{{ processed_today }} (成功 {{ success_today }} / 失败 {{ failed_today }})`）→ 面板谎报健康。<br>**现场证据**：`processed_today=6 / success_today=6`，而 6 个文件全在 inbox、`file_index` 一条都没有（这正是 TD-28 现场 6/6「归档超时」的同一时段）——"看板健康、实际什么都没入库"。<br>**与 TD-28 不重叠（实测依据）**：`handler.py:54-61` 的延迟回调在 5 秒稳定期后**先判 `os.path.exists(path)`**，而收藏链在下载返回后**立即**归档 → 文件已被链路搬走时回调根本不会触发；故 monitor 只在"文件 5 秒后仍留在 inbox"时动作，即链路归档失败或**手工投放**的场景，链路正常路径下零重叠（链路失败时反而成为兜底）。<br>**验证**：① 单元 6 例（真归档→`success`；一条没搬→**不记** `success`；解析不出→`failed` 且不调归档；归档器报 `failed>0`→`failed`；`word_source_root` == inbox 目录；归档抛异常→`failed`）；② **集成真跑 4 例**（真遍历目录 + 真 `StandardParser` + 真搬文件 + 真 `FileIndexRepository`：合规文件**真的**离开 inbox 且索引可查、源根参数正确、不合规文件留在 inbox 且记 `failed`、`auto_archive=false` 时连计数都不动）；③ **反证**（`git stash` 掉 scheduler 改动跑同一批用例）**8 failed** —— 用例确实钉住新行为而非空转；④ monitor 相关 3 个测试文件 **56 passed**；ruff / G-010 / G-012 / mypy（390 files）全绿。<br>**登记说明**：本条此前只在报告里口头提过（"`_on_file` 忽略 `auto_archive`"），**从未写入台账**（「六-B 观察项」5 行中无此行）；本次按用户指示正式编号补登。<br>**残留（已确认，不擅自改）**：monitor 只有**文件名**可用，而被 `_safe_filename` 转义过的文件名会解析成另一个 `logical_code`（实测 `GB_T 5613-2026_000002.pdf` → `'GB'`，规范口径是 `'GB/T'`，同 TD-28 的坑）→ monitor 若归档**收藏链遗留件**，索引会写在 `GB` 键下、链路的 `GB/T` 查询仍查不到（即"兜底"对手工投放有效，对转义名遗留件无效）；要给 monitor 补规范标准号需改侦测逻辑（超出本轮约束），故按现状记录。 | 2026-09-26 |
| **TD-20** `auto_archive_retry` 在 UI 不可改、不可触发 | 原 #20（登记 2026-09-25）。**修复（2026-09-25）**：①`docker/api/settings.py` 抽出 `_SCHEDULED_JOBS`（5 项，与 `scheduler.start_scheduler()` 一一对应）并补 `auto_archive_retry`；②缺键时用**当前配置值**兜底（防前端漏发把链路静默禁用）；③`SettingsTabSchedule.vue` 增加"收藏下载链（自动归档重试）"开关 + cron 输入 + 提示。**同轮自查补漏④**：`GET /api/settings` 原先不返回 `auto_archive_retry_*`——写侧可选、读侧缺失，前端只能拿组件默认值显示，保存时又把该默认值回写，用户改过的值（如 `0 6 * * *`）会被静默改回 `0 4 * * *`；已在读侧补齐两键，并加"读侧键必须与 `_SCHEDULED_JOBS` 对称 + 必须返回存值而非默认值"两例反证测试。**⑤**再补 `pilotstd/core/config/settings_schema.py` 两条 `SettingDef`（`tasks.auto_archive_retry_enabled/cron`）：e2e 字段一致性测试要求 GET 的键必须被前端 Schema 覆盖或进白名单，不注册则 `test_settings_e2e_consistency.py::test_no_unexpected_backend_only_keys` FAILED（实测）。验证：`tests/test_settings_scheduler_sync.py`（**7 passed**：任务表覆盖、scheduler 差异声明、改 cron 真重排、缺键沿用配置、health 默认值不坏、读侧键对称、读侧返回存值）——后两例在补④前用 `git stash` 实测 **2 failed**、补后 PASSED，"scheduler 差异声明"一例用注入假任务实测 FAILED；`SettingsTabSchedule.test.ts`（3 passed：字段存在、保存随载荷提交、加载回填）；`test_docker_api.py -k settings` 2 passed；`test_settings_auth/e2e_consistency/manager` 合计 21 passed；`SettingsView.test.ts` 6 passed。**现场实证（v0.110.0 / `22d4d90b`，修复前镜像）**：`GET /api/settings` 的 `tasks` 实测 8 键、缺 `auto_archive_retry_*`；同镜像 `GET /api/scheduler/status` 显示该任务已注册（next_run 04:00）；对照组 `date_reminder_cron` 现场值 `0 8 * * *` ≠ Schema 默认 `0 2 * * *` → 用户确实会改这些值，读侧缺键＝改过的值会被静默覆盖（不是理论风险）。**⑥契约细化**：现场 `GET /api/scheduler/status` 共 **6** 个 cron 任务（多一个 `auto_backup`），故 ① 里"与 scheduler 注册表一一对应"的说法不准确——`_SCHEDULED_JOBS` 只覆盖**用户可管**的 5 项，`auto_backup`（固定周日备份、无 UI 开关）为**有意排除**；新增 `test_scheduler_jobs_not_in_settings_are_intentional`：**AST 解析** `docker/scheduler.py::start_scheduler()` 的注册表，断言"未暴露的差异集合 == {auto_backup}"（注入 `fake_probe_job` 实测 **FAILED**、撤销后 PASSED）——旧测试只比对写死名单，scheduler 新增任务也不会失败，改后"漏登记"与"有意排除"才真正分得开。**部署状态（2026-09-26 00:00 实测）**：修复已随镜像 **v0.110.2** 发布（CI 全绿：`version`/`docker` job 均 success，bump 提交 `2719691b`），但**现场 `192.168.1.18:9028` 仍为 v0.110.0 / `22d4d90b`（读侧 8 键）**——该主机不会自动拉取（`docker/api/system.py:152` 的 `POST /api/system/update` 是管理员手动触发的 pull + compose 重建，无定时任务），故"读侧 8→10 键"需**部署后**复核。**✅ 部署后复核通过（2026-09-26 09:32 实测，v0.110.2 / `c421c572`）**：`/api/system/version`=0.110.2、`/api/health` build=`c421c572`；`GET /api/settings` 的 `tasks` **10 键、缺键 0**，`auto_archive_retry_enabled=True` / `cron='0 4 * * *'` 与 `/api/scheduler/status`（next_run 2026-09-27 04:00）一致——读写两侧闭环。**UI 现场复核（Playwright，v0.110.2）**：设置页「定时任务」出现"收藏下载链（自动归档重试）"行、开关为开、cron 输入框 `0 4 * * *`，且页面回填值 == 后端 `GET /api/settings` 值（截图留档 `C:\Temp\pilotstd-probe\shots\settings-schedule.png`，探针不入库）。**残留**：无"立即执行一次"按钮 → 记为可选增强（临时把 cron 改成 `* * * * *` 即可触发，等价覆盖），不进台账 | 2026-09-25 |


**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（只放"未清"的债）

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|------|------|------|------|--------------------------------------|---------|
| 11 | **ROI 判断** | G-010 警告区文件（拆分收益低于成本） | 见下方"现状"列出的 **3** 个文件 | ✅ 已偿还（第八轮执行完毕） | **根因**：历史累积复杂度进入 400-500 行警告区；集中拆分 ROI 低于组件碎片化风险。**现状（2026-09-26 第八轮实测 `check_g_010_code_size.py`）**：警告区 **8 个 → 3 个**，**最高有效行 487 → 438**（全部 < 450，距 500 阻断线余 **62** 行，无阻断风险）。本轮拆掉 5 个文件（原文件 → 新模块，均为逐字节搬移 + 调用点/文档同步）：`docker/api/announce_detail.py` **454 → 372**（拆出 `_announce_detail_parse.py` 92 行）；`scripts/check_g_012_comment_density.py` **457 → 311**（拆出 `_comment_lang_data.py` 159 行，仅搬数据表、逻辑零改动，用同一份 464 文件清单对照跑出**逐行一致**的 80 行输出）；`pilotstd/core/notification/_builders_batch.py` **477 → 287**（拆出 `_builders_task_results.py` 205 行，切口处 AST 实测无共享模块级符号 → 无反向依赖）；`pilotstd/core/notification/manager.py` **487 → 383**（拆出 `_manager_ops.py` 136 有效行的组合式 `NotificationOps`；首版用 Mixin 被 `tests/test_architecture_mixin_guard.py` 拦下——该守护测试禁止新增 Mixin、指定 Composition，随后改为 `self.ops.*` 并同步 7 处外部调用点）；`web/src/views/AnnounceDetail.vue` **487 → 314**（拆出 composable `useAnnounceDetail.ts` 234 行，模板/样式未改）。剩余 3 个：`pilotstd/core/db/_migrate_v16_v49.py:438`、`web/src/components/AppLayout.vue:434`、`web/src/components/NotificationConfig.vue:425`。**验证**：ruff 全绿；mypy 合并口径 `Success: 388 source files`；后端 270+333 tests、前端 231 tests 全过；`vue-tsc --noEmit` 零错误；每批 `check_all.sh --fast --guards --local` EXIT=0；G-031 连带文档（core.md / gates.md / README.md）与能力矩阵均已同步。**偿还窗口**：**不适用（已偿还）**。**触发式规则保留**：任一文件触及 **490** 行 → 当轮必拆；新文件新写入即受 500 行阻断档约束。**不还的代价（已消除）**：原先 5 个文件距阻断线最窄仅 13 行，任何小改动都可能撞线导致 CI 阻断；现最窄余 62 行。| 2026-08-23 |
| 15 | **ROI 判断** | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`core/notification/manager.py:118-135`（`_aggregate_enabled` 为真时在实例内新建）；管理器创建点：`core/notification/manager.py:87`（`NotificationManager.__init__`）；门面创建点：`manager/facade/_base.py:87`（`BaseFacade.__init__`）→ `:250`（`_init_services` 内新建）、`:271`（`_init_notification` 配置变更重建，调用方 `docker/api/notification.py:133`）；**`StandardManager()` 构造点本轮 AST 重测 = 生产 12 处 + 测试 22 处**：`docker/manager.py:16`、`cli/commands/_shared.py:19`、`core/task_status.py:76`、`monitor/scheduler.py:146`、`services/favorite_chain_processor.py:164/307`、`tasks/date_reminder.py:141`、`tasks/favorite_download.py:137/165/194/306`、`ui/main_window/parts/_actions_ops.py:49`；测试 `tests/test_manager.py`（20 处）、`tests/test_scanner.py:576`、`tests/test_e2e_adapters.py:277` | ✅ 已接受（本轮正式关闭） | **根因**——聚合器生命周期绑在门面上，不是"忘了单例"：`NotificationManager.__init__` 按 `_aggregate_enabled`（`core/config/defaults.py:79` 默认 true）在实例内新建 `NotificationAggregator`（`manager.py:128`），并把 `self._send_now`（绑定方法）作为回调传入；`StandardManager()` 每次都在 `_base.py:250` 新建 `NotificationManager`，故聚合器**每构造一个门面就多一个**。**现状**（本轮实测，代码树 = `62fba6ef`）：① 构造点口径由上一轮的 9 处更正为**生产 12 处 / 测试 22 处**（AST 遍历 `Call.func.id=='StandardManager'`，口径含 `docker/` 与 `cli/`）；② 逐条通知路径**仍在**（上一轮"已消除"的说法需修正）——`tasks/favorite_download.py:282` 的 `notify=False` 只在**批量链路**（`docker/app.py:160` → `services/favorite_chain_processor.py:320 process_chain(notify_per_record=False)`）由源头抑制为"每次运行 1 条汇总"，但 `services/favorite_chain_processor.py:307 _notify_abandoned` 是**无条件逐条**发（`notify` 闸只作用于 `:249` 那处），`favorite_download.py:306` 的独立 `StandardManager()` 每次下载也照建；③ 探针实测（临时探针已删）：连建 2 个 `StandardManager`，`m1.notification_mgr.aggregator is m2...` = **False**，3 次逐条 `send_event` 后**每个实例缓冲恒为 1 条**且无跨实例合并；同一个共享聚合器入队 3 条则缓冲深度 3、`shutdown()` 时 flush **1 次**（成对验证）。**偿还窗口**：**不适用（已接受）**。**不还的代价**（已接受，量化）：① 聚合失效的实测代价≈**0**——生产链路源头按批汇总（一次运行 1 条汇总），Web/定时侧本就持有长生命周期门面（`docker/manager.py:12` 进程级单例；`monitor/scheduler.py:142` `self._mgr` 缓存），仅"每条 abandoned/每次下载失败"这类低频通知退化为**延迟 window（默认 5s，`defaults.py:83`）+ 渠道请求各 1 次**；② "构造开销"经本轮实测**最轻**：`NotificationManager()` 构造（含凭据迁移 + 渠道初始化 + 聚合器）中位 **0.62 ms**（n=5：0.58/0.60/0.62/0.64/0.76，`aggregate_enabled=true`），即每次通知多 ~0.6 ms；门面构造的大头不在聚合器——`StandardManager()` 单次 **8.17 s（中位）**，`cProfile` 显示 **8.18 s / 8.27 s（98.9%）** 落在 `ssl.create_default_context → load_verify_locations`（9 个查询适配器各建一个 httpx client；本机实测裸 `httpx.Client()` ≈ **810 ms**、裸 `ssl.create_default_context()` ≈ **52 ms**），与本条无关，属另一条待登记线索；③ 因此**不还的代价 = 上述 ~5 s 通知延迟 + 每事件 ~0.6 ms + 未来交互型高频通知的限流余量**（历史上 Telegram 429 的 56% 拒收由逐条发送触发，已由源头按批汇总消除，本条不再重复计）。**为何不做单例化（代码级理由）**：聚合器的 `sender_func` 捕获的是**首个入队管理器的** `_send_now` → 闭包其 `_db`/`_ws_broadcast`/`_user_id`/`_channels`；共享聚合器会让"最后入队者"决定全部缓冲消息的收件身份（跨库写 `notification_log`、跨用户发消息）；且缓冲分组键只有 `event_type`（`aggregate_buffer.py:65` `_buffers`），**没有按 `user_id` 分桶**，共享即把不同用户的消息合并成 1 条——这是当前结构刻意避开的用户绑定洞。共享整个管理器又新增状态竞争面：`_init_notification`（`_base.py:271`，`docker/api/notification.py:133` 调用，`tests/test_notification_api.py:86/107` 断言）要求配置变更后拿到**新**管理器，单例后已绑定旧单例的代码读不到新配置。**代价**：12 处生产构造点（8 文件）+ ≥3 个测试文件、22 处测试构造需改，且新引入跨库绑定 + 跨用户合并两类正确性问题。**结论**：**不改**——实测收益≈0、成本高且会引入更严重的正确性洞；未来若出现交互型高频通知，正确方向是核心库层继续不做进程级可变全局，由应用层持有门面生命周期（复用 `docker/manager.py:12` 的应用级门面）让交互路径共享，而非把用户绑定绑在首个入队者身上。 | 2026-09-21 |
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

| # | 决策 | 日期 | 依据 / 根因 | 现状（实测） | 不还的代价（已接受） |
|---|------|------|-------------|--------------|----------------------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | 邮件投递依赖外部 SMTP 凭据与可达性，维护成本高于收益；当时 4 个 IM/Push 渠道已覆盖全部使用场景 | `pilotstd/core/notification/channels/` 仅 `wechat/feishu/dingtalk/telegram` + `base.py`，**无邮件实现**（2026-09-26 实测） | 无法用邮件接收通知；若将来只有邮件可达（如服务器所在网络屏蔽 IM 渠道），通知会全部落空——届时应重新评估解除黑名单 |
| 2 | 静态 API 令牌不支持过期 / 无 TTL | 2026-06-25 / 2026-07-16 确认 | 令牌由环境变量注入、供仓外脚本调用，加 TTL 会引入"脚本半夜失效"的运维面 | 无外部 API 调用场景；令牌落库存哈希（本轮拆出 `docker/_static_token.py`，`api_keys.key_id='pst_static'`） | 令牌一旦泄露即**永久有效**，无法通过过期收敛风险；当前无外部 API 调用场景，代价暂不可见，但一旦对外开放需先补 TTL/轮换 |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 一次性拆分 400+ 行文件会引入大面积行为风险；按"触及即拆 + 到期必拆"分批 | 警告区由 10 个降至 **8 个**（本轮拆 `check_g_012_sql_schema.py` 497→139、`docker/auth.py` 490→394；剩余最高 `manager.py`/`AnnounceDetail.vue` 487） | 警告区文件长期存在，有一次性阻断 CI 的风险（500 行硬线）；代价与偿还窗口见台账 #11 |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | 单文件 >500 行阻断 G-010，且大文件难以定位；Mixin 组合可在不改变对外 API 的前提下切分 | 已产出 12 个 `*_ops.py`（main_window/parts 等）+ 3 个 `_builders_*.py`（notification）；本轮另新增 `_sql_schema_parser.py` / `_static_token.py` 两个"逻辑层"模块 | 拆分后的 Mixin 组合增加一层间接（读代码需跳转 `_xxx_ops.py`），且 `super()`/MRO 顺序成为隐式契约；换来的是单文件可控，代价可接受 |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | 这 5 个文件只做控件构建与信号接线，无业务算法，拆解收益低于碎片化成本 | 实测有效行：`_settings.py` 371、`_file_tree_ops.py` 209、`_export_ops.py` 116、`_theme_ops.py` 109、`_file_dialog_ops.py` 39（均 <400，不进警告区） | 只靠 E2E 兜底、无单元测试；若内部沉淀出业务逻辑而未被发现，回归只能靠 E2E 抓，代价是缺陷定位更慢 |

---

## 六、待决策（不属"债"，等一个决定）

| 项 | 来源 | 现状 | 决策依据 | 最迟 |
|---|---|---|---|---|
| `POST /query`（admin SQL 端点）权限边界过宽 | 2026-09-25 巡检时实测；2026-09-26 第九轮机制复核 + 只读探针实测 | **端点**：`docker/api/admin_db.py:180-182`（router 无 prefix，`docker/app.py:317` 也无 prefix 挂载 → 真实路径就是 `POST /query`；审计标签 `/api/admin/db/query` 是错误字符串，`:176`/`:253`）。**鉴权**：只有 `@require_role(ADMIN_ROLE)`（`:181`）；`/query` 不在 `/api/` 下，被 `docker/auth.py:336-338` 白名单放行 → **完全不经鉴权中间件**：无会话存储校验（`auth.py:407`）、无 CSRF 校验（`auth.py:410-414`）、无 Origin/Referer 校验（`auth.py:387-397`），因此登出/改角色都不撤销。静态 API Key 通道对本端点**无效**。**表白名单**：`_ALLOWED_TABLES`（`:25-34` = standards/favorites/notification_log/task_execution_history/users/user_preferences）**只**在 `DROP TABLE` 分支被引用（`:110-116`，全库 grep 零其他引用点），且名单里的 `users` 反而被允许删除；名单里的 `favorites` 是**不存在的表**（实际是 `user_favorites`，`pilotstd/core/db/_migrate_v31_plus.py:207`）→ 真收藏表不受保护。**读**：SELECT 无任何表/列限制（可 `PRAGMA table_list` 枚举全库 schema）；`LIMIT 1001` 包装（`:126-128`/`:216-217`）只在语句里没写 LIMIT 时生效，截断判定在 `:244-248`。**写**：INSERT 无约束；UPDATE/DELETE 仅要求含 WHERE（`:119-121`，`WHERE 1=1` 即算通过）；CREATE/ALTER 无约束；仅 `DROP DATABASE` 硬拒（`:106-107`），多语句由 sqlite3 单语句限制兜住。**审计**：只落 `audit_logs` 表（`pilotstd/core/audit.py:26-51`），detail 含 **SQL 全文 + params**（`:251-261`），但 `user_id` **恒为 NULL**（中间件在白名单分支 `docker/auth.py:424-425` 提前 return，从未注入 ContextVar）→ **有 SQL、无操作人**；`admin_db.py` 除 `:21` 未使用的 module logger 外无任何日志调用，故 **app.log 零痕迹**（D2 取证结论） | **决定：① 维持现状 —— ✅ 已接受并关闭**（2026-09-26 第九轮）。**接受理由**：① 这是本仓唯一"免 SSH 的运维通道"，且是现场文档明写的既定通道——部署验证 `SELECT MAX(version) FROM _schema_version` 注明"无专门端点，用管理员 SQL 端点"（`docs/deployment/README.md:74-79`/`:101`）；2026-09-25 的补建与纠错（`INSERT rowcount=8` + `UPDATE 36 行`）就是靠它完成（本文档 `:231-250`）；只读巡检中三张未公开表的维度也只能靠它（本文档 `:210-214`/`:262`，公开端点确实不暴露——`docker/api/favorites.py:252-257` 的 `_DOWNLOAD_FIELDS` 只有 4 列，导出 SQL `:364-374` 不含 `favorite_downloads.standard_no`/`announcement_record.standard_type`/`download_queue.*`）。② 选项②按原措辞收益与成本不成比例：SELECT 限 6 张白名单表会**直接打断上面的部署验证步骤**（`_schema_version`/`user_favorites`/`favorite_downloads`/`announcement_record`/`download_queue` 全不在名单内），而名单里的 `users` 又**保留了口令哈希的读取**，安全收益只剩"写"这一半；并且实测证明拦截必须是"**正向仅允许 SELECT**"——黑名单式"禁 INSERT/UPDATE/DELETE"会漏掉 `ATTACH DATABASE`/`VACUUM INTO`/`PRAGMA`/`CREATE`/`ALTER`。③ 管理员对同一库本就有等价能力：容器内 `python -m sqlite3` 可用（本文档 `:188`）且运维者有宿主权限，收紧只抬高本仓运维成本，不改变有宿主权限者的能力边界。**不还的代价（写实）**：**一份有效 admin JWT 泄漏 = 内网内全库读写 + 容器文件系统任意写**——可 `SELECT password_hash, salt FROM users` 离线爆破、`UPDATE users SET role='admin'`、`DELETE ... WHERE 1=1` 批量删、`VACUUM INTO` 导出全库副本、`ATTACH`/`CREATE` 落文件；且**登出或改角色都不撤销**，暴露窗口 = JWT 有效期 **2 小时**（`docker/auth.py:44`）；事后**无法归因**（`audit_logs.user_id` 恒 NULL、app.log 零痕迹）。**已生效的缓解**：仅内网监听、cookie `httponly`+`samesite=strict`（`docker/auth.py:234-241`）、无 CORS 中间件（跨站脚本过不了 `application/json` 预检）、未设 `JWT_SECRET` 时重启即轮换密钥（`docker/entrypoint.sh:6-9`）。**若将来重开**：按"正向仅允许 SELECT + 补全真实全表名单 + 单独开只读端点 + 修审计归因"另立方案并先获批（R-012） | ✅ 已接受并关闭（2026-09-26 第九轮；依据：只读探针 5 组实测 + 仓内 grep 零生产调用方 + **现场 `audit_logs` 只读取证**（该端点不写 app.log，唯一留痕是审计表；2026-09-26 经 `POST /query` 只读查得）：`DB_QUERY` **247 条**、跨度 **2026-08-06 02:14 → 2026-09-26 11:26**、分布 9 天（09-13 64 / 09-26 63 / 08-22 45 / 08-29 33 / 08-06 23 / 08-23 20 …）；SQL 形态**全部为本仓运维/调查类**（`notification_log` 计数、`user_preferences` upsert、`sqlite_master` 读 schema、`standard_info_cache`、`_schema_version`、`user_favorites` 状态统计、`task_execution_history`）；真实写操作仅 3 条 DELETE（2026-08-29 02:37 清理测试收藏 id=37 及其队列行）与 `INSERT OR REPLACE user_preferences`，**无 ATTACH / VACUUM / DROP 的真实调用**（早先形态计数是探针自身 SQL 文本的自匹配，非真实调用）；`user_id` **247/247 全为 NULL** → 有 SQL、无操作人，无法归因到具体调用方，但**无任何外部/异常形态痕迹**） |

---

## 六-B、观察项（不属"债"，登记待观察）

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| 单条网络请求/大文件 IO 内部仍不可中断（#17a 后残留） | 2026-09-26 #17a 偿还时实测 | **根因**：worker 侧检查点只能落在"处理单元之间"（回调/循环体）；`requests` 的单次 `send()` 与 `resp.content` 整块读取无法从外部打断，要中断必须把网络层改为"分块读 + 每块查停止标志"，并把停止标志从 UI worker 一路传到适配器/会话层。**现状**：单条不可中断窗口 = 该请求的超时值——查询/公告 `network.DEFAULT_TIMEOUT = 15s`（`pilotstd/query/network.py:17`）、下载 `viewGb` 显式 120s（`pilotstd/download/adapters/openstd_download.py:114`）、SQLite `busy_timeout=5000ms`（`pilotstd/core/db/database.py:200/211`）。即：worker 现在能在"下一条"立刻停（实测 6–60ms），但若正卡在一条请求里，最坏仍要等该请求超时 | **暂不处理**：15s/120s 都有明确上界，且改动需穿透 UI→服务→适配器三层插入停止标志（ROI 判断），故不挂窗口。**不还的代价**：极端情况下（站点不响应）用户取消后最坏等 15s（查询）/120s（下载单文件）才退出，期间表现为"界面已取消但线程仍在"，不再触发保活/疑似卡死告警 |
| 拆出新模块时注释密度被稀释（G-012 ≥3%） | 2026-09-26 第八轮 #11 拆解时实测 | **根因**：拆出去的往往正好是“纯数据表/纯函数”块，说明性注释留在原文件，新模块只剩代码 → 密度天然偏低。**现状**：本轮 `_builders_task_results.py` 首版 **2.38%** 被 G-012 拦下、`pilotstd/query/adapters/gongbiaoku.py` 因拆分新增 2 行代码由 3.70% 跌到 **2.99%** 被拦（补一条注释后回到 3.70%）；TD-22 时 `_sql_schema_parser.py` 是 **1.9%**——**同一个坑第三次踩**，且都在“拆完、跑门禁”之后才暴露，等于白跑一轮。 | **✅ 已落实（2026-09-26）**：拆分清单已补一步“新模块注释密度预估”——落点 `docs/guides/refactoring-lessons.md`「五、拆分前检查项」§1（含三次实测数据表、G-012 判据口径、G-010 拆分证据与 500 行阻断档）。动手前先按 `注释行 / 非空行 ≥ 3%` 估算，不足就在新模块头部写清“拆出原因 + 分组依据”（既过门禁又是有用信息）；本项为流程改进，一次到位，**不挂偿还窗口**。**代价**：每次拆分多花约 1 分钟估算，换来少一轮返工。 |
| `_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 过时 | 2026-09-26 第八轮 #19 删端点时发现 | **根因**：该 docstring 写“两列的读取方是收藏状态接口（`docker/api/favorites.py` 的 `get_favorite_status`）”，而 `GET /api/favorites/{id}/status` 已于 #19 删除；两列本身也已被 v60（`_migrate_v60_drop_favorite_retry_columns.py`）`DROP COLUMN` 删除 → 该描述**双重过时**。**现状（2026-09-26 只读实测）**：`norm_source()`（`pilotstd/core/db/_migration_checksum.py:42-59`）只丢弃空行、以 `#` 开头的注释行、以及行首缩进；docstring 是字符串字面量，**整段保留在 checksum 输入内**——同一函数只改 docstring 一个字，`compute_checksum`（`:33-39`）与 `norm_checksum`（`:62-69`）**均变化** → “改注释不改 checksum”不成立。**同时更正原登记的两处推断**：① 原证据 `compute_checksum != norm_checksum` 与 docstring 无关——`norm_source` 每行都做 `line.strip()`（缩进被移除），故 `MIGRATIONS` 全部 **59/59** 个迁移函数 `raw != norm` 恒成立；② 原称“改动会触发 `:109-115` 的 `DatabaseError` → 生产库直接打不开”**未复现**：`:96` 的自愈分支必然命中，实际后果是**告警日志 + 运行时静默 `UPDATE _schema_version.checksum`**；`:109-115` 抛错分支只在 `tests/test_core.py:351-373` 用 mock 令两者相等时可达。 | ✅ **已决定（不改）**：docstring 确实过时，但它在 checksum 输入范围内，改动会让每台已执行过 v59 的库在下次打开时静默改写 `_schema_version.checksum`（P-106 禁止手动同步该值），为一行注释换来对生产库的无谓写入与校验状态漂移，收益 < 成本。**不挂窗口**：若未来 v59 因其他原因必须动（或该 checksum 机制被修正），顺手把 docstring 改为“两列当前无读取方且已于 v60 删除（原读取方 `/api/favorites/{id}/status` 已于 #19 删除）”。**代价**：仅阅读迁移源码的人会被这句过时描述误导，不影响运行。 |
| #23 合并前侦察未覆盖全组合（**✅ 已落实 2026-09-26**） | 2026-09-26 第八轮四分支合并时 | **根因**：合并前只做了相邻对侦察（3×4、2×1）与“各分支 × main”侦察，**漏了 3×1** —— `docs/architecture/modules/core.md` 里分支3 改 Schema 版本行、分支1 改子模块数行，两行相邻，该冲突因此未被预见，触发安全阀中止一轮。**现状**：这类冲突**不能用“取一边”解决**——两侧数值都不对（子模块数 70 / 72，实测 **73**），必须实测后重算，属需要外部事实的冲突。 | **处置（已落实）**：规则已写入 `docs/governance/development-flow.md` **§8「多分支合并流程：全组合冲突侦察」**（含规则、理由、`git merge-tree` 用法、输出要求、本轮 3×1 案例）；本条由「观察项」转为**已固化的流程规则**，不再依赖记忆。原规则内容：合并前侦察**必须覆盖全部 N×(N-1)/2 组合**（本轮 N=4 → 6 对），并在报告里逐对列出冲突文件；本项为流程改进，一次到位，**不挂窗口**。**代价**：每轮多跑几条 `git merge-tree`（秒级），换来不因未预见冲突而中止、不把“取一边”当成万能解法。 |
| #27 gates.md 版本历史两行挤在同一物理行（观察项） | 2026-09-26 第八轮文档核查时发现（**既有缺陷，非本轮引入**） | **根因**（2026-09-26 两次独立实测更正）：`docs/governance/gates.md` 版本历史表里 v1.16 与 v1.15 两个版本行被写在**同一个物理行**上——拼接处是**相邻的两个管道符 `||`（字符索引 470/471），缺的是换行符**，而不是缺行首 `|`（两个 `|` 都在）；该行为单行 879 字符。**现状**（2026-09-26 实测）：缺陷在 **L235**（本轮 v1.19 加行前为 L234）；只影响该表这两行的渲染（被当成同一行多出的单元格），表内其余版本行均正常；内容无丢失、无歧义。 | **处置**：**✅ 已修复（2026-09-26，v1.20）**：两行已拆开、内容一字未改（拆后 v1.16 → L236 / 471 字符、v1.15 → L237 / 408 字符，两段拼接仍为原 879 字符，仅补入一个换行）；原位置实测 `gates.md:235`，拆后行号因同批新增 v1.20 行整体下移 1。**代价**：无。 |

---

## 七、清理项（不属"债"，是待清理的残留）

| 项 | 来源 | 现状（实测） | 处置 |
|---|---|---|---|
| ~~`user_favorites.archive_retry_count` / `last_archive_attempt` 两列~~ | 原 #16 残留 | ✅ **已清理（2026-09-26，v60）**——删除前实测：两列在生产代码中零读取方（`pilotstd/` + `docker/` 全量 grep，排除 `_migrate_*` 历史迁移后 **0 命中**），唯一读取方是 `/status` 的 5 个旧响应键，随 #16（TD-16，2026-09-25）一并删除。v60（`pilotstd/core/db/_migrate_v60_drop_favorite_retry_columns.py`）幂等 `ALTER TABLE user_favorites DROP COLUMN` 删除，`CURRENT_SCHEMA_VERSION` 59 → 60。**真库级实测**（sqlite 3.50.4，非 mock）：v59 形态库（2 行真实数据 + 三个索引）迁移后两列消失、行数与其余列值逐值不变、无关索引保留；二次打开 + 重复调用迁移函数零副作用；无 `user_favorites` 表的库打开不抛异常；全新建库跑完整 v0→v60 链同样收敛到"无此列" | 已清理，明细见「一、已清理」 |

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

### 8.4 巡检走公开端点复核（已执行，2026-09-26，第六轮）

目的：确认 #18 三组巡检**不必依赖 admin SQL 端点**即可复现（能走公开 API 的就不该要求人执行 SQL）。

| 口径 | 公开端点可行性（实测） |
|---|---|
| 全量性前提 | `GET /api/favorites/export?format=json` → **105 行 == 库内 `user_favorites` 105 行**；接口 SQL（`favorites.py:453-470`）只有 `WHERE f.user_id = ?` + `ORDER BY`，**无 LIMIT/分页** → 全量成立，可用于本地算基线 |
| A 组（标准号/名称） | ✅ `user_favorites` 维度可算：`standard_number`=0 空、`std_name`（键名，来源 `announcement_record`）=0 空、`UNKNOWN_*`=0；❌ `favorite_downloads.standard_no/standard_name` **公开端点未暴露**（`_DOWNLOAD_FIELDS` 仅 4 列，`favorites.py:341-346`） |
| B 组（分类列未回填） | ✅ `user_favorites.standard_type` 可算：0 空（105 条全 `NationalStd`）；❌ `favorite_downloads` / `announcement_record` / `download_queue` 的分类列未暴露 |
| C 组（去重基线） | ✅ 可算：按 `(standard_number, standard_type)` 分组 = 105 组、**重复组 0**（本用户全量数据） |
| 未暴露维度 | 经 `POST /query`（同为 API）复核：`fd_std_no_null=0`、`fd_std_no_UNKNOWN=0`、`fd_std_name_null=0`、`fd_std_type_empty=0`、`ar_std_type_empty=0`、`dq_std_type_empty=0` |

探针（不入库）：`C:\Temp\pilotstd-probe\probe_a1_export_checks.py`。

### 8.5 部署后现场复核（已执行，2026-09-26，v0.110.2）

| 复核项 | 结果 |
|---|---|
| 版本 | `/api/system/version` = `0.110.2`（tag `v0.110.2`、image `ghcr.io/leanmore/pilotstd:v0.110.2`）；`/api/health` 返回的 version = 构建 sha `c421c572` |
| TD-20 读侧 | `GET /api/settings` 的 `tasks` **10 键、缺键 0**；`auto_archive_retry_enabled=True` / `auto_archive_retry_cron='0 4 * * *'` |
| 与调度器一致 | `GET /api/scheduler/status` 中 `auto_archive_retry` next_run `2026-09-27T04:00+08:00`（cron 与读侧一致） |
| UI 新任务行 | Playwright 现场：设置页「定时任务」出现"收藏下载链（自动归档重试）"、开关为开、cron 输入框 `0 4 * * *`、页面回填值 == 后端值；截图 `C:\Temp\pilotstd-probe\shots\settings-schedule.png` |
| 部署方式 | 人工部署（该主机不自动拉取；更新开关见 `docker/api/system.py:152` `POST /api/system/update`），部署后 `/api/health` 构建 sha 由 `22d4d90b` → `c421c572` |

探针（不入库）：`probe_td20_readside.py`、`verify_settings_ui.cjs`。

### 8.6 前端 CI 缺陷修复（已执行，2026-09-26，第七轮）

| 项 | 内容 |
|---|---|
| 现象 | CI run `36209088436`（提交 `4ca2c061`，纯 docs、0 个 `web/` 文件）：`Test Files 35 passed / Tests 230 passed` 却 `Errors 1 error` + exit 1，`test-frontend` 的 "Run tests" 步失败（46s），其后 `version`/`docker`/`exe` 全部 skipped（**不发版、不出镜像**） |
| 根因 | `primevue/tablist/index.mjs:48-53` 在 `mounted()` 排 `setTimeout(() => { updateInkBar(); bindInkBarObserver() }, 150)`，**不保存句柄、`unmounted` 也不清理**；测试文件在 150ms 内结束时，vitest 先摘掉 jsdom 全局再执行回调 → `@primeuix/utils` 的 `t instanceof HTMLElement`（`dist/dom/index.mjs`）抛 `ReferenceError: HTMLElement is not defined`（unhandled error → `Errors 1 error`） |
| 环境事实 | 测试环境 = **jsdom**（`web/vite.config.ts:50`），setupFiles = `web/src/test-setup.ts`（`:53`） |
| 复现 | 受控复现（fake timers 捕获真实 150ms 定时器 → 摘除 `globalThis.HTMLElement`/`window` → `vi.runAllTimers()`）：得到与 CI **完全一致**的 `HTMLElement is not defined`，栈含 `updateInkBar`/`tablist`。自然竞态在本机复现不出：jsdom 下 FavoritesView 挂载 ~440ms > 150ms，定时器总在环境内先跑完（轻量 Tabs 对照组同样 0 error）——即"本机绿、CI 红"的成因 |
| 候选否证 | 候选 1（`defineProperty(configurable:false)` 锁定）→ 全量套件 **34 errors**、报 `TypeError: Cannot delete property 'HTMLElement' of #<Object>`（vitest teardown 用 `delete` 摘全局）→ 有害，弃；候选 2（`afterEach` 补回）→ 全局是在 afterEach **之后**的 teardown 阶段被摘，结构上无效，弃；空壳类兜底 → `instanceof` 恒 false、`getOuterWidth` 静默返回 0（更隐蔽），禁用 |
| 修法 | `web/src/test-setup.ts` 接管 `setTimeout`：登记未触发句柄，文件级 `afterAll` 一并 clear 并还原真实实现（回调根本不会执行；不用 fake timers、不用 sleep）。`web/src/views/FavoritesView.test.ts` 增确定性守卫（断言接管层能登记与清理真实定时器） |
| 全库扫描 | 仅 `FavoritesView.vue` 与 `dashboard/widgets/RecentAnnounceCard.vue` 使用 Tabs/TabList；后者在 `views/__tests__/HomeView.test.ts:37` 被 `vi.mock` 整体替换 → 不实例化 TabList、无定时器 → 无风险 |
| 验证 | 全量 1 次 + 连跑 10 次：每次 `Errors 0 / exit 0`，`35 files / 231 passed`（230 + 新增守卫 1 例）；`vue-tsc --noEmit` exit 0 |

### 8.7 #17a 量化验收实测（已执行，2026-09-26）

| 路径 | 修复后退出耗时 | 占 5000ms 预算 | 修复前对照（`git stash` 掉改动） |
|---|---|---|---|
| ScanWorker（流进行中） | **14ms** | 0.3% | 5035ms、退出=False、保活 +1 |
| QueryWorker（流进行中） | **6ms** | 0.1% | 5009ms、退出=False、保活 +1 |
| QueryWorker（暂停中） | **60ms** | 1.2% | 5010ms、退出=False、保活 +1 |
| DriveEnumerator | **54ms** | 1.1% | 5055ms、退出=False、保活 +1 |

假 stream 为 20000 条 × 10ms（不中断需 ~200s）；修复后底层流在 12–14 条处被终止，`orphan_timeout_total()` 增量 0、保活残留 0。测量脚本（不入库）：`C:\Temp\pilotstd-probe\measure_worker_abort.py`。

### 8.8 #17a 首次上 CI 失败与加固（2026-09-26）

| 项 | 内容 |
|---|---|
| 现象 | 推送 `cdc308f3` 后 `test-gui-unit` 失败，**耗时 8.2 分钟**（同树前两次成功运行均为 18 分钟）→ 进程在套件中途终止，未打印 pytest 汇总；`version`/`docker`/`exe` 连带 skipped |
| 本机复现 | 用 CI 同款命令（`pytest tests/gui/ tests/test_regression_architecture.py --cov=pilotstd/ui/core/handlers/ --ignore-glob="*test_e2e*.py"` + `PILOTSTD_GUI_TEST=1`）本机 **990 passed / 覆盖率 68.71%**，不复现；本地全量两轮均 1000 passed |
| 根因（判定） | 新用例的**绝对毫秒阈值**（`elapsed_ms < 500`）在 CI 的 coverage 插桩 + 慢 runner 下会偶发失败；而断言在 `isFinished()`/收尾之前抛出 → 局部变量 `worker`（仍在运行的 QThread）随帧释放被 GC → Qt 触发 `QThread: Destroyed while thread is still running` 并 **qFatal 终止进程** → 套件中途死亡（正是 8.2 分钟无汇总的形态） |
| 加固 | ① `_stop_and_measure()` 在 `finally` 中无条件 `worker.wait(timeout_ms)`：断言失败也先把线程收干净，杜绝"运行中被析构"；② 绝对毫秒阈值全部放宽为 `2000–3000ms` 量级（真正的验收线仍是"≤80% timeout"，即 4000ms）；③ `mgr.started.wait(5.0)` → `20.0`（CI 冷启动慢） |
| 教训 | 线程类测试的收尾必须与断言解耦（先 join 再断言或 finally join）；跨环境验收线用相对预算而非绝对毫秒 |
