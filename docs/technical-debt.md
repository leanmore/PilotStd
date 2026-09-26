# 技术债登记

> 版本：v1.6.0
> 更新日期：2026-09-26
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)
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
| **TD-20** `auto_archive_retry` 在 UI 不可改、不可触发 | 原 #20（登记 2026-09-25）。**修复（2026-09-25）**：①`docker/api/settings.py` 抽出 `_SCHEDULED_JOBS`（5 项，与 `scheduler.start_scheduler()` 一一对应）并补 `auto_archive_retry`；②缺键时用**当前配置值**兜底（防前端漏发把链路静默禁用）；③`SettingsTabSchedule.vue` 增加"收藏下载链（自动归档重试）"开关 + cron 输入 + 提示。**同轮自查补漏④**：`GET /api/settings` 原先不返回 `auto_archive_retry_*`——写侧可选、读侧缺失，前端只能拿组件默认值显示，保存时又把该默认值回写，用户改过的值（如 `0 6 * * *`）会被静默改回 `0 4 * * *`；已在读侧补齐两键，并加"读侧键必须与 `_SCHEDULED_JOBS` 对称 + 必须返回存值而非默认值"两例反证测试。**⑤**再补 `pilotstd/core/config/settings_schema.py` 两条 `SettingDef`（`tasks.auto_archive_retry_enabled/cron`）：e2e 字段一致性测试要求 GET 的键必须被前端 Schema 覆盖或进白名单，不注册则 `test_settings_e2e_consistency.py::test_no_unexpected_backend_only_keys` FAILED（实测）。验证：`tests/test_settings_scheduler_sync.py`（**7 passed**：任务表覆盖、scheduler 差异声明、改 cron 真重排、缺键沿用配置、health 默认值不坏、读侧键对称、读侧返回存值）——后两例在补④前用 `git stash` 实测 **2 failed**、补后 PASSED，"scheduler 差异声明"一例用注入假任务实测 FAILED；`SettingsTabSchedule.test.ts`（3 passed：字段存在、保存随载荷提交、加载回填）；`test_docker_api.py -k settings` 2 passed；`test_settings_auth/e2e_consistency/manager` 合计 21 passed；`SettingsView.test.ts` 6 passed。**现场实证（v0.110.0 / `22d4d90b`，修复前镜像）**：`GET /api/settings` 的 `tasks` 实测 8 键、缺 `auto_archive_retry_*`；同镜像 `GET /api/scheduler/status` 显示该任务已注册（next_run 04:00）；对照组 `date_reminder_cron` 现场值 `0 8 * * *` ≠ Schema 默认 `0 2 * * *` → 用户确实会改这些值，读侧缺键＝改过的值会被静默覆盖（不是理论风险）。**⑥契约细化**：现场 `GET /api/scheduler/status` 共 **6** 个 cron 任务（多一个 `auto_backup`），故 ① 里"与 scheduler 注册表一一对应"的说法不准确——`_SCHEDULED_JOBS` 只覆盖**用户可管**的 5 项，`auto_backup`（固定周日备份、无 UI 开关）为**有意排除**；新增 `test_scheduler_jobs_not_in_settings_are_intentional`：**AST 解析** `docker/scheduler.py::start_scheduler()` 的注册表，断言"未暴露的差异集合 == {auto_backup}"（注入 `fake_probe_job` 实测 **FAILED**、撤销后 PASSED）——旧测试只比对写死名单，scheduler 新增任务也不会失败，改后"漏登记"与"有意排除"才真正分得开。**部署状态（2026-09-26 00:00 实测）**：修复已随镜像 **v0.110.2** 发布（CI 全绿：`version`/`docker` job 均 success，bump 提交 `2719691b`），但**现场 `192.168.1.18:9028` 仍为 v0.110.0 / `22d4d90b`（读侧 8 键）**——该主机不会自动拉取（`docker/api/system.py:152` 的 `POST /api/system/update` 是管理员手动触发的 pull + compose 重建，无定时任务），故"读侧 8→10 键"需**部署后**复核。**✅ 部署后复核通过（2026-09-26 09:32 实测，v0.110.2 / `c421c572`）**：`/api/system/version`=0.110.2、`/api/health` build=`c421c572`；`GET /api/settings` 的 `tasks` **10 键、缺键 0**，`auto_archive_retry_enabled=True` / `cron='0 4 * * *'` 与 `/api/scheduler/status`（next_run 2026-09-27 04:00）一致——读写两侧闭环。**UI 现场复核（Playwright，v0.110.2）**：设置页「定时任务」出现"收藏下载链（自动归档重试）"行、开关为开、cron 输入框 `0 4 * * *`，且页面回填值 == 后端 `GET /api/settings` 值（截图留档 `C:\Temp\pilotstd-probe\shots\settings-schedule.png`，探针不入库）。**残留**：无"立即执行一次"按钮 → 记为可选增强（临时把 cron 改成 `* * * * *` 即可触发，等价覆盖），不进台账 | 2026-09-25 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（只放"未清"的债）

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|------|------|------|------|--------------------------------------|---------|
| 11 | **ROI 判断** | G-010 警告区文件（拆分收益低于成本） | 见下方"现状"列出的 **3** 个文件 | ✅ 已偿还（第八轮执行完毕） | **根因**：历史累积复杂度进入 400-500 行警告区；集中拆分 ROI 低于组件碎片化风险。**现状（2026-09-26 第八轮实测 `check_g_010_code_size.py`）**：警告区 **8 个 → 3 个**，**最高有效行 487 → 438**（全部 < 450，距 500 阻断线余 **62** 行，无阻断风险）。本轮拆掉 5 个文件（原文件 → 新模块，均为逐字节搬移 + 调用点/文档同步）：`docker/api/announce_detail.py` **454 → 372**（拆出 `_announce_detail_parse.py` 92 行）；`scripts/check_g_012_comment_density.py` **457 → 311**（拆出 `_comment_lang_data.py` 159 行，仅搬数据表、逻辑零改动，用同一份 464 文件清单对照跑出**逐行一致**的 80 行输出）；`pilotstd/core/notification/_builders_batch.py` **477 → 287**（拆出 `_builders_task_results.py` 205 行，切口处 AST 实测无共享模块级符号 → 无反向依赖）；`pilotstd/core/notification/manager.py` **487 → 382**（按 ADR-010 Mixin 模式拆出 `_manager_ops.py` 129 行，调用点零改动）；`web/src/views/AnnounceDetail.vue` **487 → 314**（拆出 composable `useAnnounceDetail.ts` 234 行，模板/样式未改）。剩余 3 个：`pilotstd/core/db/_migrate_v16_v49.py:438`、`web/src/components/AppLayout.vue:434`、`web/src/components/NotificationConfig.vue:425`。**验证**：ruff 全绿；mypy 合并口径 `Success: 388 source files`；后端 270+333 tests、前端 231 tests 全过；`vue-tsc --noEmit` 零错误；每批 `check_all.sh --fast --guards --local` EXIT=0；G-031 连带文档（core.md / gates.md / README.md）与能力矩阵均已同步。**偿还窗口**：**不适用（已偿还）**。**触发式规则保留**：任一文件触及 **490** 行 → 当轮必拆；新文件新写入即受 500 行阻断档约束。**不还的代价（已消除）**：原先 5 个文件距阻断线最窄仅 13 行，任何小改动都可能撞线导致 CI 阻断；现最窄余 62 行。| 2026-08-23 |
| 15 | **ROI 判断** | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`core/notification/manager.py:118-135`（`_aggregate_enabled` 为真时在实例内新建）；管理器创建点：`core/notification/manager.py:87`（`NotificationManager.__init__`）；门面创建点：`manager/facade/_base.py:87`（`BaseFacade.__init__`）→ `:250`（`_init_services` 内新建）、`:271`（`_init_notification` 配置变更重建，调用方 `docker/api/notification.py:133`）；**`StandardManager()` 构造点本轮 AST 重测 = 生产 12 处 + 测试 22 处**：`docker/manager.py:16`、`cli/commands/_shared.py:19`、`core/task_status.py:76`、`monitor/scheduler.py:146`、`services/favorite_chain_processor.py:164/307`、`tasks/date_reminder.py:141`、`tasks/favorite_download.py:137/165/194/306`、`ui/main_window/parts/_actions_ops.py:49`；测试 `tests/test_manager.py`（20 处）、`tests/test_scanner.py:576`、`tests/test_e2e_adapters.py:277` | ✅ 已接受（本轮正式关闭） | **根因**——聚合器生命周期绑在门面上，不是"忘了单例"：`NotificationManager.__init__` 按 `_aggregate_enabled`（`core/config/defaults.py:79` 默认 true）在实例内新建 `NotificationAggregator`（`manager.py:128`），并把 `self._send_now`（绑定方法）作为回调传入；`StandardManager()` 每次都在 `_base.py:250` 新建 `NotificationManager`，故聚合器**每构造一个门面就多一个**。**现状**（本轮实测，代码树 = `62fba6ef`）：① 构造点口径由上一轮的 9 处更正为**生产 12 处 / 测试 22 处**（AST 遍历 `Call.func.id=='StandardManager'`，口径含 `docker/` 与 `cli/`）；② 逐条通知路径**仍在**（上一轮"已消除"的说法需修正）——`tasks/favorite_download.py:282` 的 `notify=False` 只在**批量链路**（`docker/app.py:160` → `services/favorite_chain_processor.py:320 process_chain(notify_per_record=False)`）由源头抑制为"每次运行 1 条汇总"，但 `services/favorite_chain_processor.py:307 _notify_abandoned` 是**无条件逐条**发（`notify` 闸只作用于 `:249` 那处），`favorite_download.py:306` 的独立 `StandardManager()` 每次下载也照建；③ 探针实测（临时探针已删）：连建 2 个 `StandardManager`，`m1.notification_mgr.aggregator is m2...` = **False**，3 次逐条 `send_event` 后**每个实例缓冲恒为 1 条**且无跨实例合并；同一个共享聚合器入队 3 条则缓冲深度 3、`shutdown()` 时 flush **1 次**（成对验证）。**偿还窗口**：**不适用（已接受）**。**不还的代价**（已接受，量化）：① 聚合失效的实测代价≈**0**——生产链路源头按批汇总（一次运行 1 条汇总），Web/定时侧本就持有长生命周期门面（`docker/manager.py:12` 进程级单例；`monitor/scheduler.py:142` `self._mgr` 缓存），仅"每条 abandoned/每次下载失败"这类低频通知退化为**延迟 window（默认 5s，`defaults.py:83`）+ 渠道请求各 1 次**；② "构造开销"经本轮实测**最轻**：`NotificationManager()` 构造（含凭据迁移 + 渠道初始化 + 聚合器）中位 **0.62 ms**（n=5：0.58/0.60/0.62/0.64/0.76，`aggregate_enabled=true`），即每次通知多 ~0.6 ms；门面构造的大头不在聚合器——`StandardManager()` 单次 **8.17 s（中位）**，`cProfile` 显示 **8.18 s / 8.27 s（98.9%）** 落在 `ssl.create_default_context → load_verify_locations`（9 个查询适配器各建一个 httpx client；本机实测裸 `httpx.Client()` ≈ **810 ms**、裸 `ssl.create_default_context()` ≈ **52 ms**），与本条无关，属另一条待登记线索；③ 因此**不还的代价 = 上述 ~5 s 通知延迟 + 每事件 ~0.6 ms + 未来交互型高频通知的限流余量**（历史上 Telegram 429 的 56% 拒收由逐条发送触发，已由源头按批汇总消除，本条不再重复计）。**为何不做单例化（代码级理由）**：聚合器的 `sender_func` 捕获的是**首个入队管理器的** `_send_now` → 闭包其 `_db`/`_ws_broadcast`/`_user_id`/`_channels`；共享聚合器会让"最后入队者"决定全部缓冲消息的收件身份（跨库写 `notification_log`、跨用户发消息）；且缓冲分组键只有 `event_type`（`aggregate_buffer.py:65` `_buffers`），**没有按 `user_id` 分桶**，共享即把不同用户的消息合并成 1 条——这是当前结构刻意避开的用户绑定洞。共享整个管理器又新增状态竞争面：`_init_notification`（`_base.py:271`，`docker/api/notification.py:133` 调用，`tests/test_notification_api.py:86/107` 断言）要求配置变更后拿到**新**管理器，单例后已绑定旧单例的代码读不到新配置。**代价**：12 处生产构造点（8 文件）+ ≥3 个测试文件、22 处测试构造需改，且新引入跨库绑定 + 跨用户合并两类正确性问题。**结论**：**不改**——实测收益≈0、成本高且会引入更严重的正确性洞；未来若出现交互型高频通知，正确方向是核心库层继续不做进程级可变全局，由应用层持有门面生命周期（复用 `docker/manager.py:12` 的应用级门面）让交互路径共享，而非把用户绑定绑在首个入队者身上。 | 2026-09-21 |
| 17b | **技术无解** | 卡死线程无法安全终止 | CPython / Qt 层面 | ✅ 已接受 | **根因**：CPython **没有**安全强杀线程的机制（`PyThreadState` 清理、GIL、锁状态无法安全回滚）；`QThread.terminate()` 是唯一 API，但会在持锁/写文件时中断线程，造成数据损坏与析构期崩溃（正是 CI `test-gui-coverage` 失败的原因，`54bd565d` 已全部移除）。**现状**：7+1 处调用点统一走"断信号 → 置停止标志 → `requestInterruption()` → `wait()` → 超时保活"，无任何 `terminate()`。**偿还窗口**：**不适用（技术无解，已接受）**——只能保活等待或人工重启容器。**不还的代价**（已接受）：卡死线程在进程退出前不释放其连接/句柄/线程栈；若发生在下载/归档链路，需要人工重启容器才能恢复，且日志里只留线索（已由 17a 的计数与 error 升级提供）。 | 2026-09-25 |
| 21 | **可偿还** | 收藏下载链 GB 类成功率 **0**：`verifyCode` 提交恒被拒 | `pilotstd/download/adapters/openstd_download.py:167-231`（`_handle_captcha`：GET `/gc` → ddddocr → POST `/verifyCode`，`:214-219` body 只有 `verifyCode`，无 Referer / 无 `X-Requested-With` / 不含 `hcno`） | ⏳ 待处理 | **根因（未定，三条可测假设）**：链路在 2026-06~09 因 `pilotstd/download/session.py` 的 `super()` 注入 bug（`'super' object has no attribute 'request'`，见 `docs/ci-lessons.md` §7）全量失败，2026-09-25 修复后请求才**首次真正到达站点**——即验证码这条最后一段从未在真实站点上验证成功过；单测 `tests/download/adapters/test_openstd_download.py:58` 的 mock 服务一律返回 `success`，把真实协议差异完全掩盖（同 §7 的教训形态）。**现状**（2026-09-26 04:00 现场，v0.110.2 / `c421c572`）：该次运行处理 **9 条**（TD-18 补建的 8 条 `pending` + 1 条既有 `failed` 复跑）→ 成功 **0**、失败 6、跳过 3（跳过 3 条为采标终态，`_abandon_terminal` 按设计直接置终态，符合规则；8 条 pending 的去向＝5 条验证码失败 + 3 条采标终态）；`verifyCode 结果` **15 次 error / 0 次 success**；`notification_log` 三条 `batch_download_complete`（09-24 成功 0/失败 1、09-25 成功 0/失败 1、09-26 成功 0/失败 6/跳过 3）成功均为 0。ddddocr 输出样本 `4RR7 / 84GR / YHEW / NACG / TLMC / 8LGU / 6EuX / 3CBN / 7TRP / X3MB / HB6R / 2L2W / R4LJ / ECSP / 76G5`（**大小写混排**，另 1 次输出长度非 4 直接判"识别失败"）。三条可测假设：①站点对 `verifyCode` 要求上下文（Referer / AJAX 头 / body 带 `hcno`）而当前都没带；②OCR 大小写与站点判定不一致（样本混排）；③验证码图片与 `showGb` 会话未绑定（`:177` 的 `/gc` 请求不带 hcno）。**偿还窗口**：**第六轮（下一轮）**出定位结论——在验证环境对真实站点跑单条下载，逐项验证 ①（补 Referer/AJAX 头与 hcno）、②（大小写归一 + 多次取样统计识别正确率）、③（会话绑定）；触发式提前——6 条 `failed`（5 条 `retry_count=1`、1 条 `=3`）按 7 天窗口每晚重试，**2026-10-02 前后将被置 abandoned**。**不还的代价**：收藏→自动入库是本工具的核心出口，成功率恒 0 ＝ 功能实质失效，用户只能手工下载；且失败项会在 7 天后变成 abandoned 脏终态，届时即使修好验证码也不能自动补下（需人工重置重试计数）。 | 2026-09-26 |
| 22 | **可偿还** | 门面构造耗时约 7 秒：查询适配器逐个新建 httpx.Client → 每个都重建 SSL context 并重新加载 CA | `pilotstd/query/adapters/registry.py:57`（`instantiate_all`）；12 处 `httpx.Client(...)`：`ccsn.py:43`、`cssn.py:33`、`energy.py:33`、`gongbiaoku.py:37`、`jjg.py:32`、`jtst.py:41`、`miit.py:31`、`ncha.py:59`、`nrsis.py:57`、`sppt.py:35`、`sppt_local.py:44`、`tdpress.py:52` | ⏳ 待偿还 | **根因**：`registry.instantiate_all()` 为每个适配器各建一个 `httpx.Client`（本轮实测 **12 次** `Client.__init__`），其中 **9 次**走到 `ssl.create_default_context()` → `load_verify_locations()`，把 CA 证书包**重新解析加载 9 遍**；调用方无处可传共享 client/context，只能各自新建。**现状**（2026-09-26 本机实测）：`StandardManager()` 构造中位 **6.8 s**（3 次：7108 / 6806 / 6731 ms；另一次 cProfile 全程 7.05 s），其中 `load_verify_locations` **6.804 s = 96.5%**、`registry.instantiate_all` 占 **98.4%**；单适配器 0.76~0.85 s（ccsn 0.852 / ncha 0.798 / nrsis 0.765 / tdpress 0.764 / jtst 0.762）。对照：本机裸 `httpx.Client()` ≈ 810 ms（并行分支独立测得中位 8.17 s，量级一致）。**偿还窗口**：**最迟第九轮**。修复方向：模块级共享一个 `ssl.SSLContext`（或共享 `httpx.Client`/`limits`）由适配器复用；**必须分档**——`energy.py:35` / `sppt.py:37` / `sppt_local.py:46` 三处是 `verify=False`（自签名站点），不能与默认校验上下文混用；共享后还需确认 `SessionManager` 的并发/超时语义不被改变。**不还的代价**：构造落在用户操作路径时卡顿肉眼可见——生产侧 `StandardManager()` 有 **12 处构造点**（`docker/manager.py:16`、`cli/commands/_shared.py:19`、`core/task_status.py:76`、`monitor/scheduler.py:146`、`services/favorite_chain_processor.py:164/307`、`tasks/date_reminder.py:141`、`tasks/favorite_download.py:137/165/194/306`、`ui/main_window/parts/_actions_ops.py:49`），交互型操作（点一次查询/收藏）每次都会吃满这 ~7 s；链路侧已由源头按批汇总压低次数，但那只是减少触发频率，单次代价未变。 | 2026-09-26 |

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
| `POST /query`（admin SQL 端点）权限边界过宽 | 2026-09-25 巡检时实测，2026-09-26 复查机制 | **端点**：`docker/api/admin_db.py:180` `@router.post("/query")`（router 无 prefix；审计标签 `/api/admin/db/query` 只是字符串，`:176`/`:253`）。**白名单**：`_ALLOWED_TABLES`（`:25-34`）= standards/favorites/notification_log/task_execution_history/users/user_preferences，**仅在 `DROP TABLE` 分支被查询**（`:110-116`）。**读**：SELECT **不受表白名单限制**，自动包 `LIMIT 1001`（`:126-128`/`:216-217`），>1000 行时返回 `truncated: true`（`:244-248`）。**写**：INSERT 无附加约束；UPDATE/DELETE 仅要求含 WHERE（`:119-121`）；仅 `DROP DATABASE` 被硬拒（`:106-107`） | 选项：①维持（管理员本就等于全权，且该端点是运维排查主力，两轮巡检/补数均靠它完成）；②收紧为"SELECT 仅限白名单表 + 写操作全禁"，另开专用只读端点。**倾向 ①并在 API 文档标注"管理员等同全库权限"**，但需你确认；若选 ② 需评估对运维排查的影响（本轮 A/B 组的队列表维度只能靠该端点，公开端点不暴露这些列） | 第七轮 |

