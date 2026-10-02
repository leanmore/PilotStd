# 通知系统覆盖度基线

> 生成日期：2026-09-26 ｜ 审计工具：[`scripts/audit_notification_coverage.py`](../../scripts/audit_notification_coverage.py)
> 用途：**新增事件的准入基线**。任何新增通知事件必须在本表中达到三个维度全 ✅ 才允许合入。
> 本文档由脚本实际扫描生成，**禁止手工编辑矩阵行**——改代码后重跑脚本并同步本文件。

---

## 一、审计方法（三维度判定标准）

| 维度 | 数据源 | 合格标准 | 性质 |
|------|--------|---------|------|
| **i18n** | `pilotstd/i18n/{zh_CN,zh_TW,en}.json` | 该事件构建器调用的全部 `t()` 键在**三语中齐备** | 阻断 |
| **端到端测试** | `tests/test_notification_e2e.py` 的 `EVENTS` | 事件出现在 EVENTS 中，**且 `trigger_file` 物理存在** | 阻断 |
| **审计留痕** | 触发文件内的 `write_audit(` | **安全类**事件（`security_*` / `notification_credential_changed`）必须有；业务类标注 `N/A` | 阻断（仅安全类） |
| **术语登记** | `docs/governance/glossary.json` | 构建器键在术语表登记 | 跟踪（不阻断） |

**扫描实现**：全部用 AST（非正则）——`ALL_EVENTS` 是**带类型注解的赋值**（`ast.AnnAssign`），
且其元素是常量名（`EventDef(EVENT_X)`）而非字符串字面量，故需两段解析；`EVENTS` 列表用
括号配平 + `ast.literal_eval`。

**已验证的审计发现（本基线的直接产出）**：

| 发现 | 性质 | 处置 |
|------|------|------|
| `batch_query_summary` / `query_failed` / `query_empty` 的 `trigger_file` 指向**已不存在的** `pilotstd/manager/facade/_query_exec.py`（真实触发在 `_query_subsystem.py:230/246/251`） | 测试元数据失真——会让覆盖度断言"有触发点"变成假绿 | **已修** |
| `notification_credential_changed` / `security_password_changed` / `security_token_refreshed` 的 `trigger_file` 记为 `security_notifier.py`（投递管道），而安全动作与审计在 **API 端点** | 元数据失真——审计维度会误判为"无审计" | **已修**（改指端点） |

---

## 二、覆盖度矩阵（39 事件 × 4 维度）

图例：✅ 通过 ｜ ⚠️ 跟踪项未达标（不阻断）｜ ❌ 阻断缺口 ｜ N/A 业务事件无安全语义

