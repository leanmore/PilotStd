# 技术债 · 技术上无解 / 已接受（含不还的代价）

> 本文件是 `docs/technical-debt.md` 四分类之一：**已接受**（维持现状、已跳过测试、已接受的设计决策、审计结论固化）。
> 判据：受语言/框架/外部系统限制，或成本 > 风险 —— 处置是"写明限制 + 记下不还的代价 + 绑定重评触发条件"，**不排期**。
> 回主档：[technical-debt.md](../technical-debt.md) ｜ 另三类：[01-archive-closed.md](01-archive-closed.md)（已完成）、[03-open.md](03-open.md)（可修未修）、[04-watch.md](04-watch.md)（已修待观察）


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

## 五、已接受的设计决策（7 条，每条含不还的代价）

> **状态：已接受（7 条，不挂窗口）**——**R15 归档 2 条**：#4（Mixin 拆分大文件，ADR-010 已 Deprecated）与 **#6（JWT_SECRET，已改为落盘复用）**。——每条均写明"不还的代价"与重评估触发条件。原 #4（Mixin 拆分大文件）已于 **R15 归档**（ADR-010 已 Deprecated、全库 Mixin 仅剩 `_WindowLifecycleMixin` 1 个，见「一、已清理」）。未来若多用户/对外开放，优先复核 #2（静态令牌无 TTL）、#7（内存会话）、#8（WebSocket 无用户级路由）。

> **2026-10-05 新增：pnpm 缓存收敛 —— WONTFIX · 永久关闭**（决策者当日裁定）。**原案**：把 pnpm store 收敛到项目盘（缓和 C 盘占用）。**未实施原因（实测）**：本机 PowerShell 执行策略禁止运行 `pnpm.ps1`（`SecurityError`：在此系统上禁止运行脚本；`Get-ExecutionPolicy -List` 全作用域 `Undefined`）。**裁定**：**不再考虑、不再处理、不再纳入任何排期**（属环境侧政策限制，非工程可解）；**后续追溯以此条为准**——本条不属"债"，不给编号（按本簿登记规则，避免"为消编号而做"）。**不还的代价（已接受）**：C 盘 pnpm store 占用保持现状；若将来环境策略放开且确实需要，再作为**新事项**重新评估（不得援引本条为"待办"）。

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

### 审计结论固化（2026-10-03，大阶段 5 审计；**不新起编号**）

> 目的：把一次性审计的**结论 + 为什么不处理 + 何时才处理**固化下来，未来碰到这些文件时不必重新侦查。
> 落点说明：本节为既有观察区（§六），按「真·观察项复核表」同款口径记录（保留理由 / 触发条件），
> **不给编号**——按登记规则，观察项不属债，给编号会诱导"为了消编号而做"。

#### A. 中文参与逻辑分支审计（全库 AST 扫描，27 处）

**结论（实测）**：**高危 0 / 中危 12 / 低危 15**（合计 27）。
> 口径修正披露：上一批交付报告初写"中危 9 / 低危 18"，本轮按 AST 命中逐条复核为 **12 / 15**（总数 27 不变），
> 以本节为准（前者为分类时的口径抖动，非审计遗漏）。

**为什么不处理**：
- **高危 0** ⇒ 无 T-39 同类问题（T-39「用渲染后的展示标题做逻辑判定」已清偿）。
  专项佐证：全库扫「`t()`/`_()` 渲染值 == 中文」模式命中 **0 处**（正则报出的 2 处经查是
  `rl.get_text(`/`item.text(` 的误判）；
- **中危 12** ⇒ 属"**措辞耦合**"隐患而非功能缺陷：比较两侧都是**本仓常量**（同一份代码写入、同一份代码比较），
  当前语言下可用；给编号会诱导"为了消编号而做"；
- **低危 15** ⇒ 匹配**外部站点内容**、**数据字典**或**防御性复核**，本就不应 i18n。

