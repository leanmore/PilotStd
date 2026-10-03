# 技术债登记

> 版本：v1.46.0（2026-10-01：R16 清空候选池 P0~P3 + 观察期边界与仪器改名）
> 更新日期：2026-09-27
> 2026-10-01 **第十四轮 R14-4d：#32-D 测试侧收敛 + 哨兵机制——#32 正式闭环**。**收敛**：`tests/` 目录中文状态字面量 **504 → 25 处**（−95%），扫描/替换与生产同一套 AST 口径（排除 docstring，UTF-8 字节偏移精确定位），共替换 **456 处**、覆盖 **67 个测试文件**；**哨兵机制**：刻意保留 **5 处**直写中文字面量作为哨兵（均带 `# Sentinel: 确保枚举 value 与现网中文契约一致` 注释且有断言），分布在「字典契约／生产扫描基准／API 历史中文入参／解析格式层外部输入／DB 历史 DDL 默认值」五个不同层，杜绝「有人顺手改枚举 value 导致与外部系统静默脱节」。**验证**：全量测试 **4356 passed / 6 skipped**（本批为纯测试侧改动，生产代码零改动）；ruff/mypy 全绿；`--fast --guards --local` 与 `--deep` EXIT=0；CI 13/13。**#32 由此正式闭环**（A 建字典 → B 后端收敛 → C 前后端闭环 → D 测试收敛+哨兵），由「二、剩余台账」移入「一、已清理」。详见 7.31。 |
> 2026-10-01 **第十四轮 R14-4c：#32-C 贯通 API 契约 + 落库迁移 + 前端 i18n 映射（前后端闭环）**。**① API 契约**：`pilotstd/core/status.py` 新增 `status_key()`（数据值 → 稳定英文键）与 `resolve_status_filter()`（同时接受英文键与历史中文值）；`/api/standards/status`、`/api/query/results`、`/api/pending/requery` 的记录在原有中文 `status` 之外新增 `status_key`（**向后兼容，无破坏性变更**）。**② DB**：新增 **v61 迁移**（`_migrate_v61_enum_status_defaults.py`）把 `file_index.status`／`standard_validity.status` 的列默认值收敛到字典——默认值已等于枚举值时**不重建表**（现网命中，零数据搬动），漂移时才走 SQLite 12 步重建修复；**未改任何历史迁移源码（P-106）**；`CURRENT_SCHEMA_VERSION` 60 → 61。**③ 前端**：新增唯一事实源 `web/src/utils/stdStatus.ts`，13 处中文状态比较全部改为 `status_key` 比较（`i18n-allow` 状态项 **13 → 0**），筛选下拉提交英文键（后端两种口径都接受）。**验证**：新增契约测试 25 例 + 迁移测试 6 例 + 前端 4 例；核心/迁移回归 506 passed；前端 vitest 301 passed、`vue-tsc -p tsconfig.app.json` 零错误；`check_i18n_key_count.py` 三语对齐 PASS（860×3）；schema 一致性 PASS；`--fast --guards --local` 与 `--deep` EXIT=0；CI 13/13。详见 7.30。 |
> 2026-10-01 **第十四轮 R14-4b：#32-B 后端业务字面量大收敛——运行时裸状态字面量 211 → 0（分 5 个原子 commit）**。**范围**：`pilotstd/` + `docker/` 业务代码，按域分 5 批（B1 core/announcement/pipeline 27 处 → B2 query 96 处 → B3 manager 32 处 → B4 ui 39 处 → B5 docker 5 处），共 **199 处**中文状态字面量改为 `Status.<MEMBER>.value`。**口径**：统一 `.value`（保证 API 返回、DB 落库、日志、SQL 参数处均为**严格 str**，不依赖 str 子类序列化细节）——API 契约绝对不变。**计数（tokenize 口径）**：生产 **220 → 21 处**，其中 **9 处＝`core/status.py` 枚举定义本身**（字典，保留）、**12 处＝`pilotstd/templates/adapter/**` cookiecutter 脚手架模板**（含 Jinja 占位符、非合法 Python、非运行时代码）→ **运行时代码裸字面量 211 → 0** ✓（≤20 验收达成）。**新增守卫测试** `tests/unit/core/test_status_convergence.py`（AST 口径扫描生产目录断言零裸字面量 + `ValidityChecker` 行为断言 + 枚举 round-trip）；受影响回归 1829+393+284+381 passed。详见 7.29。 |
> 2026-10-01 **第十四轮 R14-4a：#31 正式闭环（P3 降级观察）＋ #32-A 状态枚举落地（零行为变化）**。**#31**：用户裁定 P3（跨进程文件锁）**降级为观察项**——P2+P1 后写盘已由“每次查询必写”降到“首次创建/迁移/显式修改才写”（单批查询 126 → 2 次）、构造 133 → 1，跨进程同毫秒写冲突概率可忽略，而文件锁跨平台语义（flock vs LockFileEx／NFS／异常退出）维护成本远高于其防范风险；若未来真观测到冲突，改用“原子写+重试”或 SQLite 配置后端即可。**#31 由「二、剩余台账」移入「一、已清理」**（核心闭环），P3 另立观察项 **T-35**。**#32-A**：新增叶子模块 `pilotstd/core/status.py`（`Status` 枚举 value 与现网中文**逐字一致**；`STATUS_I18N_KEYS`/`STATUS_EN_KEYS` i18n 脚手架；`normalize_status()` 做 `废止`→`已废止` 归一；5 组命名集合），并把 **9 处容器定义**改为引用该字典（`_EXPIRE_STATUSES`×5、`ABOLISHED_STATUS_TOKENS`、`EXPIRED_STATUSES`、`_EXCLUDED_FROM_OVERRIDE`、`_VALID_STATUSES`），**取值逐一等价**；**未替换任何业务字面量**（B 阶段）、未改迁移脚本、未改 API 返回。**新受控用例 15 例**（9 值 round-trip／别名归一／映射脚手架覆盖／5 组集合等价／容器同一对象／API tuple 类型）。详见 7.28。 |
> 2026-10-01 **第十四轮 R14-3b：#31-P1 落地——共享 ConfigManager 实例 + 显式失效通知，热路径构造 133 → 1（稳态 0）**。**改动**：`pilotstd/core/config/manager.py` 新增 `get_shared_config()/invalidate_shared_config()/register|unregister_invalidation_listener()` 与 `save()` 写盘后的失效发布（`_publish_config_written`，`_SHARED_LOCK` 用**可重入锁**——首次运行写盘会重入）；消费方三处改从共享实例取（`query/routing/scorer.py`、`query/site_config/_loader.py`、`core/config/service.py`），站点配置模块注册清缓存监听者。**受控矩阵**：`test_parallel_batch_query` 的 `ConfigManager.__init__` **133 → 7**（其中 **6 为一次性 DB 迁移读配置**，落点均在 `@migration` 函数内、受 **P-106** 保护；**热路径仅 1 次**＝共享实例冷启动）、稳态探针 **50 次 get_profile 构造 1 → 0**；`get_profile` 耗时 **577 ms → 5 ms**（单次 0.04 ms）；`save()` **保持 2**（P2 未被破坏）。**新增用例 12 例**（共享/失效 8 例 + 热路径端到端 4 例）；回归 **826 passed / 1 skipped**；CI 13/13。详见 7.27。 |
> 2026-10-01 **第十四轮 R14-3a：#31-P2 落地——`_load()` 改为 dirty 写盘，热路径 save() 135 → 2（−98.5%）**。**改动**（仅 `_load()` 与一处 `import copy`，未触 P1 缓存/注入与 P3 跨进程锁）：`pilotstd/core/config/manager.py::_load()` 在“文件已存在”分支改为**先留存内存态快照 → 补默认值 + 迁移旧键 → 仅当内容真的变化才 `save()`**；**四条契约保持**：① 首次创建仍写盘 ② 补默认值/迁移有变更写盘一次 ③ 显式 `set()`+`save()` 仍持久化 ④ 损坏文件仍先备份 `.corrupted.<ts>` 再以默认值初始化并写盘。**受控矩阵（同一探针，修复前→后）**：`test_parallel_batch_query` **save() 135 → 2**、`get_profile` **577 ms → 153 ms**（单次 4.58 → **1.21 ms**，−73.6%）；对照用例 save() 26 → 1（98 → 23 ms）；单批无谓覆盖写 **≈519 KiB → ≈7.7 KiB**（config.json 4220 B × 2）。**新增受控用例** `tests/unit/core/config/test_manager_dirty.py`（7 例，锁定四条契约 + “完整配置零写盘” + “reload 零写盘”）；回归 **697 passed / 1 skipped**（20 个引用 ConfigManager 的文件集）；Ruff/Mypy/G-020/G-038 全 PASS；CI 13/13。**文档联动（R-006）**：`docs/architecture/modules/core.md` 的「配置」机制条目补写盘语义与量化收益（该文件由 G-031 与 `pilotstd/core/` 强制同步）。详见 7.26。 |
> 2026-10-01 **第十四轮 R14-2（阶段一：仅盘点与方案，不动业务代码）：#31 / #32 原挂窗项攻坚方案**。**盘点结论**：两项**挂窗均已逾期**（窗口＝第十二轮，锚定 `v0.119.x → v0.120.0`；当前 `v0.120.2-2-gcf70b6ad`）——按 #32 行自定的规则本应「当轮转已接受并关闭」，本批视为**用户显式推翻该自动条款**并要求攻坚，故在台账登记**窗口重锚**；**阻塞点均未消除**（#31 三处结构缺陷原样、#32 字面量计数一字未变），但**均非硬依赖**——拆分后每一步都可独立落地。**今日复测（只读探针）**：#31 单查询 `ConfigManager.__init__=133`／`save()=135`／`get_profile=126`（577 ms，4.58 ms/次）、对照 25/26/21；#32 生产字面量 **248 处/50 文件**、测试 **456 处/65 文件**、容器 **9 处/5 名**、前端 `i18n-allow` **27 行**（其中状态值比较 13 处）。**裁定**：#31 优先（活的数据丢失 + 性能缺陷），拆 **R14-3a=P2 dirty 标记**／**R14-3b=P1 实例复用+失效通知**／**R14-3c=P3 跨进程锁（可转观察）**；#32 拆 **R14-4a=A 枚举落地**／**R14-4b=B 后端收敛**／**R14-4c=C 契约+迁移+前端**／**R14-4d=D 测试收敛**。详见 7.25。**本批零业务代码改动**。 |
> 2026-10-01 **第十四轮 R14-1：T-27 修复——`check-repo-compliance.sh` 的「新增文件」检查在推送路径上恒空（假绿）已闭环**。**调查结论（根因）**：脚本用 `git diff --diff-filter=A "origin/${BASE_BRANCH}..HEAD"` 取“本次新增文件”，但**推送事件**触发时 CI 已把 `origin/<base>` 推进到本次 tip（`origin/main == HEAD`）→ **范围恒空** → 恒打印 `PASS: 无新增文件`（白名单/黑名单/根目录可疑文件判定**从未在推送路径生效**）。**修法**：与 docs-sync（T-25/R11-3b）**同一手法**——workflow 显式传 `COMPLIANCE_RANGE=${{ github.event.before }}..${{ github.sha }}`；脚本优先用它，未提供或 `before` 全零时回退 `origin/<base>...HEAD`（三点＝merge-base，PR/本地口径）；**加假绿防护**：显式范围若“变更文件数 == 0”直接 FAIL（拒绝静默 PASS）；并把 `--diff-filter=A` 扩为 **`AR`**（改名后的目标路径同样是新入仓路径，堵住借改名绕过）。**受控矩阵 6/6 通过**：① 修复前假绿（`PASS: 无新增文件`）→ 修复后 FAIL 拦截；② 白名单新增不误拦；③ 仅修改不误触防护；④ 显式范围 0 变更 → 防护 FAIL；⑤ `before` 全零回退不硬失败；⑥ 改名命中黑名单 → FAIL。**验证**：`--fast --guards --local` 与 `--deep` EXIT=0；CI 13/13（`repo-compliance` 步骤日志将打印真实范围与计数）。禁止项遵守：未改与 T-27 无关代码，未触碰 #31/#32。 |
> 2026-10-01 **第十三轮 R13-2：T-33 + T-34 合并收口——`tests/` 永久 skip 归零 + 本地 G-020 口径对齐 CI**。**① T-33**：删除 `tests/gui/test_e2e_settings.py` / `test_e2e_settings_io.py`（均为 `def test_x(): pass` 空壳占位，自述已由 handler 测试覆盖）→ 静态普查 **`mark_skip` 2 → 0**；受控基线 `tests/test_skip_census.py` 由 `== 2` 改为 **`== 0`**；同步更新引用文档（`docs/testing/e2e-test-manifest.md` 两行→说明、`docs/guides/settings-io-engine-pattern.md:178` 改写、本簿「四、已跳过测试」T-10 两行＋更正注记）。**② T-34**：`scripts/check_all.sh` 的 vulture 由 `vulture pilotstd/ --min-confidence 80` 对齐为 CI 口径 **`vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`**（R13-1 首跑 CI 红、本地 `--deep` 绿的成因）。**验证**：`--deep` EXIT=0（含对齐后的 vulture）、`mark_skip == 0`、CI 13/13 success。**禁止项遵守**：未改任何业务代码，未触碰 T-27／#31／#32。 |
> 2026-10-01 **第十三轮 R13-1b：CI 首跑红灯修正（vulture 100% 置信度）+ 新观察项 T-34**。**失败**：run `36795410642`（sha `0d501ee6`）`test-backend` failure → `test-gui-coverage`／`version`／`docker`／`exe` 连带 skipped（8/13）。**根因**：CI 的 G-020 步骤命令为 `vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`（**覆盖 tests/**），而**本地 `check_all.sh` 的 vulture 只扫 `pilotstd/`、`--min-confidence 80`** → 我新增用例里 `def _engine(tuples, …)` 的未用参数被 CI 判为 `unused variable 'tuples' (100% confidence)`，本地 `--deep` 却全绿（**典型“本地绿、CI 红”口径差**）。**修正**：参数改名 **`_tuples`**（vulture 默认忽略下划线前缀），本地按 CI 原命令复跑 **EXIT=0** ✓，三个受影响测试文件 **40 passed**。**新观察项 T-34**：建议把本地 G-020 口径与 CI 对齐（一行改动），待用户放行（P-103／P-107：不越界改门禁）。 |
> 2026-09-27 **第十三轮 R13-1：T-29 清零——`tests/` 全部 8 处永久 `@pytest.mark.skip` 转为真实用例（0 xfail / 0 删除）**。**关键发现**：这 8 处的**函数体全是 `pass`（空壳占位）**——skip 掩盖的不是“失败的测试”，而是**从未写过的测试**。**逐处归宿**：`tests/unit/manager/facade/test_query_subsystem_snapshot.py` ×4（公告缓存命中/未命中/超时降级、缓存优先+引擎降级回填、`_finalize_query` 统计与通知、`query()` 缓存分支+进度接线）与 `tests/unit/query/engine/test_batch_dispatch.py` ×4（`_init_batch_state` 心跳与计数、`_bucket_worker` 双路径、`_dispatch_queries` 并行编排与溢出汇总、`_finalize_batch` 组装与状态复位）**全部按策略第 1 档“修复测试”处理**，用 mock/monkeypatch 驱动真实编排逻辑（不触网、不起真实组件）。**证据**：两文件 **26 passed + 8 skipped → 34 passed（0 skipped）**；静态普查 `mark_skip` **10 → 2**（余下 2 处为 GUI 空壳，另立 **T-33**）；后端全量 CI 同口径 **4033 passed / 14 skipped → 4040 passed / 6 skipped**（+7 passed ＝ 8 处空壳转真实用例、其中 facade 侧 4→5 例；−8 skipped 完全对应）；GUI 全量 1022 passed 不变。**测试侧同步**：`tests/test_skip_census.py` 基线由 `mark_skip >= 8` 更新为 `== 2`，并新增「T-29 两文件零永久 skip 且无 `pass` 空壳」断言。
> 2026-09-27 **第十二轮 R12-8：EventBus 内部锁改 `threading.Lock`——#34 ✅ 已修复（三重回归门全绿）**。**改动**（仅锁相关代码）：`pilotstd/ui/core/event_bus.py` 类级 `_lock` 由 `QMutex()` 改 **`threading.Lock()`**，3 处 `with QMutexLocker(cls._lock):`／4 处 `with QMutexLocker(self._lock):` 改为 `with cls._lock:`／`with self._lock:`，移除 Qt 锁导入、新增 `import threading`；未动业务逻辑／订阅者管理／世代号／reset 协议，未引入第三方依赖，未保留 QMutex 备选。**三重回归门**：① 本地 `probe_mutexlocker_race.py --lock qt` → **37/100 崩（37.0%）**（探针有效性成立）；② 本地 `--lock python` → **0/100 崩**；③ CI `gui-race-probe` run `36725863997`（sha `b3dc567a`）**`2026-09-30T15:29:39.1821302Z === RESULT: loops=50 failures=0 ===`**（结论 `success`）。另加本地端到端：`probe_race_minimal.py`（修复后）**0/100 崩**（修复前基线 47/100）。**#34 终局：✅ 已修复（R12-8）**；候选池 P6 关闭。
> 2026-09-27 **第十二轮 R12-7：最小化复现 + 根因二分定位——#34 根因不在业务逻辑，而在 PyQt6 `QMutex`/`QMutexLocker` × 线程 churn 的 sip 弱引用记账竞态**。**① 最小化复现**：新增诊断脚本 `scripts/probe_race_minimal.py`（脱离 pytest）——单轮 **0.92~1.4s**，**100 次运行 47 次崩溃（47.0%）**，全部 `0xC0000005`，落点＝`event_bus.py:127`（`subscribe()` 的 `with QMutexLocker(...)`）与 `:86`（`reset()` 同类行）。**② PageHeap 受阻**：`gflags`/`appverif` 需写 HKLM IFEO，本会话**无管理员权限**（实测访问被拒绝）、WinDbg MSIX 不含 `cdb.exe` → 改用 **WER LocalDumps（HKCU，无需管理员）+ minidump/pefile 离线解析**，取得原生取证：`ExceptionCode=0xC0000005`，`ExceptionAddress=python312.dll+0x54484` → **`PyWeakref_NewRef+0x114`**，访问参数 **READ @ 0x8**（`PyWeakref_NewRef(NULL, ...)` 读空对象 `ob_type`）。**③ 决定性二分**：新增 **纯 PyQt6** 最小复现 `scripts/probe_mutexlocker_race.py`（不含本项目代码）——变体 A/B（长寿命线程）**0/12 崩**；变体 C（**每轮新建 4 线程 × 200 轮** + QMutexLocker）**6/14 崩（≈43%）**；变体 D（仅把锁换成 `threading.Lock`）**0/14 崩** ⇒ **根因＝PyQt6 Qt 锁在“线程反复创建/销毁”下的 sip 记账竞态**。**④ R12-8 候选（未实施）**：`EventBus` 内部锁由 `QMutex`+`QMutexLocker` 换成 `threading.Lock`（临界区全是纯 Python，无需 Qt 锁），并以两个探针作为回归门。
> 2026-09-27 **第十二轮 R12-6：本地 CI 同口径复现（Python 3.12.10 + PyQt6 6.11.2）**。**环境**：per-user 安装官方 Python **3.12.10** + 隔离 venv（`C:\Temp\pilotstd-probe\venv312`）+ `PyQt6==6.11.0` / **`PyQt6-Qt6==6.11.2`**（`qVersion()` 校验通过）/ sip 13.12.0 + pytest 9.1.1；**仓库零改动**。**结果**：本地 **50 轮 → failures=3**（单轮 min=48.5s / max=114.7s / 均=100.5s）。**✅ 本地复现成功**：已取得可稳定触发的本地复现器与崩溃现场（栈帧/线程/退出码），按用户裁定**不自行修复**，上报由用户裁定 R12-7 方向。 详情见 7.20。
> 2026-09-27 **第十二轮 R12-5：EventBus `reset()` 保活单例 + R4 环境 pin 校正——❌ **回归门未通过（`loops=50 → failures=2`）——按用户裁定立即停止，不自行尝试方向 2／4，转为上报待裁****。**① 环境 pin 校正（已推送 `d0e58f94`）**：探针改为 `shell: pwsh` + 严格错误处理（原先 PowerShell 不因非零退出失败，导致 `pip install PyQt6==6.11.2`（**PyPI 无此版本**）静默失败）；改钉 **`PyQt6-Qt6==6.11.2`**（Qt 运行库真身）并新增**指纹断言**步骤——快检 run `36428298369` 输出 `QT_VERSION_STR(build) 6.11.0` / **`qVersion(runtime) 6.11.2`** / `PYQT_VERSION_STR 6.11.0`，断言通过。**口径纠正**：R12-4d 记的「Qt 6.11.0」是 **PyQt6 编译期常量**，不是运行库版本（真身看 `qVersion()`）。**连带关键发现**：换到正确 Qt 运行库后崩溃率 **4%（2/50 @6.11.0）→ ≈33%（1/3 @6.11.2）**，且落点回到历史用例 `TestThreadSafety::test_concurrent_subscribe` —— 证明方向 3 对复现能力至关重要。**② 保活单例（用户裁定方向 1）**：`reset()` 不再 `cls._instance = None`／不再 `deleteLater()`，只做「关门 → 清订阅者表 + `_generation += 1` → 有界排空 → 复位」；删除实例级 `_accepting` 与无调用方的 `_drain_barrier`；新增**世代号**使 reset 前入队的旧事件失效（逻辑重置替代换新实例）。契约修正：`reset()` 保证 **`instance() is old` 且 `_subscribers == {}`**；用例 `test_reset_creates_new_instance` 不删除、改为 `test_reset_keeps_instance_and_clears_state`。**本地实测**：崩溃点文件 **20 轮连跑全绿（每轮 19 passed / exit=0，Qt 6.11.2）**；全量 `tests/gui/ + test_regression_architecture.py` → **1022 passed / 2 skipped / EXIT=0**（421.8s）。**③ 回归门**：`gui-race-probe` run `36431925613`（sha `fa179320`，loops=50）→ **failures=2**（结论 `failure`）。
> 2026-09-27 **第十二轮 R12-4d：R4 探针结果入账——❌ R2 未完全覆盖根因，#34 维持 P6 并启动 R12-5 深挖**。**探针实测**（`gui-race-probe` run `36313158979`，sha `0404cea4`＝**含 R2**，`windows-latest` + **Python 3.12.10** + **Qt 6.11.0 / PyQt 6.11.0**）：`loops=50 → failures=2`（**第 2 次、第 43 次**迭代），两次均为 `..................F`（18 passed 后第 19 项失败）且子进程退出码 **-1073741819 = 0xC0000005（STATUS_ACCESS_VIOLATION）**；单轮 ≈109s，整作业 10:38→12:39（≈121 分钟）。**失败落点**：文件顺序第 19 项＝本轮新增的 `TestResetQuiescenceProtocol::test_publisher_thread_during_reset_does_not_raise`（3 个守护线程持续 `EventBus.instance()` + publish，主线程连续 `reset()` 5 次）——即 **R2 的静止协议在该“跨线程创建单例 + 并发 reset”场景下仍会触发原生访问违例**。**裁定（按用户预设条件表）**：❌ **R2 未完全覆盖根因 → #34 维持 P6 强制项 + 立即启动 R12-5 深挖**。**附带发现**：① 探针的环境 pin **未生效**（日志指纹为 Qt 6.11.0，而登记为 6.11.2）→ R12-5 必须校正；② 该探针给出了**可复现性 4%（2/50）的回归门**，R12-5 的验收即“同一探针 loops=50 → failures=0”。
> 2026-09-27 **第十二轮 R12-4c：R2 验证数据入账（本地 20 轮循环 + CI 全绿）**。**本地循环**：`tests/gui/test_event_bus_integration.py` 连跑 **20 轮**（每轮 19 passed，`exit=0`，单轮 ≈101.6~103.9s，累计 ≈34 分钟连续执行）→ **0 次 access violation**。**CI 验证**：R12-4b 的 run `36313155232`（sha `0404cea4`）**13/13 作业 success，含 `test-gui-unit` success**（R2 落地后 CI 无回归、无 access violation）。**R4 探针状态**：`gui-race-probe` 已派发两次——修复前（`a7c7e265`）30 轮 **in_progress**、修复后（`0404cea4`）50 轮 **pending**（同一并发组串行）；两次结果待落定后记入 R12-4d。**#34 终局**：R2（根因侧）+ R4（环境实证）均已交付，是否将 #34 从「转已接受」升级为「已修复（R2）并继续观察」待 R4 数据落定后裁定。
> 2026-09-27 **第十二轮 R12-4b：R2 静止协议落地（切断 teardown 跨线程内存访问）**。**改动**：`pilotstd/ui/core/event_bus.py` 四步协议——① 关门（类级 `_resetting` + 实例级 `_accepting=False` + 清空订阅者，`publish/subscribe/unsubscribe` 一律无副作用直接返回）；② 有界排空（实例属本线程才 `processEvents()`；**移除无界 `BlockingQueuedConnection`**——实测它在“实例线程亲和性无事件循环”时会永久挂住 teardown）；③ `deleteLater()` 延迟销毁，不同步析构 QObject；④ 复位 `_resetting`；并把 `publish()` 的入队动作移入临界区（reset 拿到锁即无 in-flight publish 在入队）。**新增受控用例 6 例**（`TestResetQuiescenceProtocol`，含“多线程 publish 与 reset 并发不抛异常”的冒烟用例，该用例正是暴露无界阻塞缺陷的那一例）；**本地实测**：`tests/gui/test_event_bus_integration.py` → **19 passed in 101s**（原 13 例 + 新 6 例，其中 CI 曾失败的 `TestThreadSafety::test_concurrent_subscribe` 通过）。**R4 取证**：`gui-race-probe`（windows-latest + Python 3.12 + PyQt6 6.11.2）已分别对**修复前**（`a7c7e265`）与**修复后**派发循环跑；结果记入 R12-4c。
> 2026-09-27 **第十二轮 R12-4a：T-32 关闭（L1 触发式纳入 .pyi/.pyw）+ R4 探针工作流立项**。**T-32 修复**：`scripts/check_all.sh` 的 L1 触发式 `^scripts/|`+`\.py$` → **`^scripts/|\.py[wi]?$`**（并同步 WARN/日志文案与注释）；**受控验证**：暂存 `pilotstd/_t32_probe.pyi`（142 字符行）→ L1 **如期触发**并 `❌ [FAIL] L1 ruff check`（`E501 Line too long (142 > 120)`，EXIT=1），而修复前同一探针可正常提交（见 7.18）→ **T-32 ✅ CLOSED**，由「六、观察项」移入「一、已清理」。**R4 立项**：新增独立工作流 `.github/workflows/gui-race-probe.yml`（`workflow_dispatch` 专用，不与 ci.yml 常态流水线混跑）——在 **windows-latest + Python 3.12 + PyQt6==6.11.2**（与 `test-gui-unit` 同口径）下循环跑 `tests/gui/test_event_bus_integration.py`，用于取得 #34 的实证：**修复前捕获 access violation／修复后证明 N 次 0 崩溃**。**R2 代码（静止协议）在本批工作区已完成、随 R12-4b 提交**，故本批先以“修复前”状态派发探针取基线。
> 2026-09-27 **第十二轮 R12-3b：方案 C 受控失败实证 + G 第 3 个数据点 + ⚠️ #34 哨兵触发**。**① 方案 C 受控失败（PR #8，一次性分支，main 未受影响）**：注入 `pilotstd/_r12_3_probe.pyi`（142 字符行）→ run `36310949966` **总时长 19.0s**（基线 828s，**−97.7%**）：`lint-fast` failure（16.0s，日志 `E501 Line too long (142 > 120)`），**下游 12 个作业全部 skipped**；实验后 PR 关闭、分支（远端+本地）删除、工作区 clean。**② G 第 3 个数据点**：R12-3 的 run `36310444541` **首个作业启动 +16.0s**（lint-fast）——**原始值超 ≤10s 阈值**；分析见 7.18（同 ref 的 R12-2b 被本次推送取消、runner 分配 + 门控后的指标语义变化）。**③ 方案 C 绿灯代价实测**：快闸启动 +16.0s、时长 14.0s，下游首个作业 +32.0s（门控放行后）→ 绿灯路径 +≈30s。**④ ⚠️ #34 复发（T-26 哨兵触发）**：同一 run 的 `test-gui-unit` 在 `test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe FAILED` 后报 `Windows fatal exception: access violation`（与历史两次逐行同构）→ 按 T-26 预先约定「**再复发 ≥1 次 → 当轮必须做 R2 + R4**」，**哨兵现已触发**，R2（`reset()` 静止协议）+ R4（CI 环境对齐复现）为第十二轮强制项（计划见 7.18）；该 run 的 failure 与 R12-3 改动无关（快闸与其余 9 个下游作业均 success）。
> 2026-09-27 **第十二轮 R12-3：方案 C 落地（lint-fast 快闸 + 下游重作业 `needs` 门控）**。**改动**：`.github/workflows/ci.yml` 新增 **`lint-fast`** 作业（checkout(fetch-depth 1) → setup-python → `pip install ruff mypy` → `python scripts/check_g_038_legacy_errors.py`，命令与范围**零改动**），并给 **9 个下游作业**加 `needs` 门控（`test-backend`／`test-gui-coverage`（保留原 `test-backend` 依赖）／`e2e-coverage`／`security-scan`／`test-frontend`／`test-e2e`／`frontend-e2e`（保留原 `test-frontend` 依赖）／`test-gui-unit`／`repo-compliance`）；`version`（原 `needs` 8 作业）与 `docker`／`exe` 由此**传递性**被门控。**预期收益**：lint 失败时下游**根本不启动**，失败 run 时长 828s → ~30~60s；绿灯路径代价 ≈ +20s（快闸自身时长）。**受控失败实验（本批）**：在一次性分支用 `.pyi` 长行（ruff 会检查 `.pyi`，而本地 L1 触发式 `^scripts/|`+`\.py$` **漏 `.pyi`** → 无需 `--no-verify` 即可提交，实验干净）验证「① 快闸快速失败；② 下游未触发；③ 主分支不受影响」，结果见 R12-3b 批次；同时把该 L1 触发缺口登记为观察项 **T-32**。
> 2026-09-27 **第十二轮 R12-2b：T-28 完整落地（`-rs` 覆盖全部 pytest 调用）+ G 首个数据点入账**。**补充改动**：按用户要求把 `-rs` 从 `test-backend` 扩到**全部 5 处 pytest 调用**——`test-backend`（`tests/`）、`test-gui-coverage`（`tests/gui/`，xvfb 包裹）、`e2e-coverage`（`tests/e2e/`）、Windows GUI E2E（`tests/gui/ -m e2e`）、`test-gui-unit`（`tests/gui/ tests/test_regression_architecture.py`）；复核脚本列出 5/5 均含 `-rs`（YAML 经 PyYAML 解析）。**G 首个数据点（R12-2 推送后实测）**：R12-2 的 run `36309693229` 作业启动延迟 **中位 +2.0s**（2.0~4.0，n=7），**同一时间窗对照**旧组 run `36309485009`（R12-1）**中位 +198s**（197~257）——对照组正是旧模型的排队行为。**T-28 标记 ✅ CLOSED** 并移入「一、已清理」。**路线确认**：R12-3＝方案 C（lint-fast + `needs` 门控），D/E 挂后待 G+C 稳定。
> 2026-09-27 **第十二轮 R12-2：方案 G 落地（并发组按 ref 拆分 + cancel-in-progress）+ T-28 修复**。**改动（仅 CI 配置，检查逻辑零变更）**：① `.github/workflows/ci.yml` 的 `concurrency` 由 `group: ci-cd` + `cancel-in-progress: false` 改为 `group: ci-cd-${{ github.ref }}` + `cancel-in-progress: true`；② `test-backend` 的 pytest 命令加 `-rs`（跳过明细进 CI 日志，可被 `tests/skip_census.py` 解析）。**依据**：R12-1 归因（78 run：33% 的 run 被前一 run 挡住、等待中位 ≈300s；run 中位 828s）。**预期**：同一 ref 内新推送取消被取代的旧 run → 排队≈0；分支/PR 推送不再与 main 争同一槽位。**首个数据点**（推送后实测）与后续 3 次观察记入 R12-3 批次；若 3 次观察的“作业启动延迟”中位 ≤10s，则 G 判定生效，再启动方案 C。
> 2026-09-27 **第十二轮 R12-1：候选池立项 + T-30 排队归因（纯只读取数，未改 CI）**。**候选池**：用户批准 P0~P6 优先级，登记于新增「〇 · **0.2 第十二轮候选池**」。**T-30 归因（78 个 run 全量 + 10 个 run 关键路径，见 7.15）**：① **自串行**——`concurrency: group: ci-cd` + `cancel-in-progress: false` 使 **26/78 = 33%** 的 run 在创建时被前一个 run 挡住，等待 1~1340s（被挡样本中位 ≈300s）；② **runner 分配不是瓶颈**——未被挡时作业启动仅 **+3s**；③ **真正把等待放大的是一次 run 太长**——run 总时长中位 **828s（13.8 min）**，关键路径＝`test-gui-unit` **467s** → `version` 8s → `docker`/`exe` ≈176s；④ **「bump 提交额外 run」假设被证伪**——自动 bump 提交由 `GITHUB_TOKEN` 推送，**不触发任何 workflow**（78 个 run 中 bump 类型 **0** 个）→ 新观察项 **T-31**。**方案对比（A~F）已入 7.15**，推荐「**单并发组改按 ref + `cancel-in-progress: true`**」（1 行，消除 33% 自串行等待且分支推送不再阻塞 main）＋（第二批）缩短关键路径；**待用户选型后进 R12-2 落地**。
> 2026-09-27 **第十一轮 R11-5：T-24 L3 落地（CI 红灯暴露时间实测）**。**改动**：`.github/workflows/ci.yml` 的 `repo-compliance` 作业里，把 `G-038 — 历史遗留错误清零（Ruff+Mypy+裸noqa）`**由末位前移到最前端**（紧跟 checkout）——检查逻辑、命令、范围一字未改，纯步骤顺序调整。**数据（11 次 run 实测，见 7.14）**：该步骤原在作业内 **+13s** 完成（其前面 10 个步骤合计仅 ~3s），前移后 ≈ **+12s** → **顺序收益约 1s**；对照组 `test-backend` 的 Ruff 步骤作业内 **+30~34s**（其前置 `Install dependencies` 独占 23~29s）。**关键结论（原假设需更正）**：真正主导“红灯暴露时间”的是 **runner 排队**——11 次 run 的作业启动时刻相对 run 开始为 **中位 154s、最长 471s**（源于全局并发组 `ci-cd` + `cancel-in-progress: false` 使连续推送串行），而三次 E501 事故 run 的 lint 红灯其实在作业内 **+12~14s** 就已由 `repo-compliance` 的 G-038 报出（`test-backend` 的 Ruff 晚 22~24s）——“等 3 分钟”是排队，不是步骤顺序。故 L3 的实质收益＝让 lint 成为作业内**首个**信号；真正的杠杆（并发组按 ref 拆分／给下游重作业加 `needs` 门控）登记为新观察项 **T-30**，挂第十二轮由用户裁定。**同批入账**：**T-20 关闭（✅ CLOSED，用户裁定方案 A）**、新增 **T-29**（8 处永久 `@pytest.mark.skip`，可偿还候选，挂第十二轮）、T-28 维持挂窗。连带 `docs/governance/gates.md` v1.44 + `README.md` 索引 + 能力矩阵重生成。
> 2026-09-27 **第十一轮 R11-4：T-20 实测与 fixture 基线（口径更正）**。**实测三口径**：① **静态**——`tests/` 的 `self.skipTest` **60 处 / 10 文件**（T-20 原登记值，其中 43 处是`Fixture not found` 守卫）；② **本地运行期**——全量非 GUI 套件 **14 skipped**（网络 6／依赖 5／其他 2／平台 1）；③ **CI 运行期**——run `36306309371` 的 `test-backend` = **44 skipped**（断网 + `_CI` 双因素）。**结论（T-20 原判据被否定）**：43 个 fixture 守卫依赖的 **15 个 fixture 文件全部已入库**，运行期**一次也不触发** → 「因缺 fixture 而跳过」= **0 处**；「60 处会让跳过数长期偏高」是把**静态调用点**当成了运行期跳过数（口径错误，已在 T-20 行更正）。**交付物（仅新增，未改既有测试逻辑）**：`tests/fixture_baseline.py`（fixture 基线登记表 15 项 + 守卫覆盖率判定）、`tests/skip_census.py`（运行期/静态双口径普查工具，把 `pytest -rs` 输出按 fixture／random／platform／network／dependency／other 分类）、配套受控测试 **10 例**。**剩余可治理候选**：8 处 `@pytest.mark.skip`（`test_query_subsystem_snapshot.py` ×4 与 `test_batch_query… dispatch` ×4，理由为“依赖 HTTP／ThreadPoolExecutor／daemon 线程”），属可偿还候选而非环境依赖 → 连同新发现的 T-28 一并挂第十二轮，T-20 终局方案待用户裁定。
> 2026-09-27 **第十一轮 R11-3b：T-25 补丁之二——遗漏补修 + 浅克隆根因**。**① 自曝遗漏**：R11-3 首次提交（`30de04e4`）时 `ci.yml` 的 YAML 修改**因编辑工具在 CRLF 文件上锚点失配而未落盘**（改用补丁脚本重做时只覆盖了两个 .py，漏了 YAML）；CI 日志立刻自证——run `36306033918` 的步骤环境仍为 `DOCS_SYNC_RANGE: 409a5be1…92..`（右端为空）。**② 第二层根因**：回退候选 `origin/main...HEAD` 在推送 main 时因 `origin/main == HEAD` **恒空**。**③ 第三层根因（本轮新查明）**：同一作业更早的 `check-repo-compliance.sh` 执行 `git fetch origin main --depth=1`，**在 tip 建立浅边界**（`.git/shallow`）→ `HEAD~1` 不可用（实测 `fatal: Needed a single revision`）、`git log -n2` 只剩 1 条 → 兜底范围 `HEAD~1..HEAD` 也失效。**修复**：`.github/workflows/ci.yml` 右端改 `${{ github.sha }}`（通用上下文，push 时即本次推送 tip）；`check-repo-compliance.sh` 去掉 `--depth=1`（不再截断历史，行为等价——checkout 本已 `fetch-depth: 0`）；两个脚本新增 `_is_shallow_clone()`——浅克隆下必须声明“历史被截断”，而不是谎称“该范围无变更”。**验证（本地按 actions/checkout 流程端到端复刻浅克隆）**：右端为空 → 输出带浅克隆提示；**显式完整范围 → 真实评估 8 个文件**（证明修复在浅克隆下同样有效）；受控测试 **23 passed**（新增 4 例浅克隆断言）。**连带发现（第六个 CI 盲区同族）**：`check-repo-compliance.sh` 的“新增文件”检查在推送 main 时 `origin/<base>..HEAD` **恒空** → 白名单/黑名单判定从未生效 → 已登记「六、观察项」**T-27**，挂第十二轮。
> 2026-09-27 **第十一轮 R11-3：T-25 补丁——CI 范围取值陷阱（第五个 CI 盲区实证）**——R11-2 收尾核对 CI 证据时发现的直接续修。**根因**：`.github/workflows/ci.yml` 的 `Docs sync check` 步骤写的是 `DOCS_SYNC_RANGE: ${{ github.event.before }}..${{ github.event.sha }}`，而 **push 事件载荷里没有 `event.sha` 字段**（正确为通用上下文 `github.sha`，push 时即本次推送 tip；push 专有字段是 `github.event.after`）→ 右端展开为空 → `DOCS_SYNC_RANGE=<before>..` 被两个脚本判为非法 → 回退 `origin/main...HEAD` → 推送到 main 时 `origin/main` 与 `HEAD` 同一提交、diff 恒空 → **步骤仍旧空转**（GitHub 在步骤日志里直接打印该变量：run `36304263963` = `DOCS_SYNC_RANGE: 27a39d6102c4d076a05f960100668acc08ef9c93..`，左端正确、**右端为空**）——即 T-25 此前属“接线对了但范围算错”的半修。**修复**：① `.github/workflows/ci.yml` 右端改 `${{ github.sha }}`；② `scripts/check_docs_sync.py` 与 `scripts/docs_sync_check.py` 的回退链新增“**候选必须确实含变更文件**”校验（严格模式生效，非严格模式保持旧行为以免本地误抓历史提交去改文档）——空 diff 的候选继续回退到 `HEAD~1..HEAD`，全部为空时以“该范围无变更”显式说明收场，**绝不静默 PASS**；`--range` 硬指定不受该过滤影响。**受控验证**：右端为空 → 两脚本均回退 `HEAD~1..HEAD` 并输出真实判定（此前为“无变更文件／跳过”）；`--range` 仍被尊重；真实未同步范围 → `WARN(告警期)` + EXIT=0。**反证**：新增 11 例受控测试（`tests/test_check_docs_sync.py` 6 例 + `tests/test_docs_sync_check.py` 5 例），对修复前脚本跑 **6 failed**、修复后 **19 passed**。**T-16 观察计时器再次归零**（自 R11-3 起重新计时——前 6 次因 CI 跑的是形近脚本而无效，R11-1 之后那 1 次因范围恒空而无效）。**批次重排**：R11-4 = T-20（测试 fixture 基线）、R11-5 = T-24 L3。连带 `docs/governance/gates.md` **v1.41** + `README.md` 索引 + 能力矩阵重生成。
> 2026-09-27 **第十一轮 R11-2：三债终局裁定（#31／#32／#34）**——本轮**只出裁定书、不做全量偿还**，已逐条写入「二、剩余台账」对应行（四要素：现状量化／偿还方案+成本／转已接受的代价／终局结论）。**判决**：**#31 → [挂窗第十二轮]**（>1 commit 且连锁风险高：`_load()` 的“构造即写回”契约被 `tests/test_core_config.py:333-340` 依赖、P3 引入跨进程锁语义；“只做 P1 缓存”的 1-commit 方案经评估因缺失效通知而被否决）；**#32 → [挂窗第十二轮起分阶段偿还]**（四阶段路线图：A 枚举落地 → B 后端收敛 → C API 契约层+落库迁移 → D 测试收敛，合计 7~12 commit／跨 ≥3 轮，A 阶段须第十二轮完成）；**#34 → [转已接受+代价]**（R1 落地后 14 个 run 的 `test-gui-unit` 14／14 success，满足本行预先约定的接受判据；同时声明该样本在 ≈1／40 基率下零复发概率 ≈70%、不足以证明根因消除，**哨兵＝复发 ≥1 次即当轮做 R2+R4**）。**同批数据更正**：#32 的容器定义点由“7 处”更正为 **9 处／5 个名字**（原探针未解包 `frozenset(...)`，漏计 EXPIRED_STATUSES／_EXCLUDED_FROM_OVERRIDE）；#31 单位成本本轮复测 4.28／4.27／4.28 ms（每次恰 1.00 构造 + 1.00 save）；#34 新增 R1 后 14 run 全绿数据点与统计效力声明。连带 `docs/governance/gates.md` **v1.40** + `docs/governance/README.md` 索引版本 + 能力矩阵重生成；「六、观察项」新增 **T-26**（#34 复发哨兵）；「七、操作记录」新增 **7.10**（裁定取数方式）。
> 2026-09-27 **第十一轮 R11-1（T-25 接线修复）**：开轮侦察发现 CI 的 `Docs sync check` 步骤跑的是**形近脚本** `scripts/check_docs_sync.py`（而非第十轮实现严格模式的 `scripts/docs_sync_check.py`），且前者当时只做 `origin/<base>..HEAD`（推送 main 时恒空）→ **步骤长期空转、恒 `PASS: 无变更文件`**；后果：T-16 的 6 次告警期观察**全部无效**（第四个 CI 盲区实证）。**修复**：`ci.yml` 该步骤**依次跑两个脚本**（`set -e`）；`check_docs_sync.py` 补齐范围回退链与**告警期语义**（未同步只 `WARN(告警期) … 未阻断（exit 0）`，绝不静默 PASS；`--strict-block` 才 exit 1），并修其 GBK 控制台 `UnicodeEncodeError` 假性 exit 1；主簿新增 **T-25**、T-16 行注明**计时归零重置**（自 R11-1 起重新计时）。
> 2026-09-27 第十轮 **收尾之二（CI 事故修复 + T-24 登记）**：① **CI 事故**：`scripts/update_docs.archived.py`（T-15 归档件）头部 4 行超 ruff `line-length=120`（E501）→ `test-backend`（Ruff check blocking）与 `repo-compliance`（G-038）双双失败并连带 skipped 4 个 job（run `36300484047`/`36301031251`/`36301267833`），已由 `fed654ea` 修复（run `36301687032` **全绿 12/12**）；② **T-24 登记（用户裁定：分层落地）**——**L1 ✅** `--fast` 下暂存含 `scripts/` 或 `*.py` 时自动增跑 ruff+mypy（G-038 同口径，<5s，工具缺失降级 WARN）；**L2 ✅** 新增 `--with-lint` 强制增跑；**L3 挂第十一轮**（G-038 的 ruff/mypy 提前到 CI `repo-compliance` 最前端，红灯 1 分钟内暴露）；③ 受控反证：注入一条 150 字符行 → L1 复现 CI 同款 `E501` 并 `FAIL`（EXIT=1）；④ 连带 `gates.md` v1.38、`README.md` 索引、能力矩阵。
> 2026-09-27 第十轮 **收尾（T-23 裁定入账）**：新增「七、操作记录 **7.9**」——「三-B、i18n key 一致性检查」标签**经评估保留不收敛**（功能性子节，非结构性空档；与已收敛的「六-B」→「六」性质不同），附四条裁定理由。**本轮状态：CLOSED**（T-01~T-22 全部销项；T-23 已裁定并补记）。
> 2026-09-27 第十轮 **第五批：章节编号收敛 + 本轮收尾入账（T-22 + T-14/T-15/T-16/T-17/T-19/T-20/T-21）**——① **编号收敛**：「六-B、观察项」→ **「六、观察项」**、「八、操作记录」→ **「七、操作记录」**（含其 `8.x` → `7.x` 八个子节），全库引用同步（`gates.md` v1.31/v1.33 行、归档存根去向表、`docs/ci-lessons.md`），历史提及一律加「编号收敛前为…」限定；② **已清理补登 4 项**：T-14（删死脚本 `check_docs_sync.sh`）、T-15（归档 `update_docs.py`）、T-17（G-032/G-033 排除归档件）、T-19（删两个空章节）——按用户裁定用「根因 + 处置 + 验证 commit」三要素，不填窗口/代价；③ **观察项新增 3 条**：T-16（`docs_sync_check` 严格模式告警期 → 阻断条件与切换方式）、T-20（`self.skipTest` 60 处 → 挂第十一轮）、T-21（本地 vitest 偶发 exit=1 → 挂起观察）；④ 连带 `docs/governance/gates.md` **v1.36**、`README.md` 索引版本、能力矩阵重生成。
> **本文件为技术债唯一数据源（SSOT）**：旧簿 `architecture/technical-debt-registry.md` 已于 2026-09-27 废止并归档为
> [`technical-debt-registry.archived.md`](architecture/technical-debt-registry.archived.md)（仅存归档说明，内容不再维护）；
> 其有价值内容已并入本文件（已跳过测试明细 → 「四」；已接受决策 → 「五」#6/#7/#8；历史条目 → 「一」「六」）。
> 2026-09-27 第十轮 **第四批：P1 清理（T-19 空章节删除 + T-14 废弃死脚本）**——① **删除两个空章节**：「六、待决策」「七、清理项」的唯一内容已于同轮移入「五、已接受的设计决策 · 归档并入」与「一、已清理」；**「六-B、观察项」标签当批刻意保留不改名**（被 `gates.md` v1.31 行、归档存根与本文件共 11 处历史引用）；**该标签已在同轮第五批（T-22）统一收敛为「六、观察项」**（连同「八、操作记录」→「七、操作记录」及其 `8.x` → `7.x` 子节）。② **删除 `scripts/check_docs_sync.sh`**：其自述"渐进式部署，仅提醒不阻断"、全库无任何调用点（`git grep check_docs_sync` 排除自身后 0 命中），功能已被 CI 侧的 `docs_sync_check.py` 覆盖；连带清理 `gates.md` v1.31 行里对它的反引号引用（避免 G-032 交叉引用告警）。③ 连带 `docs/governance/gates.md` **v1.33**、`docs/governance/README.md` 索引版本、能力矩阵重生成。
> 2026-09-27 第十轮（架构优化与债务清算轮）**第三批：代码层 TODO 登记 + 门禁幽灵路径（T-12/T-13）**——① **`AppLayout.vue` 空列表兜底分支与过期 TODO 已删除**（探针实测真实 router：21 条记录 / `showInSidebar` 11 条；`navItems` role 空·guest·未知 → 10 项、user·admin → 11 项 **恒非空**；全库无 `addRoute`），同步修 `AppLayout.test.ts` fixture（原 fixture 无 `showInSidebar` 标记，项数实来自被删兜底），G-010 `AppLayout.vue` **434 → 420**；② **`Tech-Debt #8` 编号悬空补登**（真实指向 `docs/investigations/aura-token-sync-feasibility.md`，落地 `d38e88b1`；与主簿 `TD-8`（测试跳过项）撞号已在此说明）；③ 代码层另 2 类 TODO 入「六、观察项」（`_attachment_parser.py:104` 的 `.doc`/OLE2 `TODO(P2)`、`HomeView.vue:17` 的 grid-layout-plus workaround）；④ **门禁幽灵路径清理**：`scripts/check_g_030_tech_debt.py` 的 `DEBT_REGISTER_PATHS` 删除从未存在过的 `docs/governance/tech-debt-register.md`（保留 `docs/technical-debt.md`），同批更新 `docs/governance/gates.md`（v1.32）+ `docs/governance/README.md` 索引版本 + 重生成能力矩阵（G-031 联动）。
> 2026-09-27 第十轮（架构优化与债务清算轮）**第二批：过期数据与口径刷新（T-07~T-11 + T-18）**——① #11 的 `NotificationConfig.vue` 425 → **438**（批 1 i18n 化所致）；② #32 前端比较点 **9 → 13 处**并刷新全部行号（补登 `WechatTrustIP.vue:229-230`）；③ 「五」#3 警告区"8 个/最高 487" → **3 个 / 最高 438 / 阻断档 0**，并与 #11 去重（指向 #11）；④ 「四」更正"7 个 Handler E2E 已删除"的失实表述（实测 `tests/gui/` 现存 11 个 `test_e2e_*.py`、其中 2 个带 `@pytest.mark.skip`，CI 用 `--ignore-glob` 排除），并补登本节口径下漏登的环境依赖跳过点（`test_manager`×5、`test_file_utils`×3、`gui/test_file_tree`、`unit/.../test_mirror`、`test_i18n_key_count`、`stress_winui`）+ 按机制给出全库跳过点总量（**102 处**）；⑤ 「三、维持现状」行数列标注**物理行/有效行**双口径（426/371、142/109、263/209、143/116、51/39）；⑥ #27 行内未转义 `\|\|` 加转义，消除表格列错位。所有数字均为 2026-09-27 探针实测。
> 2026-09-27 第十轮（架构优化与债务清算轮）开轮：**① 轮次口径立项**（见「〇、0.1」，取代此前无锚点的"第 N 轮"表述）；**② 唯一数据源确立**——旧簿废止归档、有价值内容并入本文件、`scripts/docs_sync_check.py` 的 Handler/Mixin 联动目标重指本文件（原指向旧簿）。归档判定：旧簿「六、G-010 警告基线（9 文件）」等数字已过期（实测警告档仅 3 个），直接废弃；其余按"有价值即并入、过期即废弃"逐节处理。
> 2026-09-27 新登记 **#32（可偿还）后端状态值用中文，前端硬编码中文做比较**——阻碍 i18n 真正完成 + 同一语义两种口径。实测：后端生产代码 **248 处**中文状态字面量（50 文件，9 个值）、测试 **456 处**（65 文件 / 277 个测试函数）、**7 处**重复状态集合定义（无统一枚举）；`废止`（查询/待确认链路）与 `已废止`（统计链路）并存，前端 `PendingView.vue:62-63`（行号已于第二批 T-08 刷新，原记 60-61）还在比较后端**从不返回**的 `'Active'`/`'Withdrawn'`。窗口 **最迟第十轮（架构优化轮）· 待用户确认**（与 #31 同窗）；只登记，未修。
> 2026-09-27 新登记 **#31（可偿还）ConfigManager 多实例交错写 + 查询热路径高频 IO**——每实例一把锁（无文件锁/无单例）、`_load()` 每次无条件 `save()`、`scorer.get_profile()` 每次评分都新建实例；实测一次 mock 查询（4 条目）触发 **126 次构造 + ≈126 次写盘**，且该段无停止检查点（与 2026-09-26 的 CI GUI abort 直接相关）。窗口 **最迟第十轮（架构优化轮）· 待用户确认**；只登记，未修。
> 2026-09-26 收尾轮（monitor 计数误导）：**TD-30（原 #30）已清理**——`pilotstd/monitor/scheduler.py::_on_file` 此前只调 `scan_directory`（仅解析文件名、不搬文件、不写 `file_index`）却照记 `success`：`monitor.auto_archive` 开关与「文件就绪后触发自动归档」的注释**从未有过实现**（`git log -S 'archive_standards' -- pilotstd/monitor/scheduler.py` 为空）。现补上归档（复用统一入口 `archive_standards`，非第二套实现）并改按**真实归档结果**计数（`moved>0` 才记成功；解析不出或归档报错记失败；一条没搬不计成败）；与 TD-28 零重叠（延迟回调先判 `os.path.exists`，链路已搬走的文件根本不会触发回调）。验证：单元 6 例 + 集成真跑 4 例，`git stash` 反证 **8 failed**；至此「一、已清理」共 15 行。**#17a 残留（单条请求/大文件 IO 不可中断）转 ✅ 已接受（ROI 判断）**——本轮补齐逐层实测上界、"取消延迟不累加"的机制依据、7 处穿透成本（估 150–300 行）与两处真无上界的实情（`resp.content` 的空闲超时、`safe_move` 的复制/哈希无超时），该行在「六」内闭环；TD-30 的转义名残留同步闭环（B-1：`_safe_filename` 把 `/` 改为删除而非转义，含 `/` 的 code 往返还原 124/124、0 撞名）——**技术债文档至此零残留**。
> 2026-09-26 第八轮（四线并行）：① **#11 G-010 警告区治理执行完毕**——警告区 **8 → 3**、最高有效行 **487 → 438**（拆 5 个文件，见本条台账）；② **#15 通知聚合器实例不共享** 转最终判断；③ **#16 两个死列** 删除（新增 v60 迁移）；④ **#19 `/api/favorites/{id}/status` 端点存废** 按 `[STATUS_API]` 日志实测 UA 分布定案。各线独立分支、独立提交、独立验证。
> 2026-09-26 第七轮（两条线并行：前端 CI 缺陷 + #17a 到期偿还）：
> ① **前端 CI 缺陷已修**（非"偶发"）：`primevue/tablist/index.mjs:48-53` 在 `mounted()` 排的 150ms ink-bar 定时器无句柄、`unmounted` 不清理，测试文件在 150ms 内结束时回调落在 jsdom 全局被摘除之后 → `ReferenceError: HTMLElement is not defined`（unhandled → `Tests 230 passed` + `Errors 1 error` + exit 1）。修法：`web/src/test-setup.ts` 接管 `setTimeout` 登记未触发句柄，文件级 `afterAll` 清理；连跑 10 次 `Errors 0 / exit 0`。详见「七、操作记录 7.6」。
> ② **#17a 已偿还并移入「一、已清理」**（TD-23）：8 处停止入口对应 7 类 worker 全部加中断检查点（抛 `WorkerAborted` 终止底层流，而非仅跳过信号发射）；中断延迟实测 scan 14ms / query 6ms / 暂停中 query 60ms / DriveEnumerator 54ms（修复前四者均 ~5s 超时 + 保活计数 +1）。残留的单条网络阻塞窗口登记为「六、观察项」。
> 2026-09-26 第六轮（技术债收尾：验证 → 消除 → 记录）：① **#18 巡检改走公开 API 复核**——`GET /api/favorites/export?format=json` 无分页截断（导出行数 105 == 库内行数 105），A/B/C 三组的 `user_favorites` 维度可本地算得全 0；`favorite_downloads`/`announcement_record`/`download_queue` 三表列**未在任何公开端点暴露**（`favorites.py:341-346` 只给 4 个下载字段），其维度仍经 `POST /query` 取证，结果同为 0。② **#11 紧急项已还**：`scripts/check_g_012_sql_schema.py` 有效行 **497 → 139**（拆出 `scripts/_sql_schema_parser.py`），`docker/auth.py` **490 → 394**（拆出 `docker/_static_token.py`）；G-010 警告区 **10 → 8**，最高 487。③ **#15 现状更新**（`StandardManager()` 构造点实测 **9 处**）。④ **#21 新登记**；`docs/deployment/README.md` 过时内容已更新。⑤ 第五节 5 条已接受设计补齐审计轨迹。
> 2026-09-25 勘误与收尾：**#18 只读巡检已通过 `POST /query` API 实际执行完毕**（A/B 两组共 8 项全 0、C 组 0 行）——上一轮把它标为"环境不可达"是**错的**：`admin_db.py` 的表白名单只作用于 `DROP TABLE`，SELECT 不受限制（第三轮"该表不在白名单→只能容器内 SQL"同样不成立）。据此补记「七、操作记录」的执行通道对比，并新增一条待决策：该端点对管理员等同全库读写。
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

### 0.1 轮次口径（2026-09-27 定义，取代此前的"第 N 轮"模糊表述）

| 项 | 定义 |
|---|---|
| **当前轮次** | **第十一轮 —— 债务终局裁定轮**（R11-1 T-25 接线修复 → R11-2 #31／#32／#34 终局裁定 → **R11-3／R11-3b T-25 补丁：CI 范围取值陷阱（第五个 CI 盲区）+ 浅克隆根因** → R11-4 T-20 测试 fixture 基线 → R11-5 T-24 L3（G-038 前移））；上一轮为**第十轮 —— 架构优化与债务清算轮**（专项清理历史技术债／优化底层架构／完善治理门禁） |
| **起算点** | 自 **v0.110.0**（i18n 批 0 启动）起算，至所有 **P0/P1 债务清零或降级**为止 |
| **三债终局裁定（第十一轮 R11-2 完成）** | **#31 → [挂窗第十二轮]**（锚定 v0.119.x → v0.120.0）；**#32 → [挂窗第十二轮起分阶段偿还]**（A 阶段须第十二轮落地，B~D 跨轮推进）；**#34 → [转已接受+代价]**（保留 R1；哨兵＝复发 ≥1 次即当轮做 R2+R4，见「六、观察项」T-26）。原窗口“最迟第十轮”已到期——本轮**只出裁定书**，判决、量化与代价见「二、剩余台账」各行裁定书 |
| **后续规则** | 轮次一律按**季度**或**大版本号**（如 `v0.120.0`）划分，并写明具体版本号或时间窗口；**禁止再使用"第 N 轮"这类无锚点表述**。存量条文中已写的"最迟第 N 轮"按上表映射到第十轮 |

**每轮固定动作（2026-10-01 R15 起，耗时上限 2 分钟）**：批次收尾时**必须**打开「六、观察项 · 真·观察项复核表」，逐条只做两件事——① 若 `Review_Trigger` 已发生 → 当轮就地处理或升级为债务条目（写明版本号/季度窗口）；② 若为计数型（如 T-16 的 `1/3~5`）→ 更新计数并在表内回写。**禁止**再出现"持续观察""待观察"这类无动作表述；未回写计数的批次视为轮次未收尾。

> 说明：本口径生效前登记的"最迟第 N 轮"窗口按上表统一解释；此后新登记的债务**必须**写具体版本号或季度窗口，否则视为登记无效（§〇 四项要求之一）。

### 0.2 第十二轮候选池（2026-09-27 用户批准，按优先级）

| 优先级 | 项 | 预估成本 | 备注 | 登记位置 |
|---|---|---|---|---|
| **P0** | **T-30** CI 排队瓶颈 | 3~5 commit | 真正杠杆；需设计并发组拆分策略 + `needs` 门控方案（R12-1 归因数据 + A~F 对比已交付；**R12-2 已落地方案 G**（按 ref 分组 + cancel-in-progress），数据点 **+2.0s／+7.0s**（同窗对照旧组 +198s）；**R12-3 已落地方案 C**（lint-fast + 9 作业 needs 门控），数据点 3＝+16.0s（超 ≤10s，原因见 7.18）；**收口判定待用户裁定**；D/E 挂后） | 本节 · 六、观察项 T-30 |
| **P1** | **T-29** 8 处永久 skip | ≤2 commit | 可偿还候选；`test_query_subsystem_snapshot.py` ×4 + `tests/unit/query/engine/test_batch_dispatch.py` ×4 | **✅ CLOSED（R13-1）：8/8 转为真实用例，0 xfail／0 删除；两文件 34 passed、`mark_skip` 10→2** |
| **P2** | **T-28** CI pytest 缺 `-rs` | 1 commit | **✅ CLOSED（R12-2／R12-2b）**：`-rs` 覆盖全部 5 处 pytest 调用，CI 日志实证 44 条跳过明细 | 六、观察项 T-28 |
| **P3** | **T-27** 新增文件检查盲区 | 1~2 commit | T-25／T-26 同族（范围恒空 → 假绿）；修法类似 | 六、观察项 T-27（T-32 已 CLOSED，见「一、已清理」） |
| **P4** | **#32** 中文状态值分阶段偿还 | 7~12 commit | 四阶段路线图已就绪；视第十二轮容量决定是否启动 A 阶段 | 二、剩余台账 #32 |
| **P5** | **#31** ConfigManager 交错写 | 3~5 commit | 锚定 `v0.120.0`；需跨进程锁设计 | 二、剩余台账 #31 |
| **P6** | **#34** EventBus 竞态 R2+R4 | 2~3 commit | **⚠️ 哨兵已触发（R12-3 的 run `36310444541`，access violation 复发）→ R2+R4 升为第十二轮强制项** | **✅ CLOSED（R12-8）：根因＝PyQt6 Qt 锁 × 线程 churn；修复＝内部锁改 `threading.Lock`；三重回归门全绿** |

### 0.3 R16 候选池（2026-10-01 R15 收尾，用户裁定优先级）

| 优先级 | 项 | 台账位置 | 预估成本 | 验收判据 |
|---|---|---|---|---|
| **P0** | 门禁受控测试自动化（防 G-040 基线清零事件重演） | 六、观察项 · `tests/` 受控测试不在本地门禁路径 | ✅ **R16 完成** | `check_all.sh` 新增 `run_gate_selftests`：`--fast` 下暂存命中 G-040 基线/门禁脚本（含**删除**）即自动跑其受控测试；`--deep` 无条件跑（CI 的 trinity-gate 走该路径）。**受控实验**：删基线文件并暂存 → `--fast` **EXIT=1**（1 failed, 19 passed）；`--deep` 同样 FAIL；无门禁变更时跳过 |
| **P1** | 两形近 docs 脚本改名消除形近 | 六、观察项 · T-25 残留 | ✅ **R16 完成** | `scripts/check_docs_sync.py` → **`scripts/check_module_doc_mappings.py`**（`git mv` 保留历史；两脚本头部互指职责边界）；同步更新 `ci.yml` 执行行与注释、受控测试（`tests/test_check_module_doc_mappings.py`）、`gates.md` 历史行的反引号引用（去反引号，G-032 保持 13）；**T-16 计数归零重算**。验证：`python scripts/check_module_doc_mappings.py --strict` → PASS；改名后 3 个受控测试 **43 passed** |
| **P2** | schema 门禁提示（零成本 DX） | 六、观察项 · `check_schema_consistency` 约束无提示 | ✅ **R16 完成** | MISSING>0 分支新增两行提示：用中性表名建表 + `ALTER TABLE … RENAME TO <生产表名>`，并说明直接建同名表会因列集不全被判 MISSING |
| **P3** | T-30 收口裁定（纯文档动作） | 六、观察项 · T-30（`待裁定`） | ✅ **R16 完成** | 按「队列效应消除」收口，指标重定义为「首个作业启动 ≤20s 且旧组同窗 ≥100s」；T-30 移入「一、已清理」，观察项活跃 12 → 11 |

### 0.4 R15 观察期（2026-10-01 起，约一周）

**边界（R16 修订，2026-10-01）**：观察期内**允许**改动与三个被观察对象无关的部分（脚本 / 门禁 / 文档 / 测试）；一旦改动 `docker/auth.py`、`docker/entrypoint.sh`、`pilotstd/core/config/manager.py` 三者之一 → **观察期重新计时**；一旦改动 `scripts/check_docs_sync.py` / `scripts/docs_sync_check.py`（第 3 项的仪器）→ **T-16 计数归零重算**（先例：R11-1 / R11-3 两次归零）。

正常使用软件一周，只盯三件事：

| # | 观察点 | 判定标准 | 记录位置 |
|---|---|---|---|
| 1 | 容器重启后是否掉线 | 重启后**无需重新登录**（JWT 持久化生效）；若仍掉线 → 检查 `/app/data/.jwt_secret` 是否生成、`JWT_SECRET` 环境变量是否覆盖 | 决策 #6 归档行 |
| 2 | 配置自愈是否触发 | 日志出现 `配置解析失败，已从写前备份回滚` → 说明发生过损坏并自愈成功；同时看 `config.json.bak` 是否存在且可读 | 真·观察项复核表 · T-35 行 |
| 3 | docs_sync 误报计数 | 每批推送后读 CI `[docs-compliance]` 段：无误报 → 计数 +1（**自 R16 起重新计时，当前 0/3~5**） | 真·观察项复核表 · T-16 行 |

> **配套裁定（2026-10-01，用户裁定）：`trinity-gate.yml` 维持现状，不加 `on: push`。**
> **触发面实测更正**：该工作流实际为 `pull_request`（main/develop）+ `workflow_dispatch`——**不含 push、也不含定时**；
> 本仓日常为直推 main（无 PR 流），故它**只在手动派发时运行**（R16 用 GitHub API 查本次 tip：仅 `ci.yml` 一个 run，印证此点）。
> **裁定理由**：① P0 的防护面已闭环——`--fast` 覆盖开发者提交路径、`--deep` 在手动/PR 时兜底，两者均在本地受控实验中实测拦住（删基线 → `--fast` EXIT=1、`--deep` FAIL）；
> ② 观察期内保持 CI 信号干净（仅 `ci.yml` 13 作业）更利于快速定位 R15 引入的问题；
> ③ 待 **R15 观察期结束且 Phase 4（配置审计）落地后**，结合该工作流的实际使用频率与稳定性，再评估是否纳入 push 触发。
> **再评估触发条件**＝观察期结束 + Phase 4 完成；若届时纳入，属**门禁结构变更**，需同批更新本文件 §0.4 边界与 `docs/governance/gates.md`（G-031）。

> 排期口径：P0 起每批一次独立提交（`--fast --guards --local` + `--deep` 双跑后推送）；**候选池本身不设窗口**——它与各条目的自有窗口（P4/P5 锚定 `v0.120.0`、P6 为触发式）并行生效。


---

## 一、已清理（历史归档）

> **状态**：本区是**已闭环债务的历史归档**（每条保留量化收益摘要，便于回溯"花了多少、换来什么"）。
> 活跃债务**不**在本区——见「六、观察项」开头的汇总表（本批 R14-5 校准后：活跃 **12 条**，存续台账 **0 条**）。

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
| **TD-18** 8 条收藏无队列行 + 36 行 `standard_number` NULL | 原 #18。**修复（2026-09-25 现场）**：补建 8 行队列（`INSERT rowcount=8`、`missing=0`、全 `pending`）+ 纠正 36 行 NULL（`uf updated=36`、`uf_null_after=0`、`fd_unknown_after=0`）+ 显示层改"未加入队列" + 导出加 `COALESCE(f.standard_number, r.standard_number, '')`。现场复核：导出 105 条 0 空值、页面 8 条"已入队"。**只读巡检已完成（2026-09-25，经 `POST /query` API 执行）**：A 组 4 项（uf/fd 标准号与名称空值、`UNKNOWN_*`）全 0；B 组 4 项（四表 `standard_type` 空值）全 0；C 组去重基线 0 行 → **无其他同源回填缺口，本条彻底关闭**。**勘误**：第三轮曾判断"`favorite_downloads` 不在 admin SQL 白名单 → 只能容器内 SQL 修复"，经查 `admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**，SELECT 不受表限制 → 该判断不成立（数据修复本可经 API 完成）；SQL 与巡检语句留档见「七、操作记录」。**2026-09-26 公开端点复核（第六轮）**：`GET /api/favorites/export?format=json` 返回 **105 行 == 库内 `user_favorites` 行数**（接口 SQL 无 LIMIT/分页，`favorites.py:453-470`）→ 全量性成立；本地分组算得 A 组 `uf_std_no_null/empty = 0`、`uf_std_name_null/empty = 0`（键名 `std_name`，来自 `announcement_record`）、`uf_std_no_UNKNOWN_ = 0`；B 组 `uf_std_type_empty = 0`（105 条全 `NationalStd`）；C 组 105 组、**重复组 0**。`favorite_downloads`/`announcement_record`/`download_queue` 三表列**未在任何公开端点暴露**（`_DOWNLOAD_FIELDS` 只有 status/error/last_attempt/updated_at），其维度仍经 `POST /query` 取证：fd 标准号/名称空值、`UNKNOWN_*`、fd/ar/dq 分类空值**全 0** | 2026-09-25 |
| **TD-23** 原 #17a —— worker 阻塞点可中断上限 | 原 #17a（登记 2026-09-23，偿还窗口"最迟第六轮"，第七轮补还）。**根因**：停止信号只让回调"闭嘴"（`if self._stopped: return`），底层 `manager.*_stream()` 循环并不知道要停，仍会跑完全部条目 → `stop_worker_gracefully()` 等满 timeout → 只能保活（#17b 已接受的代价）。**改动**：① `pilotstd/ui/workers/_common.py` 新增 `WorkerAborted` + `check_stop()`（`stop()` 或 `requestInterruption()` 置位即抛）+ `wait_pause_or_abort()`（暂停等待改 200ms 切片，原无超时 `wait()` 在暂停中必然卡死）；② 7 类 worker 的逐条回调（scan/query/download/archive/normalize/announce/auto）全部改为"在检查点抛异常终止流"，而非仅跳过发射；`AutoWorker` 四阶段回调共用同一组检查点（原为无任何停止检查的 lambda）；`ArchiveWorker` 的磁盘预扫描循环、`DriveEnumerator` 的逐盘循环也加检查点；③ 各 worker 增加 `except WorkerAborted` 分支（不误报 error 信号），`finally` 的收尾信号加 `isInterruptionRequested()` 守卫；④ `WorkerAborted` **刻意继承 `BaseException`**——服务层有"单条失败继续跑"的兜底（`manager/facade/_organize.py:106-123` 把 `on_result` 包在 `try/except Exception` 内），继承 `Exception` 会被吞掉导致中断失效；已加专门回归用例（`_ExceptionSwallowingMgr` + `test_abort_survives_service_layer_except_exception`）。`AutoWorker._emit_scan_batch` 同步改为"停止即抛"契约，`tests/gui/test_coverage_workers.py::test_emit_scan_batch_when_stopped` 由"断言不发射"更新为"断言抛 WorkerAborted"（删方法时漏扫测试导致全量 GUI 首轮 2 failed，已修）。<br>**验证（量化验收）**：假 stream（20000 条 × 10ms，不中断需 200s）逐条回调，中途 `stop_worker_gracefully(timeout_ms=5000)`——**修复后**：scan **14ms**（0.3% 预算）、query **6ms**（0.1%）、暂停中 query **60ms**（1.2%）、DriveEnumerator **54ms**（1.1%），四者 `退出=True`、保活计数增量 **0**、残留 **0**；**修复前对照**（`git stash` 掉改动）：四者分别 **5035 / 5009 / 5010 / 5055ms**、`退出=False`、保活计数各 **+1**，并触发 error 级"疑似卡死线程"告警（累计超时 4）。单测：`tests/gui/test_worker_lifecycle.py` 新增 4 例（scan/query 参数化、暂停可中断、盘符枚举）→ 该文件 10 passed。窗口达标情况见「六、观察项」（单条网络请求/大文件 IO 内部仍不可中断，受既有 timeout 约束）。 | 2026-09-26 |
| **TD-22** G-010 高危文件拆解（#11 紧急项） | 编号说明：台账 **#21** 已占给"下载链验证码"，故本条取 TD-22。<br>**A**：`scripts/check_g_012_sql_schema.py` 有效行 **497 → 139**——SQL 文本解析层（`SQL_KEYWORDS`/`PYTHON_BUILTINS`/`_SQL_FUNCTIONS` + 13 个纯函数）整体搬到新模块 `scripts/_sql_schema_parser.py`（470 行 / 370 有效行），脚本以 `from _sql_schema_parser import ...` 复用。<br>**B**：`docker/auth.py` 有效行 **490 → 394**——静态令牌管理（`_STATIC_API_TOKEN`/`_STATIC_TOKEN_INITIALIZED` + `_ensure_static_token_in_db`/`get_static_token`/`refresh_static_token`）搬到 `docker/_static_token.py`（125 行 / 105 有效行）。调用方：auth.py 只 import 其仍内部使用的 `_ensure_static_token_in_db`；唯一外部调用方 `docker/api/settings.py:13` 改为直接 `from .._static_token import get_static_token, refresh_static_token`（**仓内全量 grep 确认无第二处引用**）。曾试"在 auth.py 冗余别名再导出"，但 ruff isort 会把纯再导出拆成 3 条 import（+2 行、且更难看），故改为直接引用新模块。<br>**搬移方式**：程序化按行区间提取（`C:\Temp\pilotstd-probe\split_g012.py` / `split_auth.py`），函数体逐字节未改，仅新增模块 docstring 与 4 条中文说明注释。<br>**验证**：①`python scripts/check_g_012_sql_schema.py` 前后自身输出**逐行一致**（清洗 shell 噪声后各 36 行，diff 为空）且 PASS（0 处不一致 / 73 条 SQL）；②G-010 警告区 **10 → 8**，最高 487，无文件 ≥490（auth.py 已退出警告区）；③ruff 全绿；④mypy `docker/` 单目录错误数前后同为 5（源文件 47→48）——注意 G-038 的**合并口径**（`pilotstd/ docker/` 一起跑）实测 `Success: no issues found in 385 source files`；⑤`tests/test_core.py` 107 passed、auth 相关 6 文件 **73 passed**；⑥`check_all.sh --fast --guards --local` EXIT=0 / 0 FAIL。（过程中唯一回归：新模块注释密度 1.9% < 3% 触发 G-012 注释密度 FAIL → 补"为什么"注释后 PASS） | 2026-09-26 |
| **TD-16 残留** `user_favorites` 两列死列 | 原 #16 残留（登记 2026-09-25）：`archive_retry_count` / `last_archive_attempt` 的唯一读取方是 `/api/favorites/{record_id}/status` 的 5 个旧响应键，随 #16 删除后零读取（`pilotstd/` + `docker/` grep 排除 `_migrate_*` 后 0 命中），但受 P-106（已执行迁移源码不可变）约束不能改 v52/v59 就地删列，故挂到清理项。**修复（2026-09-26）**：新增 v60 迁移 `pilotstd/core/db/_migrate_v60_drop_favorite_retry_columns.py` 幂等 `ALTER TABLE user_favorites DROP COLUMN`（先读 `PRAGMA table_info`，表不存在/列不存在均安全跳过；删列本身失败时降级为 WARNING——两列零读取方，留下的代价只是 schema 未收敛，而抛异常会让 `_run_migrations()` 直接阻断应用启动），`CURRENT_SCHEMA_VERSION` 59 → 60。**验证**：①**真库级**（`sqlite 3.50.4`，脚本 `C:\Temp\td16_v60_verify\verify_v60_real_sqlite.py`，4 段全 PASS）——v59 形态库（2 行数据 + `idx_user_favorites_user_id/status/record_id`）迁移后两列消失、行数与其余列值**逐值不变**、三索引保留；二次打开 + 直接重复调用迁移函数零副作用；无 `user_favorites` 表的库打开不抛异常；全新建库跑完 v0→v60 链无两列；②`tests/test_migrate_v60.py` **10 passed**（含"生产代码零引用"回归护栏与降级路径用例），`tests/test_migrate_v59.py`+`tests/test_migrations_full.py` **101 passed**（v59 语义不变）；③`check_schema_consistency` **EXTRA=0 / MISSING=0**（同步清理 3 处镜像生产的测试 fixture，两处历史 fixture 改由等价 `ALTER` 构造）；④`ruff` / `mypy` 全绿 | 2026-09-26 |
| **TD-19** `/status` 两态不可区分 | 原 #19。**修复（方案②，2026-09-25）**：保留端点 + 新增 `favorited: bool`（三态可辨）+ `[STATUS_API] ua/referer/path` 防御性日志（脱敏、无查询参数）。现场 v0.110.0 实测：有队列行 8 键 `favorited=true`、补建行 8 键 `favorited=true`、未收藏 4 键 `favorited=false`；日志实测 `ua=[redacted]`（敏感词整段脱敏）且无 `?`。**端点存废复评已移入「六、待决策」**（最终决定见 **TD-24**，端点已删除） | 2026-09-25 |
| **TD-24** `/api/favorites/{record_id}/status` 端点删除（#19 最终决定） | 原 #19 残留（「六、待决策」第一行，最迟第七轮）。**决定：删除**——现场日志实测**零仓外调用方**。**取证**（只读，2026-09-26）：镜像 v0.110.2；`GET /api/admin/logs/app`（admin，`docker/api/logs.py:106-122`）+ `GET /api/logs/rotated/{f}`（admin，`docker/api/logs.py:284-298`，分页读全）共读 **48428 行**，覆盖 `app.log.10` 起 **2026-09-02 11:00 → 2026-09-26 15:36**（连续无空洞）；`[STATUS_API]` 命中 **7 次**，全部落在 **2026-09-25 21:48:46～21:49:23** 同一窗口 → **UA 分布：`python-requests/2.34.0` 3、`PilotStdProbe/1.0` 2、`[redacted]` 2；referer：`http://192.168.1.18:9028/favorites` 4、`-` 3；path 全为 `/api/favorites/*/status`**。三类 UA 全为本项目自己的排查探针（`[redacted]` 是 2026-09-25 脱敏验证用 curl 探针，命中 `_SENSITIVE_MARKERS` 被整段替换），**无 curl（非探针）/扫描器/未知 UA**。**对照实证**：现场对该端点发 **1 次只读 GET**（UA `TD19-Control-Probe/1.0`）→ 200 且 app.log 中 `[STATUS_API]` 计数 7 → **8**，证明"日志机制真的生效"，即上述零命中不是日志失效造成的假阴性。**改动**：删路由 `docker/api/favorites.py`（原 222 行）+ 防御性日志辅助代码（`_log_status_api_call`/`_sanitize_header`/`_SENSITIVE_MARKERS`）+ 未再使用的 `Request` 导入；删契约测试 3 类 12 例与仅其使用的 `_FakeRequest`/`_fakeURL`/`_fake_request` 替身；`web/src/api/announce.ts` 清掉 #16 遗留的说明注释；`docs/architecture.md` 端点表删该行、v59 注记标注端点已删；`docs/testing/known-issues.md` #6 状态改「已关闭」。**证据局限**：轮转上限 10 个文件，`2026-09-02` 之前的日志已轮转丢失；窗口内有 11 天空档（`app.log.8` 起于 09-10 11:26，前一段未覆盖）——但 `[STATUS_API]` 日志自 2026-09-25 才随 v0.110.0 上线，窗口完整覆盖其全部存在期，故空档不影响结论。**残留（不擅自改，单独报告）**：`pilotstd/core/db/_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 仍称"两列的读取方是收藏状态接口"——该 docstring **在 `norm_checksum` 覆盖范围内**（实测 `raw != norm`），改动会触发 `DatabaseError: 迁移 v59 的脚本逻辑已变更`（`_migration_checksum.py:109-115`），受 P-106 约束不可改 | 2026-09-26 |
| **TD-25** 查询适配器重复加载证书包（原 #22） | **修复（2026-09-26）**：新增 `pilotstd/query/adapters/_shared_ssl.py`（进程级单例 `default_ssl_context()`，加锁保证首次只加载一次）；9 个默认校验的适配器改为 `httpx.Client(verify=default_ssl_context(), ...)`；`energy` / `sppt` / `sppt_local` 三处自签名站点**保持 `verify=False`** 不动。**根因**：httpx 对 `verify=True`（默认）的**每个** Client 都调 `ssl.create_default_context()` → `load_verify_locations()` 重新解析加载整份证书包（本机单次 ≈1.3s，cProfile 占 96.5%）。**验证**：`StandardManager()` 构造中位 **6.742s → 0.036s**（各 5 次；改后 min 0.035s，首次 0.233s 为一次性证书包加载，目标 <1.0s 达成）；查询适配器相关 8 个测试文件 **270 passed**；ruff/mypy（390 files）全绿；`check_all.sh --fast --guards --local` EXIT=0；文档同步：`docs/architecture/modules/query.md` 新增「HTTP 客户端与 SSL 复用」节（G-031 block 映射） | 2026-09-26 |
| **TD-26** 下载链无读者文档 + G-031 缺口（原 #24） | 原 #24（登记 2026-09-26，偿还窗口"最迟第十轮"）。**根因**：① `docs/` 下无描述 openstd 下载流程的现行文档——#21 修复（`532d994f` + `62fba6ef`）的三个变化点（hcno 权威来源＝openstd 搜索页、端点族 `/bzgk/std/*`、新增「全文下载页」`showGb?type=download`）只存在于代码 docstring 与台账 #21 行；② G-031 的 `DOC_SYNC_MAP` 不含 `pilotstd/download/`，该目录改动**不触发**文档同步检查。<br>**修复（2026-09-26）**：① 新建 `docs/reference/download-pipeline.md`——hcno 权威来源（搜索页逐行 `showInfo('<hcno>')`；**禁用 std_gov 的 pid**，实测 `newGbInfo?hcno=<pid>` 与空/损坏 hcno 响应**逐字节相同**，sha1 `b93e289a82d884a4`、18610 字节）、端点族 `/bzgk/std/*`（旧路径 301 → `requests` 对 POST 的 301 **退化为 GET、body 丢失** → `verifyCode` 恒被拒）、完整步骤链（详情页 → 全文下载页 → `gc` → OCR → `verifyCode` → `viewGb`，含代码行号）、`_VIEW_ROUNDS = 2` 的轮次语义（只在"验证码通过但 viewGb 取到 0 字节"时用第二轮；OCR 失败不消耗轮次）、历史事故与防回归测试清单；② `DOC_SYNC_MAP` 补 `("pilotstd/download/", "docs/reference/download-pipeline.md", "block")`（映射 11 → 12，无死映射）；③ 更正三处陈旧描述——`docs/testing/下载适配器测试方案.md`（头改 openstd + `/bzgk/std/*`；删掉**不存在**的 `tests/manual_test_download.py`（`Test-Path` = False，随 `3d16d662` 删除）改为 `pytest tests/download/adapters/test_openstd_download.py` + 手工核对清单）、`docs/testing/testing-baseline.md:37/59`（"待 P4 步骤1 / 方案锁定（待实现）"→ 已实现，依据 `openstd_download.py:175-256`）、`docs/guides/人工测试方案.md:127`（"日志为 `viewGb`（非旧 `showGb`）"→ 先走 `showGb` 全文下载页再 `viewGb` 取文件）。<br>**验证**：① **受控功能测试**（TD-13 同款）——仅暂存 `pilotstd/download/adapters/openstd_download.py` 末尾一行临时注释 → `python scripts/check_g_031_docs_sync.py` **FAIL**：`[G-031] FAIL: pilotstd/download/ 已变更，但 docs/reference/download-pipeline.md 未同步更新`、`EXIT=1`；`git restore --staged` + 还原文件后 `git status` 干净、脚本回到 `PASS: 无变更文件` / `EXIT=0`；② `python -m pytest tests/download/adapters/test_openstd_download.py -q` = **43 passed**（含 `test_query_result_pid_is_not_used_as_hcno` / `test_search_row_number_must_match` / `TestEndpointPathGuard` 三个契约测试）；③ 连带同步 `docs/governance/gates.md`（新增 v1.19 版本行 + G-031 映射条目 + 11→12 计数）与 `docs/governance/README.md`（gates.md 状态 v1.18→v1.19），并重跑 `scripts/generate_capabilities.py`；④ `ruff` / `mypy` / `check_all.sh --fast --guards --local` 全绿。**残留（不擅自改）**：`docs/governance/gates.md:234` 的 v1.16/v1.15 两行版本历史挤在同一行（缺一个行首 `|`，属既有格式缺陷，与本次改动无关） | 2026-09-26 |
| **TD-27** 迁移 checksum 自愈判定使 P-106 失效（原 #28） | **修复（2026-09-26）**：`pilotstd/core/db/_migration_checksum.py` 的自愈判定由「**当前源码** `raw != norm`」改为「**存储值 == 当前 raw**」——只有库内存的正是当前 raw 哈希（历史 raw 口径、源码未变）才 WARNING + 自愈为标准值，其余一律视为真实源码变更 → `DatabaseError` 阻断启动。**改前行为**：`norm_source()` 去缩进使任何带缩进函数恒有 `raw != norm`（实测 **59/59**）→ **任何**不匹配（含真实逻辑改动）都静默自愈、只记 WARNING，抛错分支不可达（P-106 名义生效、实际失效）。**改后行为**：① 存储值 == 标准化值 → 通过（注释/空行变化不改变标准化值——实测对注入 `#` 注释不敏感）；② 存储值 == 当前 raw → 自愈（WARNING + UPDATE）；③ 其余 → **DatabaseError 阻断启动**。**可达性证据（永久保留）**：新增 `tests/test_migration_checksum_guard.py` **6 例**，其中 `test_logic_change_raises_database_error` 断言「库内是旧逻辑的标准化哈希 + 当前源码逻辑已变」必抛错；实测原始 traceback：`DatabaseError: 迁移 v1 的脚本逻辑已变更，checksum 不匹配` @ `_migration_checksum.py:121`。`tests/test_core.py` 两条旧测试同步改写（`test_checksum_mismatch_auto_heals` → `test_checksum_legacy_raw_hash_auto_heals`，因为旧断言固化的正是本债的错误行为；`test_checksum_real_change_raises` **去掉 mock**，改用真实迁移直接触发）。**验证**：迁移+守卫相关 5 个测试文件 **222 passed**；ruff 全绿；mypy `Success: 390 files`；门禁 EXIT=0。 | 2026-09-26 |
| **TD-28** 收藏链归档期依赖周期机制 → 必然「归档超时」（原 #29） | **修复（2026-09-26）**：`pilotstd/tasks/favorite_download.py` 新增 `_archive_inbox_file()`——下载落 inbox 后**由链路自己**按**规范标准号**解析 → 交给 `archive_standards`（organizer 搬文件进标准库并 upsert `file_index`）→ 再走原有索引轮询复核；超时文案改为「文件未被归档器登记进索引（+ 归档错误原文）」。**根因（比登记时更严重）**：**没有任何调度会归档 inbox**——`auto_scan` 只 UPDATE `standards` 表（不碰 inbox）；monitor 的 `_on_file` 只调 `scan_directory`（仅解析文件名、不搬文件、不写 `file_index`，却照计 success 计数，现场 `processed_today=6 / success_today=6` 即由此而来；该计数误导与缺失归档已由 **TD-30** 修复）→ 因此等多久都不可能成功（候选「延长窗口/调调度顺序」均被证伪）。**关键口径坑**：不能用被 `_safe_filename` 转义过的 inbox 文件名解析——实测 `GB_T 5613-2026_x.pdf` → `logical_code='GB'`，而规范口径是 `'GB/T'`；用错会让「归档写入口径」与「链路查询口径」不一致、永远查不到。**改前行为**：下载成功也必然在 +60 秒判 failed（现场 6/6 复现：`收藏归档超时: favorite_id=2/1/4/3/5/106`，各在对应下载时刻 +60s）。**改后行为**：归档同步完成 → 索引命中即 `done`（不再依赖周期机制）。**验证**：① 单元 4 例（归档被调用且 `source_path` 指向 inbox 文件 / 归档异常与标准号不可解析时原因进 `error_message` / 索引已有则跳过下载与归档）；② **集成真跑端到端**（真实下载引擎 → 真 inbox → 真归档搬库 → 真 `FileIndexRepository` → 真 `_find_in_file_index` 命中 → `done`、`local_path` 指向库内、inbox 清空）；③ 契约测试固定解析口径（含「用转义文件名会退化成 GB」的反证）；④ 相关 5 个测试文件 **101 passed**；ruff/mypy 全绿；门禁 EXIT=0。**现场闭环待下次部署**（本轮按指示只做本地验证）。 | 2026-09-26 |
| **TD-29** 收藏下载链 GB 类成功率 0（`verifyCode` 恒被拒，原 #21） | **修复（2026-09-26）**：① 下载链三处流程修正（`532d994f` + `62fba6ef`）——hcno 权威来源改为从 openstd **搜索页**按标准号逐行解析（**禁用** `std_gov` 的 pid）、端点族 `/bzgk/gb/*` → `/bzgk/std/*`（旧路径 301 使 POST 退化 GET、body 丢失）、新增「全文下载页」步骤（`showGb?type=download`；缺该步时 `viewGb` 返回 200 但 0 字节）；② 归档环节见 **TD-28**。**现场验证（v0.111.2 / `ba3cb65b`，解冻后临时以 `* * * * *` 触发一轮）**：下载 **6/6 成功**——`verifyCode 结果: success` ×6（另 1 次 error 后第 2 次尝试成功）、`viewGb 第1轮取到全文` ×6、字节数 251074 / 528280 / 483415 / 470971 / 381418 / 376488、hcno 全为**搜索页实时解析值**（如 GB/T 2970-2026 `44C04018C3C0E40BE28E19DA0510F24B`，与 09-26 04:00 失败时不同）；全日志 **0 次** `301` / 缺 `showGb` / `0 字节` 痕迹 → 本条原始症状「`verifyCode` 恒被拒、成功率 0」**不再成立**。**遗留**：当时 6/6 在 +60 秒归档超时（已由 TD-28 修复并本地真跑验证；其**现场闭环待下次部署后确认**）。 | 2026-09-26 |
| **TD-30** monitor `_on_file` 从不归档却照记「成功」（原 #30） | **修复（2026-09-26）**：`pilotstd/monitor/scheduler.py::_on_file` 补上归档并改按**真实归档结果**计数——解析（`scan_directory`）→ 交**统一归档入口** `archive_standards(scanned, word_source_root=<inbox 目录>)` → `moved>0` 才记 `success`；解析不出标准号或归档器报 `failed>0` 记 `failed`；一条都没搬（源已不在/目标已存在/条目待确认）**不计成败**；`success` 不再是"文件名解析出来了"。<br>**根因（两条并存，代码实测）**：① **归档从未实现**——配置项 `monitor.auto_archive`（默认 `true`，`monitor/config.py:15` 且 `set_config` 可写）、类注释「文件就绪后触发自动归档」（`scheduler.py:54`）、日志「自动归档已禁用，跳过」三处都在描述归档，但函数体只调 `scan_directory`（**仅解析文件名**：`manager/facade/_scan.py:31-96` 不搬文件、不写 `file_index`）；`git log -S 'archive_standards' -- pilotstd/monitor/scheduler.py` **输出为空** → 自模块引入（`a11a23c7`）起从未调用过归档。② **计数语义错**——`success` 在"解析到 ≥1 条"时 +1，而前端把它显示为「成功」（`web/src/components/FileMonitor.vue:153` `{{ processed_today }} (成功 {{ success_today }} / 失败 {{ failed_today }})`）→ 面板谎报健康。<br>**现场证据**：`processed_today=6 / success_today=6`，而 6 个文件全在 inbox、`file_index` 一条都没有（这正是 TD-28 现场 6/6「归档超时」的同一时段）——"看板健康、实际什么都没入库"。<br>**与 TD-28 不重叠（实测依据）**：`handler.py:54-61` 的延迟回调在 5 秒稳定期后**先判 `os.path.exists(path)`**，而收藏链在下载返回后**立即**归档 → 文件已被链路搬走时回调根本不会触发；故 monitor 只在"文件 5 秒后仍留在 inbox"时动作，即链路归档失败或**手工投放**的场景，链路正常路径下零重叠（链路失败时反而成为兜底）。<br>**验证**：① 单元 6 例（真归档→`success`；一条没搬→**不记** `success`；解析不出→`failed` 且不调归档；归档器报 `failed>0`→`failed`；`word_source_root` == inbox 目录；归档抛异常→`failed`）；② **集成真跑 4 例**（真遍历目录 + 真 `StandardParser` + 真搬文件 + 真 `FileIndexRepository`：合规文件**真的**离开 inbox 且索引可查、源根参数正确、不合规文件留在 inbox 且记 `failed`、`auto_archive=false` 时连计数都不动）；③ **反证**（`git stash` 掉 scheduler 改动跑同一批用例）**8 failed** —— 用例确实钉住新行为而非空转；④ monitor 相关 3 个测试文件 **56 passed**；ruff / G-010 / G-012 / mypy（390 files）全绿。<br>**登记说明**：本条此前只在报告里口头提过（"`_on_file` 忽略 `auto_archive`"），**从未写入台账**（「六、观察项」5 行中无此行）；本次按用户指示正式编号补登。<br>**残留（✅ 已闭环 2026-09-26，B-1）**：原残留是「monitor 只有**文件名**可用，而被 `_safe_filename` 转义过的文件名会解析成另一个 `logical_code`（实测 `GB_T 5613-2026_000002.pdf` → `'GB'`，规范口径 `'GB/T'`）→ monitor 归档**收藏链遗留件**时索引写在 `GB` 键下、链路的 `GB/T` 查询仍查不到」。**修法（改生产者而非消费者）**：`pilotstd/tasks/favorite_download.py::_safe_filename` 把 `/` 由**转义为 `_`** 改为**直接删除**（其余非法字符 `\:*?"<>|` 仍转义），于是 `GB/T 5613-2026` → `GBT 5613-2026_000002.pdf`，而解析器的 code 映射表本就认识 `GBT→GB/T`、`GBZ→GB/Z`。**为何不在 monitor 侧补解析**：monitor 手里只有文件名，任何修补都是"猜哪个 `_` 原本是 `/`"的启发式且只修一家；改生产者后所有解析方（monitor、organizer 的 Word 重解析、人眼看 inbox）同时受益。**全量验证（真实 `_safe_filename` + 真实 parser）**：`code_mapping` 中含 `/` 的 code **124 个**——改后**往返还原 124/124**、去 `/` 后与其他 code **0 撞名**；改前为 **0/124**（`git stash` 反证同时使 3 个用例 FAILED）。边界：`GB/Z 184.1-2026`（分部号）、`GB 18047-2026`（本就无 `/`）、`JB/T` 均正确。新增契约测试 `tests/test_favorite_download.py::TestSafeFilenameRoundTrip`（3 例，数据驱动覆盖全部含 `/` 的 code，含"映射表含 `/` 的 code 少于 100 即失效"的护栏）；连带更新 3 处断言（`tests/unit/test_tasks.py:275/279`、`tests/test_favorite_download.py:37`）。验证：聚焦 75 passed；全量后端回归 + 门禁 + ruff + mypy 见提交说明。 | 2026-09-26 |
| **TD-20** `auto_archive_retry` 在 UI 不可改、不可触发 | 原 #20（登记 2026-09-25）。**修复（2026-09-25）**：①`docker/api/settings.py` 抽出 `_SCHEDULED_JOBS`（5 项，与 `scheduler.start_scheduler()` 一一对应）并补 `auto_archive_retry`；②缺键时用**当前配置值**兜底（防前端漏发把链路静默禁用）；③`SettingsTabSchedule.vue` 增加"收藏下载链（自动归档重试）"开关 + cron 输入 + 提示。**同轮自查补漏④**：`GET /api/settings` 原先不返回 `auto_archive_retry_*`——写侧可选、读侧缺失，前端只能拿组件默认值显示，保存时又把该默认值回写，用户改过的值（如 `0 6 * * *`）会被静默改回 `0 4 * * *`；已在读侧补齐两键，并加"读侧键必须与 `_SCHEDULED_JOBS` 对称 + 必须返回存值而非默认值"两例反证测试。**⑤**再补 `pilotstd/core/config/settings_schema.py` 两条 `SettingDef`（`tasks.auto_archive_retry_enabled/cron`）：e2e 字段一致性测试要求 GET 的键必须被前端 Schema 覆盖或进白名单，不注册则 `test_settings_e2e_consistency.py::test_no_unexpected_backend_only_keys` FAILED（实测）。验证：`tests/test_settings_scheduler_sync.py`（**7 passed**：任务表覆盖、scheduler 差异声明、改 cron 真重排、缺键沿用配置、health 默认值不坏、读侧键对称、读侧返回存值）——后两例在补④前用 `git stash` 实测 **2 failed**、补后 PASSED，"scheduler 差异声明"一例用注入假任务实测 FAILED；`SettingsTabSchedule.test.ts`（3 passed：字段存在、保存随载荷提交、加载回填）；`test_docker_api.py -k settings` 2 passed；`test_settings_auth/e2e_consistency/manager` 合计 21 passed；`SettingsView.test.ts` 6 passed。**现场实证（v0.110.0 / `22d4d90b`，修复前镜像）**：`GET /api/settings` 的 `tasks` 实测 8 键、缺 `auto_archive_retry_*`；同镜像 `GET /api/scheduler/status` 显示该任务已注册（next_run 04:00）；对照组 `date_reminder_cron` 现场值 `0 8 * * *` ≠ Schema 默认 `0 2 * * *` → 用户确实会改这些值，读侧缺键＝改过的值会被静默覆盖（不是理论风险）。**⑥契约细化**：现场 `GET /api/scheduler/status` 共 **6** 个 cron 任务（多一个 `auto_backup`），故 ① 里"与 scheduler 注册表一一对应"的说法不准确——`_SCHEDULED_JOBS` 只覆盖**用户可管**的 5 项，`auto_backup`（固定周日备份、无 UI 开关）为**有意排除**；新增 `test_scheduler_jobs_not_in_settings_are_intentional`：**AST 解析** `docker/scheduler.py::start_scheduler()` 的注册表，断言"未暴露的差异集合 == {auto_backup}"（注入 `fake_probe_job` 实测 **FAILED**、撤销后 PASSED）——旧测试只比对写死名单，scheduler 新增任务也不会失败，改后"漏登记"与"有意排除"才真正分得开。**部署状态（2026-09-26 00:00 实测）**：修复已随镜像 **v0.110.2** 发布（CI 全绿：`version`/`docker` job 均 success，bump 提交 `2719691b`），但**现场 `192.168.1.18:9028` 仍为 v0.110.0 / `22d4d90b`（读侧 8 键）**——该主机不会自动拉取（`docker/api/system.py:152` 的 `POST /api/system/update` 是管理员手动触发的 pull + compose 重建，无定时任务），故"读侧 8→10 键"需**部署后**复核。**✅ 部署后复核通过（2026-09-26 09:32 实测，v0.110.2 / `c421c572`）**：`/api/system/version`=0.110.2、`/api/health` build=`c421c572`；`GET /api/settings` 的 `tasks` **10 键、缺键 0**，`auto_archive_retry_enabled=True` / `cron='0 4 * * *'` 与 `/api/scheduler/status`（next_run 2026-09-27 04:00）一致——读写两侧闭环。**UI 现场复核（Playwright，v0.110.2）**：设置页「定时任务」出现"收藏下载链（自动归档重试）"行、开关为开、cron 输入框 `0 4 * * *`，且页面回填值 == 后端 `GET /api/settings` 值（截图留档 `C:\Temp\pilotstd-probe\shots\settings-schedule.png`，探针不入库）。**残留**：无"立即执行一次"按钮 → 记为可选增强（临时把 cron 改成 `* * * * *` 即可触发，等价覆盖），不进台账 | 2026-09-25 |
| **T-20（原「六、观察项」）`tests/` 运行期 `self.skipTest` 口径更正并关闭** | **R11-4 实测证伪原假设**：T-20 原登记「60 处 skipTest，语义多为 Fixture not found」被当作“运行期跳过数偏高”；实测 ① 43 个 fixture 守卫依赖的 **15 个 fixture 文件全部已入库**（`tests/fixtures/`）→ 运行期**一次也不触发**，「因缺 fixture 而跳过」= **0 处**；② 运行期真实跳过＝**本地 14 / CI 44**（静态 60 只是调用点）。**交付（仅新增，未改既有测试逻辑）**：`tests/fixture_baseline.py`（fixture 基线登记 15 项 + 守卫覆盖率判定）、`tests/skip_census.py`（运行期／静态双口径普查工具）、受控测试 10 例。**终局（用户裁定方案 A）：✅ CLOSED**——“补最小 fixture 基线”的目标已达成（0/43 需治理），继续挂窗无意义；其剩余可治理项拆为新债务 **T-29**。 | 2026-09-27 |
| **T-28（原「六、观察项」）CI 的 pytest 未开 `-rs` → 跳过明细不可得** | **R12-2 / R12-2b 修复（2026-09-27）**：`-rs` 从 `test-backend` 扩到**全部 5 处 pytest 调用**（`tests/`、`tests/gui/`（xvfb）、`tests/e2e/`、Windows GUI E2E `tests/gui/`（参数 `-m e2e`）、test-gui-unit（`tests/gui/` 与 `tests/test_regression_architecture.py`））；复核脚本列出 **5/5 均含 `-rs`**（YAML 经 PyYAML 解析）。**CI 实证**：R12-2 的 `test-backend` 日志输出 **44 条** `SKIPPED [n] path:line: reason` 明细（此前只有汇总行 `44 skipped`），与 R12-1 归因的“CI 44 skipped”完全吻合；汇总 `4007 passed, 44 skipped, 22 warnings in 130.38s`。**口径**：xdist（`-n auto`）下各 worker 各自打印短摘要、汇总可能分段，机器可读清单用 `tests/skip_census.py <日志> --json` 解析（R11-4 交付）。**终局：✅ CLOSED**（用户裁定：1 行修复、与 T-30 同批）。 | 2026-09-27 |
| **T-32（原「六、观察项」）本地 L1 快检触发式漏 `.pyi`** | **R12-4a 修复（2026-09-27）**：`scripts/check_all.sh:303` 的触发式由 `^scripts/` 或 `.py$` 改为 **`^scripts/` 或 `.py[wi]?$`**（覆盖 `.py`／`.pyi`／`.pyw`），同步更新跳过/命中提示文案与注释。**受控验证（双向）**：① 修复后暂存 `pilotstd/_t32_probe.pyi`（142 字符行）→ L1 **触发** → `E501 Line too long (142 > 120)` → `❌ [FAIL] L1 ruff check`、EXIT=1；② 修复前同一探针**可正常提交**（R12-3b 的受控失败实验即借该缺口做到“不绕过钩子”，见 7.18）。**终局：✅ CLOSED**（用户裁定：一行修复、与 R12-4 合并）。 | 2026-09-27 |
| **#34 EventBus 竞态 → Windows 原生访问违例（根因：PyQt6 `QMutex`/`QMutexLocker` × 线程 churn）** | **R12-8 修复（2026-09-27）**：`pilotstd/ui/core/event_bus.py` 内部锁 `QMutex`+`QMutexLocker` → **`threading.Lock`**（临界区全为纯 Python，无需 Qt 锁）。**根因链**：R11-2 转已接受（R1 测试侧兜底）→ R12-3 哨兵复发（access violation）→ R12-4 R2 静止协议（未覆盖）→ R12-5 保活单例 + 环境 pin 校正（仍未覆盖，Qt 6.11.2 下 2/50）→ R12-6 本地 CI 同口径复现（3/50，feasible 复现器）→ **R12-7 根因定位**（最小化复现 47% + WER 转储原生证据 `python312.dll+0x54484 → PyWeakref_NewRef+0x114`、READ @ 0x8 + 纯 PyQt6 二分：Qt 锁 × 线程 churn 6/14 崩 vs `threading.Lock` 0/14 崩）→ **R12-8 修复 + 三重回归门全绿**。**回归门**：① `probe_mutexlocker_race.py --lock qt` 37/100 崩（探针有效）；② `--lock python` 0/100 崩；③ `gui-race-probe` run `36725863997` `2026-09-30T15:29:39.1821302Z === RESULT: loops=50 failures=0 ===`；④ `probe_race_minimal.py` 0/100 崩（修复前 47/100）。**保留物**：两个诊断脚本（`scripts/probe_race_minimal.py`／`scripts/probe_mutexlocker_race.py`）与 `gui-race-probe.yml` 作为回归工具；R1 测试侧兜底保留（纵深防御）。 | 2026-09-27 |
| **T-29（原「六、观察项」）`tests/` 8 处永久 `@pytest.mark.skip`** | **R13-1 清零（2026-09-27）**：8 处**全部按策略第 1 档“修复测试”**转为真实用例（0 xfail／0 删除）——`tests/unit/manager/facade/test_query_subsystem_snapshot.py` ×4 → 公告缓存四分支、缓存优先+引擎降级回填、`_finalize_query` 统计与通知（含 `query_empty`/`record_pending`）、`query()` 缓存分支+进度接线（5 例）；`tests/unit/query/engine/test_batch_dispatch.py` ×4 → `_init_batch_state` 心跳/计数、`_bucket_worker` 双路径、`_dispatch_queries` 并行编排+溢出汇总、`_finalize_batch` 组装+状态复位。**关键发现**：原 8 处**函数体均为 `pass` 空壳**（skip 掩盖的是“从未写过的测试”）。**证据**：两文件 **26 passed + 8 skipped → 34 passed（0 skipped）**；静态普查 `mark_skip` **10 → 2**（余下 2 处 GUI 空壳另立 T-33）；后端全量 **4033 passed/14 skipped → 4040 passed/6 skipped**（+7 ＝ 8 处转真实用例、facade 侧 4→5 例；−8 skipped 对应）；GUI 全量 1022 passed 不变；`tests/test_skip_census.py` 基线更新为 `mark_skip == 2` ＋新增“两文件零永久 skip／无 `pass` 空壳”断言。**终局：✅ CLOSED**。 | 2026-09-27 |
| **T-33（原「六、观察项」）`tests/gui/test_e2e_settings*.py` 2 处永久 skip 空壳** | **R13-2 删除（2026-10-01）**：两文件均为 `def test_x(): pass` 的**空壳占位**（自述“已由 `test_settings_announce.py` / `test_settings_dialog.py` 覆盖”），按用户策略第 4 档**整体删除文件**；覆盖由既有 handler 测试承担；静态普查 `mark_skip` 随之 **2 → 0**；同步更新引用文档（`docs/testing/e2e-test-manifest.md`、`docs/guides/settings-io-engine-pattern.md`、本簿「四、已跳过测试」T-10 两行＋更正注记）。**终局：✅ CLOSED**。 | 2026-10-01 |
| **T-34（原「六、观察项」）本地 `--deep` 的 G-020（vulture）口径窄于 CI** | **R13-2 对齐（2026-10-01）**：`scripts/check_all.sh` 的 vulture 命令由 `vulture pilotstd/ --min-confidence 80` 改为与 CI 完全一致——**`vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`**（并加注释说明口径与 R13-1 的成因）。**依据**：R13-1 首跑 CI 因 `tests/` 内未用参数判红（本地 `--deep` 全绿）→ 本地绿灯必须等价于 CI 绿灯，否则 `--deep` 失去“提交前最后防线”意义。**代价（已接受）**：本地新增 vulture 范围 3 目录，耗时增加 < 2s。**终局：✅ CLOSED**。 | 2026-10-01 |
| **T-27（原「六、观察项」）`check-repo-compliance.sh` 新增文件检查在推送路径上恒空（假绿）** | **R14-1 修复（2026-10-01）**：**根因**：`git diff --diff-filter=A "origin/<base>..HEAD"` 在**推送事件**下恒空（CI 已把 `origin/<base>` 推进到本次 tip → `origin/main == HEAD`）→ 恒 `PASS: 无新增文件`，白名单/黑名单/根目录可疑判定从未生效（CI 日志实证 run 36304263963 / 36306033918）。**修复**：① `.github/workflows/ci.yml` 的 `Run repo compliance check` 步骤新增 `COMPLIANCE_RANGE: ${{ github.event.before }}..${{ github.sha }}`；② 脚本优先使用该范围，未提供/`before` 全零时回退 `origin/<base>...HEAD`（三点）；③ **假绿防护**：显式范围“变更文件数 == 0” → FAIL（拒绝静默 PASS）；④ `--diff-filter=A` → **`AR`**（改名后的目标路径同样受检，堵住改名绕过）；⑤ 输出诊断行 `范围: …（变更 N 个文件，其中新增/改名 M 个）`，让范围本身在日志里可见。**受控矩阵（临时 bare 远端忠实复刻 CI 推送态）：6/6 通过**——① 修复前假绿 PASS → 修复后 FAIL；② 白名单新增 PASS；③ 仅修改 PASS（防护不误触）；④ 显式范围 0 变更 FAIL（防护生效）；⑤ `before` 全零回退 PASS（不硬失败）；⑥ 改名命中文件名黑名单 FAIL。**终局：✅ CLOSED**。 | 2026-10-01 |
| **#31 ConfigManager 多实例交错写 + 查询热路径高频 IO（原「二、剩余台账」）** | **核心闭环（R14-3a/b 2026-10-01 + P3 降级观察）**：**P2**（R14-3a）`_load()` 改 dirty 写盘——仅首次创建/补默认值/迁移有变更才 `save()`；**P1**（R14-3b）按路径共享 `ConfigManager` 实例 + `save()` 写盘后的**显式失效通知**（他方写盘→缓存失效；自己写盘→保缓存但仍通知；站点配置缓存注册监听者），热路径 `scorer.get_profile`、`site_config/_loader`、`ConfigService` 统一取共享实例。**量化**：单批查询 `save()` **135 → 2**、`ConfigManager.__init__` **133 → 1**（稳态 0）、`get_profile` **577 → 5 ms**（单次 4.58 → 0.04 ms）；**P2/P1 契约由 19 例受控测试锁定**（dirty 7 例 + 共享/失效 8 例 + 热路径端到端 4 例），回归 826 passed。**P3（跨进程文件锁）降级为观察项 T-35**：写次数已降两个数量级，跨进程同毫秒写冲突概率可忽略；文件锁跨平台语义（`flock` vs `LockFileEx`／NFS／异常退出）与维护成本高于其防范风险；未来若观测到冲突，优选“原子写+重试”或 SQLite 配置后端（而非文件锁）。**终局：✅ 已清理（核心闭环，P3 转观察）**。 | 2026-10-01 |
| **T-26（原「六、观察项」）#34 复发哨兵**：R1 之后 `test-gui-unit` 零复发的持续观察（T-26 登记）** | 2026-09-27 第十一轮 R11-2 裁定 #34 时设立 | **背景**：#34（EventBus `reset()` 竞态 → Windows 原生访问违例）已裁定 **[转已接受+代价]**——保留 R1（teardown 等待 2s → 5s + `QThreadPool.globalInstance().waitForDone(2000)` + 主线程 `processEvents()`，到期未静止就不 `reset()`），不再投入 R2（`reset()` 静止协议）／R4（CI 装 Python 3.12 + Qt 6.11.2 复现）。**现状（2026-09-27 实测）**：GitHub API 全量 **73 run**，`test-gui-unit` 失败 **3 次**（`3298b530` 2026-09-13、`cdc308f3` 2026-09-26、`71e70054` 2026-09-27）；**R1（`c78cbd89`，2026-09-27T04:26:43Z）之后 14 个 run 全部 success（14／14）**。**统计效力**：历史基率 ≈1／40（2.5%），14 次零复发的概率 ≈70% → 不足以证明根因消除。 | **处置（哨兵，保留有效）**：**每轮复核“R1 之后的 run 统计”并登记数据点**；**触发条件＝再复发 ≥1 次 → 当轮必须做 R2 + R4**（不得再用测试侧序列化／等待搪塞）。**不挂窗口**（已接受项的伴生监控）。**代价**：① 残余间歇红风险——一次抖动即连带阻塞 3~4 个下游 job（`test-gui-coverage`／`version`／`docker`／`exe`）；② R1 属测试侧兜底，若出现**跨用例状态串味**（而非单个用例自身断言失败）即视为兜底失效信号。<br>**⚠️ 哨兵已触发（2026-09-27，R12-3 的 run `36310444541`）**：`test-gui-unit`（job `108595281670`）的 `Run GUI unit tests` 步骤失败——`tests/gui/test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe FAILED` 紧跟 `Windows fatal exception: access violation`（进程 exit 1），与 #34 行的历史两次**逐行同构**（同一测试、同一异常、R1 仍在位）。**按本行预先约定「再复发 ≥1 次 → 当轮必须做 R2 + R4」，R2/R4 自本批起为第十二轮强制项**（不得再用测试侧序列化／等待搪塞）：**R2**＝`event_bus.reset()` 静止协议（`_resetting` 期间 `publish()` 直接返回、单例销毁改 `deleteLater()` 或延迟到 in-flight publish 结束）；**R4**＝CI 环境对齐（装 Python 3.12 + Qt 6.11.2 循环跑 `tests/gui/` 把推断升为实证）。**观察数据**：R1 落地后至本次复发前的窗口为 **14 run 零复发 + 本次 1 次复发**（此前基线 ≈1/40）。<br>**R12-4b：R2 已落地（2026-09-27）**——`pilotstd/ui/core/event_bus.py` 实施静止协议（关门／有界排空／`deleteLater` 延迟销毁／复位；入队动作移入临界区），并补 6 例受控用例（含跨线程 publish 与 reset 并发的冒烟用例）；本地 19 passed。**R4**：新增 `gui-race-probe` 工作流（windows-latest + Python 3.12 + PyQt6 6.11.2，与 `test-gui-unit` 同口径）循环复现，修复前/后两次派发结果记入 R12-4c；**#34 终局（继续保持「转已接受」还是转为已修复）待 R4 数据落定后在同批更新**。<br>**R12-4c 验证数据（2026-09-27）**：① 本地 `tests/gui/test_event_bus_integration.py` **20 轮连跑**——每轮 **19 passed / exit=0**（单轮 ≈101.6~103.9s，累计 ≈34 分钟）→ **0 次 access violation**；② **CI**：R12-4b 的 run `36313155232`（`0404cea4`）**13/13 作业 success（含 `test-gui-unit`）**；③ **R4 探针**：修复前（`a7c7e265`）30 轮 in_progress、修复后（`0404cea4`）50 轮 pending（同组串行），结果将记入 R12-4d。**判据回顾**：R4 的“修复前抓到直接证据”分支**已由 R12-3 的 run `36310444541` 满足**（`test_concurrent_subscribe FAILED` + `Windows fatal exception: access violation` + faulthandler 转储）；“修复后 50 轮 0 crash”分支待探针落定。**#34 终局待裁定**（候选：升级为「已修复（R2）＋ 继续观察」，或维持「转已接受」并把 R2 记为额外缓解）。<br>**R12-4d 终局裁定（2026-09-27）**：R4 探针（`gui-race-probe` run `36313158979`，sha `0404cea4` 含 R2）**`loops=50 → failures=2`**——第 **2**、**43** 次迭代均以 `..................F`（18 passed 后第 19 项失败）+ 退出码 **-1073741819（0xC0000005）**结束；失败落点＝新增冒烟用例 `TestResetQuiescenceProtocol::test_publisher_thread_during_reset_does_not_raise`（跨线程创建单例 + 并发 reset）。**按预设条件表第三行：❌ R2 未完全覆盖根因 → #34 维持 P6 强制项，立即启动 R12-5 深挖**。**R12-5 候选方向**：① `reset()` **不再销毁实例**（改为“清空订阅者 + 保持单例”，从根上消除析构与跨线程引用的交错窗口；需同步调整 `test_reset_creates_new_instance` 语义）；② `EventBus.instance()` 禁止在非主线程创建 QObject（首建绑定主线程，或按线程返回代理）；③ 跨线程 `deleteLater`/GC 与线程亲和性专项（必要时 ASan／Qt 线程模型分析）。**回归门**：`gh workflow run gui-race-probe.yml -f loops=50` → 必须 `failures=0`。**附带**：探针环境 pin 未生效（实测 Qt 6.11.0）需在 R12-5 校正；本轮新增的冒烟用例**保留**（它是当前唯一的稳定复现器，也是 R12-5 的靶子）。<br>**R12-5 结果（2026-09-27）**：① 环境 pin 校正后确认探针真跑 **Qt 运行库 6.11.2**（`qVersion()`），且崩溃率随之从 4% 升到 ≈33%（落点＝历史用例 `test_concurrent_subscribe`）；② `reset()` 改为**保活单例**（永不析构 QObject + 世代号隔离），本地崩溃点文件 **20 轮全绿**、全量 GUI 套件 **1022 passed / EXIT=0**；③ **回归门 `gui-race-probe` run `36431925613`（loops=50）→ failures=2**。**终局：❌ 未通过回归门 → 按用户裁定停止自行尝试方向 2／4，上报待裁（候选：方向 4 ASan／Qt 线程模型专项）。**<br>**R12-6（本地 CI 同口径复现）**：本地 Python 3.12.10 + PyQt6/Qt 6.11.2 + sip 13.12.0 隔离 venv，50 轮 → **failures=3**——**本地复现成功**，崩溃现场已存档（逐轮日志 `r12_6_iter_NN.log`）；**不自行修复**，等用户裁定 R12-7。<br>**R12-7 根因定位（2026-09-27）**：最小化复现（`scripts/probe_race_minimal.py`，单轮 ≈1s）**100 轮 47 崩（47%）**；PageHeap 因**无管理员权限**受阻，改用 **WER 转储 + minidump/pefile 离线符号解析**取得原生证据——`python312.dll+0x54484 → PyWeakref_NewRef+0x114`，**READ @ 0x8**（NULL 对象弱引用）；**纯 PyQt6 二分**（`scripts/probe_mutexlocker_race.py`）：长寿命线程 0/12 崩、**线程 churn + QMutexLocker 6/14 崩**、**换 `threading.Lock` 0/14 崩** ⇒ 根因＝**PyQt6 Qt 锁 × 线程 churn 的 sip 弱引用记账竞态**，与 EventBus 业务逻辑无关。R12-8 候选：EventBus 内部锁改 `threading.Lock`（待裁定）。<br>**R12-8 终局：✅ 已修复（2026-09-27）**——`pilotstd/ui/core/event_bus.py` 内部锁由 `QMutex`+`QMutexLocker` 换为 **`threading.Lock`**（仅锁相关代码；业务逻辑／订阅者管理／世代号／reset 协议未动）。**三重回归门全绿**：① 本地 `probe_mutexlocker_race.py --lock qt` **37/100 崩**（探针有效）；② 本地 `--lock python` **0/100 崩**；③ CI `gui-race-probe` run `36725863997`（`b3dc567a`）**`2026-09-30T15:29:39.1821302Z === RESULT: loops=50 failures=0 ===`**。本地端到端：`probe_race_minimal.py` 修复后 **0/100 崩**（修复前 47/100）；`tests/gui/test_event_bus_integration.py` 19 passed。**哨兵（保留）**：任何 GUI 作业再现 access violation → 立即重跑 `gui-race-probe`（loops=50）并回溯是否引入新的 Qt 锁／线程 churn 模式。 **终局：✅ 已清理（R12-8 随 #34 修复关闭）。** | 2026-10-01（R14-5 归档） |
| **T-24（原「六、观察项」）`.py` 变更的快速 lint 未覆盖 → 本地全绿、CI 连红三次（T-24 登记） | 2026-09-27 第十轮 CI 事故复盘 + 用户裁定（分层落地） | **根因**：ruff/mypy 只在 `check_all.sh --deep` 与 CI 中执行，**不在 pre-commit 的 `--fast` 口径内**，且各机 PATH 不保证存在 → 归档件超宽行（E501：362 / 256 / 201 / 185 字符）未被本地拦住；CI `test-backend`（Ruff check blocking）与 `repo-compliance`（G-038）双双失败，**连带 skipped `docker`/`exe`/`version`/`test-gui-coverage`**（run `36300484047`、`36301031251`、`36301267833`；已于 `fed654ea` 修复，run `36301687032` 全绿 12/12）。**现状（分层）**：**L1 ✅ 已落地**——`--fast` 下若暂存变更含 `scripts/` 或 `*.py`，自动增跑 `ruff check pilotstd/ docker/ tests/ scripts/` + `mypy pilotstd/ docker/`（与 G-038 同口径，<5s）；工具缺失**降级 WARN 不阻断**（沿既有理由：各机 PATH 不一致）。**L2 ✅ 已落地**——新增 `--with-lint` 显式强制增跑（不依赖暂存区）。**L3 ✅ 已落地（R11-5，2026-09-27）**——`.github/workflows/ci.yml` 的 `repo-compliance` 作业里 `G-038` 步骤**由末位前移到最前端**（紧跟 checkout；命令/范围/逻辑零改动）。**实测数据（11 次 run，见「七、操作记录 7.14」）**：该步骤原在作业内 **+13s** 完成（前面 10 个步骤合计仅 ~3s）、前移后 ≈ **+12s** → **顺序收益约 1s**；对照组 `test-backend` 的 Ruff 步骤作业内 +30~34s。**结论更正**：红灯暴露时间由 **runner 排队**主导（11 次 run 作业启动中位 **154s**、最长 **471s**；源于全局并发组 `ci-cd` 串行），而非步骤顺序——三次 E501 事故 run（`73a35ed5`／`f1e55d4a`／`e94f8ddb`）的 lint 红灯本就在作业内 +12~14s 报出；故 L3 的实质收益是“让 lint 成为作业内首个信号”，真正的杠杆登记为 **T-30**（并发组按 ref 拆分／下游重作业 `needs` 门控）挂第十二轮。 | **窗口：已收口（L1/L2 第十轮落地、L3 R11-5 落地）**；后续效率优化转入 T-30。**L1/L2 已于第十轮落地**（commit `T-24` 批次）。**代价**：① 有 `.py`/`scripts/` 变更时 `--fast` 由 <10s 增至约 13~15s；② 未装 ruff/mypy 的机器只见 WARN、仍可能漏到 CI（缓解：本机已装 ruff 0.15.17 + mypy 2.1.0，PATH 目录 `%APPDATA%\Python\Python314\Scripts`）；③ L3 落地需重排 CI job 依赖，属门禁结构变更。 | **终局：✅ 已清理（L1/L2/L3 全部落地收口）。** | 2026-10-01（R14-5 归档） |
| **R14-5 适配器模板三缺陷（伪占位符／`-%}` 缩进／死条件片段）** | **根因**：`pilotstd/templates/adapter/**` 从未被真实渲染过（既无生成物测试，也不在 ruff/mypy 范围——`pyproject.toml` 排除 `pilotstd/templates/**`），三个缺陷因此静默存活：① 3 处伪占位符 `{{模板引擎.*}}`（cookiecutter 默认 `Undefined` 下**渲染为空串**，模块注释被吃掉）；② **48 处 `-%}`** 尾随空白控制吞掉换行与缩进 → 生成物 `IndentationError`（默认 `response_type` 即生成**不可编译**的适配器）；③ 1 处残留死条件 `[rec] if True  # … else mock_resp` → 生成物 `SyntaxError`。**修复（R14-5 任务一）**：模板状态字面量改引 `Status.*.value`；修 3 处伪占位符；`-%}` → `%}`；死条件片段按等价语义改写（`if True` 分支恒被选中，故删死分支）；**新增生成物契约测试** `tests/unit/test_adapter_template_generation.py`（10 例）：四种 `response_type` 分支渲染 + `ast.parse`/`py_compile` + AST 扫描零裸状态字面量 + 生成物 import 行 `exec` 验证可解析 + 夹具 JSON 保留外部中文载荷。**验证**：4 个分支全部渲染并编译通过；10 passed；ruff 全绿。 | 2026-10-01 |
| **`vue-tsc` 不带 `-p` 恒假绿（教训固化）** | **根因**：`vue-tsc --noEmit`（缺 `-p tsconfig.app.json`）在方案式 `tsconfig.json`（`files: []` + references）下**不检查任何文件、恒返回 0**；R14-4c 本地据此误判"类型全绿"，门禁口径才暴露 2 处类型缺口。**处置**：`scripts/check_all.sh` 的前端类型检查**显式带 `-p tsconfig.app.json`**（注释已写明"不带 -p 时曾为假绿"）；本行作为教训留痕（与 G-038/T-34 的"本地口径必须等价 CI"同族）。 | 2026-10-01 |
| **`_batch.py` 溢出回收逻辑部分内联（原「六、观察项」）** | **归档（R15，无行动项）**：溢出处理自始即委托 `_overflow`（`_batch.py:22` 导入、`:55 self._overflow = overflow`），`query_batch_parsed` 在该文件内已无引用；关联的纯逻辑提取早已完成（AutoFlowEngine 7 + ScanFlowEngine 31 + AnnounceFlowEngine 20 测试）。**保留此行的唯一目的**：将来再动 `_batch.py` 时有对照物。 | 2026-10-01（R15 归档） |
| **数据库迁移链顺序依赖（v7 需 `file_index` 先存在）（原「六、观察项」）** | **归档（R15，无行动项）**：`file_index` 由迁移链自身创建（`_migrate_v2_v15.py::_migrate_v2_add_file_index`），后续迁移按 `CURRENT_SCHEMA_VERSION` 顺序执行——该依赖是**链内固有顺序**，不构成外部风险。**保留此行的唯一目的**：将来重排迁移顺序时避免踩坑。 | 2026-10-01（R15 归档） |
| **已接受决策 #4「Mixin 模式拆分大文件」→ 归档（已被 ADR-010/Handler 组合取代）** | **原决策**（2026-06-30）：单文件 >500 行阻断 G-010，用 Mixin 组合在不改对外 API 的前提下切分；当时记录的代价是"Mixin 组合增加一层间接、`super()`/MRO 成为隐式契约"。<br>**现状实测（2026-10-01）**：① `docs/adr/ADR-010-mixin-refactor.md` 状态已是 **🗄 Deprecated**（由 Handler 组合系列 ADR 承接）；② 全库 `class …(*Mixin…)` 只剩 **1 个** `_WindowLifecycleMixin`（`pilotstd/ui/main_window/_window_lifecycle.py:18`，Qt 生命周期硬约束，`tests/test_architecture_mixin_guard.py` 明令豁免），其余拆分载体为 `*_ops.py` **组合**（`self.ops = …`）。<br>**结论**：该决策作为"当前政策"已不成立（项目自己已改判并完成 16→1 重构），台账保留它只会误导读代码的人；**无需任何代码改动**，仅归档并注明取代关系。 | 2026-10-01（R15 归档） |
| **SQL 文本内嵌 1 处状态字面量（原「六、观察项」）** | **R15 修复（2026-10-01）**：`pilotstd/core/validity_checker.py::register_new_standard` 的 `INSERT` 原写作 `VALUES (?, '未知', ?, ?, ?)`——该中文值嵌在 SQL 文本内，R14-4b 的 AST 口径收敛**覆盖不到**，是全库最后一处漏网。**改为占位符参数** `VALUES (?, ?, ?, ?, ?)` + `Status.UNKNOWN.value`。**验证**：`pytest tests/unit/core/test_validity_checker.py -q` 通过；`git grep` 中 `'未知'` 仅剩 `_migrate_v16_v49.py`（P-106 保护的历史 DDL）。 | 2026-10-01（R15 归档） |
| **本地 `tests/` 全量运行遇网络用例挂起（原「六、观察项」）** | **R15 修复（2026-10-01）**：`tests/test_manager.py` 的 5 处网络用例原先只有 `skipif(CI)` 守卫，本地无网时会**真实执行并长时间阻塞**（R14-3a/3b/4d 各踩一次，工具调用被迫超时中断）。**改动**：新增模块级 `_NETWORK_DISABLED`（CI 或未设 `PILOTSTD_RUN_NETWORK_TESTS=1`）与 `skip_network` 标记，5 处装饰器统一替换；另加 `pytestmark = pytest.mark.timeout(30)`。**实测**：`pytest tests/test_manager.py -q` → **48 passed / 5 skipped in 3.28s**（此前无限挂起）。**注**：pytest-timeout 在 Windows 只能 dump 栈、无法打断阻塞的 socket 读，真正解决问题的是 opt-in 跳过而非超时。 | 2026-10-01（R15 归档） |
| **已接受决策 #6「JWT_SECRET 固定默认值（不设环境变量则进程内随机）」→ 归档（R15 已实现持久化）** | **原决策**（2026-06-30）：两种取舍都已接受——显式设 `JWT_SECRET` 时密钥泄露无法靠重启收敛；不设时每次进程启动随机，重启即全体会话失效。<br>**R15 落地（2026-10-01）**：`docker/auth.py` 新增 `_load_or_create_secret()`，优先级为 **环境变量 > `DATA_DIR/.jwt_secret`（权限 600）> 新生成并落盘**；`docker/entrypoint.sh` 同步改为 「环境变量 > 读落盘文件 > 交给应用生成」，不再每次启动随机。**两头问题同时消除**：既不重启掉线，也不依赖固定值。<br>**验证（实测三态）**：首启生成 → 复启复用（两次 `SECRET` 一致、文件存在）；`JWT_SECRET=explicit` 时环境变量优先。**注**：Windows 本机 `os.chmod` 只切只读位（显示 0o666），容器内 Linux 为 600。 | 2026-10-01（R15 归档） |
| **T-30（原「六、观察项」）CI 红灯暴露时间被 runner 排队主导 + 下游重作业未做 lint 门控** | **修复（R12-2 / R12-3，2026-09-27）**：① **方案 G**——`concurrency.group` 改 `ci-cd-${{ github.ref }}` + `cancel-in-progress: true`；② **方案 C**——新增 `lint-fast` 作业并把 9 个重作业接上 `needs` 门控（含传递性：`version` → `docker`/`exe`）。**实测（见 7.15/7.17/7.18）**：队列效应消除——新组首个作业启动 **+2.0 / +7.0 / +16.0s**，同窗旧组对照 **+197~257s**（中位 ≈198s）；lint 失败时下游 skipped（受控实验）。**收口裁定（R16，用户 P3裁定）**：原阈值「连续 3 次中位 ≤10s」的第 3 个数据点 16.0s 未达标，但成因是「门控落地后该指标已含 runner 分配 + 快闸时长两层」而非队列 → 按 **「队列效应消除」** 宣告第一阶段收口，指标重定义为「首个作业启动延迟 **≤20s** 且旧组同窗对照 **≥100s**」。**残余**：关键路径缩短（方案 D/E，`test-gui-unit` 467s 为 run 中位 828s 的主因）**不排期**（属性能优化，非债务）。 | 2026-10-01（R16 归档） |
| **T-25 残留（原「六、观察项」）两形近 docs 脚本** | **主体修复**：R11-1~R11-3 修掉「CI 步骤跑错脚本 + 范围恒空 → 假绿」；**残留（R16 P1 解决）**：`check_docs_sync.py` 与 `docs_sync_check.py` 仅差 `check_` 前缀，曾直接导致接线事故，且两次观察计时因此作废。**改动**：`git mv scripts/check_docs_sync.py scripts/check_module_doc_mappings.py`（语义化命名：模块 → 文档映射），两脚本头部互指职责边界；同步 `ci.yml`、受控测试（`tests/test_check_module_doc_mappings.py`）与 `gates.md` 引用。**验证**：脚本 `--strict` 运行 PASS；改名后 3 个相关受控测试 **43 passed**；G-032 保持 13 无新增；T-16 计数按既定口径归零。 | 2026-10-01（R16 归档） |
| **#32 状态值中文化自由字符串（原「二、剩余台账」）** | **✅ 已清理（A→D 四阶段闭环，2026-10-01）**：**A**（R14-4a）建权威字典 `pilotstd/core/status.py`（`Status` 9 值，value 与现网中文逐字一致；i18n/英文键脚手架；`normalize_status` 别名归一）并收敛 9 处容器定义；**B**（R14-4b）后端业务字面量 **211 → 0**（199 处改引 `Status.*.value`，分 5 个原子 commit）；**C**（R14-4c）API 契约显式化（`status_key` 字段 + 键/中文双口径过滤）＋ **v61 迁移**把状态列默认值收敛到字典（P-106 合规）＋ 前端 13 处中文比较 → **0**（`web/src/utils/stdStatus.ts` 唯一事实源）；**D**（R14-4d）测试字面量 **504 → 25**（替换 456 处／67 文件）＋ **5 处哨兵**（字典契约／扫描基准／API 历史入参／解析层外部输入／DB 历史 DDL，均带注释与断言）。**终局收益**：状态值单一事实源（生产+测试同源）、i18n 与逻辑彻底解耦（改文案不再静默破坏判定）、枚举 value 受跨层哨兵保护；**代价（接受）**：新增测试文件/代码需引用字典而非直写中文（哨兵除外，见 7.31 的五处清单）。 | 2026-10-01 |


| `test_migration_runs_pending` patch 路径错误（旧簿「三、已知问题」#5 并入） | 旧簿记载：断言原先 patch 了错误的符号路径，已修正为 `database.CURRENT_SCHEMA_VERSION`。**2026-09-27 并入时复核**：现由模块级导入取真值（`tests/test_core.py:179` `from pilotstd.core.db import CURRENT_SCHEMA_VERSION`），与记载一致 | 2026-06-30（2026-09-27 自旧簿并入） |
| PyInstaller `--noconsole sys.stderr=None` 兜底（旧簿「三、已知问题」#16 并入） | 旧簿记载：`_SafeStream` 于 2026-07-09 禁用、改用原生 stderr。**2026-09-27 并入时复核**：全库 `git grep _SafeStream` 命中 **0 处代码**（仅旧簿文本残留），确认已回退 | 2026-07-09（2026-09-27 自旧簿并入并复核） |
| AppLayout.vue「空列表兜底」分支 + 其过期 TODO（#49 收尾，T-12） | **根因**：`navItems` 改为「从路由 meta 动态生成」（#49）后，仍保留一段"meta 派生列表为空时返回硬编码 10 项"的兜底，其 TODO 原文 `// TODO: Remove fallback after #49 verification - deadline 2026-08-09`（**登记到期已过 49 天**）。**实测（2026-09-27，临时 vitest 探针用真实 `router`，探针已删）**：`router.getRoutes()` 共 **21** 条记录、其中 `showInSidebar` = **11** 条；`navItems` 在 role 空 / `guest` / `unknown-role` 下 **10 项**（`/settings` 因 `permission:'user'` 被过滤）、在 `user` / `admin` 下 **11 项** → **恒非空**；另全库 `git grep addRoute` **0 命中**（纯静态路由，不存在"后加路由把列表变空"的路径）。**处置**：删除兜底分支与过期 TODO，原位写明复核结论与实测数据；同步修 `AppLayout.test.ts` 的 fixture——原 fixture 的 8 条路由**无任何 `showInSidebar` 标记**，其项数实际来自这段被删的兜底，现按真实 `router.ts` 的 meta 形态构造（含 `titleKey` / `sidebarOrder` / `permission:'user'`）。**验证**：`src/components/AppLayout.test.ts` **3 passed**；`vue-tsc` 0 错误；前端全量测试见本轮报告；G-010 `AppLayout.vue` 有效行 **434 → 420**（仍 >400，警告档个数不变） | 2026-09-27 |
| **Tech-Debt #8**（Aura text/content token 运行时同步）——代码注释编号悬空/冲突补登（T-12） | **根因**：代码注释引用 `Tech-Debt #8`（`web/src/composables/useThemeSync.ts:3/46/83/104`、`web/src/theme/aura-token-map.ts:2/29/53`，含 `hotfix(tech-debt#8)` 字样），而**主簿中长期无对应条目**——主簿 `TD-8` 是另一个主题（`test_04_large_batch_sub_buckets`，测试跳过类），两套编号撞号且互不指向。**真实指向（2026-09-27 定位）**：`docs/investigations/aura-token-sync-feasibility.md`，其标题即《Aura Token 运行时同步可行性报告（Tech-Debt #8 · P0 调研）》，内含 P0（版本策略/Token 解析链/运行时 API 边界，Playwright 实证）→ P1（映射表范围 + 组件作用域 token 实测）→ P2（运行时注入机制，"连续切换 10 次 light↔dark 无残留"验证表）三阶段结论；落地提交 `d38e88b1 fix(theme): sync Aura text/content tokens per theme (tech-debt #8 P2)` 及其后续 hotfix（`f307535a`/`7b43fd93`）。**处置**：本行即为其在主簿的正式登记（**不改代码注释**——该编号在代码与调研报告间是自洽的，缺的只是主簿这一环；编号冲突在此明确说明）；此后全库检索 `Tech-Debt #8` 可在主簿命中 | 2026-09-27（补登） |
| mypy `--no-verify` 豁免策略（旧簿「四、Mypy 豁免项」并入，**并入即作废**） | 旧簿策略原文："mypy 错误不阻断 pre-commit（使用 `--no-verify`），CI 中仍运行 mypy 但标记为 non-blocking"。该策略与现行 **G-038 历史遗留错误清零**（`scripts/check_g_038_legacy_errors.py`，判据＝"存在任何未修复的历史遗留错误"）及 **P-104**（门禁不绕过：禁止 `noqa`/`skipif`/`continue-on-error`）**直接冲突** → 策略作废；`attr-defined` 已于 2026-08-25 实测清零（旧簿同记 244→0） | 2026-09-27（自旧簿并入并判定作废） |
| 死脚本 `scripts/check_docs_sync.sh`（T-14 补登） | **根因**：自述"渐进式部署，仅提醒不阻断"，且**全库 0 调用点**（`git grep check_docs_sync` 排除自身后无命中；不在 `.husky/pre-commit`、`check_all.sh` 任何模式、CI 任何步骤）——其"源路径 → 需更新文档"提醒映射已被 CI 侧 `docs_sync_check.py` 覆盖。**处置**：`git rm`（119 行）；`gates.md` v1.31 行内对它的反引号引用同步去除。**验证**：`check_all.sh --fast --guards --local` EXIT=0；G-032 保持 13 warning 无新增 | 2026-09-27（`2014219d`） |
| `scripts/update_docs.py` 整脚本（T-15 补登） | **根因**：全库 0 调用点，五个功能均已被取代——测试数同步 → `scripts/generate_status_metrics.py`（STATUS.md AUTO-METRICS 区块）+ G-032 维度4；聚合器描述 → `pilotstd/core/notification/aggregate_buffer.py` 常量 + `docs/architecture/modules/core.md`（G-031）；技术债条目 → **T-02 已惰性化**；模块清单 → 目标文档自身 2026-08-19 即 ARCHIVED，现由 `docs/architecture/modules/*` + G-030/G-031/G-037 承担；自动 `git add` → 废弃。**处置**：`git mv` 为 `scripts/update_docs.archived.py`（**保留参考实现**），头部注释列出各函数现行承担者与历史取回方式；连带更正 2 处过时指针（`docs/DOCUMENTATION_MAP.md`、`docs/archive/specs/模块与功能清单.md` 头部）。**验证**：门禁 EXIT=0；三个改动脚本 `ast.parse` 语法 OK | 2026-09-27（`e94f8ddb`） |
| 归档件参与新鲜度 / 架构变更检查（T-17 补登） | **根因**（预防性）：`*.archived.md` / `*.archived.py` 停止维护——其 mtime 必然落后于新鲜度上限、内部链接可能指向历史路径，G-032 维度2/3 与 G-033 的架构变更判定对它们只会产生无行动价值的噪音。**处置**：`check_g_032_doc_health.py`（维度2 人工层新鲜度 + 维度3 交叉引用）与 `check_g_033_adr_integrity.py`（架构变更文件列表）新增统一 `is_archived()` 并接入。**验证（受控反证）**：`is_architecture_change("docs/architecture/technical-debt-registry.archived.md")=True` 且 `is_archived(...)=True` → 计入 **False**；对照组 `docs/architecture/modules/core.md` 与 `scripts/check_g_032_doc_health.py` 均计入 **True**（**未过度排除**）；门禁 EXIT=0、G-032 13 warning | 2026-09-27（`e94f8ddb`） |
| 技术债文档两个空章节「六、待决策」「七、清理项」（T-19 补登） | **根因**：两节唯一内容已于同轮移入「五、已接受的设计决策 · 归档并入」与「一、已清理」，保留空标题无信息价值。**处置**：删除两节；**当批刻意保留「六-B、观察项」标签**以免打断 11 处历史引用，该标签已在本批（T-22）统一收敛为「六、观察项」。**验证**：门禁 EXIT=0；章节结构复核（〇/一/二/三/三-B/四/五/六/七） | 2026-09-27（`2014219d` + 本批 `T-22`） |

### 归档并入（原格式，表头沿用原表，行文本原文未改）

来源「二、剩余台账」：

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|---|---|---|---|---|---|
| 11 | **ROI 判断** | G-010 警告区文件（拆分收益低于成本） | 见下方"现状"列出的 **3** 个文件 | ✅ 已偿还（第八轮执行完毕） | **根因**：历史累积复杂度进入 400-500 行警告区；集中拆分 ROI 低于组件碎片化风险。**现状（2026-09-26 第八轮实测 `check_g_010_code_size.py`）**：警告区 **8 个 → 3 个**，**最高有效行 487 → 438**（全部 < 450，距 500 阻断线余 **62** 行，无阻断风险）。本轮拆掉 5 个文件（原文件 → 新模块，均为逐字节搬移 + 调用点/文档同步）：`docker/api/announce_detail.py` **454 → 372**（拆出 `_announce_detail_parse.py` 92 行）；`scripts/check_g_012_comment_density.py` **457 → 311**（拆出 `_comment_lang_data.py` 159 行，仅搬数据表、逻辑零改动，用同一份 464 文件清单对照跑出**逐行一致**的 80 行输出）；`pilotstd/core/notification/_builders_batch.py` **477 → 287**（拆出 `_builders_task_results.py` 205 行，切口处 AST 实测无共享模块级符号 → 无反向依赖）；`pilotstd/core/notification/manager.py` **487 → 383**（拆出 `_manager_ops.py` 136 有效行的组合式 `NotificationOps`；首版用 Mixin 被 `tests/test_architecture_mixin_guard.py` 拦下——该守护测试禁止新增 Mixin、指定 Composition，随后改为 `self.ops.*` 并同步 7 处外部调用点）；`web/src/views/AnnounceDetail.vue` **487 → 314**（拆出 composable `useAnnounceDetail.ts` 234 行，模板/样式未改）。剩余 3 个：`pilotstd/core/db/_migrate_v16_v49.py:438`、`web/src/components/AppLayout.vue:420`（2026-09-27 删兜底分支后 434 → 420，仍 >400）、`web/src/components/NotificationConfig.vue:438`（2026-09-27 复核实测：后者由批 1 i18n 化增至 **438**，原文记 425 已过期）。**验证**：ruff 全绿；mypy 合并口径 `Success: 388 source files`；后端 270+333 tests、前端 231 tests 全过；`vue-tsc --noEmit` 零错误；每批 `check_all.sh --fast --guards --local` EXIT=0；G-031 连带文档（core.md / gates.md / README.md）与能力矩阵均已同步。**偿还窗口**：**不适用（已偿还）**。**触发式规则保留**：任一文件触及 **490** 行 → 当轮必拆；新文件新写入即受 500 行阻断档约束。**不还的代价（已消除）**：原先 5 个文件距阻断线最窄仅 13 行，任何小改动都可能撞线导致 CI 阻断；现最窄余 62 行。| 2026-08-23 |

来源「六、观察项」：

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| 拆出新模块时注释密度被稀释（G-012 ≥3%） | 2026-09-26 第八轮 #11 拆解时实测 | **根因**：拆出去的往往正好是“纯数据表/纯函数”块，说明性注释留在原文件，新模块只剩代码 → 密度天然偏低。**现状**：本轮 `_builders_task_results.py` 首版 **2.38%** 被 G-012 拦下、`pilotstd/query/adapters/gongbiaoku.py` 因拆分新增 2 行代码由 3.70% 跌到 **2.99%** 被拦（补一条注释后回到 3.70%）；TD-22 时 `_sql_schema_parser.py` 是 **1.9%**——**同一个坑第三次踩**，且都在“拆完、跑门禁”之后才暴露，等于白跑一轮。 | **✅ 已落实（2026-09-26）**：拆分清单已补一步“新模块注释密度预估”——落点 `docs/guides/refactoring-lessons.md`「五、拆分前检查项」§1（含三次实测数据表、G-012 判据口径、G-010 拆分证据与 500 行阻断档）。动手前先按 `注释行 / 非空行 ≥ 3%` 估算，不足就在新模块头部写清“拆出原因 + 分组依据”（既过门禁又是有用信息）；本项为流程改进，一次到位，**不挂偿还窗口**。**代价**：每次拆分多花约 1 分钟估算，换来少一轮返工。 |
| #23 合并前侦察未覆盖全组合（**✅ 已落实 2026-09-26**） | 2026-09-26 第八轮四分支合并时 | **根因**：合并前只做了相邻对侦察（3×4、2×1）与“各分支 × main”侦察，**漏了 3×1** —— `docs/architecture/modules/core.md` 里分支3 改 Schema 版本行、分支1 改子模块数行，两行相邻，该冲突因此未被预见，触发安全阀中止一轮。**现状**：这类冲突**不能用“取一边”解决**——两侧数值都不对（子模块数 70 / 72，实测 **73**），必须实测后重算，属需要外部事实的冲突。 | **处置（已落实）**：规则已写入 `docs/governance/development-flow.md` **§8「多分支合并流程：全组合冲突侦察」**（含规则、理由、`git merge-tree` 用法、输出要求、本轮 3×1 案例）；本条由「观察项」转为**已固化的流程规则**，不再依赖记忆。原规则内容：合并前侦察**必须覆盖全部 N×(N-1)/2 组合**（本轮 N=4 → 6 对），并在报告里逐对列出冲突文件；本项为流程改进，一次到位，**不挂窗口**。**代价**：每轮多跑几条 `git merge-tree`（秒级），换来不因未预见冲突而中止、不把“取一边”当成万能解法。 |
| #27 gates.md 版本历史两行挤在同一物理行（观察项） | 2026-09-26 第八轮文档核查时发现（**既有缺陷，非本轮引入**） | **根因**（2026-09-26 两次独立实测更正）：`docs/governance/gates.md` 版本历史表里 v1.16 与 v1.15 两个版本行被写在**同一个物理行**上——拼接处是**相邻的两个管道符 `\|\|`（字符索引 470/471），缺的是换行符**，而不是缺行首 `|`（两个 `|` 都在）；该行为单行 879 字符。**现状**（2026-09-26 实测）：缺陷在 **L235**（本轮 v1.19 加行前为 L234）；只影响该表这两行的渲染（被当成同一行多出的单元格），表内其余版本行均正常；内容无丢失、无歧义。 | **处置**：**✅ 已修复（2026-09-26，v1.20）**：两行已拆开、内容一字未改（拆后 v1.16 → L236 / 471 字符、v1.15 → L237 / 408 字符，两段拼接仍为原 879 字符，仅补入一个换行）；原位置实测 `gates.md:235`，拆后行号因同批新增 v1.20 行整体下移 1。**代价**：无。 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、剩余台账（只放"未清"的债）

> **状态：存续债务 0 条**（2026-10-01 R14-4d 清空，本批 R14-5 复核仍为 0——#31 / #32 均已闭环并归档到「一」）。
>
> **状态词汇（全簿统一）**：`进行中`（当轮正在做）/ `观察中`（已接受现状，等待触发条件）/ `待排期`（已定性、未排期）/ `待裁定`（需用户选型后才能动）/ `已收口`（动作完成，保留留痕）/ `已修复·残留待排期`（主项已修，残留子项待排）。

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|------|------|------|------|--------------------------------------|---------|

> **2026-09-27 结构重整**：已闭环的 **#11**（✅ 已偿还）移入「一、已清理 · 归档并入」；**#15 / 17b**（✅ 已接受）移入「五、已接受的设计决策 · 归档并入」。本节现只列**未清**项（#31 / #32 / #34）。
>
> **2026-09-27 裁定补记（第十一轮 R11-2）**：三行均已写入**裁定书**（现状量化／偿还方案+成本／转已接受的代价／终局结论）。**#31 / #32 仍属未清**（[挂窗第十二轮]／[挂窗第十二轮起分阶段偿还]）；**#34 已裁定为 [转已接受+代价]**——按用户指定“裁定书载体＝本节对应条目”而**仍列在本节**（不迁往「五」），其复发哨兵另登记于「六、观察项」**T-26**。 **2026-09-27（R12-8）补记**：**#34 已修复**（内部锁 `QMutex`+`QMutexLocker` → `threading.Lock`，三重回归门全绿）→ 由本节**移入「一、已清理」**；T-26 哨兵观察项随之关闭。本节现只列 **#31 / #32** 两行。 **2026-10-01（R14-4a）补记**：**#31 已核心闭环**（P2+P1，P3 转观察项 T-35）→ 移入「一、已清理」；本节现只列 **#32**。 **2026-10-01（R14-4d）补记**：**#32 已正式闭环**（A→D 全部完成）→ 移入「一、已清理」；本节**首次清空**（剩余台账为零）。

---

## 三、维持现状（E2E 兜底，不再拆解）

> **状态：维持现状（已接受，不排期）**——判据见下方"策略"：文件为纯 Qt 控件构建、无可提取业务逻辑。

以下文件经审查为纯 Qt 控件构建，无可提取业务逻辑。**停止底层拆解**，仅通过 E2E 测试覆盖：

| 文件 | 物理行数 / 有效行数 | 内容特征 | 策略 |
|------|------|---------|------|
| `pilotstd/ui/core/handlers/_settings.py` | 426 / 371 | QTabWidget/QGroupBox/QFormLayout 构建 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_theme_ops.py` | 142 / 109 | QIcon/QTranslator/QStyleSheet 管理 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py` | 263 / 209 | QTreeWidget+QMenu+QThread 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_export_ops.py` | 143 / 116 | QFileDialog+QTextEdit+QTableWidget 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_dialog_ops.py` | 51 / 39 | QFileDialog 封装，零业务逻辑 | E2E 兜底 |

> **2026-09-27 口径标注（T-11）**：原表"行数"列填的是**物理行数**（426/142/263/143/51），而「五 #5」同一批文件填的是**有效行数**（371/109/209/116/39，G-010 口径）——两处**都正确但口径不同**，此前未标注导致并列看似矛盾。本表改为两口径并列（2026-09-27 实测值），「五 #5」仍用有效行数。

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

> **状态：环境依赖保留（不排期）**——外部站点不可达／缺 OCR provider／平台不支持，**代码侧无解**；
> 运行期 `self.skipTest()`（fixture 未采集）**不属本类**；永久 `mark.skip` 已于 T-29/T-33 清零。

> 2026-09-27：旧簿「一、已跳过的测试（13 条登记）」已**逐条并入**下表（旧簿归档为 `architecture/technical-debt-registry.archived.md`，不再维护）。
> 下表为旧簿 **2026-09-21 快照**逐字保留；其中"已删除"类条目的**实测更正**与"未登记跳过点补登"在本轮 Commit 3（T-10）执行，届时本表将刷新为实测口径。

| # | 测试 | 文件:行号 | 原因 | 分类 | 处理方式 |
|---|------|-----------|------|------|---------|
| 1 | `test_gb_exact_match` | `test_e2e_adapters.py:42`（TestE2EStdGov，原 :28） | 外部 API (std_gov) 返回空 `match_status` | E2E 网络依赖 | 2026-06-30 添加 `@unittest.skip`（现 :40-41 为 `skipIf(_CI)` + `skip`） |
| 2 | `test_hg_exact_match` | `test_e2e_adapters.py:118`（TestE2EHbba，原 :103） | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest`（:97 `skipIf(_CI)`） |
| 3 | `test_cold_start_pending` | `test_e2e_adapters.py`（原 :239，已不存在） | ahbz 未登录状态 | E2E 认证依赖 | 2026-08-25 审计：测试已删除；TestE2EAhbz（:234）重构为 `test_gb_exact_match`/`test_sh_exact_match`/`test_iso_exact_match`，`skipIf(_CI)` 网络防护保留 |
| 4 | `test_sh_exact_match` | `test_e2e_adapters.py:104`（TestE2EHbba，原 :300） | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest`（:97 `skipIf(_CI)`） |
| 5 | `test_split_pdf_pages` | `test_ocr_fallback.py:38`（fixture skip）/ `:56`（def，原 :39） | 无可用 OCR provider | 环境依赖 | `pytest.skip` 在 setup/fixture 中（非函数内） |
| 6 | (sparse file) | `test_scanner.py:502`（原 :472） | 系统不支持此场景文件 | 平台依赖 | 原有 `self.skipTest` |
| 7 | `test_e2e_dialog` | `tests/gui/test_e2e_dialog.py`（旧簿记"已删除"） | DialogHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除（Handler/Mixin dual-track 清理），由单元测试间接覆盖 |
| 8 | `test_e2e_file_tree` | `tests/gui/test_e2e_file_tree.py`（旧簿记"已删除"） | FileTreeHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除，文件树操作由 `test_file_tree.py` 覆盖 |
| 9 | `test_e2e_settings` | `tests/gui/test_e2e_settings.py`（**R13-2 已删除该文件**：原为空壳 `pass` skip 占位） | SettingsHandler 由 SettingsDialog 独立创建 | 架构重构 | 覆盖由 `test_settings_announce.py` / `test_settings_dialog.py` 承担 |
| 10 | `test_e2e_table` | `tests/gui/test_e2e_table.py`（旧簿记"已删除"） | TableHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除，表格操作由 `test_table.py` 覆盖 |
| 11 | `test_e2e_settings_io` | `tests/gui/test_e2e_settings_io.py`（**R13-2 已删除该文件**：原为空壳 `pass` skip 占位） | SettingsConfigIO 是 SettingsHandler 内部组件 | 架构重构 | 覆盖由 `test_settings_announce.py` / `test_settings_dialog.py` 承担 |
| 12 | `test_e2e_theme` | `tests/gui/test_e2e_theme.py`（旧簿记"已删除"） | ThemeHandler 纯 Qt 控件操作 | 架构重构 | `cfb166fe` 删除，应用主题由 MainWindow 初始化路径覆盖 |
| 13 | `test_e2e_table_helper` | `tests/gui/test_e2e_table_helper.py`（旧簿记"已删除"） | TableHelperHandler 不在 MainWindowCore 中 | 架构重构 | 旧簿记为历史条目，表格操作由 `test_table.py` 覆盖 |

**旧簿处理策略（逐字保留）**：#1~#6（外部 API/环境依赖）E2E 测试保留在本地开发时手动运行，CI 环境自动跳过。#7~#13（架构重构）旧簿称对应测试文件均已不存在：其中 #7/#8/#10/#12（dialog/file_tree/table/theme）由 `cfb166fe`（Handler/Mixin dual-track 清理，删 8 个死 Handler/Mixin 文件 + `tests/gui/test_e2e_*.py` 6 个测试）删除；#9/#11/#13（settings/settings_io/table_helper）旧簿称不在删除集合中、为历史条目。功能均由对应单元测试间接覆盖。

**2026-09-27 实测更正（T-10）——"已删除"的表述不准确**：`tests/gui/` 现存 **11 个 `test_e2e_*.py`**（`test_e2e_announce/auto/cleanup/download/persistence/project/query/query_summary/scan/settings/settings_io`），并非"均已删除"；其中 **2 个**带无条件跳过标记——`tests/gui/test_e2e_settings.py:19`、`tests/gui/test_e2e_settings_io.py:17` 的 `@pytest.mark.skip`。CI 的 GUI job 是用 `--ignore-glob="*test_e2e*.py"` **排除**它们，而不是因为文件不存在。上表 #3 的"测试已不存在"同样需以此为口径理解（`test_e2e_adapters.py` 该用例本体已删）。 **R13-2（2026-10-01）补记**：上述 2 个文件（`test_e2e_settings.py` / `test_e2e_settings_io.py`）经 T-33 裁定**删除**（原为 `def test_x(): pass` 空壳，删除后 `tests/` 永久 skip 归零）。

**2026-09-27 实测（跳过点总量与机制分类，全库 `tests/` 扫描）**：跳过标记共 **102 处**，按机制分布如下——本节只**逐条登记"环境依赖"类**（条件跳过中与外部站点/平台/CI 环境相关者），其余运行期跳过属"本地 fixture 未就绪"的运行期防护，仅给总量与代表文件，不逐条登记（不属技术债）：

| 机制 | 处数 | 文件数 | 性质 / 是否逐条登记 |
|---|---|---|---|
| `@unittest.skipIf(_CI, …)` | 18 | 7 | **环境依赖（CI 无外网）** → 属本节口径（网络类 E2E） |
| `@pytest.mark.skipif(…)` | 10 | 4 | **环境依赖（平台/长路径）** → 属本节口径 |
| `@pytest.mark.skip`（无条件） | 10 | 4 | 架构重构类（含 2 个 `tests/gui/test_e2e_*.py`）+ 单测快照类（`tests/unit/…`，`依赖 HTTP/线程` 的原因写在 reason 里） |
| `@unittest.skip`（无条件） | 1 | 1 | `test_e2e_adapters.py:41`（外部 API 不稳定） |
| `pytest.skip()`（运行期） | 3 | 3 | 运行期防护：`test_ocr_fallback.py:39`（无 OCR provider，**属本节口径**）、`test_i18n_key_count.py:27`（脚本缺失时整模块跳过）、`stress_winui.py:107`（需外部驱动传参） |
| `self.skipTest()`（运行期） | 60 | 10 | **运行期防护**：多为适配器/查询测试的 `Fixture not found`（本地未跑 Task 0 采集 fixture），非环境依赖债务 |
| **合计** | **102** | — | — |

**本节"环境依赖"口径下、原文漏登的跳过点（2026-09-27 实测，逐条补登）**：

| 文件:行号 | 机制 | 原因 |
|---|---|---|
| `tests/test_manager.py:96` / `:114` / `:132` / `:244` / `:375` | `@pytest.mark.skipif(os.environ.get("CI") == "true", reason="离线 CI 环境无外部网络…")` | 需真实外网，CI 跳过（本地/集成环境运行） |
| `tests/test_file_utils.py:62` / `:77` | `skipif(sys.platform != "win32")` | Windows 长路径特性，仅 Windows 适用 |
| `tests/test_file_utils.py:249` | `skipif(sys.platform != "win32")` | 文件移动权限行为在 Linux 下不同 |
| `tests/gui/test_file_tree.py:31` | `skipif(sys.platform != "win32")` | Windows-only：需多盘符 |
| `tests/unit/manager/organize/test_mirror.py:166` | `skipif(sys.platform != "win32")` | 长路径前缀 `\\?\` 仅 Windows 支持 |
| `tests/test_i18n_key_count.py:27` | `pytest.skip(..., allow_module_level=True)` | 门禁脚本缺失时整模块跳过（防御性） |
| `tests/stress_winui.py:107` | `pytest.skip(...)` | 需 `stress_driver.py` 传入 `--source --step1 --step2` |

**分类说明**：以上均为**环境依赖**（外部站点不可达 / 缺少 OCR provider / 平台不支持 sparse file 或长路径 / CI 无外网），代码侧无解，因此保留在本节、不挂偿还窗口。运行期 `self.skipTest()` 的 60 处（10 文件）**不属**本类——其语义是"本地 fixture 未采集，本次跳过该断言"，在具备 fixture 的环境会真实执行。

---

## 五、已接受的设计决策（6 条，每条含不还的代价）

> **状态：已接受（6 条，不挂窗口）**——**R15 归档 2 条**：#4（Mixin 拆分大文件，ADR-010 已 Deprecated）与 **#6（JWT_SECRET，已改为落盘复用）**。——每条均写明"不还的代价"与重评估触发条件。原 #4（Mixin 拆分大文件）已于 **R15 归档**（ADR-010 已 Deprecated、全库 Mixin 仅剩 `_WindowLifecycleMixin` 1 个，见「一、已清理」）。未来若多用户/对外开放，优先复核 #2（静态令牌无 TTL）、#7（内存会话）、#8（WebSocket 无用户级路由）。

> 2026-09-27：旧簿「二、已接受的设计决策」8 条已并入——其中 #1~#5 与本表原有 5 条同源（不重复），**#6 JWT_SECRET 固定默认值**、**#7 内存会话存储（无持久化）** 为本表原先缺失者，已补为下表 **#6/#7**；
> 旧簿「三、已知问题」#6 **WebSocket 广播无用户级路由** 属"已接受"性质，补为下表 **#8**；旧簿 #8（`__init_tr` 命名）为"已修复"，属「一、已清理」性质，不计入本表。

| # | 决策 | 日期 | 依据 / 根因 | 现状（实测） | 不还的代价（已接受） |
|---|------|------|-------------|--------------|----------------------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | 邮件投递依赖外部 SMTP 凭据与可达性，维护成本高于收益；当时 4 个 IM/Push 渠道已覆盖全部使用场景 | `pilotstd/core/notification/channels/` 仅 `wechat/feishu/dingtalk/telegram` + `base.py`，**无邮件实现**（2026-09-26 实测） | 无法用邮件接收通知；若将来只有邮件可达（如服务器所在网络屏蔽 IM 渠道），通知会全部落空——届时应重新评估解除黑名单 |
| 2 | 静态 API 令牌不支持过期 / 无 TTL | 2026-06-25 / 2026-07-16 确认 | 令牌由环境变量注入、供仓外脚本调用，加 TTL 会引入"脚本半夜失效"的运维面 | 无外部 API 调用场景；令牌落库存哈希（本轮拆出 `docker/_static_token.py`，`api_keys.key_id='pst_static'`） | 令牌一旦泄露即**永久有效**，无法通过过期收敛风险；当前无外部 API 调用场景，代价暂不可见，但一旦对外开放需先补 TTL/轮换 |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 一次性拆分 400+ 行文件会引入大面积行为风险；按"触及即拆 + 到期必拆"分批 | **2026-09-27 复核实测**（`check_g_010_code_size.py`）：警告档（>400 且 ≤500）**3 个**、阻断档（>500）**0 个**，最高有效行 **438**（`pilotstd/core/db/_migrate_v16_v49.py` 438 / `web/src/components/AppLayout.vue` **420**（同日删兜底分支后 434→420）/ `web/src/components/NotificationConfig.vue` 438）；第八轮已拆 5 个文件（`check_g_012_sql_schema.py` 497→139、`docker/auth.py` 490→394 等）。原文记"降至 8 个、剩余最高 487"已过期 | 警告区文件长期存在，有一次性阻断 CI 的风险（500 行硬线）；**明细与偿还窗口见台账 #11**（本行不重复登记） |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | 这 5 个文件只做控件构建与信号接线，无业务算法，拆解收益低于碎片化成本 | 实测有效行：`_settings.py` 371、`_file_tree_ops.py` 209、`_export_ops.py` 116、`_theme_ops.py` 109、`_file_dialog_ops.py` 39（均 <400，不进警告区） | 只靠 E2E 兜底、无单元测试；若内部沉淀出业务逻辑而未被发现，回归只能靠 E2E 抓，代价是缺陷定位更慢 |
| 7 | 内存会话存储（无持久化） | 2026-06-30（2026-09-27 自旧簿并入） | 简单够用；重启后需重新登录是预期行为 | **实测**：`docker/session_store.py` 存在，会话仅存于进程内存 | 进程/容器重启即全体掉线需重新登录；多副本部署无法共享会话（横向扩容前必须先引入 Redis 等外部会话存储） |
| 8 | WebSocket 广播无用户级路由（广播到所有连接） | 2026-06-25（2026-09-27 自旧簿并入）／**2026-10-02 关闭** | 当前为单用户部署，全局广播够用 | **已关闭（阶段 0 死代码清理）**：原文行号（`manager.py:88`/`:114`）早已漂移；实测 `ws_broadcast` 从未被生产代码注入（唯一构造点 `pilotstd/manager/facade/_base.py:250/:271` 不传），故 `_ws_broadcast` 恒 `None`、广播线程永不创建，服务端实现已于 `1784ecbe` 删除。本次删除残留形参/属性/方法与 `_manager_ops.broadcast_to_ws`，5 处测试同步清理 —— **条目描述的对象已不存在**，见 [通知架构重设计阶段 0](../plans/notification-redesign/06-阶段0-1实施方案.md) §1.2 | 无（越权可见风险随代码一并消失）；若将来重建实时通道，须**先设计**按 `user_id` 路由再落地（勿重蹈"先广播后补路由"） |

### 归档并入（原格式，表头沿用原表，行文本原文未改）

来源「二、剩余台账」：

| # | 分类 | 项目 | 位置 | 状态 | 根因 / 现状 / 偿还窗口 / 不还的代价 | 登记日期 |
|---|---|---|---|---|---|---|
| 15 | **ROI 判断** | 通知聚合器实例不共享 → 聚合对"每次新建门面"的路径失效 | 聚合器：`core/notification/manager.py:118-135`（`_aggregate_enabled` 为真时在实例内新建）；管理器创建点：`core/notification/manager.py:87`（`NotificationManager.__init__`）；门面创建点：`manager/facade/_base.py:87`（`BaseFacade.__init__`）→ `:250`（`_init_services` 内新建）、`:271`（`_init_notification` 配置变更重建，调用方 `docker/api/notification.py:133`）；**`StandardManager()` 构造点本轮 AST 重测 = 生产 12 处 + 测试 22 处**：`docker/manager.py:16`、`cli/commands/_shared.py:19`、`core/task_status.py:76`、`monitor/scheduler.py:146`、`services/favorite_chain_processor.py:164/307`、`tasks/date_reminder.py:141`、`tasks/favorite_download.py:137/165/194/306`、`ui/main_window/parts/_actions_ops.py:49`；测试 `tests/test_manager.py`（20 处）、`tests/test_scanner.py:576`、`tests/test_e2e_adapters.py:277` | ✅ 已接受（本轮正式关闭） | **根因**——聚合器生命周期绑在门面上，不是"忘了单例"：`NotificationManager.__init__` 按 `_aggregate_enabled`（`core/config/defaults.py:79` 默认 true）在实例内新建 `NotificationAggregator`（`manager.py:128`），并把 `self._send_now`（绑定方法）作为回调传入；`StandardManager()` 每次都在 `_base.py:250` 新建 `NotificationManager`，故聚合器**每构造一个门面就多一个**。**现状**（本轮实测，代码树 = `62fba6ef`）：① 构造点口径由上一轮的 9 处更正为**生产 12 处 / 测试 22 处**（AST 遍历 `Call.func.id=='StandardManager'`，口径含 `docker/` 与 `cli/`）；② 逐条通知路径**仍在**（上一轮"已消除"的说法需修正）——`tasks/favorite_download.py:282` 的 `notify=False` 只在**批量链路**（`docker/app.py:160` → `services/favorite_chain_processor.py:320 process_chain(notify_per_record=False)`）由源头抑制为"每次运行 1 条汇总"，但 `services/favorite_chain_processor.py:307 _notify_abandoned` 是**无条件逐条**发（`notify` 闸只作用于 `:249` 那处），`favorite_download.py:306` 的独立 `StandardManager()` 每次下载也照建；③ 探针实测（临时探针已删）：连建 2 个 `StandardManager`，`m1.notification_mgr.aggregator is m2...` = **False**，3 次逐条 `send_event` 后**每个实例缓冲恒为 1 条**且无跨实例合并；同一个共享聚合器入队 3 条则缓冲深度 3、`shutdown()` 时 flush **1 次**（成对验证）。**偿还窗口**：**不适用（已接受）**。**不还的代价**（已接受，量化）：① 聚合失效的实测代价≈**0**——生产链路源头按批汇总（一次运行 1 条汇总），Web/定时侧本就持有长生命周期门面（`docker/manager.py:12` 进程级单例；`monitor/scheduler.py:142` `self._mgr` 缓存），仅"每条 abandoned/每次下载失败"这类低频通知退化为**延迟 window（默认 5s，`defaults.py:83`）+ 渠道请求各 1 次**；② "构造开销"经本轮实测**最轻**：`NotificationManager()` 构造（含凭据迁移 + 渠道初始化 + 聚合器）中位 **0.62 ms**（n=5：0.58/0.60/0.62/0.64/0.76，`aggregate_enabled=true`），即每次通知多 ~0.6 ms；门面构造的大头不在聚合器——`StandardManager()` 单次 **8.17 s（中位）**，`cProfile` 显示 **8.18 s / 8.27 s（98.9%）** 落在 `ssl.create_default_context → load_verify_locations`（9 个查询适配器各建一个 httpx client；本机实测裸 `httpx.Client()` ≈ **810 ms**、裸 `ssl.create_default_context()` ≈ **52 ms**），与本条无关，属另一条待登记线索；③ 因此**不还的代价 = 上述 ~5 s 通知延迟 + 每事件 ~0.6 ms + 未来交互型高频通知的限流余量**（历史上 Telegram 429 的 56% 拒收由逐条发送触发，已由源头按批汇总消除，本条不再重复计）。**为何不做单例化（代码级理由）**：聚合器的 `sender_func` 捕获的是**首个入队管理器的** `_send_now` → 闭包其 `_db`/`_ws_broadcast`/`_user_id`/`_channels`；共享聚合器会让"最后入队者"决定全部缓冲消息的收件身份（跨库写 `notification_log`、跨用户发消息）；且缓冲分组键只有 `event_type`（`aggregate_buffer.py:65` `_buffers`），**没有按 `user_id` 分桶**，共享即把不同用户的消息合并成 1 条——这是当前结构刻意避开的用户绑定洞。共享整个管理器又新增状态竞争面：`_init_notification`（`_base.py:271`，`docker/api/notification.py:133` 调用，`tests/test_notification_api.py:86/107` 断言）要求配置变更后拿到**新**管理器，单例后已绑定旧单例的代码读不到新配置。**代价**：12 处生产构造点（8 文件）+ ≥3 个测试文件、22 处测试构造需改，且新引入跨库绑定 + 跨用户合并两类正确性问题。**结论**：**不改**——实测收益≈0、成本高且会引入更严重的正确性洞；未来若出现交互型高频通知，正确方向是核心库层继续不做进程级可变全局，由应用层持有门面生命周期（复用 `docker/manager.py:12` 的应用级门面）让交互路径共享，而非把用户绑定绑在首个入队者身上。 | 2026-09-21 |
| 17b | **技术无解** | 卡死线程无法安全终止 | CPython / Qt 层面 | ✅ 已接受 | **根因**：CPython **没有**安全强杀线程的机制（`PyThreadState` 清理、GIL、锁状态无法安全回滚）；`QThread.terminate()` 是唯一 API，但会在持锁/写文件时中断线程，造成数据损坏与析构期崩溃（正是 CI `test-gui-coverage` 失败的原因，`54bd565d` 已全部移除）。**现状**：7+1 处调用点统一走"断信号 → 置停止标志 → `requestInterruption()` → `wait()` → 超时保活"，无任何 `terminate()`。**偿还窗口**：**不适用（技术无解，已接受）**——只能保活等待或人工重启容器。**不还的代价**（已接受）：卡死线程在进程退出前不释放其连接/句柄/线程栈；若发生在下载/归档链路，需要人工重启容器才能恢复，且日志里只留线索（已由 17a 的计数与 error 升级提供）。 | 2026-09-25 |

来源「六、待决策」：

| 项 | 来源 | 现状 | 决策依据 | 最迟 |
|---|---|---|---|---|
| `POST /query`（admin SQL 端点）权限边界过宽 | 2026-09-25 巡检时实测；2026-09-26 第九轮机制复核 + 只读探针实测 | **端点**：`docker/api/admin_db.py:180-182`（router 无 prefix，`docker/app.py:317` 也无 prefix 挂载 → 真实路径就是 `POST /query`；审计标签 `/api/admin/db/query` 是错误字符串，`:176`/`:253`）。**鉴权**：只有 `@require_role(ADMIN_ROLE)`（`:181`）；`/query` 不在 `/api/` 下，被 `docker/auth.py:336-338` 白名单放行 → **完全不经鉴权中间件**：无会话存储校验（`auth.py:407`）、无 CSRF 校验（`auth.py:410-414`）、无 Origin/Referer 校验（`auth.py:387-397`），因此登出/改角色都不撤销。静态 API Key 通道对本端点**无效**。**表白名单**：`_ALLOWED_TABLES`（`:25-34` = standards/favorites/notification_log/task_execution_history/users/user_preferences）**只**在 `DROP TABLE` 分支被引用（`:110-116`，全库 grep 零其他引用点），且名单里的 `users` 反而被允许删除；名单里的 `favorites` 是**不存在的表**（实际是 `user_favorites`，`pilotstd/core/db/_migrate_v31_plus.py:207`）→ 真收藏表不受保护。**读**：SELECT 无任何表/列限制（可 `PRAGMA table_list` 枚举全库 schema）；`LIMIT 1001` 包装（`:126-128`/`:216-217`）只在语句里没写 LIMIT 时生效，截断判定在 `:244-248`。**写**：INSERT 无约束；UPDATE/DELETE 仅要求含 WHERE（`:119-121`，`WHERE 1=1` 即算通过）；CREATE/ALTER 无约束；仅 `DROP DATABASE` 硬拒（`:106-107`），多语句由 sqlite3 单语句限制兜住。**审计**：只落 `audit_logs` 表（`pilotstd/core/audit.py:26-51`），detail 含 **SQL 全文 + params**（`:251-261`），但 `user_id` **恒为 NULL**（中间件在白名单分支 `docker/auth.py:424-425` 提前 return，从未注入 ContextVar）→ **有 SQL、无操作人**；`admin_db.py` 除 `:21` 未使用的 module logger 外无任何日志调用，故 **app.log 零痕迹**（D2 取证结论） | **决定：① 维持现状 —— ✅ 已接受并关闭**（2026-09-26 第九轮）。**接受理由**：① 这是本仓唯一"免 SSH 的运维通道"，且是现场文档明写的既定通道——部署验证 `SELECT MAX(version) FROM _schema_version` 注明"无专门端点，用管理员 SQL 端点"（`docs/deployment/README.md:74-79`/`:101`）；2026-09-25 的补建与纠错（`INSERT rowcount=8` + `UPDATE 36 行`）就是靠它完成（本文档 `:231-250`）；只读巡检中三张未公开表的维度也只能靠它（本文档 `:210-214`/`:262`，公开端点确实不暴露——`docker/api/favorites.py:252-257` 的 `_DOWNLOAD_FIELDS` 只有 4 列，导出 SQL `:364-374` 不含 `favorite_downloads.standard_no`/`announcement_record.standard_type`/`download_queue.*`）。② 选项②按原措辞收益与成本不成比例：SELECT 限 6 张白名单表会**直接打断上面的部署验证步骤**（`_schema_version`/`user_favorites`/`favorite_downloads`/`announcement_record`/`download_queue` 全不在名单内），而名单里的 `users` 又**保留了口令哈希的读取**，安全收益只剩"写"这一半；并且实测证明拦截必须是"**正向仅允许 SELECT**"——黑名单式"禁 INSERT/UPDATE/DELETE"会漏掉 `ATTACH DATABASE`/`VACUUM INTO`/`PRAGMA`/`CREATE`/`ALTER`。③ 管理员对同一库本就有等价能力：容器内 `python -m sqlite3` 可用（本文档 `:188`）且运维者有宿主权限，收紧只抬高本仓运维成本，不改变有宿主权限者的能力边界。**不还的代价（写实）**：**一份有效 admin JWT 泄漏 = 内网内全库读写 + 容器文件系统任意写**——可 `SELECT password_hash, salt FROM users` 离线爆破、`UPDATE users SET role='admin'`、`DELETE ... WHERE 1=1` 批量删、`VACUUM INTO` 导出全库副本、`ATTACH`/`CREATE` 落文件；且**登出或改角色都不撤销**，暴露窗口 = JWT 有效期 **2 小时**（`docker/auth.py:44`）；事后**无法归因**（`audit_logs.user_id` 恒 NULL、app.log 零痕迹）。**已生效的缓解**：仅内网监听、cookie `httponly`+`samesite=strict`（`docker/auth.py:234-241`）、无 CORS 中间件（跨站脚本过不了 `application/json` 预检）、未设 `JWT_SECRET` 时重启即轮换密钥（`docker/entrypoint.sh:6-9`）。**若将来重开**：按"正向仅允许 SELECT + 补全真实全表名单 + 单独开只读端点 + 修审计归因"另立方案并先获批（R-012） | ✅ 已接受并关闭（2026-09-26 第九轮；依据：只读探针 5 组实测 + 仓内 grep 零生产调用方 + **现场 `audit_logs` 只读取证**（该端点不写 app.log，唯一留痕是审计表；2026-09-26 经 `POST /query` 只读查得）：`DB_QUERY` **247 条**、跨度 **2026-08-06 02:14 → 2026-09-26 11:26**、分布 9 天（09-13 64 / 09-26 63 / 08-22 45 / 08-29 33 / 08-06 23 / 08-23 20 …）；SQL 形态**全部为本仓运维/调查类**（`notification_log` 计数、`user_preferences` upsert、`sqlite_master` 读 schema、`standard_info_cache`、`_schema_version`、`user_favorites` 状态统计、`task_execution_history`）；真实写操作仅 3 条 DELETE（2026-08-29 02:37 清理测试收藏 id=37 及其队列行）与 `INSERT OR REPLACE user_preferences`，**无 ATTACH / VACUUM / DROP 的真实调用**（早先形态计数是探针自身 SQL 文本的自匹配，非真实调用）；`user_id` **247/247 全为 NULL** → 有 SQL、无操作人，无法归因到具体调用方，但**无任何外部/异常形态痕迹**） |

来源「六、观察项」：

| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| 单条网络请求/大文件 IO 内部仍不可中断（#17a 后残留） | 2026-09-26 #17a 偿还时实测 | **根因**：worker 侧检查点只能落在"处理单元之间"（回调/循环体）；`requests` 的单次 `send()` 与 `resp.content` 整块读取无法从外部打断，要中断必须把网络层改为"分块读 + 每块查停止标志"，并把停止标志从 UI worker 一路传到适配器/会话层。**现状**：单条不可中断窗口 = 该请求的超时值——查询/公告 `network.DEFAULT_TIMEOUT = 15s`（`pilotstd/query/network.py:17`）、下载 `viewGb` 显式 `timeout=120`（`pilotstd/download/adapters/openstd_download.py:262`，旧登记写 `:114` 是请求头所在行，勘误）、SQLite `busy_timeout=5000ms`（`pilotstd/core/db/database.py:200/211`）。即：worker 现在能在"下一条"立刻停（实测 6–60ms），但若正卡在一条请求里，最坏仍要等该请求超时 | **✅ 已接受（ROI 判断，2026-09-26 收尾轮闭环）**。**实测上界（逐层）**：查询 `safe_request` 单次 `session.request(timeout=…)` 15s（`query/network.py:114`）；下载前置请求 30s×3（搜索页 `openstd_download.py:141` / 详情页 `:196` / 全文下载页 `:218`）、验证码 15s×2（`img` `:325` / `verifyCode` `:374`）、`viewGb` **120s**（`:262`）；SQLite 锁 5s；每请求前随机延迟 ≤3s（`download.max_delay`）。**取消延迟不累加**：`check_stop` 的检查点落在 `on_result`/`on_progress`（`ui/workers/download.py:52/62`），而请求超时会让 `adapter.download` 直接返回 → 当轮即抛 `WorkerAborted` 退出；故最坏 = **当前在途请求的剩余超时**（查询 ≤15s、下载 ≤120s），不是各请求相加。**穿透成本（为何不做）**：需 7 处传停止标志——① `ui/workers/download.py` 造 abort 回调；② 门面 `manager/facade/_download.py:89 download_stream`；③ 引擎 `download_single`/`download_batch`/`fetch_bytes`（另含 `run_paced_batches:301` 的 15s 批间睡眠、`_execute_retry_batch:186` 的 2s/4s 退避）；④ 适配器基类 + `openstd_download.py:262-278` 改 `iter_content` 分块读并逐块检查；⑤ 查询侧 `query/network.py::safe_request`（**10 个查询适配器共用**）；⑥ `core/file_utils.py:168 safe_move` 分块复制；⑦ 测试 + G-031 文档同步（`docs/reference/download-pipeline.md`、`docs/architecture/modules/query.md`）。估算 **150–300 行**，远超"<100 行可控"阈值，且要动 10 个适配器共用的网络层。**两处确无时间上界的实情（更正旧表述"都有明确上界"）**：① `viewGb` 用 `resp.content` 整块读（`:278`），`timeout=120` 是**空闲**超时（urllib3 按 socket 读操作计时），慢速滴流可把总时长拖到无界；② `safe_move` 的 `shutil.copy2`（`file_utils.py:208`）与目标同名时的**两次**全文件 `sha256`（`:187`）均无超时，随文件大小线性增长（标准 PDF ≤1MB → 毫秒级；把大体积 Word/模板镜像到慢速网络盘才会变分钟级）。**接受理由**：上界虽非严格（滴流/大文件两例），但**都不是永久卡死**——超时或读完即当轮退出，无连接/句柄泄漏（requests 异常路径关闭 socket），无状态损坏、无脏数据。**不还的代价（已接受，量化）**：极端情况（站点半死不活）下用户点"取消"后，查询最坏等 **15s**、下载最坏等 **120s** 才退出，期间表现为"界面已取消但线程仍在"，不再触发保活/疑似卡死告警；大文件归档复制期间取消需等本次复制完成（与文件大小成正比）。**本条闭环。** |
| `_migrate_v59_ensure_favorite_retry_columns.py:24` 函数 docstring 过时 | 2026-09-26 第八轮 #19 删端点时发现 | **根因**：该 docstring 写“两列的读取方是收藏状态接口（`docker/api/favorites.py` 的 `get_favorite_status`）”，而 `GET /api/favorites/{id}/status` 已于 #19 删除；两列本身也已被 v60（`_migrate_v60_drop_favorite_retry_columns.py`）`DROP COLUMN` 删除 → 该描述**双重过时**。**现状（2026-09-26 只读实测）**：`norm_source()`（`pilotstd/core/db/_migration_checksum.py:42-59`）只丢弃空行、以 `#` 开头的注释行、以及行首缩进；docstring 是字符串字面量，**整段保留在 checksum 输入内**——同一函数只改 docstring 一个字，`compute_checksum`（`:33-39`）与 `norm_checksum`（`:62-69`）**均变化** → “改注释不改 checksum”不成立。**同时更正原登记的两处推断**：① 原证据 `compute_checksum != norm_checksum` 与 docstring 无关——`norm_source` 每行都做 `line.strip()`（缩进被移除），故 `MIGRATIONS` 全部 **59/59** 个迁移函数 `raw != norm` 恒成立；② 原称“改动会触发 `:109-115` 的 `DatabaseError` → 生产库直接打不开”**未复现**：`:96` 的自愈分支必然命中，实际后果是**告警日志 + 运行时静默 `UPDATE _schema_version.checksum`**；`:109-115` 抛错分支只在 `tests/test_core.py:351-373` 用 mock 令两者相等时可达。 | ✅ **已决定（不改）**：docstring 确实过时，但它在 checksum 输入范围内，改动会让每台已执行过 v59 的库在下次打开时静默改写 `_schema_version.checksum`（P-106 禁止手动同步该值），为一行注释换来对生产库的无谓写入与校验状态漂移，收益 < 成本。**不挂窗口**：若未来 v59 因其他原因必须动（或该 checksum 机制被修正），顺手把 docstring 改为“两列当前无读取方且已于 v60 删除（原读取方 `/api/favorites/{id}/status` 已于 #19 删除）”。**代价**：仅阅读迁移源码的人会被这句过时描述误导，不影响运行。 |

---

## 六、观察项（不属"债"，登记待观察）

**活跃项分两档（2026-10-01 R15 终态）**：**真·观察项 6 条**（下表：受外部依赖/当前架构限制，暂不能动，已绑定事件触发 + 周期兜底）；
**其余 4 条为「可动作」项**（`待排期` 1 / `观察中` 3——按 R16 候选池推进；T-30 与 T-25 残留已分别于 R16 P3/P1 收口归档，另 2 条 R15 已修项也已归档）。
已归档至「一、已清理」的共 **6 条**：2 条 `已收口·并入留痕`（R15 初）+ 2 条 R15 已修复（SQL 内嵌字面量、本地网络用例挂起）+ **T-30**（R16 P3 收口裁定）+ **T-25 残留**（R16 P1 改名解决）。

### 真·观察项复核表（R15 起生效；每批收尾必读，见 §0.1）

| 条目 | 保留理由 | Review_Trigger（事件触发） | Review_Cycle（周期兜底） | 取证入口 / 动作 |
|---|---|---|---|---|
| **#33 TaskView.vue 逼近 G-010 警告线**（有效行 399 / 线 400） | 拆分是重构而非修 bug，且越线只警告不阻断 | 任何编辑 `web/src/views/TaskView.vue` 的提交 | 每季度 | `python scripts/check_g_010_code_size.py`；触发即顺手把"任务历史/历史详情"块拆为子组件 |
| **HomeView grid-layout-plus workaround** | 依赖第三方库内部微任务调度行为，不升级库无法判断是否仍需要 | 升级 `grid-layout-plus`（`web/package.json:22`） | 每半年 | 删 `layout.value = [...layout.value]` 克隆 → 浏览器实测锁定/解锁后拖拽是否仍生效 |
| **T-35 配置文件跨进程写锁（原 #31-P3）** | 文件锁跨平台语义成本 > 风险；R15 已用 `.bak` 写前备份 + 启动回滚把恢复成本压到接近 0 | 实测到一次并发写丢配置（"设置自己变回去了" / 回归用例失败） | 每季度 | 对比 `config.json` 与 `config.json.bak` 的键差异；确认后仍优先"原子写+重试+写后校验"或 SQLite 配置后端，**不引入文件锁** |
| **T-16 `docs_sync_check.py` 严格模式（告警期→阻断期）** | 切阻断需「连续 3~5 次零误报」；**计数已于 R16 归零**（仪器改名：`check_docs_sync.py` → `check_module_doc_mappings.py`，旧样本对新仪器无效）→ 自 R16 推送起重新计时 **0/3~5**（先例：R11-1 / R11-3 两次归零） | 每次推送后读 CI 日志的 `[docs-compliance]` 段 | 每批收尾（≈每 1~2 周） | 计数 +1 或记误报；累计达 3~5 → `.github/workflows/ci.yml` 两处 `--strict` 改 `--strict-block` |
| **T-21 本地 `vitest run` 偶发「全绿但 exit=1」** | 本地≈2/12 次、CI 0 次，现有证据不足以定位 | 再次出现 | 每季度 | 立即执行 `npx vitest run *> log.txt 2>&1` 保存完整 stdout/stderr，再排查 teardown / 管道提前关闭 |
| **T-31 自动 `chore: bump version` 不触发 CI** | 有 `G-009 CHANGELOG 一致性` 兜底，收益只是"提前发现" | 出现一次版本号/CHANGELOG 不一致 | 每半年 | 查 `pilotstd/__init__.py` 与 `CHANGELOG.md` 顶部版本；确认后可评估改 PAT 触发或加显式校验 |


| 项 | 来源 | 根因 / 现状 | 处置与代价 |
|---|---|---|---|
| **[观察中]** #33 TaskView.vue 距 G-010 警告线仅 1 行 | 2026-09-27 批 3 i18n 化后 `check_g_010_code_size.py` 实测 | **现状**：`web/src/views/TaskView.vue` 有效行 **397 → 399**（批 3 i18n 化：`import { useI18n }` + `const { t } = useI18n()` 各 +1），距 G-010 警告线（**>400**）**仅 1 行**。G-010 为两档制——**>400 仅警告、>500 才阻断**，故越线**不阻断 CI**；但越线后此后每次改动都会带一条警告，稀释警告信噪比。**位置**：`web/src/views/TaskView.vue`（有效行 399）。 | **处置**：**下次动该文件时顺手拆分**（局部重构即可，不需专项、**不挂窗口**；候选切口：模板里的"任务历史 + 历史详情"块可拆为子组件）。**代价**：暂不处理时，若某次改动越线，仅多一条 G-010 警告（不阻断），但会让"警告区"多一个长期住户。 |
| **[待排期]** `tests/` 受控测试不在本地门禁路径 → 改门禁脚本/基线时无法被拦住 | 2026-09-27 批 6 推送后 CI `test-backend` 失败时定位 | **根因**：`scripts/check_all.sh` 只有 `run_docs()` 才调 `pytest`（`check_all.sh:144`，且 `--ignore=tests/gui/`）——**`--fast` 与 `--deep` 都不跑 pytest**；pre-commit 钩子（`.husky/pre-commit`）只跑 `--fast --guards --local`；只有 CI 的 `test-backend` job 才跑 `tests/`（`python -m pytest tests/ -q --tb=short -n auto -p no:pytest-qt … --ignore=tests/gui/`）。于是"改门禁脚本/基线"这类改动的**受控测试**（`tests/test_check_i18n_hardcoded.py`）在本地**结构上不可能被触发**。**现状**：批 6 把 G-040 存量基线从 16 条清零为 0 条（只剩表头），`tests/test_check_i18n_hardcoded.py:245` 的 `assert baseline, "基线文件缺失或为空"` 断言"基线非空"这一**隐含前提**被打破 → CI `test-backend` 失败（run `36293074107`：`1 failed, 3972 passed`），**而本地 `check_all.sh --fast --guards --local` 连跑两次全绿**（G-040 只跑门禁脚本本体，不跑其受控测试）。本地确定性复现方式：`python -m pytest tests/test_check_i18n_hardcoded.py -x -q` → `1 failed, 18 passed`。 | **处置**：① 该用例已改为"断言**基线文件存在**（允许为空）+ 空基线时 `beyond` 捕获全部"，并补 1 条回归用例证明"空基线 ≠ 门禁失效"（任务 A，`49748c19`，现 **20 passed**）；② **流程补强（未实施，本任务明确不改脚本）**——下次改门禁脚本或基线时，本地自查清单追加 `python -m pytest tests/test_check_i18n_hardcoded.py -q`；或评估让 `check_all.sh` 检测到 `scripts/i18n_hardcoded_baseline.txt` 变更时自动跑该受控测试（属门禁变更，需单独决策，届时会连带 G-031 文档同步）。**不挂窗口**。**代价**：自动化落地前，每次改门禁/基线都靠人工记住这条自查，漏掉就红一次 CI 并浪费一轮排查（本次即为实例：从推送→拉日志→定位→修复多花一轮）。 |
| **[观察中]** `.doc`（OLE2）附件不被支持（原 `TODO(P2)`，R15 已消除其静默失效） | 2026-09-27 代码层 TODO 盘点（全库仅 3 类真实 TODO，另 2 类见下与「一、已清理」） | **现状**：注释原文——`# TODO(P2): .doc（OLE2）格式 python-docx 不支持，需另寻解析器（如 antiword/textract）或显式跳过标记`；其所在 `except` 分支只做 `logger.debug("DOCX 解析失败: %s", e)` 后 **返回空串**（`:105-107`）→ 公告附件若是 `.doc`（OLE2），正文会被**静默解析为空**（无用户可见提示） | **处置**：登记为观察项，**不挂窗口**（无用户反馈、无数据支撑 `.doc` 附件占比）。**触发条件**：出现 `.doc` 附件解析需求时，按"引入 `antiword`/`textract` 解析器"或"界面显式标注不支持"二选一评估。**代价**：该类附件正文静默缺失，需人工察觉 |
| **[观察中]** `web/src/views/HomeView.vue:17` 的 grid-layout-plus workaround（T-12 登记） | 2026-09-27 代码层 TODO 盘点 | **现状**：`:13-17` 注释记录——库内微任务调度器（he/Ze）与 Vue 响应式队列不同步，动态切换 `isDraggable` 时 GridItem 的 interact.js 拖拽监听器不重绑；现以 `layout.value = [...layout.value]` 克隆数组强制 GridItem 重新挂载绕过（`watch(() => appStore.dashboardLocked, …)`）。依赖版本 `web/package.json:22` `"grid-layout-plus": "^1.1.1"`；本轮**未做升级动作**，故 workaround 是否仍必需**未复评** | **处置**：保留 workaround，登记为观察项；**触发条件**：升级 `grid-layout-plus` 时复评（删克隆 → 浏览器实测锁定/解锁后拖拽是否仍生效）。**不挂窗口**。**代价**：每次锁定切换多一次数组克隆 + GridItem 重挂载（可忽略）；风险是库升级后行为变化时，workaround 可能掩盖新问题 |
| **[观察中]** **配置文件跨进程写锁（原 #31-P3，降级观察；T-35 登记）** | 2026-10-01 R14-4a 用户裁定（#31 核心闭环时降级） | **现状**：`ConfigManager.save()` 为「写 `.tmp` → `os.replace`」的原子替换 + 最多 3 次重试，**无跨实例/跨进程文件锁**；两个进程同时对同一 `config.json` 显式写入属 last-writer-wins。**量化判断**：R14-3a/b 后单批查询写盘 **126 → 2 次**、构造 **133 → 1**，且写盘只发生在「首次创建 / 迁移有变更 / 显式 GUI 或 API 修改」——两进程在同毫秒内显式写的概率在工程上可忽略。**不引入的理由**：文件锁跨平台语义差异大（POSIX `flock` vs Windows `LockFileEx`）、边缘情况多（NFS 挂载、异常退出遗留锁），维护成本高于其防范风险。**处置**：**挂观察**（不排期）。**触发条件**＝实际观测到并发写导致的配置丢失（日志/用户反馈/回归用例）→ 届时优先用「原子写 + 重试 + 写后校验」或「SQLite 配置后端」，**而非**引入文件锁。**代价（接受）**：极端并发下仍可能丢一次显式写入（写盘次数已降两个数量级，风险同比例下降）。 |

| **[观察中·计时中]** `docs_sync_check.py` 严格模式：当前为**告警期**（T-16 登记） | 2026-09-27 深挖 + 修复（`bf1a8521`） | **根因（四重失效，实测）**：① **8 条触发规则全部是死代码**——`_match_trigger_rules` 用字典字面量做 arity 分派（`{3: fn(a,b,c), 2: fn(a,b), 1: fn(a)}.get(n)`），Python 先求值三个调用 → 每次都有 TypeError 被 `except` 吞掉（对照实验：旧写法 8/8 规则异常；新写法 `feat:/fix:` 与源码变更两条正常触发）；② 只读 `git diff --cached`（CI 全新检出恒空 → "无暂存区变更，跳过"）；③ `main()` 所有路径 `return 0`（**永不阻断**）；④ 设计动作是调用 `claude` CLI 自动改写文档（`AUTO_FIX_DOCS` 默认 true）。**现状**：已修复 arity 分派 + 新增变更来源回退链（`--range` → `DOCS_SYNC_RANGE` → `--base`/`BASE_BRANCH` → 暂存区 → `origin/main...HEAD` → `HEAD~1..HEAD`；三点范围与全 0 SHA 正确处理）+ `--strict`（只判定、**不改文档**，强制 `auto_fix=False` 满足 CI 离线前提）；CI 步骤 `Docs sync check` 改为 `--strict` + `AUTO_FIX_DOCS=false` + `DOCS_SYNC_RANGE=before..sha`。**实测**：`--strict --range 5b859064..71e70054` 报出未同批更新的 `CHANGELOG.md` 且 **EXIT=0**；同范围 `--strict-block` **EXIT=1**。 | **处置（告警期，暂不阻断）**：**切换阻断的条件 = 连续 3~5 次提交误报为 0**（**计时自 R11-3 重新开始**——两次归零：第十轮的 6 次「告警期观察」因 CI 步骤实际跑的是形近脚本 `check_docs_sync.py` 而**全部无效**；R11-1 之后那 1 次（run `36304263963`）因 `DOCS_SYNC_RANGE` 右端为空、范围恒空而无效——两次都见 T-25 与其 R11-3 补丁）。**首个有效数据点＝R11-3（run `36306309371`，2026-09-27）：范围正确解析 `30de04e4..6434578c`、报出 2 项真实未同步（`docs/development.md` 工作流规则 + `CHANGELOG.md` feat/fix 规则）、误报 0 → 累计 **1／3~5**（用户 2026-09-27 批准记入）**；**切换方式 = 把 `.github/workflows/ci.yml` 的 `Docs sync check` 步骤中 `--strict` 改为 `--strict-block`（一行，两个脚本各自切换）**，此后未同批更新入库文档即 exit 1。**代价（告警期）**：规则义务面较宽（`feat:/fix:` → `CHANGELOG.md`；任意源码变更 → `STATUS.md`；Handler/Mixin 类增删 → `architecture.md` + 本主簿；`.py` 增删 → 模块清单；workflow → `development.md`），阻断期开启后每次提交需同批更新对应文档；观察期内只打印不拦。 |
| **[观察中]** 本地 `vitest run` 偶发「汇总全绿但 exit=1」（T-21 登记） | 2026-09-27 两次实测（批 6 一次、Commit 4 前一次） | **现状**：两次均为 `Tests 297 passed (297)` 而进程 **exit=1**；第一次仅保留输出尾部（未捕获完整日志），第二次立即重跑并捕获全量输出 = **exit 0 且无 `Unhandled`/`Errors` 段**，随后累计 **5 次连跑全绿**。**CI 未受影响**：`test-frontend` 在最近多次推送均 success。 | **处置（决策：挂起观察）**：**不挂窗口**；**触发条件 = 再次出现时立即保存完整 stdout/stderr**（`npx vitest run *> log.txt 2>&1`）以便定位（候选原因：teardown 未处理错误 / 下游管道提前关闭）。**代价**：偶发红灯需人工复跑甄别（本地≈2/12 次全量运行，CI 侧 0 次）。 |

| **[观察中]** **自动 `chore: bump version` 提交不触发任何 CI（T-31 登记）** | 2026-09-27 R12-1 排队归因取数时发现（原假设“bump 提交会产生额外 run”被证伪） | **现状**：`version` 作业用 `GITHUB_TOKEN` 推送 bump 提交，而 GitHub 规定**用 `GITHUB_TOKEN` 的推送不触发 workflow** → 78 个 run 中 head 为 bump 提交的**0 个**；即 bump 内容（版本号写入 `pilotstd/__init__.py`、`CHANGELOG.md` 等）**没有独立 CI 验证**，靠**下一次推送**的 `test-backend` 里 `G-009 — Check CHANGELOG version consistency` 兜底。**影响（正面与负面）**：正面＝不额外占用 CI 与排队（T-30 归因因此少一源）；负面＝若某次 bump 写坏而此后长期无推送，问题会静默滞留。 | **处置**：登记为观察项，**暂不动作、不挂窗口**（兜底已存在且 bump 由版本脚本生成、内容确定性高）。**触发条件**：出现“版本号/CHANGELOG 不一致”类事故时，评估给 bump 提交加显式验证或改用 PAT 触发。**代价**：极端情况下 bump 错误可静默到下一位开发者推送。 |
| **[观察中]** **cookiecutter CLI 端到端生成仍未纳入 CI（R14-5 新增，R15 部分缓解）** | 2026-10-01 R14-5 任务一"生成物验证"落地时发现 | **现状**：`requirements-dev.txt` 无 `cookiecutter`；本仓库对模板的正确性验证改用 **jinja2 等价渲染**（`tests/unit/test_adapter_template_generation.py`，FastAPI 依赖链自带 jinja2）。即"真实 cookiecutter 生成路径"（含 `hooks/post_gen_project.py` 的自动注册）**未被 CI 覆盖**。 | **处置（R15 更新）**：`cookiecutter` 已加入 `requirements-dev.txt`；钩子本体已由 `tests/test_adapter_post_gen_hook.py`（jinja2 渲染 + 假项目根跑通五处注册）覆盖，并在落地时当场抓到并修掉钩子内 f-string 与 Jinja 占位符冲突的静默缺陷。**仍缺**：真实 `cookiecutter` CLI 的端到端生成（含目录命名/交互）未被 CI 覆盖。**触发条件**＝模板改动涉及 hooks 或脚手架被频繁使用 → 补一条真实 CLI 用例。**代价**：hooks 脚本的回归只能靠人工跑一次 cookiecutter；模板本体（渲染/编译/零字面量）已由 jinja2 用例覆盖。 |
| **[观察中]** **`check_schema_consistency` 的"测试建生产同名表"约束无提示（R14-5 新增）** | 2026-10-01 R14-4c 提交被该门禁阻断时实测 | **现状**：`scripts/check_schema_consistency.py` 扫描 `tests/` 内 `CREATE TABLE <生产表名>`，要求列集与迁移链产出的生产 schema **完全一致**（否则 `MISSING > 0` 阻断提交）。R14-4c 的 v61 迁移测试需要一个"默认值漂移"的 `file_index` 表 → 直接建表会 MISSING=50 → 最终用**中性表名 + `ALTER TABLE … RENAME TO`** 规避（RENAME 保留 DEFAULT 子句）。**影响**：约束本身合理（防测试 fixture 与生产脱节），但**无自动化提示**——新人写同类测试时只能靠门禁报错反推。 | **处置**：登记为**观察中**。**触发条件**＝再出现一次同类阻断（或有人反馈难以理解）→ 在该脚本输出里补一行指引（"若只想构造局部形态，请用中性表名 + RENAME"）。**代价**：偶尔一次提交被拦 + 需阅读脚本才能理解缘由。 |
| **[观察中]** **空库跑迁移链固定打印 3 条 `OperationalError` 告警（T-36 登记）** | 2026-10-02 通知架构重设计阶段 1a/1b 跑迁移探针时发现；**已用 `git worktree` 对基线复现确认为预存** | **现状**：全新空库执行 `Database(path)` 的迁移链，stderr 固定出现三条（去重后）`sqlite3.OperationalError`：`no such table: _schema_version`（首次建表前的 `SELECT MAX(version)`）、`no such table: standard_info_cache`（×3：`ADD COLUMN source_version` / `data_state` / `last_accessed_at`）、`duplicate column name: user_id`（`notification_policy` 的补列迁移在已含该列的库上重跑）。**三者都是有意的防御分支**（`database.py` 先查后改、迁移函数逐列 `try/except`），**无功能影响**——只是以 ERROR 级日志打印出来。**根因**：部分 `ALTER TABLE` 在目标表不存在时直接执行（未先查 `sqlite_master`），而 `docs/architecture/modules/core.md` 已把"先查 `sqlite_master` 确认表存在再执行"写为约定（v53/v59 即按该约定实现）。**复现命令（只读，不改仓）**：`git worktree add --detach $env:TEMP\_base f2311a4c` → 在该 worktree 下 `python -c "import os,tempfile,sys;sys.path.insert(0,'.');os.environ.setdefault('SUPERUSER','probe');os.environ.setdefault('ADMIN_PASSWORD','probe');from pilotstd.core.db import Database;d=tempfile.mkdtemp();db=Database(os.path.join(d,'p.db'));db._get_conn();db.close()" 2>&1 \| Select-String OperationalError` → 基线同样输出上述三条 → 判定预存。**同口径判据（供后续批次用）**：任何批次跑同一探针，**去重后消息集合应与上面三条完全一致**；多出的即该批引入，必须修。 | **处置**：登记为**观察中**，**不挂窗口**（无功能影响，且修它要动已执行迁移或 `database.py` 的查询顺序——属 P-106 敏感面）。**触发条件**＝① 有人因这些日志误判为故障（反馈一次即可）；② 任一批次跑该探针出现"多出的告警"（说明该批引入了新的同类问题，应就地修）；③ 做 `database.py` 迁移执行顺序改造时顺手收口。**代价**：新接触者排查安装问题时会被这三条 ERROR 误导；且未来若新增同类 `ALTER TABLE` 仍会继续打印（已由上面的判据兜住回归）。 | 2026-10-02 |

> **2026-09-27 结构重整**：已闭环的 5 行按归属移出——「单条网络请求/大文件 IO 不可中断」（✅ 已接受）与「`_migrate_v59_…` docstring 过时」（✅ 已决定不改）→「五、已接受的设计决策 · 归档并入」；「拆出新模块时注释密度被稀释」（✅ 已落实）、「#23 合并前侦察未覆盖全组合」（✅ 已落实）、「#27 gates.md 版本历史两行挤在同一物理行」（✅ 已修复）→「一、已清理 · 归档并入」。本节现只保留**仍未闭环**的观察项。 **2026-09-27（R11-5）补记**：**T-20 已 ✅ CLOSED**（R11-4 实测证伪原假设 + 交付基线/普查工具），按本节规则移入「一、已清理」；其剩余可治理项拆为 **T-29**（8 处永久 `mark.skip`，挂第十二轮）。 **2026-09-27（R12-2b）补记**：**T-28 亦 ✅ CLOSED**（`-rs` 已覆盖全部 5 处 pytest 调用，CI 日志实证 44 条跳过明细），同样移入「一、已清理」。 **2026-09-27（R12-4a）补记**：**T-32 亦 ✅ CLOSED**（L1 触发式已覆盖 `.pyi/.pyw`，双向受控验证通过），同样移入「一、已清理」。 **2026-09-27（R12-8）补记**：**T-26（#34 复发哨兵观察项）随 #34 修复而关闭**——新哨兵转为：任何 GUI 作业再现 access violation → 立即重跑 `gui-race-probe`（loops=50）并回溯是否引入新的 Qt 锁／线程 churn 模式。 **2026-10-01（R14-5）校准**：**T-26 与 T-24 两行自本节移入「一、已清理」**（前者 R12-8 已关闭、后者 L1/L2/L3 全部落地收口），本节仅保留仍未闭环的观察项；同时新增 4 条 R14 复盘发现的隐性债务（SQL 内嵌状态字面量／cookiecutter CLI 未入依赖／本地网络用例挂起／schema 一致性门禁约束无提示），并给每条加状态标签 + 汇总表。

---

## 七、操作记录（一次性数据操作 + 留档 SQL + 只读巡检）

### 7.1 执行通道（2026-09-25 实测修正）

| 通道 | 是否可用 | 依据 |
|---|---|---|
| `POST /query`（admin SQL 端点） | ✅ **可用，且首选** | 路由无 prefix，真实路径就是 **`POST /query`**（审计里写的 `/api/admin/db/query` 只是标签字符串）。`admin_db.py:100-123` 的 `_ALLOWED_TABLES` **只作用于 `DROP TABLE`**；SELECT 自动包 `LIMIT 1001`，INSERT/UPDATE/DELETE 分别受"WHERE 必需"等约束 → **普通读写不受表白名单限制**，无需 SSH/容器执行 |
| 容器内 `python -m sqlite3` | ✅ 可用（备选） | 容器**无 `sqlite3` CLI**（`Dockerfile:30` 只装 gosu/git/curl）；需以 `appuser` 执行（`Dockerfile:27` + `entrypoint.sh:151-152` `gosu appuser`），避免 root 写库改 WAL/SHM 属主 |

### 7.2 只读巡检（已执行，2026-09-25）

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

### 7.3 一次性补建（已执行，2026-09-25，v0.109.4）

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

### 7.4 巡检走公开端点复核（已执行，2026-09-26，第六轮）

目的：确认 #18 三组巡检**不必依赖 admin SQL 端点**即可复现（能走公开 API 的就不该要求人执行 SQL）。

| 口径 | 公开端点可行性（实测） |
|---|---|
| 全量性前提 | `GET /api/favorites/export?format=json` → **105 行 == 库内 `user_favorites` 105 行**；接口 SQL（`favorites.py:453-470`）只有 `WHERE f.user_id = ?` + `ORDER BY`，**无 LIMIT/分页** → 全量成立，可用于本地算基线 |
| A 组（标准号/名称） | ✅ `user_favorites` 维度可算：`standard_number`=0 空、`std_name`（键名，来源 `announcement_record`）=0 空、`UNKNOWN_*`=0；❌ `favorite_downloads.standard_no/standard_name` **公开端点未暴露**（`_DOWNLOAD_FIELDS` 仅 4 列，`favorites.py:341-346`） |
| B 组（分类列未回填） | ✅ `user_favorites.standard_type` 可算：0 空（105 条全 `NationalStd`）；❌ `favorite_downloads` / `announcement_record` / `download_queue` 的分类列未暴露 |
| C 组（去重基线） | ✅ 可算：按 `(standard_number, standard_type)` 分组 = 105 组、**重复组 0**（本用户全量数据） |
| 未暴露维度 | 经 `POST /query`（同为 API）复核：`fd_std_no_null=0`、`fd_std_no_UNKNOWN=0`、`fd_std_name_null=0`、`fd_std_type_empty=0`、`ar_std_type_empty=0`、`dq_std_type_empty=0` |

探针（不入库）：`C:\Temp\pilotstd-probe\probe_a1_export_checks.py`。

### 7.5 部署后现场复核（已执行，2026-09-26，v0.110.2）

| 复核项 | 结果 |
|---|---|
| 版本 | `/api/system/version` = `0.110.2`（tag `v0.110.2`、image `ghcr.io/leanmore/pilotstd:v0.110.2`）；`/api/health` 返回的 version = 构建 sha `c421c572` |
| TD-20 读侧 | `GET /api/settings` 的 `tasks` **10 键、缺键 0**；`auto_archive_retry_enabled=True` / `auto_archive_retry_cron='0 4 * * *'` |
| 与调度器一致 | `GET /api/scheduler/status` 中 `auto_archive_retry` next_run `2026-09-27T04:00+08:00`（cron 与读侧一致） |
| UI 新任务行 | Playwright 现场：设置页「定时任务」出现"收藏下载链（自动归档重试）"、开关为开、cron 输入框 `0 4 * * *`、页面回填值 == 后端值；截图 `C:\Temp\pilotstd-probe\shots\settings-schedule.png` |
| 部署方式 | 人工部署（该主机不自动拉取；更新开关见 `docker/api/system.py:152` `POST /api/system/update`），部署后 `/api/health` 构建 sha 由 `22d4d90b` → `c421c572` |

探针（不入库）：`probe_td20_readside.py`、`verify_settings_ui.cjs`。

### 7.6 前端 CI 缺陷修复（已执行，2026-09-26，第七轮）

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

### 7.7 #17a 量化验收实测（已执行，2026-09-26）

| 路径 | 修复后退出耗时 | 占 5000ms 预算 | 修复前对照（`git stash` 掉改动） |
|---|---|---|---|
| ScanWorker（流进行中） | **14ms** | 0.3% | 5035ms、退出=False、保活 +1 |
| QueryWorker（流进行中） | **6ms** | 0.1% | 5009ms、退出=False、保活 +1 |
| QueryWorker（暂停中） | **60ms** | 1.2% | 5010ms、退出=False、保活 +1 |
| DriveEnumerator | **54ms** | 1.1% | 5055ms、退出=False、保活 +1 |

假 stream 为 20000 条 × 10ms（不中断需 ~200s）；修复后底层流在 12–14 条处被终止，`orphan_timeout_total()` 增量 0、保活残留 0。测量脚本（不入库）：`C:\Temp\pilotstd-probe\measure_worker_abort.py`。

### 7.8 #17a 首次上 CI 失败与加固（2026-09-26）

| 项 | 内容 |
|---|---|
| 现象 | 推送 `cdc308f3` 后 `test-gui-unit` 失败，**耗时 8.2 分钟**（同树前两次成功运行均为 18 分钟）→ 进程在套件中途终止，未打印 pytest 汇总；`version`/`docker`/`exe` 连带 skipped |
| 本机复现 | 用 CI 同款命令（`pytest tests/gui/ tests/test_regression_architecture.py --cov=pilotstd/ui/core/handlers/ --ignore-glob="*test_e2e*.py"` + `PILOTSTD_GUI_TEST=1`）本机 **990 passed / 覆盖率 68.71%**，不复现；本地全量两轮均 1000 passed |
| 根因（判定） | 新用例的**绝对毫秒阈值**（`elapsed_ms < 500`）在 CI 的 coverage 插桩 + 慢 runner 下会偶发失败；而断言在 `isFinished()`/收尾之前抛出 → 局部变量 `worker`（仍在运行的 QThread）随帧释放被 GC → Qt 触发 `QThread: Destroyed while thread is still running` 并 **qFatal 终止进程** → 套件中途死亡（正是 8.2 分钟无汇总的形态） |
| 加固 | ① `_stop_and_measure()` 在 `finally` 中无条件 `worker.wait(timeout_ms)`：断言失败也先把线程收干净，杜绝"运行中被析构"；② 绝对毫秒阈值全部放宽为 `2000–3000ms` 量级（真正的验收线仍是"≤80% timeout"，即 4000ms）；③ `mgr.started.wait(5.0)` → `20.0`（CI 冷启动慢） |
| 教训 | 线程类测试的收尾必须与断言解耦（先 join 再断言或 finally join）；跨环境验收线用相对预算而非绝对毫秒 |

### 7.9 T-23：「三-B」标签经评估保留（已裁定，2026-09-27）

**裁定：保留现状，不收敛**——「三-B、i18n key 一致性检查」是**功能性子节**（描述一个具体检查项的补充说明），与「六-B、观察项」（**结构性容器**，本轮已收敛为「六」）**性质不同**；本轮 T-22 编号收敛的目标是消除**结构性空档**（六-B → 八），「三-B」不存在空档问题。

| # | 裁定理由 |
|---|---|
| 1 | 「三-B」是功能性子节标签（一条具体检查项的补充说明），与「六-B」这类结构性容器的性质不同 |
| 2 | 强行改为「三」会与父章节「三、门禁规则清单」的平级子节产生语义混淆——它不是一个独立的门禁规则 |
| 3 | 本轮编号收敛的目标是消除结构性空档（六-B → 八），「三-B」不存在空档问题 |
| 4 | 若未来 i18n 检查升级为独立门禁规则，再自然提升为「三-x」即可 |

**处置**：不动作（无代码/文档结构变更）；本条为**已裁定**记录，**不挂窗口**。

### 7.10 #31／#32／#34 三债终局裁定（已裁定，2026-09-27，第十一轮 R11-2）

**本轮定位**：用户指定“本轮只出裁定书，不做全量偿还”。三份裁定书已逐条写入「二、剩余台账」对应行，四要素齐备（现状量化／偿还方案+成本／转已接受的代价／终局结论），判决均落在三选一（[本轮偿还] / [挂窗第N轮] / [转已接受+代价]）。

| 项 | 终局结论 | 关键判据（2026-09-27 本轮实测） | 后续动作 |
|---|---|---|---|
| **#31** ConfigManager 多实例交错写 + 热路径高频 IO | **[挂窗第十二轮]** | `get_profile()` 单次 **4.28／4.27／4.28 ms**，每次恰 **1.00 次构造 + 1.00 次 save**；单查询 126 次 → **≈0.54 s + 519 KiB 写盘**；沉淀面＝生产构造点 21 处 + 测试 31 文件／104 行；P2 冲击“构造即写回”契约（`tests/test_core_config.py:333-340`）；“只做 P1 缓存”因需配置失效通知而被否决 | 第十二轮按 P1→P2→P3 分期偿还，或转已接受并按裁定书 ③ 记账 |
| **#32** 后端状态值用中文 + 前端硬编码比较 | **[挂窗第十二轮起分阶段偿还]** | 生产 **248 处／50 文件**、测试 **456 处／65 文件**；容器定义点 **9 处／5 个名字**（更正旧记“7 处”）；四阶段路线图合计 **7~12 commit** | A 阶段（新建 pilotstd/core/status.py 枚举模块）须第十二轮完成；未动即当轮转已接受 |
| **#34** EventBus reset 竞态 → CI `test-gui-unit` 间歇红 | **[转已接受+代价]** | R1 之后 **14 run／`test-gui-unit` 14-14 success**；该样本在 ≈1／40 基率下零复发概率 ≈70%（不足以否认基率） | 保留 R1；哨兵登记为「六、观察项」T-26（复发 ≥1 次 → 当轮做 R2+R4） |

**取数方式（探针一律不入库，存于仓库外临时目录）**：
1. **#34 走 GitHub Actions API**——`/actions/runs` 取全量 73 run（3 页），逐 run 读 `/jobs` 判 `test-gui-unit` 结论与 skipped 明细；R1 分界取提交 `c78cbd89` 的提交时间（2026-09-27T04:26:43Z）。
2. **#31 走运行时打点 + pytest 插件探针**——包装 `ConfigManager.__init__` 与 `ConfigManager.save` 计数、`scorer.get_profile()` 计时 3×100 次；另以 `-p cfgcount2` 插件跑单个查询用例（`tests/test_query.py` 的 `TestQueryEngine::test_parallel_batch_query`）统计单查询的构造／写盘／`get_profile` 次数（复现上一轮的 126 次数据点）。
3. **#32 走 AST + tokenize 口径复跑**——字符串字面量“内容恰为 9 个状态值之一”（排除注释／docstring）计生产 248／测试 456；容器定义点改用**解包 `frozenset(...)` 的 AST 探针**（这是旧记“7 处”漏计 2 处的原因）。

**本轮未产生任何代码／测试变更**（用户明确禁止 #32 产出代码变更，且 #31／#34 经评估均超“≤1 commit 且无连锁风险”阈值，一律挂窗）。

### 7.11 R11-3：CI 范围取值陷阱的取证与修复（已执行，2026-09-27，第十一轮）

**触发**：R11-2 收尾核对 R11-1 修复在 CI 的实际效果时发现——步骤虽已跑对脚本，但**变更范围恒空**，仍在空转。

| 步 | 取证动作（可复现） | 结果 |
|---|---|---|
| 1 | GitHub API 读 run `36304263963` 的 `repo-compliance` 作业（job `108577660279`） | step 6 `Docs sync check` = **success**——与修复前的空转**不可区分** |
| 2 | 取该作业日志（`curl -H "Authorization: Bearer …" …/actions/jobs/108577660279/logs`） | `AUTO_FIX_DOCS: false`；**`DOCS_SYNC_RANGE: 27a39d6102c4d076a05f960100668acc08ef9c93..`（右端为空）**；`[docs-compliance] 变更来源: origin/main...HEAD（BASE_BRANCH=main）｜模式: 告警期`；`PASS: 无变更文件` |
| 3 | 根因判定 | push 载荷无 `event.sha` 字段（应为 `github.sha`）→ `DOCS_SYNC_RANGE=<before>..` 右端空 → 脚本判该候选非法 → 回退 `origin/main...HEAD`；推送到 main 时 `origin/main == HEAD` → diff 恒空 |
| 4 | 本地同形态复现 | `DOCS_SYNC_RANGE='27a39d61..' BASE_BRANCH=main python scripts/check_docs_sync.py --strict` → 与 CI **逐字相同**的两行输出 |
| 5 | 修复后同形态 | `变更来源: HEAD~1..HEAD（HEAD~1..HEAD）｜模式: 告警期` + `PASS: 所有核心模块变更已同步文档`（真实判定，不再“无变更文件”） |
| 6 | 真实未同步场景 | `--range 27a39d61..b2a8717c`（该范围改了工作流文件）→ 正确报出 `docs/development.md` 未同步（触发规则：CI/CD 工作流变更）+ CHANGELOG.md，**EXIT=0**（告警期） |
| 7 | 反证 | 新增 11 例受控测试，对**修复前**脚本跑 **6 failed / 13 passed**；修复后 **19 passed** |

**修复内容**：`.github/workflows/ci.yml` 的 `DOCS_SYNC_RANGE` 右端 `github.event.sha` → `github.sha`；`scripts/check_docs_sync.py` 与 `scripts/docs_sync_check.py` 的回退链新增“候选必须确实含变更文件”校验（严格模式生效），全部候选为空时打印显式原因。**未产生任何功能代码变更**（仅门禁脚本与 CI 接线）。

**推送后应观察到（预测验证）**：该 run 的 `Docs sync check` 步骤须打印真实的 `WARN(告警期)`（本批改了工作流文件却未同批更新 `docs/development.md`），彻底破除“空转即 PASS”的假绿。


### 7.12 R11-3b：遗漏补修与浅克隆根因（已执行，2026-09-27，第十一轮）

**① 自曝的遗漏**：R11-3 首次提交（`30de04e4`）**只落盘了两个脚本与文档，`ci.yml` 的 YAML 修改丢失**——起因是编辑工具在 CRLF 文件上锚点失配报错，改用 Python 补丁脚本重做时只写了两个 `.py`。CI 立即自证：run `36306033918` 的 `Docs sync check` 步骤环境仍为 `DOCS_SYNC_RANGE: 409a5be18435bfc5a50aede873513a54ee0a0492..`（右端仍为空）。**教训**：改多文件时应对每个目标逐一确认"已真正落盘"（`git diff --stat` 复核），而不是依赖改完即推。

**② 三层根因（全部有证据）**：

| 层 | 事实 | 证据 |
|---|---|---|
| 第一层 | push 载荷没有 `event.sha` 字段 → 右端展开为空 → 该候选被脚本判为非法 | run `36304263963` 的步骤环境：`DOCS_SYNC_RANGE: 27a39d61…93..` |
| 第二层 | 回退候选 `origin/main...HEAD` 在推送到 main 时恒空（`origin/main == HEAD`） | run `36306033918` 日志：`变更来源: origin/main...HEAD（BASE_BRANCH=main，该范围无变更）` |
| 第三层 | 同一作业更早的 `check-repo-compliance.sh` 执行 `git fetch origin main --depth=1` → **在 tip 建立浅边界** → `HEAD~1` 不可用、`git log -n2` 只剩 1 条 → 兜底 `HEAD~1..HEAD` 也失效 | 本地按 actions/checkout 流程复刻（见③）：`.git/shallow` 出现、`git rev-parse HEAD~1` = `fatal: Needed a single revision`、`git diff origin/main...HEAD` = 0 文件 |

**③ 本地端到端复刻浅克隆（探针不入库，位于仓库外临时目录）**：`git init` → `git fetch --no-tags --prune --no-recurse-submodules origin '+refs/heads/*:refs/remotes/origin/*'`（模拟 `fetch-depth: 0`）→ `git checkout -B main refs/remotes/origin/main` → `git fetch origin main --depth=1`（模拟 `check-repo-compliance.sh`）→ 复刻出的现象与 CI 完全一致。

| 复刻场景 | 修复前 | 修复后（本批） |
|---|---|---|
| 浅克隆 + 右端为空（原始事故形态） | `变更来源: origin/main...HEAD` → `PASS: 无变更文件` | 回退失败但**显式说明**：`（BASE_BRANCH=main，该范围无变更（提示：仓库为浅克隆，HEAD~1 等历史范围不可用））` |
| 浅克隆 + 显式完整范围 `409a5be1..30de04e4`（= `ci.yml` 修复后的形态） | 未被使用（右端为空） | **真实评估 8 个文件**：`变更来源: 409a5be1..30de04e4（环境变量 DOCS_SYNC_RANGE）` + `PASS: 所有核心模块变更已同步文档` |

**④ 修复清单**：`.github/workflows/ci.yml` 右端 `github.event.sha` → `github.sha`；`.github/scripts/check-repo-compliance.sh` 去掉 `--depth=1`；`scripts/check_docs_sync.py` 与 `scripts/docs_sync_check.py` 新增 `_is_shallow_clone()` 说明与 4 例受控断言（合计 **23 passed**）。

**⑤ 连带发现**：`check-repo-compliance.sh` 的“新增文件”检查在推送 main 时 `origin/<base>..HEAD` 恒空 → 白名单／黑名单判定从未生效（第六个 CI 盲区同族）→ 登记「六、观察项」**T-27**，挂第十二轮。


### 7.13 R11-4：T-20 跳过普查与 fixture 基线（已执行，2026-09-27，第十一轮）

**任务口径**：为「60 处 `self.skipTest`」补最小 fixture 基线，识别可治理部分；不做全量治理、不改既有测试逻辑。

**① 三口径实测**：

| 口径 | 方法 | 结果 |
|---|---|---|
| 静态调用点 | AST 扫描 `tests/**/test_*.py` | `self.skipTest` **60 处 / 10 文件**（43 处为 `Fixture not found` 守卫）；`pytest.skip()` 2、`@pytest.mark.skip` 10、`@pytest.mark.skipif` 10、`@unittest.skipIf/skipUnless` 17 |
| 本地运行期 | `python -m pytest tests/ -q -rs --ignore=tests/gui/` | **4290 passed / 14 skipped**（含 R11-4 新增 10 例；分类：网络 6／依赖 5／其他 2／平台 1） |
| CI 运行期 | run `36306309371` 的 `test-backend` 日志 | **3997 passed / 44 skipped**（CI 断网 + `_CI` 跳过；CI 未开 `-rs`，明细不可得 → 见 T-28） |

**② 逐文件实测（7 个 fixture 文件 + 3 个其余文件）**：

| 文件 | 静态守卫 | 运行期跳过 | 说明 |
|---|---|---|---|
| `tests/test_adapters.py` | 25 | 0 | 25 处全为 fixture 守卫，fixture 在库 → 全部真实执行 |
| `tests/test_e2e_adapters.py` | 15 | 4（本地） | 站点状态驱动（无响应/未收录）；CI 另有类级 `@unittest.skipIf(_CI)` |
| `tests/test_energy.py` | 4 | 0 | fixture 在库 |
| `tests/test_ncha.py` | 4 | 0 | fixture 在库 |
| `tests/test_cssn.py` | 3 | 0 | fixture 在库 |
| `tests/test_gongbiaoku.py` | 3 | 0 | fixture 在库 |
| `tests/test_miit.py` | 2 | 0 | fixture 在库 |
| `tests/test_tdpress.py` | 2 | 0 | fixture 在库 |
| `tests/test_scanner.py` | 1 | 1 | 平台／文件系统能力（超长文件名） |
| `tests/test_mock_pipeline.py` | 1 | 0 | mock 随机兜底（未触发） |
| 其他（不在 T-20 原口径内） | — | 9 | `test_ocr_fallback` 1（provider）+ `test_query_subsystem_snapshot` 4 + `test_batch_dispatch` 4（均为 `@pytest.mark.skip`） |

**③ 结论**：**因缺 fixture 而跳过 = 0 处**——43 个守卫依赖的 15 个 fixture 文件全部已入库（`tests/fixtures/`，登记见 `tests/fixture_baseline.py`），运行期一次也不触发。
T-20 原表述「60 处会让跳过数长期偏高」是**静态口径误用**，已更正。真正剩余的可治理候选是 **8 处 `@pytest.mark.skip`**（依赖真实 HTTP／ThreadPoolExecutor／daemon 线程），属可偿还；其余 6 处为环境依赖（网络/平台），按 §〇 归「环境依赖」。

**④ 交付物（仅新增，未改既有测试逻辑）**：

| 文件 | 作用 | 覆盖 |
|---|---|---|
| `tests/fixture_baseline.py` | fixture 基线登记（15 项）＋ `missing_fixtures()`／`uncovered_guards()`／`baseline_report()` | 登记表覆盖全部 7 个有守卫的文件 |
| `tests/skip_census.py` | 运行期／静态双口径普查：解析 `pytest -rs` → 分类（fixture／random／platform／network／dependency／other），支持 `--json`／`--static` | — |
| `tests/test_fixture_baseline.py` | 5 例：fixture 就位、无缺失、守卫全覆盖、静态基线数一致（43／7）、登记 ⊇ 守卫文件 | 受控 |
| `tests/test_skip_census.py` | 5 例：分类六类、`-rs` 解析与 `[n]` 展开、非跳过行忽略、按文件汇总、静态口径 60 一致 | 受控 |

**⑤ 复现命令**：
```
python -m pytest tests/ -q -rs --ignore=tests/gui/ > skip.txt 2>&1
python tests/skip_census.py skip.txt              # 运行期分类报告
python tests/skip_census.py --static --json        # 静态口径清单
python tests/fixture_baseline.py                   # fixture 基线汇总
```


### 7.14 R11-5：CI 红灯暴露时间实测与 T-24 L3 落地（已执行，2026-09-27，第十一轮）

**① 11 次 run 耗时统计（GitHub Actions API：run `run_started_at` → 作业/步骤 `started_at`／`completed_at`）**

| # | run（sha） | 结论 | 排队：作业启动（相对 run 开始） | `repo-compliance` G-038 作业内完成 | `test-backend` Ruff 作业内完成 |
|---|---|---|---|---|---|
| 1 | `6434578c` | success | +302s | +15s | +30s |
| 2 | `30de04e4` | success | +3s | +13s | +43s |
| 3 | `409a5be1` | success | +3s | +14s | +46s |
| 4 | `b2a8717c` | success | +3s | +8s | +46s |
| 5 | `e1b75246` | success | +3s | +12s | +42s |
| 6 | `fed654ea` | success | +154s | +14s | +38s |
| 7 | `f1e55d4a` | **failure**（E501） | +188s | +14s | +36s |
| 8 | `73a35ed5` | **failure**（E501） | +93s | +12s | +36s |
| 9 | `e94f8ddb` | **failure**（E501） | +288s | +14s | +36s |
| 10 | `bf1a8521` | success | +471s | +10s | +40s |
| 11 | `2014219d` | success | +234s | +12s | +38s |

**中位值**：排队 **154s**；`repo-compliance` G-038 作业内完成 **+13s**（步骤自身耗时中位 9s）；`test-backend` Ruff 作业内完成 **+38s**。

**② 逐步骤对照（run `36308445948` / `7086ef0c`，排队仅 3s 的样本）**

| 作业 | 步骤（关键） | 作业内完成 | 耗时 |
|---|---|---|---|
| `repo-compliance` | checkout | +2s | 1s |
| `repo-compliance` | 前 10 个检查（compliance/bash、G-026/029、Docs sync、Capabilities、G-030/032/033/037）**合计** | +3s | ≤1s each |
| `repo-compliance` | **G-038（ruff+mypy）**（前移前位于末位） | **+13s** | 10s |
| `test-backend` | Setup Python | +4s | 2s |
| `test-backend` | **Install dependencies** | +33s | **29s** |
| `test-backend` | **Ruff check（G-038）** | **+34s** | 1s |

→ 前移后 G-038 紧跟 checkout（+2s）执行，作业内完成 ≈ **+12s**（收益 ≈ **1s**）；`test-backend` 的 Ruff 受 `Install dependencies` 独占 29s 拖累，作业内 **+34s**。

**③ 实施**：`.github/workflows/ci.yml` 的 `repo-compliance` 作业中，把 `G-038 — 历史遗留错误清零（Ruff+Mypy+裸noqa）` 步骤由**末位移到 checkout 之后第一位**（检查命令、范围、逻辑零改动；由 PyYAML 解析复核步骤顺序：checkout → G-038 → compliance → …）。

**④ 结论与更正**：T-24 L3 原表述假设“ruff 红灯要等 ~3 min（test-backend 报错）”。实测表明：**lint 红灯本就在作业内 +12~14s 由 `repo-compliance` 的 G-038 报出**（三次 E501 事故 run 均是如此），
“3 分钟”来自 **runner 排队**（11 次中位 154s）而非步骤顺序；故 L3 的实质收益＝让 lint 成为作业内**首个**信号（顺序收益 ~1s）。真正的杠杆（并发组按 ref 拆分／下游重作业 `needs` 门控）已登记 **T-30**。

**⑤ 复现命令**（探针不入库，存仓库外）：
```
python <probe>/r11_5_timing.py     # 11 次 run 的排队与步骤完成时刻表
python <probe>/r11_5_steps.py      # 单个 run 的逐步耗时（repo-compliance / test-backend 对照）
python -c "import yaml;d=yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8'));print([s.get('name') for s in d['jobs']['repo-compliance']['steps']])"
```


### 7.15 R12-1：T-30 排队归因取数与方案对比（已执行，2026-09-27，第十二轮；只读，未改 CI）

**① 三源归因（GitHub Actions API 全量 78 个 run）**

| 源 | 判据 | 实测 | 结论 |
|---|---|---|---|
| **自串行（并发组）** | 某 run 创建时，是否有更早的 run `updated_at > created_at` | **26/78 = 33%** 被挡住；等待 1／1／1／1／13／73／90／129／153／186／231／247／286／300／321／332／470／653／678／699／705／1132／1179／1211／1216／1340 s（被挡样本中位 ≈300s） | **主因**（由本仓库 `concurrency: group: ci-cd` + `cancel-in-progress: false` 造成） |
| **runner 分配** | 未被挡 run 的作业启动时刻 | **+3s**（多次一致） | 不是瓶颈 |
| **bump 额外 run** | head 为 `chore: bump version` 的 run 数 | **0 个**（`GITHUB_TOKEN` 推送不触发 workflow） | 假设证伪 → 登记 T-31 |

**② 关键路径（最近 10 个已完成 run 的逐作业时长，中位）**

| 作业 | 中位时长 | 说明 |
|---|---|---|
| **`test-gui-unit`** | **467s** | **关键路径第一名**；`version`／`docker`／`exe` 都要等它 |
| `test-gui-coverage` | 215s | 依赖 test-backend 的覆盖率产物 |
| `test-backend` | 184s | 含 94~133s 的 pytest |
| `exe` | 176s | 需 `version` 的产物 |
| `test-e2e` | 103s | — |
| `docker` | 93s | 需 `version` 的产物 |
| `frontend-e2e` | 79s | Playwright |
| `test-frontend` | 55s | — |
| `e2e-coverage` | 45s | — |
| `security-scan` | 35s | — |
| `repo-compliance` | 16s | 已含前移后的 G-038 |
| `version` | 8s | 等全部测试作业 |

run 总时长中位 **828s**；关键路径 ≈ `test-gui-unit` 467s → `version` 8s → `docker`/`exe` ≈176s。

**③ 方案对比（A~F，均待用户选型；R12-1 不落地任何一条）**

| 方案 | 机制 | 依据实测的预期效果 | 风险 | 成本 |
|---|---|---|---|---|
| **A 并发组按 ref 拆分** | `group: ci-cd-${{ github.ref }}` | 同 ref 的 run 并行 → 33% 的等待消失；**CI 分钟近翻倍** | 中高：`version` bump／`docker`/`exe` tag 竞态需额外设计 | 2~3 commit |
| **B 取消旧 run** | 保留单组 + `cancel-in-progress: true` | 新推送立即开始（等待≈0），但被取消 run **无完整验证** | 中：连续推送时前一次验证被腰斩 | 1 行 + 1 run 观察 |
| **G（推荐）按 ref 单组 + 取消**（A∩B 的最小版） | `group: ci-cd-${{ github.ref }}` + `cancel-in-progress: true` | 消除 33% 自串行等待；**分支推送不再阻塞 main**（现状是全局组共享）；同 ref 只保留最新 run | 低-中：被打断的 main run 无完整结论（其提交会被下一次 run 覆盖验证） | 1~2 commit |
| **C lint-fast 门控** | 新增轻量 lint 作业 + 重作业 `needs` | 失败 run 时长 828s → ~60s；成功路径 +~15s 串行 | 低 | 1~2 commit |
| **D 缩短 `test-gui-unit`（467s）** | 拆分／并行／减覆盖率开销 | run 总时长 ≈828 → ~610s（−26%），排队上限同步下降 | 中：GUI 测试拆分曾与 #34 抖动同源，须谨慎 | 2~4 commit |
| **E `docker`/`exe` 与测试并行** | 只让**发布**依赖测试，构建与测试重叠 | run 总时长 ≈828 → ~500s（−40%） | 中：构建与版本号时序需重设计 | 2~4 commit |
| **F 接受 + 流程约定** | 推送前确认上一个 run 已结束 | 等待消失，但每批节奏被 run 时长（≈14 min）限制 | 低 | 0 |

**④ 推荐路线**：R12-2 先落 **G**（1~2 commit，收益最大/风险最低）并观察 3 次 run 的排队指标；R12-3 视情况落 **C**（与 P2 的 T-28 同批）；**D/E** 作为“缩短关键路径”专项，在 G 的效果数据出来后再评估（避免同时动队列与关键路径导致归因不清）。

**⑤ 复现命令**（探针不入库，存仓库外）
```
python <probe>/r12_1_queue.py      # 全量 run 的三源归因（自串行/时长/提交类型）
python <probe>/r12_1_critical.py   # 最近 10 个 run 的逐作业时长与关键路径
```


### 7.16 R12-2：方案 G + T-28 落地（已执行，2026-09-27，第十二轮）

**① 改动清单（仅 CI 配置，检查逻辑零变更）**

| 文件 | 位置 | 改动 |
|---|---|---|
| `.github/workflows/ci.yml` | 顶层 `concurrency` | `group: ci-cd` → **`ci-cd-${{ github.ref }}`**；`cancel-in-progress: false` → **`true`**（方案 G） |
| `.github/workflows/ci.yml` | `test-backend` → `Run backend tests` | pytest 命令加 **`-rs`**（T-28：跳过明细进日志） |

**② 生效机制与代价**

| 维度 | 旧（全局单组 + 不取消） | 新（按 ref 单组 + 取消） |
|---|---|---|
| 同 ref 连续推送 | 后一个 run **排队等前一个跑完**（实测被挡中位 ≈300s、最长 1340s） | 新 run **取消**该组内旧 run 并立即开跑（排队≈0） |
| 分支/PR 推送 | 与 main **共用** `ci-cd` 槽位 → 互相阻塞 | 各自 `ci-cd-refs/heads/<branch>` / `ci-cd-refs/pull/<n>/merge`，互不阻塞 |
| 代价 | 无 | **被取消的旧 run 无完整结论**（其提交内容会被下一次 run 的检出覆盖验证）；本仓库 bump 提交由 `GITHUB_TOKEN` 推送、不触发 workflow（T-31），故无额外冲突面 |

**③ 观察口径（判定是否生效）**：指标＝**作业启动延迟** ＝ `job.started_at − run.run_started_at`。

| 基线（R12-1 实测，78 run） | 目标 |
|---|---|
| 未被挡样本 **+3s**；被挡样本中位 **≈300s**（26/78 = 33% 的 run 被挡） | 连续 3 次 run 的中位作业启动延迟 **≤10s** |

**④ 首个数据点**：R12-2 推送后按上述口径实测，数值记入 R12-3 批次（同批记录 3 次观察）。**方法**：
```
python -c "…读取 runs?per_page=N，对目标 run 取 jobs，算 job.started_at − run.run_started_at 的中位…"
# 或复用探针：<probe>/r12_1_queue.py（三源归因） / r12_1_critical.py（关键路径）
```



**⑤ 首个数据点与同窗对照（R12-2 推送后实测，2026-09-27）**

| run | 并发组 | sha | 作业启动延迟（`job.started_at − run.run_started_at`） |
|---|---|---|---|
| **R12-2** `36309693229` | **`ci-cd-refs/heads/main`（新）** | `46a4a67f` | **中位 +2.0s**（2.0／2.0／2.0／2.0／3.0／3.0／4.0，n=7） |
| R12-1 `36309485009`（同窗对照） | `ci-cd`（旧，与 R11-5 的 run 串行） | `5e34f862` | **中位 +198s**（197~257） |

基线（R12-1 的 78 run 统计）：未被挡 +3s、被挡中位 ≈300s、被挡比例 33%。→ **G 生效**（+2.0s ≤ 目标 10s）；对照组 +198s 即旧模型行为。
**附带事实**：R12-1 的 run 因组名不同**未被取消**，其验证完整保留。

**⑥ T-28 的 CI 实证（同一 run）**：`test-backend` 日志含 **44 条** `SKIPPED [n] path:line: reason`（此前只有汇总行），首 12 条均为 `tests/test_e2e_adapters.py` 的「CI 环境跳过网络依赖测试」（类级 `@unittest.skipIf(_CI)`），与 R12-1 归因吻合；汇总 `4007 passed, 44 skipped, 22 warnings, 4 subtests passed in 130.38s`。
**R12-2b 补充**：`-rs` 由 1 处扩到**全部 5 处** pytest 调用（复核脚本 5/5 ✓）。

### 7.17 R12-3：方案 C（lint-fast 门控）落地与受控失败实验（已执行，2026-09-27，第十二轮）

**① 改动（`.github/workflows/ci.yml`，仅作业结构与 `needs`）**

| 项 | 内容 |
|---|---|
| 新增作业 | **`lint-fast`**：checkout（`fetch-depth: 1`）→ `setup-python`（3.12 + pip cache）→ `pip install ruff mypy` → `python scripts/check_g_038_legacy_errors.py` |
| 下游门控（9 个） | `test-backend`、`test-gui-coverage`（`needs: [lint-fast, test-backend]`）、`e2e-coverage`（原 `needs: []`）、`security-scan`、`test-frontend`、`test-e2e`、`frontend-e2e`（`needs: [lint-fast, test-frontend]`）、`test-gui-unit`、`repo-compliance` |
| 传递性门控 | `version`（原 `needs` 8 作业）→ `docker`／`exe`（`needs: version`）：`lint-fast` 失败 → 上游 skipped → 三者 skipped |
| 未改动 | G-038 脚本与 ruff/mypy 范围、`repo-compliance` 内的同名步骤（**保留**作纵深防御）、任何测试逻辑 |

**② 预期与判定口径（受控失败）**

| 判据 | 目标 | 基线（失败 run） |
|---|---|---|
| `lint-fast` 失败耗时 | ≈20~40s | — |
| 下游作业状态 | **skipped**（未触发） | 全部真实执行 |
| 失败 run 总时长 | **≤60s** | **828s**（中位） |

**③ 受控失败实验设计（无需 `--no-verify`）**

实测确认：`ruff check pilotstd/` 与 `check_g_038_legacy_errors.py` **都会检查 `.pyi`**（长行判 E501），而本地 pre-commit 的 L1 触发式 `^scripts/|`+`\\.py$` **漏 `.pyi`** → 因此可在**一次性分支**上提交 `pilotstd/_r12_3_probe.pyi`（142 字符注释行）而**不绕过任何钩子**：
  · 分支组名 `ci-cd-refs/heads/probe/r12-3-lint-gate`（按 ref 分组后**与 main 完全隔离**，不干扰主线）；
  · 观察点：① `lint-fast` 结论与耗时；② 其余 12 个作业是否全部 skipped；③ run 总时长；
  · 实验后立即删除远端与本地分支，主分支不受影响（该缺口另登记 **T-32**）。

**④ 其余观察数据（R12-3 主分支推送后实测）**：第 3 个 run 的作业启动延迟（G 的第一阶段收口判据）与实验结果一并记入 R12-3b 批次。

### 7.18 R12-3b：方案 C 受控失败实证、G 数据点 3 与 #34 哨兵触发（已执行，2026-09-27，第十二轮）

**① 受控失败实验（目标：验证「快闸快速失败 + 下游不启动 + 修复后全绿」）**

| 步 | 动作 | 结果 |
|---|---|---|
| 1 | 一次性分支 `probe/r12-3-lint-gate` 注入 `pilotstd/_r12_3_probe.pyi`（142 字符行）并提交 | 提交**未绕过钩子**（L1 触发式漏 `.pyi`，见 T-32）；分支推送**未产生 run**——因 `.github/workflows/ci.yml` 的 `on.push.branches: [main]` 只对 main 生效 |
| 2 | 改为 **PR #8**（`pull_request` 事件）触发 | run `36310949966`，head `4bc58444` |
| 3 | 观察 | **run 结论 failure，总时长 19.0s**（基线 828s，**−97.7%**）；`lint-fast` **failure，时长 16.0s**；日志 `❌ G-038 … Ruff 检查失败：E501 Line too long (142 > 120)`；**下游 12 个作业全部 skipped**（test-backend／test-gui-unit／test-frontend／test-e2e／frontend-e2e／repo-compliance／e2e-coverage／security-scan／test-gui-coverage／version／docker／exe） |
| 4 | 清理 | PR #8 关闭、远端与本地分支删除、`git status` clean、**main 未受影响**；修复路径＝删除探针文件（PR 关闭即等价），主分支无需“修复提交” |

**判定**：① 快闸快速失败 ✅（16s）；② 下游未被触发 ✅（12/12 skipped）；③ 失败 run 总时长 19.0s ≤ 60s 目标 ✅（−97.7%）。**唯一未满足**：指令中的“修复后重推全绿”在 main 侧被 **#34 复发**（见 ④）打断——与本方案无关。

**② G 第 3 个数据点（R12-3 的 run `36310444541`，2026-09-27T09:46:37Z）**

| 作业 | 启动（相对 run） | 时长 | 结论 |
|---|---|---|---|
| `lint-fast (G-038)` | **+16.0s** | 14.0s | success |
| 下游 8 个（test-backend／e2e-coverage／repo-compliance／test-e2e／test-frontend／test-gui-unit／security-scan／frontend-e2e） | +32.0~89.0s | — | 6 success／**test-gui-unit failure**／test-gui-coverage +216.0s |
| `version`／`docker`／`exe` | +442.0s | — | skipped |

**分析（16.0s 的构成与阈值语义）**：
  · 该 run 创建时**同 ref 的 R12-2b 正在飞**（09:39:52 起）→ 被本次推送**取消**（`7c478c6f` 结论＝cancelled，实证取消语义）；同时 runner 需为新年 job 分配机器 → **首个作业启动 = 分配延迟 + 门控前开销**，不再是纯“并发组排队”。
  · 门控落地后，**下游作业的启动时刻由 `lint-fast` 完成时间决定**（+32.0s），「所有作业同时起跑」的旧指标语义已改变。
  · 与旧模型对比：旧组同窗对照 R12-1 `36309485009` = **+198s**（被挡），R12-1 的 78 run 统计被挡中位 **≈300s** → 队列效应确已消除。
  **结论建议**：G 按“**队列效应消除**”收口（指标改写为“首个作业启动延迟 ≤20s 且旧组同窗对照 ≥100s”），或再取一次空闲窗口的测量；**采纳与否待用户裁定**。

**③ 方案 C 的绿灯代价（实测）**：`lint-fast` 启动 +16.0s、时长 14.0s → 下游首个作业 **+32.0s**；即绿灯路径新增 ≈ **28~32s**（原估 +20s）。

**④ ⚠️ #34 哨兵触发（T-26）**

| 项 | 内容 |
|---|---|
| run / job | `36310444541`（sha `85fa65f0`）／`test-gui-unit` job `108595281670` |
| 失败步骤 | `Run GUI unit tests`（第 5 步 failure；`Tests passed — checking coverage thresholds` 被 skipped） |
| 日志指纹 | `tests/gui/test_event_bus_integration.py::TestThreadSafety::test_concurrent_subscribe FAILED` → `Windows fatal exception: access violation` → exit 1（09:50:54Z） |
| 与历史对比 | 与 #34 行记录的两次**逐行同构**（同一测试、同一异常）；R1（teardown 等待 5s + `waitForDone` + 到期不 reset）**仍在位却未拦住** |
| 触发规则 | T-26 预先约定「再复发 ≥1 次 → 当轮必须做 R2 + R4」→ **R2/R4 为第十二轮强制项** |
| R2 计划 | `reset()` 静止协议：`_resetting` 期间 `publish()` 直接返回；单例销毁改 `deleteLater()` 或延迟到 in-flight publish 结束；`pilotstd/ui/core/event_bus.py:57-88` + `tests/gui/test_event_bus_integration.py` 覆盖 |
| R4 计划 | CI/本地环境对齐：装 Python 3.12 + Qt 6.11.2，循环跑 `tests/gui/` 统计频率，把“堆已破坏”的推断升为实证 |
| 影响 | 该 run 结论 failure（连带 `version`／`docker`／`exe` skipped）；与本批 CI 改动**无关**（快闸与其余 9 个下游作业均 success） |

**⑤ 复现命令**（探针不入库）
```
python <probe>/r12_3_full.py      # 单个 run 的完整时序（首个作业启动/快闸时长/下游启动/总时长）
python <probe>/r12_3_probe_pr.py  # 受控失败实验（建 PR → 观察 → 关闭 PR + 删分支）
python <probe>/r12_3_gui_diag.py  # test-gui-unit 失败诊断（步骤 + 日志指纹）
```

### 7.19 R12-4：R2 静止协议、R4 环境对齐实证与 T-32 关闭（第十二轮）

**① T-32（L1 触发式漏 `.pyi`）——双向受控验证**

| 方向 | 动作 | 结果 |
|---|---|---|
| 修复前 | 暂存/提交 `pilotstd/_r12_3_probe.pyi`（142 字符行） | L1 未触发 → 提交成功（R12-3b 借此做到“不绕过钩子”的受控失败实验） |
| 修复后 | 暂存 `pilotstd/_t32_probe.pyi`（142 字符行）后跑 `--fast --guards --local` | L1 **触发**：`📋 暂存 .py/.pyi/.pyw/scripts 变更：pilotstd/_t32_probe.pyi` → `E501 Line too long (142 > 120)` → `❌ [FAIL] L1 ruff check`，**EXIT=1** |

改动：`scripts/check_all.sh` 触发式 `grep -E '^scripts/|\.py$'` → **`grep -E '^scripts/|\.py[wi]?$'`**（+ 文案/注释同步）。**T-32 ✅ CLOSED。**

**② R4：CI 同口径环境下的循环复现探针**

新增独立工作流 `.github/workflows/gui-race-probe.yml`（**仅 `workflow_dispatch`**）：

| 项 | 内容 |
|---|---|
| 环境 | `windows-latest` + **Python 3.12** + `desktop/requirements-win.txt` + `requirements-dev.txt` + **`PyQt6==6.11.2` / `PyQt6-Qt6==6.11.2`**（与 `test-gui-unit` 同口径）；启动时打印 python/Qt/PyQt 指纹 |
| 循环 | `python -m pytest tests/gui/test_event_bus_integration.py -q --timeout=120 --timeout_method=thread`，迭代次数由输入 `loops` 决定（默认 30） |
| 产物 | 每次迭代打印 `=== iteration i / N ===` 与退出码；结尾 `=== RESULT: loops=N failures=M ===`，M>0 即 `exit 1` |
| 为什么独立文件 | `workflow_dispatch` 会执行该文件内**全部**作业——放进 `ci.yml` 会让每次探针连带跑完整 14 作业流水线，既慢又污染归因 |
| 触发方式 | `gh workflow run gui-race-probe.yml -f loops=50` 或 Actions UI |

**③ R2：静止协议（代码随 R12-4b 提交）**——`pilotstd/ui/core/event_bus.py`：

| 步 | 机制 | 目的 |
|---|---|---|
| ① 关门 | 类级 `_resetting=True` + 实例级 `_accepting=False` + 清空订阅者 | `publish()` 在 reset 窗口/退役实例上**无副作用直接返回**（不入队、不抛异常）；`subscribe`/`unsubscribe` 同样门控 |
| ② 有界排空 | 实例属本线程 → `processEvents()` 跑完已排队 deliver；**不再用无界 `BlockingQueuedConnection`** | 实测（R12-4 冒烟用例）无界阻塞在“实例线程亲和性无事件循环”时会永久挂住 teardown |
| ③ 延迟销毁 | `deleteLater()` | 不在此刻同步析构 QObject，切断 use-after-free 窗口 |
| ④ 复位 | 清 `_resetting` | 保证后续 publish 正常 |
| 附加 | `publish()` 的**入队动作移入临界区** | reset() 拿到锁即意味没有 in-flight publish 正在入队（“确保 in-flight publish 结束”） |
| 附带 | `deliver()` 对退役实例直接丢弃 | 门闸兜底，安全性不依赖排空 |

新增受控用例 6 例（`TestResetQuiescenceProtocol`）：门闸复位／退役实例 publish no-op／reset 窗口内 publish no-op／窗口内 subscribe no-op／reset 后得到全新实例／**多线程 publish 与 reset 并发不抛异常**（该用例正是暴露“无界阻塞会挂住”的那一例）。
**本地实测**：`tests/gui/test_event_bus_integration.py` → **19 passed in 101s**（含原 13 例 + 新 6 例，其中 CI 曾失败的 `TestThreadSafety::test_concurrent_subscribe` 通过）。

**④ 取证数据**：R4 探针的“修复前／修复后”两次派发结果与本地 20 轮循环结果记入 R12-4b 批次。



**⑤ R2 验证数据（R12-4c，2026-09-27）**

| 项 | 方法 | 结果 |
|---|---|---|
| 本地循环 | `pytest tests/gui/test_event_bus_integration.py -q --timeout=120` × **20 轮** | 每轮 **19 passed / exit=0**，单轮 101.6~103.9s，累计 ≈34 分钟 → **0 access violation** |
| CI 回归 | R12-4b 的 run `36313155232`（sha `0404cea4`） | **13/13 success**，含 `test-gui-unit` success |
| R4 探针（修复前） | `gui-race-probe` @ `a7c7e265`，loops=30 | in_progress（结果记 R12-4d） |
| R4 探针（修复后） | `gui-race-probe` @ `0404cea4`，loops=50 | pending（排队于前一次之后） |

**修复前的直接证据**（R4 判据的“要么”分支）＝ run `36310444541` 的 `test-gui-unit` 日志：`test_concurrent_subscribe FAILED` → `Windows fatal exception: access violation` → exit 1。
**复现命令**：`python <probe>/r12_4_dispatch.py 30 before` / `50 after`（脚本不入库）；本地循环命令见上表。

**⑥ R4 探针结果与 #34 终局（R12-4d，2026-09-27）**

| 探针 | sha | loops | 结果 | 证据 |
|---|---|---|---|---|
| 修复后（含 R2） | `0404cea4` | **50** | **failures=2**（第 2、43 次），退出码 **-1073741819 = 0xC0000005** | run `36313158979`（10:38→12:39，≈121 min，单轮 ≈109s）；两次均为 `..................F` |
| 修复前 | `a7c7e265` | 30（未跑满） | 人工取消（同并发组串行、耗时过长；取消前无失败记录） | 修复前直接证据改用 run `36310444541`（R12-3：`test_concurrent_subscribe FAILED` + `Windows fatal exception: access violation` + faulthandler） |

**环境指纹（日志实测）**：`python 3.12.10`、**`Qt 6.11.0` / `PyQt 6.11.0`** —— 探针里 `pip install PyQt6==6.11.2 PyQt6-Qt6==6.11.2` **未生效**（与登记中的 6.11.2 不符），**R12-5 必须校正并复测**。

**失败落点分析**：`..................F` ＝ 该文件 19 个用例中前 18 个通过、第 **19** 个失败；文件顺序第 19 项正是本轮新增的 `TestResetQuiescenceProtocol::test_publisher_thread_during_reset_does_not_raise`（3 守护线程 `EventBus.instance()` + publish ↔ 主线程 5 次 `reset()`）。即：**R2 的静止协议挡住了“经退役实例发布”，但挡不住“工作线程首建单例 + 主线程并发 reset”这条路径上的原生层访问违例。**

**裁定**：❌ R2 未完全覆盖根因；**#34 维持 P6 强制项**，立即启动 **R12-5**。

**R12-5 计划（候选 → 待用户批准）**：
| # | 方向 | 预期 |
|---|---|---|
| 1 | `reset()` **不再销毁实例**：只清空订阅者与状态、保持单例存活（消除“析构 × 跨线程引用”窗口） | 直接命中根因路径；需同步调整 `test_reset_creates_new_instance`（改为断言“状态被清空且实例复用”） |
| 2 | `EventBus.instance()` **禁止非主线程首建** QObject：首建绑定主线程（或返回线程安全代理） | 消除“工作线程亲和性 + 主线程 reset”的非法跨线程生命周期 |
| 3 | 校正 R4 环境 pin（Qt 6.11.2 vs 实测 6.11.0）并复测 | 让“同口径环境”名副其实 |
| 4 | 必要时引入 ASan／Qt 线程模型专项分析 | 把推断升级为实证 |

**回归门**：`gh workflow run gui-race-probe.yml -f loops=50` → 必须 `failures=0`（当前 4%，2/50）。

**复现命令**：`python <probe>/r12_4_after_observer.py`（等待并抓取）+ `python <probe>/r12_4_parse.py`（定位失败迭代上下文）；本地等价：`for i in $(seq 50); do python -m pytest tests/gui/test_event_bus_integration.py -q --timeout=120; done`。


**⑦ R12-5：环境 pin 校正 + 保活单例 + 回归门（2026-09-27）**

| 项 | 内容 | 结果 |
|---|---|---|
| ① 环境 pin | `gui-race-probe.yml`：pwsh 严格错误处理 + 钉 `PyQt6-Qt6==6.11.2` + 指纹断言（`qVersion()` 必须 6.11.2） | 快检 run `36428298369`：`QT_VERSION_STR(build)=6.11.0`、**`qVersion(runtime)=6.11.2`**、`PYQT_VERSION_STR=6.11.0`；断言通过 |
| ① 连带发现 | 崩溃率随 Qt 运行库变化 | **4%（2/50 @6.11.0）→ ≈33%（1/3 @6.11.2）**，落点＝历史用例 `test_concurrent_subscribe` |
| ② 保活单例 | `reset()` 不再销毁 QObject；清状态 + 世代号 + 有界排空；删除 `_accepting`/`_drain_barrier`；契约改为「同一实例 + 状态清零」 | 本地崩溃点文件 **20/20 轮全绿**（Qt 6.11.2，每轮 19 passed）；全量 GUI 套件 **1022 passed / 2 skipped / EXIT=0** |
| ③ 回归门 | `gui-race-probe` run `36431925613`（sha `fa179320`）loops=50 | **failures=2**（结论 `failure`）— 未通过 ❌ |

**复现命令**：`gh workflow run gui-race-probe.yml -f loops=50`；本地等价：`for i in $(seq 50); do python -m pytest tests/gui/test_event_bus_integration.py -q --timeout=120; done`。

**失败迭代明细**：

- `2026-09-28T13:55:22.7637379Z [36;1m    Write-Output "!!! iteration $i FAILED (exit $LASTEXITCODE)"[0m`
- `2026-09-28T14:25:37.6420895Z ..................!!! iteration 17 FAILED (exit -1073741819)`
- `2026-09-28T15:16:49.9004964Z ..................F                                                      [100%]!!! iteration 47 FAILED (exit -1073741819)`


### 7.20 R12-6：本地 CI 同口径复现（Python 3.12.10 + PyQt6 6.11.2）

**目的（用户裁定选项 2）**：把 #34 的复现从 CI（单轮 ≈110s + 排队 + 网络抖动）搬到本地，取得可稳定触发的**本地复现器**，为后续定位根因提速。
**约束遵守**：未修改 EventBus 代码或测试逻辑；未尝试方向 2／4；无论结果如何都不宣称“CI 误报”。

**① 环境搭建（全部脚本/命令置于仓库外 `C:\Temp\pilotstd-probe\`，仓库零改动）**

| 步 | 命令 | 结果 |
|---|---|---|
| 1 | `Invoke-WebRequest https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe` | 26,964,224 bytes |
| 2 | `python-3.12.10-amd64.exe /quiet InstallAllUsers=0 TargetDir=C:\Temp\pilotstd-probe\py31210 PrependPath=0 Include_launcher=0` | exit=0；`py31210\python.exe --version` → **Python 3.12.10**（per-user 安装，不改 PATH、不碰系统 Python 3.14） |
| 3 | `py31210\python.exe -m venv C:\Temp\pilotstd-probe\venv312` | 隔离 venv（`pip 25.0.1`） |
| 4 | `venv312\Scripts\pip install -r desktop/requirements-win.txt` | PyQt6 **6.11.0**、PyQt6-Qt6 **6.11.2**、PyQt6-sip **13.12.0** |
| 5 | `venv312\Scripts\pip install -r requirements-dev.txt` | pytest **9.1.1**、pytest-qt **4.5.0**、pytest-timeout **2.4.0**、pytest-xdist **3.8.0** |
| 6 | 指纹校验 | `python 3.12.10` / `QT_VERSION_STR(build) 6.11.0` / **`qVersion(runtime) 6.11.2`** / `PYQT_VERSION_STR 6.11.0` |

> **差异表（P-105）**：提示词给出的 `pip install --force-reinstall PyQt6==6.11.2 PyQt6-Qt6==6.11.2` 中 **`PyQt6==6.11.2` 在 PyPI 不存在**（实测 `pip index versions PyQt6` → 最新即 6.11.0）；CI 的真实口径为 `PyQt6==6.11.0`（`desktop/requirements-win.txt`）+ `PyQt6-Qt6==6.11.2`（Qt 运行库真身，`qVersion()`）。
> 本地按 **CI 实际口径**安装并以 `qVersion()==6.11.2` 校验通过；Python 取提示词要求的精确版本 **3.12.10**。

**② 50 轮结果**（`PYTHONFAULTHANDLER=1`；逐轮独立进程 + 逐轮独立日志 `r12_6_iter_NN.log`）

| 项 | 值 |
|---|---|
| 轮数 / 失败轮数 | **50 / 3** |
| 单轮耗时 | min=48.5s / max=114.7s / 均=100.5s |
| 失败轮明细 | 见下表 |
| 结论 | ✅ **本地复现成功**——按用户裁定：**不自行修复**，记录完整崩溃上下文后上报，由用户裁定 R12-7 修复方向。 |

| 失败轮 | 退出码 | 耗时 | 日志 |
|---|---|---|---|
| 第 9 次 | `0xC0000005`（3221225477） | 49.0s | `r12_6_iter_09.log` |
| 第 19 次 | `0xC0000005`（3221225477） | 49.6s | `r12_6_iter_19.log` |
| 第 33 次 | `0xC0000005`（3221225477） | 48.5s | `r12_6_iter_33.log` |

**iter 9 现场（退出码 0xC0000005）**

```
........FWindows fatal exception: access violation
Current thread 0x00002180 (most recent call first):
File "D:\PilotStd\pilotstd\ui\core\event_bus.py", line 86 in reset
File "D:\PilotStd\tests\gui\test_event_bus_integration.py", line 66 in _reset_event_bus
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\fixtures.py", line 1014 in _teardown_yield_fixture
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\fixtures.py", line 1156 in finish
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 568 in teardown_exact
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 199 in pytest_runtest_teardown
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 250 in <lambda>
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 361 in from_call
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 249 in call_and_report
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 144 in runtestprotocol
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 118 in pytest_runtest_protocol
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 408 in pytest_runtestloop
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 384 in _main
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 330 in wrap_session
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 377 in pytest_cmdline_main
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
```

**iter 19 现场（退出码 0xC0000005）**

```
........FWindows fatal exception: access violation
Current thread 0x00003028 (most recent call first):
File "D:\PilotStd\pilotstd\ui\core\event_bus.py", line 86 in reset
File "D:\PilotStd\tests\gui\test_event_bus_integration.py", line 66 in _reset_event_bus
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\fixtures.py", line 1014 in _teardown_yield_fixture
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\fixtures.py", line 1156 in finish
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 568 in teardown_exact
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 199 in pytest_runtest_teardown
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 250 in <lambda>
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 361 in from_call
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 249 in call_and_report
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 144 in runtestprotocol
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 118 in pytest_runtest_protocol
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 408 in pytest_runtestloop
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 384 in _main
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 330 in wrap_session
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 377 in pytest_cmdline_main
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
```

**iter 33 现场（退出码 0xC0000005）**

```
........FWindows fatal exception: access violation
Current thread 0x00000f14 (most recent call first):
File "D:\PilotStd\pilotstd\ui\core\event_bus.py", line 86 in reset
File "D:\PilotStd\tests\gui\test_event_bus_integration.py", line 66 in _reset_event_bus
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\fixtures.py", line 1014 in _teardown_yield_fixture
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\fixtures.py", line 1156 in finish
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 568 in teardown_exact
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 199 in pytest_runtest_teardown
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 250 in <lambda>
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 361 in from_call
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 249 in call_and_report
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 144 in runtestprotocol
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\runner.py", line 118 in pytest_runtest_protocol
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 408 in pytest_runtestloop
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_manager.py", line 120 in _hookexec
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_hooks.py", line 512 in __call__
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 384 in _main
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 330 in wrap_session
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\_pytest\main.py", line 377 in pytest_cmdline_main
File "C:\Temp\pilotstd-probe\venv312\Lib\site-packages\pluggy\_callers.py", line 121 in _multicall
```

**③ 本地 vs CI 环境差异量化**

| 维度 | 本地（本次复现环境） | CI（`gui-race-probe` / `test-gui-unit`） |
|---|---|---|
| Python | **3.12.10**（官方安装包，精确同版本） | 3.12.10（`setup-python`） |
| PyQt6 / Qt 运行库 / sip | 6.11.0 / **6.11.2** / 13.12.0 | 6.11.0 / **6.11.2** / 13.12.0（本次已 pin 并断言） |
| pytest 系 | pytest 9.1.1 / pytest-qt 4.5.0 / timeout 2.4.0 / xdist 3.8.0 | 同（requirements-dev.txt 解析） |
| OS | **Windows 11 专业版 Build 26300**（Version 10.0.26300） | **Windows Server（windows-latest 镜像）** |
| CPU / 内存 | 8 逻辑核 / 14.9 GB | GitHub 标准 runner（通常 4 核 / 16 GB） |
| VC++ 运行库 | x64 **14.50.35719.00**（`vcruntime140.dll` / `msvcp140.dll` 同版本） | runner 镜像自带（版本随镜像滚动） |
| Driver Verifier | **未启用**（`verifier` 查询无已校验驱动） | 未启用 |
| 显示会话 | 交互式桌面会话（真实窗口站） | runner 会话（无交互桌面） |
| 其它 | 仓库工作区直接运行（`cwd=D:\PilotStd`） | `actions/checkout` + `pip install -e .` |

**④ 裁定节点**：✅ **本地复现成功**——按用户裁定：**不自行修复**，记录完整崩溃上下文后上报，由用户裁定 R12-7 修复方向。

**复现命令（本地）**：
```powershell
$venv = "C:\Temp\pilotstd-probe\venv312\Scripts\python.exe"
$env:PILOTSTD_GUI_TEST='1'; $env:PYTHONFAULTHANDLER='1'
for ($i=1; $i -le 50; $i++) { & $venv -m pytest tests/gui/test_event_bus_integration.py -q --timeout=120 --timeout_method=thread -p no:cacheprovider }
```


### 7.21 R12-7：最小化复现 + 根因二分定位（QMutex/QMutexLocker × 线程 churn）

**用户裁定路径**：方向 3（最小化复现）+ 方向 2（PageHeap）组合；方向 1（Python 插桩）挂后、方向 4（ASan）否决。
**约束遵守**：未修改 `pilotstd/ui/core/event_bus.py` 任何逻辑（含未加日志）；未在 pytest 内死磕；未引入 ASan。

#### 一、阶段一：最小化独立复现（交付物 ① ②）

新增诊断脚本 **`scripts/probe_race_minimal.py`**（纯标准库 + PyQt6，脱离 pytest；复刻
`TestThreadSafety::test_concurrent_subscribe` + autouse fixture teardown 的等价流程：每轮 4 线程 × 100 次
`subscribe` → 等静止 → `processEvents()` → `EventBus.reset()`）。

| 项 | 结果 |
|---|---|
| 单轮耗时（正常轮） | **0.92 ~ 1.4s**（远低于 5s 要求）；崩溃轮因 faulthandler 转储 + WER 收尾为 4.7~6.5s |
| 100 次运行统计 | **crashes=47 / 100 = 47.0%**（other=0），总耗时 5.1 min |
| 退出码 | 全部为 **3221225477 = 0xC0000005** |
| 崩溃落点 | 绝大多数为 `event_bus.py:127`（`subscribe()` 的 `with QMutexLocker(self._lock):`），少数为 `event_bus.py:86`（`reset()` 的同类行） |

> 结论：**复现率 47% ≫ 1% 要求**，且单轮 ≈1s —— #34 从此可在本地秒级迭代，不再依赖 CI（此前单轮 ≈100s、6%）。

#### 二、阶段二：PageHeap 受阻 + 替代取证（交付物 ③）

**受阻事实（如实报告）**：`gflags.exe /p /enable` 与 Application Verifier 均需写
`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options`，
而本机当前会话 **无管理员权限**（`elevated=False`，实测 HKLM 写入 `访问被拒绝`）；
winget 安装的 WinDbg 为 MSIX 包，仅提供 `WinDbgX.exe`（GUI），**不含 `cdb.exe`**，且弹出 GUI 会干扰用户桌面 → 未采用。

**替代方案（已生效）**：`HKCU` 配置 WER LocalDumps（无需管理员）→ Windows 自动为每次崩溃落盘 4.2 MB 转储
（`%LOCALAPPDATA%\CrashDumps\python.exe.<pid>.dmp`，已捕获 10+ 个）→ 用 `minidump` + `pefile`
**离线解析**（读异常记录、线程上下文、模块表，并以各模块导出表把 RVA 解析成函数名）。

**关键取证结果**：

| 项 | 值 |
|---|---|
| ExceptionCode | `0xC0000005 (EXCEPTION_ACCESS_VIOLATION)` |
| ExceptionAddress | `0x00007FFF4EF54484` |
| 故障指令归属 | **`python312.dll+0x54484 → PyWeakref_NewRef+0x114`** |
| 访问参数 | `NumberParameters=2`，`params=[0x0, 0x8]` → **READ @ 0x8** |
| 含义 | CPython 在 `PyWeakref_NewRef` 内读对象的 `ob_type`（偏移 8）时指针为 **NULL** ⇒ 上游有人调用了 `PyWeakref_NewRef(NULL, ...)`（sip/PyQt 的弱引用记账路径） |
| 线程 | 崩溃线程为工作线程（`threading.py:run → bootstrap`），主线程当时仍在 `join()` |

#### 三、根因二分（决定性实验，含纯 PyQt6 最小复现）

为把「业务逻辑」与「PyQt6 自身」分离，新增 **`scripts/probe_mutexlocker_race.py`**（**不含本项目任何代码**，
仅 `QObject` + 一把锁 + 字典追加），按 `--lock qt|python` 切换锁实现：

| 变体 | 锁 | QApplication/QObject | 线程模式 | 崩溃/样本 |
|---|---|---|---|---|
| A | `QMutex`+`QMutexLocker` | 无 | 4 个长寿命线程 × 20000 次加锁 | **0/6** |
| B | `QMutex`+`QMutexLocker` | 有 + 字典追加 | 长寿命线程 | **0/6** |
| **C** | `QMutex`+`QMutexLocker` | 有 | **每轮新建 4 线程 × 200 轮（≈800 次线程创建）** | **6/14（≈43%）** |
| **D** | **`threading.Lock`** | 有 | **同 C** | **0/14** |

（C 组样本含 `scripts/probe_mutexlocker_race.py` 复跑 1/6；D 组含复跑 0/6；C vs D 的 Fisher 精确检验 p≈0.007。）

**结论（根因）**：崩溃与 `EventBus` 业务逻辑**无关**；触发条件为
**PyQt6 `QMutex`/`QMutexLocker`（走 sip）在多线程反复创建/销毁的 churn 下出现的弱引用记账竞态**
（`PyWeakref_NewRef(NULL)` → READ @ 0x8）；**换成 Python 原生 `threading.Lock` 后完全消失（0/14）**，
且更快（变体 C 与 D 单轮同为 200 轮 × 4 线程 × 100 次，D 稳定 0.20~0.22s 完成）。

#### 四、R12-8 候选方向（待用户裁定，本批未实施）

| # | 方向 | 依据 |
|---|---|---|
| 1 | 把 `EventBus` 内部锁由 `QMutex`+`QMutexLocker` 换成 `threading.Lock` | 变体 D 0/14；且 `publish/subscribe/deliver/reset` 全是纯 Python 临界区，无需 Qt 锁 |
| 2 | 回归门：`scripts/probe_mutexlocker_race.py --lock qt`（应崩）vs `--lock python`（应 0 崩），并复用 `scripts/probe_race_minimal.py` 100 轮 | 本批已建立基线（47% / 43% / 0%） |
| 3 | 若需进一步确认 sip 记账细节 | 需管理员权限装 `gflags.exe`+`cdb.exe`（PageHeap/完整栈），本批因权限受阻 |

**复现命令**：
```powershell
$py = "C:\Temp\pilotstd-probe\venv312\Scripts\python.exe"   # Python 3.12.10 + Qt 6.11.2
& $py scripts/probe_race_minimal.py              # 200 轮；退出码 0xC0000005 即复现
& $py scripts/probe_mutexlocker_race.py           # 变体 C（Qt 锁）
& $py scripts/probe_mutexlocker_race.py --lock python   # 变体 D（对照，应恒为 0）
```


### 7.22 R12-8：#34 根因定论与修复（内部锁换 `threading.Lock`）+ 三重回归门

**根因定论（R12-7 取证 + R12-8 验证）**：崩溃与 `EventBus` 业务逻辑无关，触发条件为
**PyQt6 `QMutex`/`QMutexLocker`（sip）在“线程反复创建/销毁”下出现的弱引用记账竞态**——
原生证据：`ExceptionCode=0xC0000005`，`ExceptionAddress=python312.dll+0x54484 → PyWeakref_NewRef+0x114`，
访问参数 `READ @ 0x8`（`PyWeakref_NewRef(NULL, …)` 读空对象 `ob_type`）；
控制变量：同等负载下 `QMutexLocker` **6/14 崩**、仅换 `threading.Lock` **0/14 崩**（Fisher p≈0.007）。

**修复方案（仅锁相关代码）**：

| 位置 | 修改前 | 修改后 |
|---|---|---|
| `event_bus.py` 类级锁 | `_lock = QMutex()` | **`_lock = threading.Lock()`** |
| 3 处（`instance`/`reset`/内部） | `with QMutexLocker(cls._lock):` | `with cls._lock:` |
| 4 处（`subscribe`/`unsubscribe`/`publish`/`deliver`） | `with QMutexLocker(self._lock):` | `with self._lock:` |
| 导入 | `QMutex`、`QMutexLocker`（PyQt6.QtCore） | 移除；新增 `import threading`（标准库，无新依赖） |

未改动：业务逻辑、订阅者管理、世代号机制、`reset()` 协议（R12-4 R2 / R12-5 保活单例语义全部保留）；**未保留 QMutex 备选路径**。

**三重回归门（全部通过）**：

| 门 | 命令 | 期望 | 实测 |
|---|---|---|---|
| ① 探针有效性 | `probe_mutexlocker_race.py --lock qt` × 100 | ≥1 崩 | **37/100 崩（37.0%）**，单轮均 2.55s ✅ |
| ② 对照 | `probe_mutexlocker_race.py --lock python` × 100 | 0 崩 | **0/100 崩**，单轮均 0.43s ✅ |
| ③ 端到端（CI） | `gh workflow run gui-race-probe.yml -f loops=50` | failures=0 | run `36725863997`（sha `b3dc567a`）**`2026-09-30T15:29:39.1821302Z === RESULT: loops=50 failures=0 ===`**，结论 `success` ✅ |
| ④ 端到端（本地，附加） | `probe_race_minimal.py` × 100（修复后） | 0 崩 | **0/100 崩**（修复前基线 47/100），单轮均 0.64s ✅ |

**其余验证**：`tests/gui/test_event_bus_integration.py` → **19 passed / 103.6s**；
`check_all.sh --fast --guards --local` 与 `--deep` 均 EXIT=0（Ruff/Mypy/G-020 Vulture/G-038 全 PASS）。

**#34 终局**：**✅ 已修复（R12-8）**，由「二、剩余台账」移入「一、已清理」；候选池 P6 关闭；T-26 观察项关闭。
**保留物**：`scripts/probe_race_minimal.py`、`scripts/probe_mutexlocker_race.py`、`.github/workflows/gui-race-probe.yml`（回归工具）；R1 测试侧兜底保留（纵深防御）；
**新哨兵**：任何 GUI 作业再现 access violation → 立即重跑 `gui-race-probe`（loops=50）并回溯是否引入新的 Qt 锁/线程 churn 模式。

**复现/回归命令**：
```powershell
$py = "C:\Temp\pilotstd-probe\venv312\Scripts\python.exe"   # Python 3.12.10 + Qt 6.11.2
& $py scripts/probe_mutexlocker_race.py --lock qt        # 探针有效性（应崩）
& $py scripts/probe_mutexlocker_race.py --lock python    # 对照（应 0 崩）
& $py scripts/probe_race_minimal.py                      # 端到端（应 0 崩）
gh workflow run gui-race-probe.yml -f loops=50           # CI 门（应 failures=0）
```


### 7.23 R13-1：T-29 清零——8 处永久 skip 全部转为真实用例

**目标（用户裁定）**：彻底消除 `tests/` 下 8 处永久 `@pytest.mark.skip`（或条件恒真的 `skipif`）。
**关键发现**：这 8 处的**函数体全是 `pass`（空壳占位）**——skip 掩盖的不是“失败的测试”，而是**从未写过的测试**（比失败的测试更危险的“虚假安全感”）。

**逐处归宿（8/8 全部第 1 档“修复测试”；0 xfail、0 删除）**：

| # | 文件 :: 用例 | 原 skip 理由 | 归宿 | 替代实现（真实断言） |
|---|---|---|---|---|
| 1 | `test_query_subsystem_snapshot.py::test_query_announcement_match` | 依赖 HTTP 请求（requests.get） | 修复测试 | monkeypatch `requests.get`：**命中**返回 `{data,cached_at}`／**未命中** `None`／**超时**降级 `None`／**未配置 api_key 不发请求**（四分支） |
| 2 | `…::test_query_via_cache` | 依赖 HTTP + query_engine 降级 | 修复测试 | 命中项 `source_site=web_announcement_match`、未命中项降级引擎并**按原索引回填**（含 `_fallback_callback` 闭环）＋ 回调顺序断言 |
| 3 | `…::test_finalize_query` | 修改 5+ core 状态 + 通知发送 | 修复测试 | 统计口径 `(total,found,exact,downloadable)`、`query_failed`／`batch_query_summary` 通知、`classifier.classify` 调用；另一例覆盖**空结果 → `query_empty` ＋ `record_pending`** |
| 4 | `…::test_query_main` | query() 入口聚合 | 修复测试 | `use_announcement_match=True` 走**缓存分支**＋ `progress_callback(count,total)` 接线（触发闭包断言） |
| 5 | `test_batch_dispatch.py::test_dispatch_queries` | 需 ThreadPoolExecutor + 真实组件 | 修复测试 | mock `mini_bucket`/`csres` 驱动**真实 ThreadPoolExecutor 编排**，断言溢出项汇总进 `state["all_overflow"]` 与 `bucket_times` 记录 |
| 6 | `…::test_bucket_worker` | 需 mini_bucket 真实交互 | 修复测试 | **指定站点单链**（`skip_overflow=True` 断言）与**默认优先级链**两条路径，含 `(溢出, 耗时, 完成数)` 返回值 |
| 7 | `…::test_init_batch_state` | `_init_batch_state` 创建 daemon 线程 | 修复测试 | 状态容器 + **心跳线程启停生命周期** + `bump()` 计数/回调（`pause_event` 置位语义） |
| 8 | `…::test_finalize_batch` | 依赖 `_init_batch_state` | 修复测试 | 结果组装（未完成项 `error_message="查询未完成"` 兜底）+ `report._report_batch_summary` 委托 + `core` 状态复位（`_persist_batch_state` 打桩） |

**验证与证据**：

| 检查项 | 修复前 | 修复后 |
|---|---|---|
| 两个目标文件 | 26 passed ＋ **8 skipped**（空壳） | **34 passed（0 skipped）** |
| 静态普查 `mark_skip`（`tests/skip_census.py --static`） | **10** | **2**（余下 2 处＝GUI 空壳，另立 T-33） |
| 静态普查 `skipTest` | 60 | 60（未变，T-20 基线仍成立） |
| `tests/test_skip_census.py` | 5 passed | **6 passed**（基线 `mark_skip >= 8` → `== 2`，并新增“T-29 两文件零永久 skip 且无 `pass` 空壳”断言） |
| 后端全量（CI 同口径命令，`-n auto`） | 4 failed / **4033 passed** / **14 skipped** | 6 failed / **4040 passed** / **6 skipped** |
| GUI 全量（`tests/gui/` ＋ 回归架构） | 1022 passed / 2 skipped | **1022 passed** / 2 skipped（未变，属 T-33） |

**后端 failed 项与本次改动无关（已对照证明）**：在 `HEAD` 的独立 worktree（`C:\Temp\pilotstd-probe\pre13`，无本次改动）复跑同一命令 → 同样失败 4 处（`tests/test_manager.py` 的 `test_auto_run`／`test_query_with_mock`／`test_download_after_query`／`test_auto_run_all_stages_complete`）；修复后再现同 4 处 ＋ 2 处网络相关（`test_core.py::TestFileIndexRepository::test_clear_stale_refreshes_existing_old`、`test_round3_features.py::TestAnnounceStats::test_stats_returns_200_with_expected_structure`）。二者均为**本地网络/worker 环境所致**，CI 以 iptables 屏蔽外网、按设计快速失败/跳过。
**数字自洽性**：`passed 4033 → 4040`（**+7** ＝ 8 处空壳转真实用例、其中 facade 侧 4 → 5 例）、`skipped 14 → 6`（**−8**）✓ 与 T-29 的 8 处完全对应。

**复现命令**：
```powershell
python -m pytest tests/unit/manager/facade/test_query_subsystem_snapshot.py tests/unit/query/engine/test_batch_dispatch.py -q -rs
python tests/skip_census.py --static     # mark_skip 应为 2
python -m pytest tests/test_skip_census.py -q
```


**R13-1b：CI 首跑红灯与修正（2026-10-01）**

| 项 | 内容 |
|---|---|
| 失败 run | `36795410642`（sha `0d501ee6`）：`test-backend` failure，连带 `test-gui-coverage`／`version`／`docker`／`exe` skipped（8/13 success） |
| 直接原因 | CI 日志：`tests/unit/manager/facade/test_query_subsystem_snapshot.py:186: unused variable 'tuples' (100% confidence)` → vulture `exit 3` |
| 深层原因 | **本地 G-020 口径窄于 CI**：`scripts/check_all.sh:270`＝`vulture pilotstd/ --min-confidence 80`；CI `.github/workflows/ci.yml:196`＝`vulture pilotstd/ docker/ tests/ scripts/ whitelist.py --min-confidence=100`（范围少 3 目录、阈值低 20）→ 本地 `--deep` EXIT=0 而 CI 红 |
| 修正 | 参数 `tuples` → **`_tuples`**（vulture 默认忽略下划线前缀）；本地按 CI 原命令复跑 **EXIT=0**，受影响三文件 **40 passed** |
| 后续 | 新观察项 **T-34**（本地 G-020 与 CI 对齐，一行改动，待放行） |


### 7.24 R14-1：T-27 修复——入仓合规检查的「新增文件」假绿闭环

**用户裁定**：治理基础设施缺陷优先于被治理对象——合规检查本身不可信＝“门卫睡着了”，每次新增文件都可能逃逸。

#### 一、调查（先定位根因，再动手）

| 假说 | 判定 | 依据 |
|---|---|---|
| glob 模式遗漏？ | **否** | `WHITELIST_*` / `BLACKLIST_*` / `FILENAME_BLACKLIST` 三组模式本身完备；受控实验里违规文件一旦进入 `NEW_FILES` 即被正确判 FAIL |
| git diff 解析错误？ | **否** | `git diff --name-only --diff-filter=A <range>` 行为正确；问题在 `<range>` |
| 条件分支逻辑缺陷？ | **否** | `[ -z "$NEW_FILES" ] && PASS` 分支本身正确 |
| **范围取值在推送路径上恒空（真因）** | **是** | 脚本第 14 行 `origin/${BASE_BRANCH}..HEAD`：**推送事件**触发时 GitHub 已把远端 `<base>` 更新为本次 tip，CI checkout 出来的 `origin/main` **就等于 `HEAD`** → 差集恒空 → 恒 `PASS: 无新增文件`（CI 日志实证 run `36304263963` / `36306033918` 该步骤仅此一行） |

**附带确认**：同一根因家族此前已在 docs-sync 修过（T-25 / R11-3b：`DOCS_SYNC_RANGE=${{ github.event.before }}..${{ github.sha }}`）——本修复沿用**同一手法**，保持治理工具口径一致。

#### 二、修复

| # | 文件 | 改动 |
|---|---|---|
| 1 | `.github/workflows/ci.yml` | `Run repo compliance check` 步骤新增 `COMPLIANCE_RANGE: ${{ github.event.before }}..${{ github.sha }}`（push 专用字段 `event.before` ＋ 通用 `github.sha`） |
| 2 | `.github/scripts/check-repo-compliance.sh` | 范围优先取 `COMPLIANCE_RANGE`；`before` 为空或全零（新建分支/首次推送）→ 回退 `origin/<base>...HEAD`（三点＝merge-base，PR/本地口径） |
| 3 | 同上 | **假绿防护**：显式范围“变更文件数 == 0” → `FAIL`（拒绝静默 PASS）；输出诊断行 `范围: …（变更 N 个文件，其中新增/改名 M 个）` |
| 4 | 同上 | `--diff-filter=A` → **`AR`**：改名（R）后的目标路径同样是“新入仓路径”，不得借改名绕过黑名单/文件名判定 |

#### 三、受控矩阵（临时 bare 远端**忠实复刻 CI 推送态**：`git push` 后 `origin/main == HEAD`）

| # | 场景 | 期望 | 实测 |
|---|---|---|---|
| ① | 推送态新增 `docs/notes/leak_plan.md`（命中 `*_plan.md`）·**修复前**脚本 | 假绿 PASS | **`PASS: 无新增文件`**（exit 0）✅ 假绿复现 |
| ① | 同场景 · **修复后**脚本（`COMPLIANCE_RANGE=before..sha`） | FAIL 拦截 | `范围: f544d34f..6e473096（变更 3 个文件，其中新增/改名 3 个）` → **结论: FAIL** ✅ |
| ② | 新增 `pilotstd/probe_ok.py`（白名单路径） | PASS（不误拦） | `结论: PASS` ✅ |
| ③ | 仅修改已有文件（无新增） | PASS ＋ 防护不误触 | `变更 1 个文件，其中新增/改名 0 个` → `PASS: 无新增文件` ✅ |
| ④ | 显式范围却 0 变更（`HEAD..HEAD`） | FAIL（防护生效） | `❌ FAIL: … 内变更文件数为 0 —— 范围取值异常（假绿防护：拒绝 PASS）` ✅ |
| ⑤ | 首次推送（`before` 全零） | 回退基线口径、不硬失败 | `范围: origin/main...HEAD` → `PASS: 无新增文件` ✅ |
| ⑥ | 改名 `pilotstd/probe_ok.py` → `docs/notes/renamed_report.md`（命中 `*_report.md`） | FAIL（不得绕过） | `变更 1 个文件，其中新增/改名 1 个` → `结论: FAIL` ✅ |

**矩阵结论：6/6 全部符合预期**（脚本与实验脚本均置于仓库外临时目录，实验用 bare 远端不污染仓库）。

#### 四、CI 侧验证（本轮提交的 run 内实证）

本轮推送的 `repo-compliance` 作业日志中，该步骤**不再只打印一行 `PASS: 无新增文件`**，而会先打印真实范围与计数——
即“范围恒空”这一假绿形态在真实流水线上被消除。CI 结论：**13/13 success**。

**复现命令（本地等价）**：
```bash
# 推送态复刻：work 的 origin/main 已等于 HEAD（本次 tip）
COMPLIANCE_RANGE="<before>..<sha>" bash .github/scripts/check-repo-compliance.sh
# 不传该变量时回退：origin/<base>...HEAD
bash .github/scripts/check-repo-compliance.sh
```


### 7.25 R14-2（阶段一）：#31 / #32 原挂窗项盘点与攻坚方案

> 本批**只出调查与方案，不动业务代码**（用户约束）；所有数据由**只读探针**在 2026-10-01 复测（探针不入库）。

#### 一、Issue 回顾与阻塞点状态

| 项 | 核心诉求 | 最初挂起原因（阻塞点） | 阻塞点是否已消除 |
|---|---|---|---|
| **#31** | 消除 ConfigManager **多实例交错写**（last-writer-wins 静默丢配置）与**查询热路径高频 IO** | ① P2（`_load()` 去无条件 `save()`）直接冲击“**构造即写回**”契约——31 测试文件／104 处引用，`tests/test_core_config.py:333-334` 明写“初始化会 save() → `_get_fernet` 查库”；② P3 引入跨进程锁语义（docker scheduler 与 GUI 同机）；③ “只做 P1 缓存”被否——缓存实例读不到 GUI 设置页（`core/config/service.py:43`）写入，需配套失效通知 | **否**——三处结构缺陷原样（`manager.py:27` 实例级锁、`:148-172` 无条件 `save()`、`scorer.py:96` 每次新建）；今日复测量级一致。**但已非硬依赖**：P2 可单独落地（保持三条契约），P1 与失效通知可同批，P3 可后置 |
| **#32** | 后端状态值**中文化自由字符串** → 引入规范枚举，使 i18n 可收口、状态语义一致、API 契约稳定 | 规模巨大且**必须避免同批破坏前端**：生产 248 处／测试 456 处字面量、9 处容器 5 种写法、前端 13 处中文比较、中文值**已落库** | **否**——计数一字未变（见下）；**但 A 阶段为纯增量、零行为变化**，可作为无前置的第一步 |

#### 二、影响面评估

| 维度 | #31（P2 → P1 → P3） | #32（A → B → C → D） |
|---|---|---|
| 涉及文件数 | 核心 2 文件（`core/config/manager.py` 192 行、`query/routing/scorer.py` 263 行）＋ **21 个生产构造点**（pilotstd 16／docker 5）＋ **31 个测试文件** | A：新增 1 文件 ＋ 改 **9 处容器**（导入面 9 文件）；B：**50 生产文件**；C：API 3 处 ＋ DB 迁移 ＋ 前端 13 处；D：**65 测试文件** |
| 是否触碰核心架构 | **否**（不触 EventBus／引擎调度／UI 主循环）；触 **config 读写契约** 与查询评分热路径 | **否**（枚举为叶子模块）；触 **后端契约层 + 前端展示层** |
| 数据迁移／配置变更 | **无 DB schema 迁移**；**有配置写盘语义变更**（P2：由“每次构造写”改为“仅在需要时写”）→ 需补文档（R-006） | C 阶段**有落库迁移**（`file_index.status` 中文→英文，`_migrate_v2_v15.py:22/47`、`_migrate_v16_v49.py:16`；遵循 P-106 不改历史迁移函数）；A/B 阶段无迁移 |

#### 三、今日复测数据（只读探针，2026-10-01）

| 指标 | #31 | #32 |
|---|---|---|
| 主量级 | `test_parallel_batch_query`：`ConfigManager.__init__`=**133**、`save()`=**135**、`get_profile`=**126**、`score_adapter`=**126**、`get_profile` 总 **577 ms**（**4.58 ms/次**）→ 单批 ≈ **0.58 s ＋ ≈519 KiB 写盘**；对照用例 25／26／21（98 ms） | 生产字面量 **248 处／50 文件**；测试 **456 处／65 文件**；容器 **9 处／5 名**；前端 `i18n-allow` **27 行**（状态值比较 **13** 处）；DB 默认值 **3** 处 |
| 风险面 | 测试 `save` 相关 **57 行**、`_get_fernet` patch **39 行**、`save.*assert` **33 处**、`reload()` 用例 **5 处**、引用 ConfigManager 的测试 **31 文件** | 值分布：现行 60／废止 57／已废止 27／被代替 26／未知 26／即将实施 21／作废 19／待确认 7／过期 5（与 R11-2 逐项一致） |

#### 四、测试策略

**#31**
1. **新增受控用例** `tests/unit/core/config/test_manager_dirty.py`：① 已存在配置构造后 **不写盘**（文件 mtime／内容不变）；② **首次创建仍写盘**；③ **迁移有变更才写盘**（`_migrate_ui_keys` 需回报“是否改动”）；④ 显式 `set()` 后写盘；⑤ 损坏文件备份路径不变。
2. **受控矩阵（热路径）**：复用本轮探针（pytest 插件注入 `ConfigManager.__init__`／`save` 计数）→ 断言 `test_parallel_batch_query` 的 `save()` 由 **135 → ≤2**、`get_profile` 耗时显著下降。
3. **回归面**：31 个引用 ConfigManager 的测试文件全绿；`tests/test_core_config.py` 的 reload／fernet 相关 5 组用例保持通过（构造期写盘契约由用例 ①②③ 显式覆盖）。
4. **端到端**：`check_all.sh --fast --guards --local` ＋ `--deep` 全绿；CI 13/13。

**#32**
1. **A 阶段**：新增 `tests/unit/core/test_status.py`——9 值全量 round-trip；`废止`↔`已废止` 别名归一等价；**与 9 处旧容器取值集合逐一等价断言**（保证零行为变化）；生产字面量计数保持 248。
2. **B 阶段**：逐模块 diff 仅替换字面量、无逻辑改动；`pytest tests/ -k "query or validity or standard or adapter"` 全绿；生产字面量计数逐批下降并登记（目标 ≤20）。
3. **C 阶段**：新增状态取值契约测试（API 取值集合、归一后一致）；`scripts/check_i18n_key_count.py` 三语对齐 PASS；前端 `npm run test` 全绿且状态值比较的 `i18n-allow` **13 → 0**。
4. **D 阶段**：测试字面量收敛至 ≤50，**保留 ≥3 处直写字面量用例**作为真实数据回归哨兵。

#### 五、优先级裁定与拆分

**先做 #31**（活的数据丢失风险 + 已量化的 0.58 s／519 KiB 代价），**#32 紧随其后**：

| 批次 | 内容 | 规模 | 时间盒 |
|---|---|---|---|
| **R14-3a** | #31-**P2**：`_load()` dirty 标记（仅在首次创建／迁移有变更时 `save()`） | 1~2 commit | **1 周期** |
| **R14-3b** | #31-**P1**：`scorer.get_profile` 复用/注入实例 ＋ **配置失效通知**（避免陈旧缓存） | 1~2 commit | 1~2 周期 |
| **R14-3c** | #31-**P3**：`os.replace` 前跨实例／跨进程文件锁 | 1 commit | 1 周期（**可转观察**：若 a+b 后写盘窗口已收窄到可接受） |
| **R14-4a** | #32-**A**：`pilotstd/core/status.py` 枚举 ＋ 9 处容器改引用（零行为变化） | 1~2 commit | **1 周期** |
| **R14-4b** | #32-**B**：后端 248 处收敛（适配器 → 统计 → 校验器/匹配器/路由） | 3~5 commit | 2 周期 |
| **R14-4c** | #32-**C**：API 契约 ＋ 落库迁移 ＋ 前端 13 处映射（须更新 `docs/architecture.md`） | 1~2 commit | 1 周期 |
| **R14-4d** | #32-**D**：测试 456 处收敛（保留 ≥3 处字面量哨兵） | 2~3 commit | 1~2 周期 |

**合计约 8~13 个交付周期**；每个批次独立提交、独立门禁、可停可续。
**可选交换**：若你更希望先清 #32-A 的“零风险增量”（同时消解“A 阶段逾期”的历史违约），可将 R14-3 与 R14-4a 对调——两者无前置依赖，仅影响风险与收益的先后。

#### 六、窗口重锚登记（规则违约的明示处理）

- #31 行原定「**第十二轮为最终期限，逾期不再顺延**」；#32 行原定「A 阶段须在第十二轮落地，否则**当轮直接转已接受并关闭**」。
- 事实：两项在第十二轮**均未收口**，当前已至 `v0.120.2`（第十三／十四轮）→ **两条自定规则均已逾期**。
- 本批按用户裁定（"拉回主战线"）**显式推翻 #32 的自动接受条款**，并在台账将窗口**重锚为 R14-3 / R14-4**（见两行 `R14-2a 盘点结论`）。**重锚仅此一次**：R14-3a 与 R14-4a 若在下批仍未启动，则按原条款转「已接受」并按各自代价章节关闭。

**盘点探针（均不入库）**：`r14_2_survey.py`（构造点/容器/字面量 tokenize 计数）、`r14_2_hotpath_probe.py`（pytest 插件注入计数）。


### 7.26 R14-3a：#31-P2 落地——`_load()` dirty 写盘（消除热路径整份覆盖写）

**用户裁定**：维持 R14-3a 优先（#31 是活的数据丢失风险；P2 是 P1/P3 的地基）。**时间盒 1 周期，实际单批完成。**

#### 一、改动（最小面）

| 位置 | 改动 |
|---|---|
| `pilotstd/core/config/manager.py`（顶部） | 新增 `import copy`（快照比较用） |
| `pilotstd/core/config/manager.py::_load()` | “文件已存在”分支：`self._data = _walk_sensitive(...)` 之后**留存 `copy.deepcopy(self._data)` 快照** → `populate_defaults(FACTORY_DEFAULTS)` → `_migrate_ui_keys(self)` → **仅当 `self._data != before` 才 `self.save()`**（原为无条件 `save()`） |
| 同函数 docstring | 登记写盘语义与四条契约（R-011：说明“为什么”） |

**未触碰**：`save()` 本体（原子替换 + 重试）、`set()/get()/reset()/reload()` 语义、`_populate_first_run()`、损坏备份分支、以及 **P1（`scorer.get_profile` 缓存/注入）与 P3（跨进程文件锁）**（用户禁止项）。

#### 二、四条契约与验证

| # | 契约 | 覆盖用例 | 结果 |
|---|---|---|---|
| ① | 首次创建（文件不存在）仍写盘 | `test_first_run_writes_file` | ✅ save 计数 = 1，文件生成且含 `appearance.theme=经典白` |
| ② | 补默认值 / 迁移旧键**有变更才写盘一次** | `test_missing_defaults_backfill_writes_once`、`test_legacy_ui_keys_migrate_writes_once` | ✅ 各 save=1，且**第二次构造 save=0**（幂等）；用户已有值不被默认值覆盖 |
| ③ | 显式 `set()` + `save()` 仍持久化 | `test_explicit_set_then_save_persists` | ✅ `set()` 本身零写盘（mtime/内容不变）→ `save()` 落盘 → 再构造零写盘 |
| ④ | 损坏文件仍先备份 `.corrupted.<ts>` | `test_corrupted_config_backup_and_write` | ✅ 备份 1 个 + 以默认值初始化并写盘；既有 `tests/test_core.py::TestConfigManager::test_corrupted_config_backup` 亦通过 |
| ⑤ | 已存在且完整 → **构造零写盘**（P2 主目标） | `test_existing_complete_config_writes_nothing` | ✅ save=0 且 `(mtime_ns, bytes)` 完全不变 |
| ⑥ | `reload()` 无变更 → 零写盘 | `test_reload_unchanged_writes_nothing` | ✅ save=0，内存态正常刷新 |

新增用例文件：**`tests/unit/core/config/test_manager_dirty.py`（7 例，全绿）**；隔离手段沿用 `tests/test_core_config.py:333-340` 的做法（patch `pilotstd.core.config.paths.get_db_path` 到临时空库，避免构造期 `_get_fernet` 误读真实库）。

#### 三、热路径受控矩阵（同一探针：pytest 插件注入 `ConfigManager.__init__`/`save` 计数）

| 指标 | 修复前（R14-2 盘点） | 修复后（本批） | 变化 |
|---|---|---|---|
| `test_parallel_batch_query` · `save()` | **135** | **2** | **−98.5%**（远优于 ≤2 的验收线） |
| 同用例 · `ConfigManager.__init__` | 133 | 133 | 不变（**构造次数未变，仅消除无谓写盘**） |
| 同用例 · `get_profile` 总耗时 | **577 ms** | **153 ms** | **−73.5%** |
| 同用例 · `get_profile` 单次 | 4.58 ms | **1.21 ms** | **−73.6%** |
| 对照用例（不发起批量查询）· `save()` | 26 | **1** | −96.2% |
| 对照用例 · `get_profile` 总耗时 | 98 ms | **23 ms** | −76.5% |
| 单批无谓覆盖写字节 | ≈519 KiB（4220 B × 126） | **≈7.7 KiB**（4220 B × 2） | −98.5% |

#### 四、回归与门禁

| 检查项 | 结果 |
|---|---|
| 引用 ConfigManager 的文件集（20 文件：core/config/manager/docker_scheduler/migrations/notification*/validity*/settings*/gui settings 等） | **697 passed / 1 skipped**（EXIT=0） |
| `tests/test_core.py` 配置用例（含损坏备份） | 通过 |
| `tests/test_core_config.py`（reload/fernet 5 组） | 通过 |
| Ruff / Mypy（门禁口径 `pilotstd/ docker/`）/ G-020 Vulture / G-038 | 全 PASS |
| `check_all.sh --fast --guards --local` 与 `--deep` | 均 **EXIT=0** |
| CI（13 作业） | **13/13 success** |
| 本地 `tests/test_manager.py` | **本地网络依赖致挂起**（与本改动无关：R13-1 已用 HEAD worktree 对照证明同样 4 个用例在无改动时同样超时）；CI 以 iptables 屏蔽外网，按设计快速失败/跳过 → 以 CI 为准 |

#### 五、文档联动（R-006 / G-031）

- `docs/architecture/modules/core.md`「关键机制 · 配置」条目补写盘语义 + 量化收益 + 用例文件（该文件与 `pilotstd/core/` 由 **G-031** 强制同步，改 `manager.py` 必改它）。
- 本簿：#31 台账行追加 `R14-3a 实施结果（P2 完成）`；表头 R14-3a；版本 v1.38.0；gates.md v1.66。

#### 六、剩余与影响

- **P1（R14-3b）**：`scorer.get_profile` 复用/注入实例 + **配置失效通知**（避免陈旧缓存）——P2 已让“实例化”本身不再昂贵（单次 1.21 ms），但 126 次构造仍存在，P1 可再降一个量级。
- **P3（R14-3c）**：`os.replace` 前加跨实例/跨进程文件锁——P2 后写次数由 126/批降到 ≈2/批，**last-writer-wins 窗口同比例收窄**；若 R14-3b 后窗口已可接受，P3 可转观察。
- **不引入新技术债**：未用缓存静默绕过、未放宽任何断言、未改 `save()` 语义。

**探针（不入库）**：`r14_2_hotpath_probe.py`（本次前后对比复用同一探针，保证可比性）。


### 7.27 R14-3b：#31-P1 落地——共享 ConfigManager 实例 + 显式配置失效通知

**用户裁定**：继续推进 R14-3b（上下文连贯性 + P1 是彻底终结 #31 性能问题的最后一步）。
**时间盒 1~2 周期，本批完成。**

#### 一、改动清单

| 文件 | 改动 |
|---|---|
| `pilotstd/core/config/manager.py` | 新增模块级 `_SHARED_LOCK`（**可重入锁**）/`_SHARED_INSTANCES`/`_INVALIDATION_LISTENERS`；新增 `default_config_path()`、`get_shared_config()`、`invalidate_shared_config()`、`register/unregister_invalidation_listener()`、`_notify_config_invalidated()`、`_publish_config_written()`；`__init__` 缺省路径统一走 `default_config_path()`；`save()` 写盘成功后发布失效通知（**通知在释放实例锁之后**发出） |
| `pilotstd/query/routing/scorer.py` | `get_profile()` 内 `ConfigManager()` → **`get_shared_config()`**（**函数签名未改**） |
| `pilotstd/query/site_config/_loader.py` | `_load_site_overrides()` 改用共享实例；新增 `_on_config_invalidated()` 并于模块导入时注册（清 `_site_config_cache`） |
| `pilotstd/core/config/service.py` | `ConfigService.__init__` 缺省由 `ConfigManager()` 改 `get_shared_config()`（缺省参数签名不变，显式注入仍生效） |
| `docs/architecture/modules/core.md` | 「配置」条目补**共享实例与失效通知数据流**（G-031 强制同步） |

**未触碰**：P3（跨进程锁）——`os.replace` 前后无任何新增文件锁；P2 dirty 语义——`_load()` 的“仅变更才写盘”一字未动；任何函数签名（`get_profile(adapter_name)`、`ConfigManager.__init__/save` 均保持原样）。

#### 二、失效通知数据流（显式、可测试）

```
GUI 设置页 (ui/core/handlers/_settings*.py)          Web API (docker/api/settings.py)
        │ 各自持有 ConfigManager 实例                          │
        └──────────────► ConfigManager.save() ────────────────┘
                                   │ 原子写盘成功
                                   ▼
                    _publish_config_written(instance)
              ┌────────────────────┴─────────────────────┐
              ▼                                          ▼
  ① 缓存中实例 ≠ 写入者 → 移除缓存            ② 回调所有 _INVALIDATION_LISTENERS(path)
     （他方写盘＝缓存陈旧；自己写盘则保留）              │
                                                        ▼
                                    site_config/_loader._on_config_invalidated
                                    → _site_config_cache = None
                                    → 下次 get_site_config() 重建，拿到新覆盖值
```

- **无 TTL**：未写盘则共享实例长期有效（`test_no_time_based_ttl` 显式锁定）——不做基于时间的静默过期。
- **可重入锁的必要性**：首次运行构造会在 `_load()` 内写盘 → 发布通知 → 再进 `_SHARED_LOCK`；非重入锁会自死锁（本轮实测并已修正）。
- **监听者约束**（已写入代码注释）：回调在持锁上下文内执行，须保持轻量、不得阻塞等待其它需要该锁的线程；单个监听者异常被隔离（`test_listener_exception_is_isolated`）。

#### 三、受控矩阵与证据

| 指标 | R14-2 盘点（基线） | R14-3a（P2） | **R14-3b（P1）** |
|---|---|---|---|
| `test_parallel_batch_query`·`ConfigManager.__init__` | 133 | 133 | **7** |
| ↳ 其中**热路径**构造 | 133 | 133 | **1**（共享实例冷启动） |
| ↳ 其中**一次性 DB 迁移**构造 | — | — | **6**（`_migrate_v31_plus.py:166`×2、`_migrate_v37_plus.py:43`×2、`:67`×2；均在 `@migration` 函数体内 → **P-106 禁止改动**） |
| ↳ 稳态（同进程同路径 50 次 `get_profile`） | — | — | **0 次构造**（冷启动 1 次） |
| `save()` | 135 | **2** | **2**（P2 契约未破坏） |
| `get_profile` 总耗时 | 577 ms | 153 ms | **5 ms**（单次 4.58 → **0.04 ms**，−99.1%） |
| 对照用例（`test_single_query_found`） | 25 构造 / 26 save / 98 ms | 25 / 1 / 23 ms | **4 / 1 / 4 ms**（4 = 3 迁移 + 1 热路径） |

**关于“≤2”验收口径的说明（如实报告）**：热路径属性上的构造次数为 **1（冷启动）/ 0（稳态）**，满足 ≤2；同用例**总**构造数 7 中的 6 次来自**一次性 DB 迁移读配置**（测试用临时新库必然触发迁移；生产库已迁移则不发生），
而其落点全部在 `@migration` 装饰的函数体内 —— 修改它们会改变已执行迁移的源码哈希，触发 `_migration_checksum` 校验并**阻断启动**（P-106），故**不动**。若强行追求“同用例总数 ≤2”，唯一手段就是改迁移源码，本批按约束**拒绝**。

#### 四、新增用例（12 例）

| 文件 | 用例 | 锁定内容 |
|---|---|---|
| `tests/unit/core/config/test_manager_shared.py` | 8 例 | 同路径复用／并发首次单实例（8 线程 Barrier）／**无 TTL 静默过期**／他方写盘→缓存失效+通知／自己写盘→保缓存+通知／显式失效返回值 1→0／注册去重与注销生效／监听者异常隔离／缺省路径与构造器同口径 |
| `tests/unit/query/routing/test_scorer_hot_path_config.py` | 4 例 | 热路径 50 次调用构造 ≤2 且稳态 0／**GUI 写盘后热路径读到新值（端到端）**／经共享实例写盘后一致／站点缓存被清后 `window_limit` 覆盖生效 |

#### 五、回归与门禁

| 检查项 | 结果 |
|---|---|
| 回归集（20 文件 + `tests/unit/query` + `tests/test_query.py`） | **826 passed / 1 skipped**（EXIT=0） |
| 新增两测试文件 | **20 passed**（含 `test_manager_dirty.py` 7 例回归） |
| Ruff / Mypy（门禁口径 `pilotstd/ docker/`）/ G-020 / G-038 | 全 PASS |
| `check_all.sh --fast --guards --local` 与 `--deep` | 均 **EXIT=0**（G-032 保持 13 无新增） |
| CI（13 作业） | **13/13 success** |

#### 六、#31 剩余

- **P3（跨进程文件锁）→ R14-3c**：P2+P1 后单批查询写盘 **126 → ≈2**、构造 **133 → 1**，last-writer-wins 的窗口已与写次数同比例收窄。**建议**：若下一轮观测无并发丢配置迹象，可将 P3 转「观察」而非立即实施（届时请用户裁定）。
- **不引入新技术债**：未用 TTL 掩盖陈旧、未放宽断言、未改迁移源码、未改任何函数签名。

**探针（不入库）**：`r14_3b_steady.py`（冷启动/稳态构造计数）、`r14_3b_site_probe.py`／`r14_3b_detail_probe.py`（构造点归属）、`r14_2_hotpath_probe.py`（前后可比的热路径矩阵）。


### 7.28 R14-4a：#31 闭环（P3→观察）+ #32-A 状态字典落地（零行为变化）

#### 一、#31 正式闭环（P3 降级观察，用户裁定）

| 阶段 | 内容 | 量化结果 |
|---|---|---|
| P2（R14-3a） | `_load()` 改 dirty 写盘（仅首次创建／补默认值／迁移有变更才 `save()`） | 单批查询 `save()` **135 → 2** |
| P1（R14-3b） | 按路径共享 `ConfigManager` 实例 + 写盘后的**显式失效通知**（消费方：`scorer.get_profile`、`site_config/_loader`、`ConfigService`） | `ConfigManager.__init__` **133 → 1**（稳态 0）；`get_profile` **577 → 5 ms** |
| P3（**降级观察**） | 跨进程文件锁 —— **不做**，登记为观察项 **T-35** | 写次数已降两个数量级；文件锁跨平台语义/边缘情况维护成本 > 防范收益；未来若观测到冲突，优选「原子写+重试」或 SQLite 配置后端 |

**#31 由「二、剩余台账」移入「一、已清理」**（核心闭环）；「二、剩余台账」现只列 **#32**。

#### 二、#32-A：状态字典（纯增量、零行为变化）

**新增** `pilotstd/core/status.py`：

| 组成 | 内容 |
|---|---|
| `Status`（`str` 混入 Enum） | 9 值，**value 与现网中文逐字一致**：现行／即将实施／废止／已废止／被代替／作废／过期／待确认／未知 |
| `ALL_STATUS_VALUES` | 9 值全集（`frozenset`） |
| `STATUS_I18N_KEYS` | 枚举值 → i18n key（`status.active` …）；**双拼写 废止／已废止 映射同一 key** |
| `STATUS_EN_KEYS` | 枚举值 → 英文 canon（`active`/`upcoming`/`withdrawn`/…）——B/C 阶段写入 API/DB 的目标值 |
| `normalize_status()` | `废止` → `已废止` 别名归一（strip；未知值原样返回，不猜测） |
| 5 组命名集合 | `ABOLISHED_STATUSES`(4)／`ABOLISHED_STATUSES_WITH_EXPIRED`(5)／`EXPIRED_STATUSES`(3)／`NON_OVERRIDABLE_STATUSES`(4，含待确认)／`API_VALID_STATUSES`(tuple，3) |

**9 处容器收敛**（原字面量集合 → 引用字典）：

| # | 位置 | 原字面量 | 现引用 |
|---|---|---|---|
| 1 | `manager/classifier.py:26`（`QueryClassifier._EXPIRE_STATUSES`） | 4 值 | `ABOLISHED_STATUSES` |
| 2 | `manager/facade/_organize.py:186`（方法内局部变量） | 5 值 | `ABOLISHED_STATUSES_WITH_EXPIRED` |
| 3 | `manager/facade/_query.py:33`（`QueryHandler._EXPIRE_STATUSES`） | 4 值 | `ABOLISHED_STATUSES` |
| 4 | `manager/facade/_query_subsystem.py:48`（`QuerySubsystem._EXPIRE_STATUSES`） | 4 值 | `ABOLISHED_STATUSES` |
| 5 | `organizer/mover.py:35`（`FileMover._EXPIRE_STATUSES`） | 5 值 | `ABOLISHED_STATUSES_WITH_EXPIRED` |
| 6 | `core/notification/_format_utils.py:10`（`ABOLISHED_STATUS_TOKENS`） | 5 值 | `ABOLISHED_STATUSES_WITH_EXPIRED` |
| 7 | `ui/core/handlers/auto_flow_engine.py:18`（`AutoFlowEngine.EXPIRED_STATUSES`） | 3 值 | `EXPIRED_STATUSES` |
| 8 | `ui/core/handlers/query_flow_engine.py:30`（`_EXCLUDED_FROM_OVERRIDE`） | 4 值（含待确认） | `NON_OVERRIDABLE_STATUSES` |
| 9 | `docker/api/standards.py:17`（`_VALID_STATUSES`） | tuple 3 值 | `API_VALID_STATUSES` |

**未触碰**：业务逻辑中的中文状态字面量（B 阶段）、DB 迁移脚本、API 返回字符串、各容器类型（frozenset 保持 frozenset、tuple 保持 tuple）。

#### 三、生产字面量计数（tokenize 口径，探针 `r14_4a_count.py`）

| 指标 | 重构前 | 重构后 | 说明 |
|---|---|---|---|
| 生产（`pilotstd/` + `docker/`） | **248 处 / 50 文件** | **220 处 / 46 文件** | 差值＝**−37**（9 处容器定义里的字面量被移除）**+9**（枚举 9 值在新模块中登记一次）＝ −28 ✓ 算术自洽 |
| ↳ 9 个容器文件内 | 50 处 | **13 处** | 13 处为该 9 文件内的**其它业务字面量**（如状态→颜色映射、比较逻辑），**本批未动** |
| ↳ 其余业务字面量 | 198 处 | **198 处（未动）** | 「不替换业务代码字面量」的实证 |
| 测试（`tests/`） | 456 处 | **504 处** | +48＝新增 `test_status.py` 内的等价性基准字面量；D 阶段收敛 |

> **口径说明（P-105）**：用户预期“生产字面量仍为 248 处”。实测为 **220 处**——因为“容器引用枚举”与“容器字面量保留”在计数上互斥：37 处容器字面量被移除，9 处规范值进入 `status.py`。
> 该结果是 A 阶段目标的**正确形态**（“建字典 + 容器收敛”）；**业务字面量（198 + 13）确实一字未改**。

#### 四、验证

| 检查项 | 结果 |
|---|---|
| 新增 `tests/unit/core/test_status.py` | **16 passed**（9 值 round-trip／`Status` 与 str 兼容／别名归一 9 组参数化／映射脚手架覆盖与双拼写同键／5 组集合等价／容器与命名集合**同一对象**／API tuple 类型与 `废止∉白名单` 口径）；**无 PyQt6 环境（后端作业）为 15 passed + 1 skipped**（UI 侧断言按 `importorskip` 环境守卫跳过），模拟实测 EXIT=0 |
| 受影响模块回归（14 文件集：flow engine／manager／organizer／facade／format utils／notification 等） | **768 passed**；其中 `test_notification_aggregator.py` 4 例失败已由 **HEAD worktree 对照**证明为该组合下的**既有顺序干扰**（HEAD 上同样 4 例失败），与本批无关 |
| Ruff / Mypy（门禁口径 391 源文件）/ G-020 / G-038 | 全 PASS |
| `check_all.sh --fast --guards --local` 与 `--deep` | 均 **EXIT=0**；G-032 保持 13 无新增 |
| CI（13 作业） | **13/13 success** |

#### 五、后续（#32 B/C/D）

- **B（R14-4b）**：逐模块把 248（现 220）处业务字面量改为枚举引用；对外 API 输出仍为中文（不破坏前端 13 处比较）；目标生产字面量 ≤20。
- **C（R14-4c）**：`docker/api/standards.py` 等契约层由枚举派生；DB 默认值加显式迁移（**不改历史迁移源码**，P-106）；前端 13 处比较点改「枚举→i18n key」映射，`i18n-allow` 状态比较项 13 → 0。
- **D（R14-4d）**：测试字面量收敛（现 504）至 ≤50，**保留 ≥3 处直写字面量哨兵**。

**探针（不入库）**：`r14_4a_count.py`（字面量计数与按文件分布、容器文件占比）。


### 7.29 R14-4b：#32-B 后端业务字面量大收敛（211 → 0，5 个原子 commit）

**用户裁定**：A 阶段建好字典后，B 阶段把后端散落的"旧衣服"逐件叠进收纳盒。**时间盒 2 周期，本批完成。**

#### 一、分批与改动量（AST 口径逐处可核）

| 批次 | 域 | 替换处数 | 主要落点 |
|---|---|---|---|
| B1 `cfe1bbc4` | `pilotstd/core` + `announcement` + `pipeline` | 27 | `validity_checker.py`(7)、`_file_index_query.py`(5)、`announcement/matcher.py`(5)、`pipeline/router.py`(8)、`file_index.py`(1)、`_validity_pipeline.py`(1) |
| B2 `4c6183ff` | `pilotstd/query` | 96 | 20 个适配器（jjg 10／jtst 10／nrsis 9／ttbz 7／njbz365 5／std_gov 4／mock 4 …）、`search_strategy.py`(25)、`engine/_overflow.py`(1) |
| B3 `21324731` | `pilotstd/manager` | 32 | `standard_service.py`(18)、`facade/_download.py`(6)、`facade/_query_subsystem.py`(3)、`organize/organizer.py`(2) 等 |
| B4 `584085e7` | `pilotstd/ui` | 39 | `archive_flow_engine.py`(15)、`main_window/parts/_query_ops.py`(11)、`query_flow_engine.py`(6)、`workers/archive.py`(5) |
| B5（本 commit） | `docker` | 5 | `api/standards.py`(3)、`health_check_service.py`(2) |
| **合计** | — | **199** | 46 文件 |

#### 二、替换策略（用户约束 ①②的落地）

- **统一使用 `Status.<MEMBER>.value`**：API 返回、DB 落库、日志、SQL 参数处均为**严格 `str`**，不依赖 `str` 子类序列化细节 → **API 契约绝对不变**（用户约束 ②）。
- 替换工具为**一次性 AST 脚本**（不入库）：精确定位 `ast.Constant` 字符串节点，排除 docstring，用 **UTF-8 字节偏移**单遍替换（`col_offset` 是字节偏移——用字符偏移会切错中文，实测踩坑后修正），替换后 `ast.parse` 自校验。
- **未触碰**：`web/src/`（前端 13 处映射留 C 阶段）、DB 迁移脚本（P-106）、任何 API 返回结构。
- 因替换变长的 12 行按项目风格折行（`ruff` E501 全绿）。

#### 三、计数（tokenize 口径，逐处枚举可核）

| 口径 | A 阶段末 | B 阶段末 | 说明 |
|---|---|---|---|
| 生产（`pilotstd/` + `docker/`） | **220** | **21** | −199 处业务字面量 ✓ |
| ↳ `pilotstd/core/status.py` 枚举定义 | 9 | **9** | 字典本身，**必须保留** |
| ↳ `pilotstd/templates/adapter/**` | 12 | **12** | cookiecutter **脚手架模板**（含 `{{ cookiecutter.* }}` 占位符→非法 Python、不参与运行时）；收敛它属另一议题 |
| **运行时业务代码** | **199** | **0** | ✓ 达成「≤20」验收（且为 0） |

#### 四、验证

| 检查项 | 结果 |
|---|---|
| 新增守卫 `tests/unit/core/test_status_convergence.py` | 28 passed（含既有 status 用例）：① AST 扫描 `pilotstd/`+`docker/` 断言**零裸状态字面量**（docstring 除外；字典与模板豁免）② `ValidityChecker._determine_status` 行为断言（废止名→`Status.WITHDRAWN_NORMALIZED.value`；正常名→`Status.ACTIVE.value`）③ 9 值 round-trip 与 `type(...) is str` |
| 分批回归 | B1 393 passed；B2 284 passed；B3 381 passed；**B4 `tests/gui`+`tests/unit` 全量 1829 passed** |
| Ruff / Mypy（门禁口径 391 源文件） | 每批全绿（含 12 处折行） |
| `check_all.sh --fast --guards --local` 与 `--deep` | 均 EXIT=0；G-032 保持 13 无新增 |
| 文档联动 G-031 | `core.md`／`announcement-pipeline.md`／`query.md`／`manager.md`／`ui.md` 各补字典引用说明（按批次同 commit） |
| CI（13 作业） | **13/13 success** |

#### 五、剩余（#32 C/D）

- **C（R14-4c）**：契约层（`docker/api/standards.py` 等）由枚举派生；DB 默认值 3 处加**显式迁移**（不改历史迁移源码，P-106）；前端 13 处状态比较改「枚举→i18n key」映射（`i18n-allow` 状态项 13 → 0）。
- **D（R14-4d）**：测试字面量 504 → ≤50，**保留 ≥3 处直写字面量哨兵**。
- **可选后续**：`pilotstd/templates/adapter/**` 模板同步引用字典（本次未做，理由：模板非运行时代码且含 Jinja 占位符）。

**探针（不入库）**：`r14_4b_inventory.py`（AST 盘点）、`r14_4b_transform.py`（AST 替换器）、`r14_4b_leftovers.py`（tokenize 复测 + 残余逐处枚举）。


### 7.30 R14-4c：#32-C 贯通 API 契约 + 落库迁移 + 前端 i18n 映射

**用户裁定**：趁后端枚举化（A+B）刚完成，一鼓作气打通前后端与 DB 的"大动脉"，让 i18n 收口真正落地到界面；测试侧收敛（D）留作收尾。

#### 一、三项交付

| 子项 | 交付 | 关键点 |
|---|---|---|
| ① API 契约 | `pilotstd/core/status.py` 新增 `status_key()`／`resolve_status_filter()`／`STATUS_KEY_TO_VALUE`；`/api/standards/status`、`/api/query/results`、`/api/pending/requery` 新增 `status_key`；`WechatIPService.get_status()` 新增 `current_ip_known` | 中文 `status` 字段与响应结构**一律保留**；过滤参数**英文键与中文值并存**（老书签有效）；无版本升级策略变更 |
| ② DB 迁移 | 新增 `_migrate_v61_enum_status_defaults.py`（`@migration(61)`）＋`CURRENT_SCHEMA_VERSION` 60 → 61 ＋ migrations.py 注册 | **P-106 合规**（v2/v3/v16 历史迁移源码零改动）；默认值＝枚举值 → **不重建**（现网零数据搬动）；漂移 → SQLite 12 步重建修复（保数据与索引）；失败降级告警（同 v60 口径）；幂等 |
| ③ 前端 | 新增 `web/src/utils/stdStatus.ts`；`StandardsStatusView.vue`(6)、`PendingView.vue`(3)、`QueryHistory.vue`(1)、`WechatTrustIP.vue`(1) 改比较 `status_key`；类型补 `status_key` | **13 处中文比较 → 0**，`i18n-allow` 状态项 **13 → 0**；筛选下拉提交英文键；各视图兜底色按原样保留（`severityOfStatusKey(key, fallback)`） |

#### 二、契约字段一览（向后兼容）

| 端点 | 新增字段 | 原有字段 |
|---|---|---|
| `GET /api/standards/status` | `items[].status_key`；`status` 参数接受 `active`／`现行` | `items[].status`（中文）、`total`／`page`／`page_size` |
| `GET /api/query/results` | `results[].status_key` | `results[].status` 及全部字段（**磁盘文件不改写**） |
| `POST /api/pending/requery` | `results[].status_key` | 同上 |
| `GET /api/wechat-ip/status` | `current_ip_known`（布尔） | `current_ip` 等全部字段 |

#### 三、验证

| 检查项 | 结果 |
|---|---|
| `tests/unit/core/test_status_contract.py`（新增 25 例） | PASS：`status_key` 归一/兜底/幂等；`resolve_status_filter` 双口径；列表 item 带键；`active` 与 `现行` 等价、`Active` 不生效；非法值忽略；结果文件字节不变；重查结果带键；IP 已知标志 |
| `tests/unit/core/test_migrate_v61.py`（新增 6 例） | PASS：无漂移不重建（DDL 与数据原样）／漂移修复（默认值改枚举值、数据与索引保留、临时表已改名）／幂等／缺表跳过／无 DEFAULT 跳过／注册号＝`CURRENT_SCHEMA_VERSION`＝61 |
| `web/src/utils/stdStatus.test.ts`（新增 4 例） | PASS：8 键分级、废止族全 danger、未知键兜底、**只认英文键（中文文案不匹配）** |
| 核心/迁移回归 | `tests/test_core.py`＋`tests/test_migrations_full.py`＋`tests/unit/core`＋`final_complete`＋`manager_unit` → **506 passed** |
| 前端 | `vitest run` **301 passed**（41+1 文件）；`vue-tsc -p tsconfig.app.json --noEmit` **零错误**（含 app 配置严格模式） |
| i18n | `scripts/check_i18n_key_count.py` **PASS**（三语 860 key 一一对应；本批未新增 key——颜色分级不是 UI 文案） |
| Schema | `scripts/check_schema_consistency.py` **PASS**（v61 测试改用"中性表名 + RENAME"避免误报生产表列集） |
| 门禁 | `check_all.sh --fast --guards --local` 与 `--deep` 均 **EXIT=0**；G-032 保持 13 无新增 |
| CI | **13/13 success** |

#### 四、实施中踩到并修正的问题（如实记录）

1. **`vue-tsc` 假绿**：`vue-tsc --noEmit`（不带 `-p`）不检查任何文件、恒返回 0；门禁用 `-p tsconfig.app.json` 才暴露 2 处类型缺口（`WeworkIPStatus.current_ip_known`、`QueryHistory` 局部结果类型的 `status_key`）→ 已补齐类型（教训：**必须用门禁口径**，同 G-038 的假绿往事）。
2. **schema 一致性门禁**：v61 测试最初直接 `CREATE TABLE file_index (...)`（列集远少于生产）→ MISSING=50 阻断提交；改为**中性表名 + `ALTER TABLE ... RENAME TO`**（RENAME 保留 DEFAULT 子句）后 PASS。
3. **重建逻辑需兼容引号表名**：SQLite 对 RENAME 后的表把名字写成 `"table"`，初版正则只认裸名 → 漂移修复分支失败（测试当场暴露）→ 正则改为兼容 `"x"`／`[x]`／`` `x` `` 四写法。
4. **文档 schema 版本漂移**：`core.md`／`deployment/README.md` 里的 `CURRENT_SCHEMA_VERSION = 60` 同步为 61。

#### 五、剩余（#32 D）

- **D（R14-4d）**：测试字面量 **504 → ≤50**（保留 ≥3 处直写字面量哨兵）；`pilotstd/templates/adapter/**` 脚手架模板可选同步。

**探针/脚本（不入库）**：`r14_4c_frontend.py`（前端 6 文件改造）、`r14_4c_c1_fix.py`（类型/schema/版本修正）。


### 7.31 R14-4d：#32-D 测试侧收敛 + 哨兵机制（#32 正式闭环）

**用户裁定**：测试里的 504 处中文状态字面量是 #32 最后一块"自留地"；收敛目标 ≤50，且**必须留哨兵**防止枚举 value 被误改而与外部系统脱节。

#### 一、收敛结果

| 口径 | 收敛前 | 收敛后 | 说明 |
|---|---|---|---|
| `tests/` 中文状态字面量（AST，排除 docstring） | **513** | **25** | 本批替换 **456 处**；其余差额为 A/B/C 阶段已随生产改造同步的部分 |
| 涉及测试文件 | — | **67 个** | 与生产同一套 AST 替换器（UTF-8 字节偏移精确定位、docstring 不触碰、替换后 `ast.parse` 自校验） |
| 验收线 | ≤50 | **25** | ✓ |

最终 25 处全部位于**哨兵**文件（见下表），无一处游离字面量。

#### 二、五处哨兵清单（≥3 要求达成；均带 `# Sentinel: 确保枚举 value 与现网中文契约一致` 注释）

| # | 位置 | 层 | 断言要点 |
|---|---|---|---|
| 1 | `tests/unit/core/test_status.py::test_sentinel_enum_values_match_live_chinese_contract` | **字典契约** | 9 值逐字比对（现行/即将实施/废止/已废止/被代替/作废/过期/待确认/未知）——9 处字面量 |
| 2 | `tests/unit/core/test_status_convergence.py::test_all_status_values_are_reachable_from_enum` | **扫描基准** | 生产代码零裸字面量扫描的 9 值基准必须独立于被测枚举实现 |
| 3 | `tests/unit/core/test_status_contract.py`（`resolve_status_filter` 参数表末项） | **API 历史入参** | 旧前端/老书签发来的 `"现行"` 仍必须被接受并解析为 `Status.ACTIVE.value` |
| 4 | `tests/test_format_utils.py::test_sentinel_abolished_tokens_match_live_chinese_contract` | **解析/格式层（外部输入）** | `is_abolished_status("废止") is True`、`("现行") is False`——外部文本仍是中文 |
| 5 | `tests/unit/core/test_migrate_v61.py::test_sentinel_historical_default_matches_enum_value` | **DB 历史 DDL** | v2/v3 的 `DEFAULT '现行'`、v16 的 `DEFAULT '未知'`（P-106 不可改）必须仍等于枚举值 |

**为什么必须是"直写中文"**：若哨兵也写 `Status.ACTIVE.value`，则"枚举 value 被改成 `有效`"时哨兵会跟着一起变、永远通过——哨兵的价值恰恰在于**独立于被测实现**。这正是用户要求"保留硬编码"的原因（与 `EXPECTED_VALUES` 之类派生断言互补）。

#### 三、改动范围与红线遵守

| 红线 | 实测 |
|---|---|
| 禁止改生产代码（`pilotstd/`、`docker/`、`web/src/`） | `git status` 仅 `tests/` 下文件变更 ✓ |
| 禁止改 DB 迁移脚本 | 零改动 ✓ |
| 禁止为凑数字删测试 | 未删除任何用例；全量测试数 **4356 passed / 6 skipped**（改造前基线一致，无用例消失）✓ |

#### 四、验证

| 检查项 | 结果 |
|---|---|
| 全量测试（`tests/`，排除本地网络依赖挂起的 `tests/test_manager.py`） | **4356 passed / 6 skipped / 4 subtests passed**（266 s，`-n auto`） |
| 契约/字典/迁移单测 | `test_status.py`(17) + `test_status_convergence.py` + `test_status_contract.py`(25) + `test_migrate_v61.py`(7) 全绿 |
| Ruff / Mypy（门禁口径）/ G-020 / G-038 | 全 PASS（19 处因替换超长的测试行已按项目风格折行） |
| `check_all.sh --fast --guards --local` 与 `--deep` | 均 **EXIT=0**；G-032 保持 13 无新增 |
| CI（13 作业） | **13/13 success** |

#### 五、#32 四阶段总账（闭环）

| 阶段 | 批次 | 核心交付 | 量化 |
|---|---|---|---|
| A | R14-4a | 权威字典 + 9 处容器收敛 | 生产字面量 248 → 220（差额＝容器字面量入字典 9 处） |
| B | R14-4b | 后端业务字面量收敛（5 个原子 commit） | 运行时业务字面量 **211 → 0** |
| C | R14-4c | API 契约 + v61 迁移 + 前端键化 | 前端中文比较 **13 → 0**；schema 60 → 61 |
| D | R14-4d | 测试收敛 + 哨兵机制 | 测试字面量 **504 → 25**；哨兵 **5 处** |

**探针/脚本（不入库）**：`r14_4d_inventory.py`（tests/ 双口径盘点）、`r14_4d_wrap.py`（超长行自动折行）、`r14_4d_sentinels.py`／`r14_4d_sentinel4.py`（哨兵落地）。


### 7.32 R14-5：适配器模板状态字典同步 + 技术债台账归档整理与存续项校准

**执行方式**：两个任务同批完成（用户指定并行、各 0.5 周期）。

#### 一、任务一：Adapter 模板状态字典同步

| 项 | 内容 |
|---|---|
| 核心目标 | `pilotstd/templates/adapter/**` 内硬编码中文状态字面量 → 引用 `pilotstd.core.status.Status` |
| 改动 | ① 适配器主体模板：`status_map` 与兜底默认值改 `Status.*.value`（归一方向与原模板**逐字等价**）+ 新增 `from pilotstd.core.status import Status`；② 测试模板：夹具取值与断言改 `Status.ACTIVE.value` + 同样补 import |
| 未定/保留 | `fixtures/*_sample.json` 的 `"standardStatusName": "现行"` **刻意保留**——它模拟**外部站点报文**（被解析的输入，非代码常量），与 R14-4d 哨兵同理；模板内 `"现行有效"` 为站点自定义写法（**不在 9 值字典内**）亦保留原文 |
| 生成物验证 | 新增 `tests/unit/test_adapter_template_generation.py`（**10 例**）：`cookiecutter.json` 上下文 + jinja2 `StrictUndefined` 渲染 → **四种 `response_type` 分支**全部 `ast.parse` + `py_compile` + AST 扫描零裸状态字面量 + 生成物 import 行 `exec` 验证可解析 + 夹具 JSON 保留外部中文载荷 |
| 依赖说明 | 本仓库未把 `cookiecutter` 包列入依赖 → 用 jinja2 等价渲染（变量替换 + 目录改名语义一致），**不为 CI 增加新依赖**；真实 CLI 路径的缺口已登记为观察项 |

**模板缺陷（生成测试当场抓到并修复，3 类）**：

| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | 3 处伪占位符 `{{模板引擎.*}}` | cookiecutter 默认 `Undefined` 下**静默渲染为空串**（模块注释被吃掉） | 改为正确的 `{{ cookiecutter.* }}` 占位符 |
| 2 | **48 处 `-%}`** 尾随空白控制 | 吞掉换行与缩进 → **默认配置下生成的适配器就 `IndentationError`** | 统一改为 `%}`（控制标签独占行，渲染为空白行） |
| 3 | 1 处死条件 `[rec] if True  # … else mock_resp` | 生成物 `SyntaxError` | 按等价语义改写（`if True` 分支恒被选中，删死分支） |

**验证**：4 个 `response_type` 分支渲染后全部编译通过；生成测试 **10 passed**；`ruff check tests/` 全绿。

#### 二、任务二：台账归档整理 + 存续项校准 + 隐性债务显性化

| 动作 | 落实 |
|---|---|
| ① 已清理项归档 | 「一、已清理」更名为**历史归档**区并加状态导语；**#31 / #32** 的量化摘要复核无误（`save() 135→2`／构造 `133→1`／`get_profile 577→5ms`；`211→0`／前端 `13→0`／测试 `504→25`）；本批另归档 **T-26**（R12-8 随 #34 修复关闭）、**T-24**（L1/L2/L3 收口）、**R14-5 模板三缺陷**、**`vue-tsc` 假绿教训** |
| ② 存续项全量盘点 | **「二、剩余台账」实测 0 条**（#31/#32 均已闭环）并在本区明写；「三/三-B/四/五」分别加状态标注（**维持现状（已接受）／✅ 已实施／环境依赖保留（不排期）／已接受（8 条）**）；「六、观察项」**逐条加状态标签**（`观察中` 8、`观察中·计时中` 1、`待排期` 3、`待裁定` 1、`已收口·并入留痕` 2、`已修复·残留待排期` 1）并新增**状态汇总表**（项／状态／挂窗口／触发条件） |
| ③ 隐性债务显性化 | 复盘 R14 各批交付报告的"侥幸点／坑／可选未做项"，补登 **4 条**：SQL 文本内嵌 1 处状态字面量（AST 口径外）／cookiecutter CLI 未入依赖／本地网络用例挂起无超时兜底／`check_schema_consistency` 的测试建表约束无提示 |
| ④ 版本与链接 | 版本 **v1.43.0 → v1.44.0**（本簿自有序列；用户提示的"v1.71"对应 `gates.md` 版本线，已在报告差异表说明）；**内部链接检查：文件级死链 0 / 锚点级死链 0** |
| 交叉验证 | 代码层 `TODO/FIXME/HACK` 全库 **4 处**——`_attachment_parser.py:104`（已登记）、`scripts/check_g_030_tech_debt.py:6`（门禁脚本文档，非债）、`docker/requirements-docker.txt:28`（passlib/bcrypt 待上游修复，随本次纳入观察口径）、`pilotstd/scan/parser/__init__.py:200`（解析失败日志格式统一，低优先） |

**用户验收项对照**：① 活跃条目**全部**有明确状态标注（16/16，无模糊描述）✓；② 存续项数量与代码现状一致（剩余台账 0 条 + 观察项 16 条，与 TODO 扫描交叉验证）✓；③ 历史摘要数据与交付报告一致（#31/#32 数字均为各批报告实测值）✓；④ 内部链接可点击（死链 0）✓。