<!-- BEGIN GENERATED MATRIX -->
| 事件 | i18n | 术语 | e2e | 审计 | 构建器 |
|------|------|------|-----|------|--------|
| `archive_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_archive_complete_message` |
| `standard_status_changed` | ✅ | ⚠️ | ✅ | N/A | `_build_standard_status_changed_message` |
| `standard_first_registered` | ✅ | ⚠️ | ✅ | N/A | `_build_standard_first_registered_message` |
| `announcement_fetch_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_announcement_fetch_complete_message` |
| `auto_backup` | ✅ | ⚠️ | ✅ | N/A | `_build_auto_backup_message` |
| `announcement_check_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_announcement_check_complete_message` |
| `batch_download_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_batch_download_complete_message` |
| `auto_scan_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_auto_scan_failed_message` |
| `validity_batch_report` | ✅ | ⚠️ | ✅ | N/A | `_build_validity_batch_report_message` |
| `validity_round_summary` | ✅ | ⚠️ | ✅ | N/A | `_build_validity_round_summary_message` |
| `validity_standard_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_validity_standard_failed_message` |
| `validity_system_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_validity_system_failed_message` |
| `image_update_available` | ✅ | ⚠️ | ✅ | N/A | `_build_image_update_available_message` |
| `batch_query_summary` | ✅ | ⚠️ | ✅ | N/A | `_build_batch_query_summary_message` |
| `trust_ip_update` | ✅ | ⚠️ | ✅ | N/A | `_build_trust_ip_update_message` |
| `worker_error` | ✅ | ⚠️ | ✅ | N/A | `_build_worker_error_message` |
| `date_reminder` | ✅ | ⚠️ | ✅ | N/A | `_build_date_reminder_message` |
| `download_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_download_failed_message` |
| `archive_abandoned` | ✅ | ⚠️ | ✅ | N/A | `_build_archive_abandoned_message` |
| `normalize_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_normalize_complete_message` |
| `scan_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_scan_complete_message` |
| `task_execution_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_task_execution_failed_message` |
| `scan_empty` | ✅ | ⚠️ | ✅ | N/A | `_build_scan_empty_message` |
| `query_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_query_failed_message` |
| `query_empty` | ✅ | ⚠️ | ✅ | N/A | `_build_query_empty_message` |
| `archive_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_archive_failed_message` |
| `announcement_fetch_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_announcement_fetch_failed_message` |
| `normalize_failed` | ✅ | ⚠️ | ✅ | N/A | `_build_normalize_failed_message` |
| `expire_standard_moved` | ✅ | ⚠️ | ✅ | N/A | `_build_expire_standard_moved_message` |
| `replacement_not_found` | ✅ | ⚠️ | ✅ | N/A | `_build_replacement_not_found_message` |
| `quota_exhausted` | ✅ | ⚠️ | ✅ | N/A | `_build_quota_exhausted_message` |
| `announce_fetch_summary` | ✅ | ⚠️ | ✅ | N/A | `_build_announce_fetch_summary_message` |
| `favorite_created` | ✅ | ⚠️ | ✅ | N/A | `_build_favorite_created_message` |
| `download_started` | ✅ | ⚠️ | ✅ | N/A | `_build_download_started_message` |
| `download_complete` | ✅ | ⚠️ | ✅ | N/A | `_build_download_complete_message` |
| `notification_credential_changed` | ✅ | ⚠️ | ✅ | ✅ | `_build_notification_credential_changed_message` |
| `security_password_changed` | ✅ | ⚠️ | ✅ | ✅ | `_build_security_password_changed_message` |
| `security_token_refreshed` | ✅ | ⚠️ | ✅ | ✅ | `_build_security_token_refreshed_message` |
| `security_login_failed` | ✅ | ✅ | ✅ | ✅ | `_build_security_login_failed_message` |
<!-- END GENERATED MATRIX -->

**汇总**：i18n **39/39** ｜ e2e **39/39** ｜ 安全事件审计 **4/4** ｜ 术语登记 **1/39**（跟踪项）

---

## 三、缺口分类与处置

### A 类（必须修）——**本批已清零**

| # | 缺口 | 处置 |
|---|------|------|
| A-1 | 3 个事件 `trigger_file` 指向已删除的 `_query_exec.py` | 已修正为 `_query_subsystem.py` |
| A-2 | 3 个安全事件 `trigger_file` 记为投递管道而非触发端点，致审计维度误判 | 已修正为对应 API 端点 |

**结论**：i18n 键齐备率 39/39、e2e 覆盖率 39/39、安全事件审计 4/4——**A 类为零**。

### B 类（建议修，本批仅记录）

| # | 缺口 | 影响 | 建议 |
|---|------|------|------|
| B-1 | **glossary 只登记 40 / 221 个 `notification.*` 键**（38 个事件的文案键未登记） | G-044 的**三层检查覆盖范围不同**（源码核实：`check_terminology.py:_check_key` / `_check_term_consistency`）：① 三语**存在性**与 ② 禁用词/别名 -> **全部 221 个作用域内键**（作用域外 478 键不检查）；③ 术语三语**值与术语表严格相等** -> **仅 40 个登记键**。故其余 181 键的**值**无标准答案可比对（改简体忘改繁体不会被拦），但键**存在性**已全量校验 | 分批登记：优先高频事件（`scan_*` / `download_*` / `archive_*` / `validity_*`），每批 20–30 键。**不建议一次性全量**——术语表是"受控词汇表"不是"全量字典"，无限扩张会失去治理意义 |
| B-2 | e2e `EVENTS` 的 `module`/`level`/`aggregation`/`builder_keys` 字段为人工维护，**G-045 只校验 `trigger_file` 的存在性**，其余字段未校验 | 元数据可能与构建器脱节。**但 `level` 已于本批做集合精查（AST 语义遍历）：39 事件声明集合与构建器实际分支集合完全一致，零漂移**。注意 `level` 用 `a/b` 表示**可产出集合**（如 `info/warning` = 按分支取 info 或 warning），把它当单值读会得出错误的"漂移"结论 | 若扩审计脚本比对：须按**集合**比对，且构建器 level 可能经局部变量传递（`level = ...` 再 `level=level`），正则提取会漏——必须走 AST |
| B-3 | 测试覆盖为"事件级"而非"渠道级"：仅 `batch_download_complete` 等少数事件有逐渠道渲染断言 | 新增渠道或改渲染器时，多数事件无跨渠道回归网 | 按渠道补渲染断言（`tests/test_notification_renderer.py` 已有基础设施） |