**位置清单（中危 12）**：
| 位置 | 现状 | 分类 |
|---|---|---|
| `pilotstd/ui/core/handlers/_archive.py:275` | `if status != "已归档"`（status 来自归档引擎结果元组） | 中危 |
| `pilotstd/ui/core/handlers/_download.py:268` | `if status == "已下载"`（status 取自工作表单元格文本） | 中危 |
| `pilotstd/ui/core/handlers/archive_flow_engine.py:102` | `s == "已归档"`（统计成功数） | 中危 |
| `pilotstd/ui/core/handlers/archive_flow_engine.py:127` | `status != "已归档" and …`（写 file_index 前的判定） | 中危 |
| `pilotstd/ui/main_window/parts/_query_ops.py:35` | `result.replaces != "网站无此分类"` | 中危 |
| `pilotstd/ui/main_window/parts/_query_ops.py:36` | 同上（`publish_date`） | 中危 |
| `pilotstd/ui/main_window/parts/_query_ops.py:37` | 同上（`implementation_date`） | 中危 |
| `pilotstd/ui/main_window/parts/_query_ops.py:38` | 同上（`responsible_dept`） | 中危 |
| `pilotstd/services/favorite_chain_processor.py:170` | `"无法获取下载链接" in text`（按中文错误文案分支） | 中危 |
| `pilotstd/services/favorite_chain_processor.py:176` | `"数据库操作失败" in text`（同上） | 中危 |
| `pilotstd/services/favorite_chain_processor.py:178` | `"归档超时" in text`（同上） | 中危 |
| `pilotstd/services/favorite_chain_processor.py:181` | `"超时" in text`（同上） | 中危 |

**位置清单（低危 15）**：
| 位置 | 现状 | 分类 |
|---|---|---|
| `pilotstd/announcement/_content_cleaner.py:193` | `stripped.startswith("序号")`（清理**外部公告正文**） | 低危 |
| `pilotstd/announcement/_content_cleaner.py:205`（2 处） | `startswith("中文名称："/"中文名称:")`（同上） | 低危 |
| `pilotstd/pipeline/router.py:324` | `any("一" <= c <= "鿿" …)`（**CJK 码点区间**判断，非字面量比较） | 低危 |
| `pilotstd/query/adapters/csres.py:164` | `"标准编号" in rows[0].get_text()`（解析**站点页面**） | 低危 |
| `pilotstd/query/adapters/csres.py:280` | 同上 | 低危 |
| `pilotstd/query/adapters/sppt_local.py:112`（2 处） | `"重新登录" in resp.text or "会话过期" in resp.text`（站点响应判定） | 低危 |
| `pilotstd/query/adapters/std_gov.py:167` | `rl.get_text(strip=True) == "采"`（表格单元格内容） | 低危 |
| `pilotstd/query/engine/_single.py:327` | `"采标" in result.status`（领域状态） | 低危 |
| `pilotstd/query/routing/router_v2.py:223` | `level1 == "特色"`（站点分类**数据**） | 低危 |
| `pilotstd/query/routing/router_v2.py:227` | `level2 == "全综合"`（同上） | 低危 |
| `pilotstd/scan/edition_detect.py:50` | `language == "中文版"`（版本字符串判定） | 低危 |
| `pilotstd/scan/edition_detect.py:58` | 同上 | 低危 |
| `pilotstd/ui/main_window/parts/_table_ops.py:242` | `item.text() == "采标"`（同文件 238 行**写入同一字面量**，属冗余复核） | 低危 |

**何时才需要处理（触发条件）**：
- **中危**：**所在文件因其他改动被触碰时顺手收敛**为常量/枚举（**不做专项批次**）；
  若某处在**非中文语言**下被证实逻辑失效（复现路径可写入用例）⇒ **升级为高危，立即处理**；
- **低危**：**不处理**（外部内容匹配与数据字典本就与语言无关）。

#### B. G-010 五个 >400 文件的处置决策（按离 500 阻断线最近者先）