---

## 六-B、观察项（不属"债"，登记待观察）

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| 单条网络请求/大文件 IO 内部仍不可中断（#17a 后残留） | 2026-09-26 #17a 偿还时实测 | **根因**：worker 侧检查点只能落在"处理单元之间"（回调/循环体）；`requests` 的单次 `send()` 与 `resp.content` 整块读取无法从外部打断，要中断必须把网络层改为"分块读 + 每块查停止标志"，并把停止标志从 UI worker 一路传到适配器/会话层。**现状**：单条不可中断窗口 = 该请求的超时值——查询/公告 `network.DEFAULT_TIMEOUT = 15s`（`pilotstd/query/network.py:17`）、下载 `viewGb` 显式 120s（`pilotstd/download/adapters/openstd_download.py:114`）、SQLite `busy_timeout=5000ms`（`pilotstd/core/db/database.py:200/211`）。即：worker 现在能在"下一条"立刻停（实测 6–60ms），但若正卡在一条请求里，最坏仍要等该请求超时 | **暂不处理**：15s/120s 都有明确上界，且改动需穿透 UI→服务→适配器三层插入停止标志（ROI 判断），故不挂窗口。**不还的代价**：极端情况下（站点不响应）用户取消后最坏等 15s（查询）/120s（下载单文件）才退出，期间表现为"界面已取消但线程仍在"，不再触发保活/疑似卡死告警 |
| 拆出新模块时注释密度被稀释（G-012 ≥3%） | 2026-09-26 第八轮 #11 拆解时实测 | **根因**：拆出去的往往正好是“纯数据表/纯函数”块，说明性注释留在原文件，新模块只剩代码 → 密度天然偏低。**现状**：本轮 `_builders_task_results.py` 首版 **2.38%** 被 G-012 拦下；TD-22 时 `_sql_schema_parser.py` 是 **1.9%**——**同一个坑第二次踩**，且都在“拆完、跑门禁”之后才暴露，等于白跑一轮。 | **处置**：拆分清单里增加一步“新模块注释密度预估”——动手前先按 `注释行 / 非空行 ≥ 3%` 估算，不足就在新模块头部写清“拆出原因 + 分组依据”（既过门禁又是有用信息）；本项为流程改进，一次到位，**不挂偿还窗口**。**代价**：每次拆分多花约 1 分钟估算，换来少一轮返工。 |
| `_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 过时 | 2026-09-26 第八轮 #19 删端点时发现 | **根因**：该 docstring 写“两列的读取方是收藏状态接口”，而 `GET /api/favorites/{id}/status` 已于 #19 删除；**现状**：实测这段 docstring **在 `norm_checksum` 覆盖范围内**（`compute_checksum != norm_checksum`），改动会触发 `pilotstd/core/db/_migration_checksum.py:109-115` 的 `DatabaseError: 迁移 v59 的脚本逻辑已变更` → 生产库直接打不开，受 P-106（已执行迁移源码不可变）约束**不可单独改**。 | **处置**：保留现状（模块级 `#` 注释不在函数内、未受影响）；若未来因其他原因必须动 v59 脚本，按“函数体逐字符不动 + 同步更新 `_schema_version.checksum`”的专门流程顺手改。**不挂窗口**。**代价**：仅阅读迁移源码的人会被这句过时描述误导，不影响运行。 |

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