### C 类（设计如此，不予修复）

| # | 项 | 理由 |
|---|----|------|
| C-1 | 35 个业务事件的审计维度为 `N/A` | 业务通知（扫描/查询/下载/归档/时效性/公告）**无安全语义**，写 `audit_logs` 只会淹没真正的安全事件。审计的价值来自稀缺性 |
| C-2 | 安全告警经 `NotificationManager`（硬编码 `user_id=1`）定向 | 告警目标是**系统所有者/管理员**，而非触发操作的用户——这是正确语义。per-user 投递属已登记技术债（设计文档 D-1） |
| C-3 | `notification_credential_changed` / `security_password_changed` / `security_token_refreshed` **不由** `send_event` 投递 | 第 2 批方案 A：凭证类告警必须在**新凭证落库前**送达**旧**渠道，`send_event` 的聚合缓冲与静音时段会把告警推迟到落库之后 → 流向攻击者。故它们**有意豁免** e2e 的"必须有 send_event 触发点"契约（见 `SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED`），改由 `security_notifier` 直连临时渠道同步 `send()` |
| C-4 | 登录失败告警阈值硬编码 `LOGIN_FAILURE_ALERT_THRESHOLD = 5` | 与限流闸门 `MAX_ATTEMPTS=100` **故意解耦**（后者为压测放宽）。**不应**做成用户可写配置——否则攻击者可调高阈值关闭告警 |

---

## 四、新增事件准入检查清单

新增一个通知事件时，必须逐项完成（缺任一项则 e2e 契约或本审计会 FAIL）：

- [ ] **1. 注册事件**：`pilotstd/core/notification/events.py` 加 `EVENT_X` 常量 + 加入 `ALL_EVENTS`
- [ ] **2. 构建器**：在对应 `_builders_*.py` 加 `_build_x_message(data)`；文案一律 `t("notification.<category>.<event>.<field>")`，**调用期取 `t()`**（模块级求值会把语言固化）
- [ ] **3. 重导出与映射**：`_message_builders.py` 加导入；`manager._init_event_builders` 加 `"x": _build_x_message,`（键名与事件名一致）
- [ ] **4. i18n 三语齐备**：`pilotstd/i18n/{zh_CN,zh_TW,en}.json` 同步加键，**占位符集合三语必须一致**
- [ ] **5. 术语登记**：`docs/governance/glossary.json` 加条目（含 `keys`），随后跑 `check_terminology.py`
- [ ] **6. 默认渠道规则**：若事件应默认投递，在 `defaults.py` 加 `notification.rules.<event>`——否则策略表为空时回退 config 也拿不到渠道，事件"注册了但发不出去"
- [ ] **7. e2e 契约**：`tests/test_notification_e2e.py` 的 `EVENTS` 加条目（`name`/`module`/`level`/`aggregation`/`trigger_file`/`builder_file`/`builder_method`/`builder_keys`）；**`trigger_file` 必须真实存在且含触发方**
- [ ] **8. 安全类额外要求**：触发文件必须调用 `write_audit`；若因时序要求绕过 `send_event`，需加入 `SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED` 并写明理由
- [ ] **9. 跑门禁**：`audit_notification_coverage.py`（G-045 本基线）+ `check_terminology.py`（G-044）+ `check_sensitive_endpoint_audit.py`（G-043，若涉及敏感端点）

---

## 五、门禁接入状态