| 条目（实测有效行） | 决策 | 为什么现在这样做 | Review_Trigger（何时重新评估） |
|---|---|---|---|
| `scripts/docs_sync_check.py`（489） | **不拆**（⚠️ **已被 T-41/2 取代**：2026-10-06 用户立项 T-41 将该脚本列入清单并**已拆分** ⇒ 现 **483 原始行**、有效行退出 >400） | **G-031 门禁自身的入口**（pre-commit 按路径调用 + CI 步骤 + 测试三处引用）；489 未越 500 阻断线；四类职责（变更来源解析/文档映射/改写/CLI）耦合于同一流程，拆点不净 ⇒ 收益（计数）与风险（门禁行为）不成比例 | **接近阻断线**（≥490）或 **G-031 行为变更需要触碰该文件**时 ⇒ **先补行为回归用例再拆** |
| `scripts/audit_notification_chain_scan.py`（464） | **不拆**（⚠️ **已被 T-41/2 取代**：同上，**已拆分** ⇒ 现 **396 原始行**） | 与上一条同性质（CI 直接调用的审计脚本，且有配套测试锁输出） | 同第一条；建议与第一条**同批专项** |
| `pilotstd/core/notification_aggregator.py`（448 → **已 < 400**） | **已拆**（提交 `b51ad54d`） | 数据段（主题索引）外移到同级 `_topic_index.py` + `topic_index_data.json`，接口零变更；G-010 警告由 5 条降为 4 条 | —（已闭环，无触发条件） |
| `pilotstd/core/db/_migrate_v16_v49.py`（438） | **永久不拆** | **P-106**：已执行迁移函数源码不可变（`inspect.getsource` 哈希）；拆分只能"逐字符原样移动"，收益仅计数，风险是迁移链完整性与哈希不变式 | **永不**（除非迁移链本身要变更时另行评估） |
| `web/src/components/AppLayout.vue`（420） | **不拆（就近做）**（⚠️ **已被 T-41/6 取代**：2026-10-07 随前端子批**已拆分** ⇒ 现 418 原始行、**有效行退出 >400**，逻辑入 `useAppLayout.ts`） | 拆分需新增子组件并回归 `vue-tsc` + vitest（组件/布局用例）；420 距阻断线 80 行 | **下次前端功能改动**时顺手拆；届时**单独查**"自测 452 vs 门禁 420"的口径差异（注释/模板行计法，属 R1 类口径差异） |

#### C. 观察项（**不编号**，登记待观察）

| 条目 | 为什么记 | 为什么现在不做 | Review_Trigger（何时推进） |
|---|---|---|---|
| **主题判定改为「事件键优先、关键词兜底」**（大阶段 5 审计建议 2） | 是**设计改进**（可绕开中文匹配、减少语言相关性），不是债 | 当前实现有 i18n 契约表兜底（`_TOPIC_BY_EVENT` 41 条 + 跨语言兜底 10 组），行为已被 `tests/test_notification_aggregator_topic_i18n.py` 锁定 | 作为**待排期设计改进**推进；推进时**先 grep 编号**（按登记规则取空号），不沿用本节的"不编号"口径 |
| **中危 12 处「措辞耦合」** | 见内容 A（两侧皆本仓常量，当前可用，非功能缺陷） | 给编号会诱导"为了消编号而做"；且专项批次收益低于就地收敛 | 见内容 A 的触发条件（**文件被其他改动触碰时顺手收敛**；若在非中文语言下被证实失效 ⇒ 升级高危立即处理） |

> **2026-09-27 结构重整**：已闭环的 5 行按归属移出——「单条网络请求/大文件 IO 不可中断」（✅ 已接受）与「`_migrate_v59_…` docstring 过时」（✅ 已决定不改）→「五、已接受的设计决策 · 归档并入」；「拆出新模块时注释密度被稀释」（✅ 已落实）、「#23 合并前侦察未覆盖全组合」（✅ 已落实）、「#27 gates.md 版本历史两行挤在同一物理行」（✅ 已修复）→「一、已清理 · 归档并入」。本节现只保留**仍未闭环**的观察项。 **2026-09-27（R11-5）补记**：**T-20 已 ✅ CLOSED**（R11-4 实测证伪原假设 + 交付基线/普查工具），按本节规则移入「一、已清理」；其剩余可治理项拆为 **T-29**（8 处永久 `mark.skip`，挂第十二轮）。 **2026-09-27（R12-2b）补记**：**T-28 亦 ✅ CLOSED**（`-rs` 已覆盖全部 5 处 pytest 调用，CI 日志实证 44 条跳过明细），同样移入「一、已清理」。 **2026-09-27（R12-4a）补记**：**T-32 亦 ✅ CLOSED**（L1 触发式已覆盖 `.pyi/.pyw`，双向受控验证通过），同样移入「一、已清理」。 **2026-09-27（R12-8）补记**：**T-26（#34 复发哨兵观察项）随 #34 修复而关闭**——新哨兵转为：任何 GUI 作业再现 access violation → 立即重跑 `gui-race-probe`（loops=50）并回溯是否引入新的 Qt 锁／线程 churn 模式。 **2026-10-01（R14-5）校准**：**T-26 与 T-24 两行自本节移入「一、已清理」**（前者 R12-8 已关闭、后者 L1/L2/L3 全部落地收口），本节仅保留仍未闭环的观察项；同时新增 4 条 R14 复盘发现的隐性债务（SQL 内嵌状态字面量／cookiecutter CLI 未入依赖／本地网络用例挂起／schema 一致性门禁约束无提示），并给每条加状态标签 + 汇总表。

---

