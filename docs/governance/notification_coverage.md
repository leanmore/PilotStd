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
| B-1 | **glossary 只登记 40 / 221 个 `notification.*` 键**（38 个事件的文案键未登记） | G-044 的"三语一致性"检测**只覆盖已登记键**；未登记的文案改了简体忘改繁体不会被拦 | 分批登记：优先高频事件（`scan_*` / `download_*` / `archive_*` / `validity_*`），每批 20–30 键。**不建议一次性全量**——术语表是"受控词汇表"不是"全量字典"，无限扩张会失去治理意义 |
| B-2 | e2e `EVENTS` 的 `module`/`level`/`aggregation` 字段为人工维护，无门禁校验其准确性 | 可能与实际构建器的 `level` 漂移（如实际 warning 而元数据记 info） | 可扩审计脚本做"元数据 vs 构建器常量"比对（需解析构建器 return 的 `level=`） |
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
| `audit_notification_chain.py` | — | 吞错/空文本风险 | ⏳ 未接入（存量 74 问题中 72 为误报，需先修判定逻辑） |