| 工具 | 编号 | 阻断 | 接入位置 |
|------|------|------|---------|
| `audit_notification_coverage.py` | **G-045** | 阻断缺口 → 退出码 1 | ✅ `check_all.sh --fast` + `ci.yml`（紧跟 G-044） |
| `check_sensitive_endpoint_audit.py` | G-043 | 敏感端点缺 `write_audit` | ✅ `check_all.sh --fast` + `ci.yml` |
| `check_terminology.py` | G-044 | 禁用词命中 / 术语三语不一致 | ✅ `check_all.sh --fast` + `ci.yml` |
| `audit_notification_chain.py` | **G-046** | 静默吞错 / 空文本风险 / 缺空值守卫 | ✅ `check_all.sh --fast` + `ci.yml`（紧跟 G-045，**问题数 79 → 0** 后接入） |

**三个已接入门禁均打印 `[覆盖摘要]`（L-23）**：PASS 之后追加五段式摘要（`范围` /
`检查项` / `检查口径` / `豁免明细`或`跟踪项明细` / `未覆盖说明`），显式声明**检查了什么、
豁免了什么、没检查什么**——否则 PASS 会掩盖空洞（G-044 的术语三语值校验只覆盖
40 个登记键、G-043 的 7 项豁免、G-045 未校验的 `level`/`module`/`aggregation`/`builder_keys`）。

**豁免/跟踪**必须以**逐条名单**呈现，不能只给计数——三处门禁的豁免数据源都可枚举：
G-043 的 7 项待接入路由（含理由）、G-044 的 16 个豁免键 + 10 个豁免词、
G-045 的 38 个未登记术语表的事件。段标题按语义区分（G-045 用「跟踪项明细」）。
格式实现见 `scripts/_gate_coverage_summary.py`（三处门禁共用，改动须同步三处），
契约由 `tests/test_gate_coverage_summary.py`（12 例）锁定。

---

## 六、已修复的遗留项

| # | 遗留项 | 状态 | 修复方式 |
|---|--------|------|---------|
| 1 | **`i18n._lang` 模块级全局导致线程/异步串扰** | ✅ **已修复**（2026-09-26 专项） | `pilotstd/i18n/__init__.py` 的语言状态由模块级 `_lang`/`_current` 改为 `contextvars.ContextVar`；新增 `language()` 上下文管理器（嵌套安全 + 异常路径恢复）；新增 `SUPPORTED_LANGUAGES` / `DEFAULT_LANGUAGE`，非法语言码回退默认并告警。原实现下"另一线程 set_language 会改写本线程看到的语言"，而通知构建器/渲染器/聚合器都在 `ThreadPoolExecutor`（6 文件）与 `asyncio`（8 文件）中调用 `t()`。契约由 `tests/test_i18n_thread_safety.py`（17 例）锁定，其中"子线程免疫其它线程的语言写入"用例经对照实验确证有判别力（旧实现 6/6 被污染）。 |
| 2 | **`_on_timer` 续期末轮跨越硬上界** | ✅ **已修复**（2026-09-26 专项） | `notification/aggregate_buffer.py::_on_timer` 的续期由「固定完整窗口」改为「`min(窗口, 到上界的剩余时间)`」，并在剩余不足 `min(窗口×0.1, 0.05)` 时直接强制发送。**缺陷上界**：`elapsed < MAX` 只保证"下一次续期会超时"，那次续期可能跨过上界**最多一个窗口 w** → 越界上界 `MAX + w`（生产 `w=5s/MAX=300s` 即 305s）。**实测判别**：`window=0.2s/max=0.3s` 时旧实现 409ms（越界 109ms）→ 新实现界内；`tests/test_scheduler_timer_drift.py` 对该比例 1 FAIL / 其余 13 pass。同批把两条发送路径统一移到**锁外**（原早退路径在 `with self._lock` 内发送），并新增"强制发送偏差 ms"告警日志与"续期下次触发时刻"调试日志。**过程更正**：专项前两次分析各错一次——先误判"必然越界一个完整窗口"（`w=5s/MAX=300s` 整除时不越界），后误判"旧实现永不越界"（由整除特例错误推广）；结论以上述实测比例为准。 |
| 3 | **`_extract_topic` 主题分组跨语言失效** | ✅ **已修复**（2026-09-26 专项） | `core/notification_aggregator.py::_extract_topic` 原用**简体中文关键词**猜测主题，故 `失败`（zh_CN）命中而 `失敗`（zh_TW）不命中、英文标题全不命中，其余落到「标题前 8 字符 + `_`」兜底 → **同一事件在不同语言下归入不同分组**；实测 **46 个标题变体 × 3 语言中 65 条**落兜底。修法改为 **i18n 契约驱动**：扫三语语言包取 `notification.*` 下全部 `.title*` 键（47 键，实测 **39/39 可映射到事件**，唯一无关键是 `notification.channel.test.title`），建立「标题 → 主题」**精确索引（134 条）+ 9 条模板正则**（覆盖 `第 {round} 轮…` 裸值占位符与 `Scan Complete ({failed} unrecognized)` 计数形态）；生成正则时**仅把紧邻占位符的字面空白转为弹性 `\s*`**——否则占位符取空值时「通配符与字面空格争抢同一空格」会让 `Scan Complete ( unrecognized)` 失配（该缺陷由第三轮审核带出；首次修复用「折叠空白」机制错误且不生效，已改为弹性空白，实测完整形正则独立命中）；「括号去掉」变体**只针对含占位符的括号组，并连同其前导空白一并删除**——否则英文会留下尾随空格（`Scan Complete `）而与静态标题字面`Scan Complete` 不相等，成为**死正则**（第五轮审核发现；中英原本不对称）；**构建期冲突检测**——同一标题若推导出不同主题则告警（实测 0 冲突）。原简体关键词表保留为回退层（自定义标题向后兼容）。**终检（用渲染器同款 `str.format` 构造样本）**：标题变体（三语合计）**138 = 静态 132 + 动态 6**；动态 6 变体 × 12 取值 = 72 样本；**总样本 204，兜底 0**；跨语言主题不一致事件 **0**。**测试有效性前提**：样本必须用 `str.format` 而非 `re.sub` 构造——后者会产出渲染器**不会产出**的形态（如 `Scan Complete ()`），据此断言属无效验证（曾因此得出错误结论）。**实际生效范围（实测）**：全库唯一调用点，平台层调用方传 `_("download_results_title")` 这类静态键，故现实收益是"UI 切繁中/英文后分组重新正确"。**边界现状**：`第 {round} 轮…` 取空串渲染为双空格亦**能命中**（弹性空白覆盖），但该输入实际不可达（调用方恒传 `round = round_count + 1 ≥ 1`）；非 i18n 自定义标题的跨语言合并**不在范围内**（`TestCustomTitleBoundary` 锁定）。契约由 `tests/test_notification_aggregator_topic_i18n.py`（**53 例**）锁定。同批确认 `_BUFFER_WINDOW = 0.3s` **设计意图正确、不变更**——桌面 toast 合并窗口，与服务端 `DEFAULT_WINDOW_SECONDS = 5.0s` 分属两条独立链路（`TestBufferWindowIntent`）。 |

### L-01：敏感端点审计（G-043 升级为函数级判定）

- **判定升级**：G-043 原为**模块级**判定（同文件任一端点有 `write_audit` 即整模块通过），
  实测该口径对 4 个敏感路由"通过"是**对的但理由不全对**：其中 3 个（`update_config` /
  `api_change_password` / `login`）的审计**经同模块辅助函数**实现
  （`_persist_config_and_audit` / `_audit_password_change` / `_notify_login_failure`），
  故"只看函数体"会**假 FAIL**；而"展开同模块全部辅助函数"又会因
  `trigger_cleanup → get_stats` 这类非审计调用**假 PASS**。
  → 采用 **`AUDIT_WRAPPERS` 显式注册表**（当前 8 条，含 `write_audit` 本体）+
  `validate_wrappers()` 自校验（每条必须真的调用 `write_audit`）。
  **本方案以人工维护注册表换取判定精确性，不是消除依赖**。
- **接线范围**：`EXEMPT_ROUTES` 由 7 项**清空为 0**——6 项 P1/P2 端点（用户增删 / 自助注册 /
  日志批删 / 缓存清理 / 手动备份）共 **24 处出口**（成功 8 + 失败 16，按 HTTP 状态码区分）
  全部接入审计；`POST /query` 本就函数可达 `write_audit`，移出豁免。
- **B 类补漏（出口级，非端点级）**：两个已合规端点内部各有一处遗漏出口——
  `notification.py` 的掩码字段预校验失败（400）补 `NOTIFICATION_CREDENTIAL_CHANGE_REJECTED`；
  `auth.py` 的锁定超限（429）补 `LOGIN_ATTEMPT_BLOCKED`（含 **S2 时间闸门**去重：
  该路径不写 `login_attempts`，计数停滞在阈值上，故不能用"恰好等于阈值"判断）。
- **L2（出口覆盖）的定位：《接线约定，不进入 G-043 判定》**
  G-043 只做 **L1（函数可达 `write_audit`）**。"产生状态变更的出口"无法纯静态判定
  （需理解语义），故 L2 由**接线时遵守 + 测试断言**承担，而非门禁。
  **本批 24 处接线已按 L2 处理**。

### L-08：`audit_notification_chain.py`（G-046）

- **判定缺陷与修复**（问题数 **79 → 0**）：
  1. **A-1 `empty_text_risk` 是恒真式**：`(not has_body_kwarg) or empty_return`——40 个
     构建器**无一填写 `body`**（正文载体是 `blocks`）→ 40/40 全误报；且没看 `blocks`/`title`，
     而 `manager.py` 的硬约束是三者**至少一项非空**。改为"三者皆空才报"。
  2. **A-2 `missing_null_guard` 过粗 74.8%**：只认 4 种窄形态，漏掉 `data.get(f, DEFAULT)`、
     正向真值判断、`or` 兜底（含推导式内）、类型强转、裸下标、作为可空 dataclass 字段传入。
     判定边界重新界定为"**字段无保护却进入 `str.format()`**"（此时 `None` 会渲染成 "None"）。
  3. **A-3 不解析 `EVENT_*` 常量**：构建器侧与调用点侧均修复（共享常量符号表）；
     无法静态确定者标 `<dynamic>`（**不臆造解析**）。
- **接入**：`ci.yml` 与 `check_all.sh` 的 **G-046**（紧跟 G-045），`--strict`，
  **零基线**——问题数为 0，任何新发现立即阻断（P-104 门禁不绕过）。
- **判别力验证**：`tests/test_audit_notification_chain.py`（40 例）按"好形态不报 + 坏形态必报"
  成对设计；注入修复前形态（A-1 恒真式 / A-2 窄形态 / A-3 只认字面量）分别使
  3 / 4 / 1 个用例 FAIL。

### 未修复（仍在册）

| # | 项 | 归属 |
|---|----|------|
| 4 | B-1 术语登记率 40/221、B-2 EVENTS 元数据无校验、B-3 测试为事件级非渠道级 | §三 |
| 5 | ~~`audit_notification_chain.py` 未接入 CI~~ | ✅ **已修复**（L-08，第 13 批）：判定逻辑修复后问题数 **79 → 0**，已接入 `ci.yml` 与 `check_all.sh` 为 **G-046**（零基线） |
| 6 | `DesktopRenderer` 字段名前缀（第 7 批论证不应加） | 待裁决 |
| 7 | **`desktop_toast` 未登记进 `ALL_EVENTS`**（G-045 盲区） | 见下方 L-22 专项 |

### L-22：`desktop_toast` 未登记进 `ALL_EVENTS`

- **性质**：`desktop_toast` 是 L2 桌面协调层向 L1 服务端聚合器投递时使用的标签（唯一产出点 `pilotstd/core/notification_aggregator.py:537` 的 `self._new.push(...)`），**不经 `manager.send_event`**，且**无独立构建器与 i18n 键**——其标题/正文由上游传入（如 `pilotstd/ui/core/handlers/_download.py:286` 传 `_("download_results_title")`），故多语言能力**继承自上游事件**，而非"没有 i18n 支持"。
- **当前处置：方案 B（不登记）**——G-045 的 `[覆盖摘要]` 中显式声明该事件未覆盖，使 PASS 不再掩盖此盲区。不登记的理由：登记会**必然即红**（无 e2e `EVENTS` 条目 → G-045 阻断；无构建器 → i18n 维度判 False；`assert len(EVENTS)` 硬编码），需一次性改 6 个文件并引入"平台层事件"新分类。
- **方案 A 触发条件**（满足任一即须实施）：
  1. 引入**第 2 个平台层事件**时——否则每加一个都要改摘要声明，声明本身会腐化；
  2. 当 G-045 的覆盖度矩阵需要**按投递入口分组统计**时（方案 B 无法区分"`send_event` 产出"与"平台层直接构造"）。
- **方案 A 成本**：约 34 行 / 6 文件（`events.py` ×2、`test_notification_e2e.py` ×3 处、`audit_notification_coverage.py`、本文件）。
