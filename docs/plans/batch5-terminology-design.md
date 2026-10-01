# 第 5 批方案设计：术语表 + 禁用词门禁

> 编写日期：2026-09-26
> 编写方式：先实地扫描全部 i18n 语言包与测试断言，再出方案（R-004 实证优先 / P-105 先实测后交付）
> 状态：**设计文档，本轮零代码改动**
> 关联：[notification-refactor-design.md](notification-refactor-design.md) §3（任务 3：通知用语统一性治理）

---

## 〇、侦察方法与可复现声明

所有数字来自对本仓库的实读扫描，无推断。

| 扫描项 | 方法 |
|--------|------|
| 语言包规模与三语差异 | `json.load` 三份 `pilotstd/i18n/*.json`，求键集合差集 |
| 竞争译法 | 对 `zh_CN` 值做概念域关键词族计数（`归档`/`保存`、`废止`/`作废`/`失效`/`过期` 等 11 组） |
| 同义键精确冲突 | 按语义配对取键值直接比对（如 `notification.archive.archive_complete.title` vs `save_results_title`） |
| 禁用词候选 | 29 个探针词（技术黑话 / 内部代号 / 客套话 / 相对时间 / 敏感表述）全文匹配 |
| 快照断言影响面 | 两步收窄：① 取 `zh_CN` 中"无占位符 + 含中文 + 4–40 字"的 369 个展示型文案值；② 在 `tests/**/*.py` 的 `assert` 行内做**精确子串匹配** |

**重要更正**：粗粒度扫描（`assert` 行含任何中文）得到 1264 处 / 210 文件，但其中绝大多数是**断言消息**（`assert x, "扫描后应有已解析标准"`）与**领域数据**（标准名、CSV 表头），**不随文案变更而失败**。收窄到"精确匹配 i18n 文案值"后为 **97 处 / 43 文件**；再收窄到"本方案实际要改的 5 类文案"后仅 **7 处 / 4 文件**（见 §D）。

---

## Task 5.1：侦察结果

### 1.1 规模

| 语言 | 键数 |
|------|------|
| `zh_CN` | **686** |
| `zh_TW` | **603** |
| `en` | **682** |

其中 `notification.*` **208 键**（通知/渲染/聚合/渠道/安全告警），其余 **478 键**为历史扁平键（`btn_*` / `msg_*` / `col_*` / `title_*` 等 UI 文案）。

**三语差异（既有缺口，非本批引入）**：`zh_TW` 缺 **83** 键、`en` 缺 **4** 键（`announcement_failures`、`btn_use_query_name`、`btn_use_source_name`、`title_name_conflict`）。三语均无多余键。

> **本批须先决断**：门禁若要求"术语表覆盖的键三语齐备"，则启动前必须先补这 87 个键（否则门禁一上线即红）。见 §E-2。

### 1.2 竞争译法（实证）

| 概念域 | 变体 | 键数 | 判定 |
|--------|------|------|------|
| 文件入库动作 | `归档` / `保存` | 24 / 29 | 🔴 **真实漂移**：同一动作两个词，且**同一事件的两处文案用不同词** |
| 标准失效态 | `废止` / `作废` / `失效` / `过期` | 11 / 4 / 4 / 7 | 🔴 **真实漂移**：`废止` 与 `作废` 在**同一个键值串**里并存（见 1.3） |
| 错误语义 | `失败` / `错误` / `异常` | 57 / 7 / 4 | 🟡 部分合理（`失败`=业务失败、`异常`=系统异常），但边界未定义 |
| 文件名不可解析 | `无法识别` / `未识别` | 6 / 5 | 🔴 **真实漂移**：同一场景两个词 |
| 站点查询无果 | `未查询到` / `未命中` | 6 / 1 | 🟡 `未命中` 仅 1 处（孤例，且是技术味用词） |
| 通知类名词 | `通知` / `提醒` / `消息` / `告警` | 11 / 4 / 3 / 5 | 🟡 `提醒`/`告警` 有明确子语义（日期提醒、安全告警），`消息` 3 处宜并入 `通知` |
| 新增类动词 | `新增` / `创建` | 3 / 2 | 🟢 可接受（`创建` 用于任务台账，`新增` 用于公告计数） |
| 删除类动词 | `删除` / `移除` | 6 / 2 | 🟡 `移除` 仅用于"移除所选文件"，宜统一为 `删除` |
| 凭证名词 | `令牌` / `token` | 4 / 2 | 🔴 `bot_token` / `chat_id` 是**配置字段名**不应翻译，需白名单 |
| 站点名词 | `适配器` / `站点` | 2 / 5 | 🔴 `适配器` 是内部代号，用户不可见概念 |

### 1.3 同义键精确冲突（同一动作两种说法）

| 场景 | 键 A | 键 B | 冲突 |
|------|------|------|------|
| 归档完成标题 | `notification.archive.archive_complete.title` = **归档完成** | `save_results_title` = **保存完成** | 同一动作两种标题 |
| 归档结果正文 | `…archive_complete.body.count` = **已归档：{n} 个文件** | `save_results_success` = **保存成功: {} 个** | 同一结果两种句式 + 半角冒号 |
| 扫描结果口径 | `…scan_complete.body.stats` = **已扫描：{t} 个文件，成功：{s} 个，失败：{f} 个** | `msg_scan_complete` = **扫描完成：{success} 个识别成功，{failed} 个无法识别** | 同一统计两种词（`失败` vs `无法识别`） |
| 查询无果 | `…query_empty.body` = **共 {total} 条标准，全部未命中** | `query_cat_not_found` = **未查询到** | `未命中` vs `未查询到` |
| 废止状态 | `notification.common.abolished` = **已废止** | `auto_run_summary_expired` = **已废止(移入过期作废): {count} 个** | 同一行里 `废止`（状态）与 `作废`（目录名）并用 |

### 1.4 标题歧义（与术语无关，但同属文案缺陷）

**`notification.scan.scan_complete.title` 与 `notification.scan.scan_empty.title` 的值完全相同：「扫描完成」**。

用户无法从标题区分"扫到 30 个"与"未发现新文件"，只能读正文。设计文档 §3.1 C-3 已记为缺陷。

### 1.5 禁用词候选（实证命中）

| 探针 | 命中 | 示例 | 处置建议 |
|------|------|------|---------|
| `webhook` / `Webhook` | **6** | `notification.channel.config.webhook_url` = "Webhook 地址" | **豁免**：这是用户必须填的**配置字段名**，翻译后用户无法与渠道文档对应 |
| `token` | **2** | `notification.channel_test.missing_bot_token` = "缺少 bot_token" | **豁免**：同为配置字段名 |
| `API` | **2** | `notification.system.security_token_refreshed.title` = "API 静态令牌已轮换" | **豁免**：安全告警需精确指向"API 令牌"以区别于登录密码 |
| `适配器` | **2** | `notification.system.quota_exhausted.title` = "适配器日配额已耗尽" | 🔴 **改用**「站点」：`适配器` 是内部代号；同名指标 `站点` 已有 5 键在用 |
| `堆栈` | **1** | `notification.validity.validity_system_failed.body.hint` = "💡 详细错误**堆栈**已记录至系统日志，请联系**管理员**查看。" | 🔴 **改写**：技术黑话 + 单人项目无"管理员"角色 |
| `管理员` | **2** | 同上 + `notification.system.security_password_changed.body.hint` | 🟡 安全提示场景的"联系管理员"**保留**（多用户已支持，`ADR-012`）；有效性检查场景的**删除** |
| `未命中` | 1 | `notification.query.query_empty.body` | 🔴 **改用**「未查询到」 |
| `失败`（用于"文件名无法解析"） | 1 | `notification.scan.scan_complete.body.stats` | 🔴 **改用**「无法识别」 |
| emoji 混入错误类 | 2 | `validity_system_failed.body.hint` = "💡 …"、`notification.aggregated.body.header` = "📦 聚合通知（{n} 条）" | 🟡 错误类去 emoji；聚合头可保留（信息类） |
| 相对时间（`分钟前`/`小时前`/`刚刚`） | **0** | — | ✅ 无命中，无需治理 |
| 客套话（`亲`/`请您`/`麻烦`/`谢谢`） | **0** | — | ✅ 无命中 |
| 内部代号（`PILOTSTD`/`mock`/`stub`/`TODO`） | **0** | — | ✅ 无命中 |
| `payload`/`endpoint`/`traceback`/`null`/`None` | **0** | — | ✅ 无命中 |

**结论**：禁用词问题**远小于预期**——语言包里没有客套话、相对时间、开发用语。真实问题集中在 **6 处**：`适配器`(2)、`堆栈`(1)、`未命中`(1)、`失败`误用(1)、错误类 emoji(1)。

---

## Task 5.2：方案设计

### A. 术语表结构

**推荐：JSON（`docs/governance/glossary.json`）**

| 候选 | 优势 | 劣势 | 结论 |
|------|------|------|------|
| **JSON** | 与既有 `pilotstd/i18n/*.json`、`scripts/i18n_hardcoded_baseline.txt` 生态一致；`json` 标准库直读；门禁脚本可直接对照键结构 | 无法写注释 | ✅ **采用**：理由说明放 `notes` 字段 + 配套 §《文案风格指南》 |
| TOML | 可写注释（对"为什么禁用某译法"很合适）；`tomllib` 3.11+ 标准库 | 项目**无数据 TOML 约定**（`pyproject.toml` 是唯一，且属工具配置）；数组表语法对 30 条术语可读性一般 | ⚪ 备选：若你重视"就地写理由"，改 TOML 成本极低 |
| YAML | 项目已有 `config/site_capabilities.yaml` 约定 | 需 PyYAML 依赖（不符"零新依赖"原则） | ❌ 否决 |

**字段定义**：

```jsonc
{
  "meta": {
    "version": 1,
    "updated": "2026-09-26",
    "scope_keys": ["notification.*"],   // 门禁作用域：仅通知文案（见 §C.4 作用域决策）
    "docs": "docs/reference/notification-copywriting.md"
  },
  "terms": [
    {
      "id": "archive",                       // 术语标识（稳定，供引用）
      "zh_CN": "归档",
      "zh_TW": "歸檔",
      "en": "Archive",
      "aliases": ["保存"],                   // 视作同一概念的其它写法（不报错，但记录）
      "forbidden": ["保存完成", "入库"],      // 明确禁止的变体 → 命中即 FAIL
      "notes": "文件进入标准库的动作；以工具栏 toolbar_save 的口径为准"
    }
  ]
}
```

| 字段 | 必需 | 语义 |
|------|------|------|
| `id` | ✅ | 稳定标识，门禁输出用它定位术语 |
| `zh_CN` / `zh_TW` / `en` | ✅ | 三语**首选**写法 |
| `aliases` | ⚪ | 可接受的同义写法（**不报错**，仅用于生成报告，避免把合理差异当违规） |
| `forbidden` | ⚪ | **禁止**的变体（命中即 FAIL）——这是门禁的阻断面 |
| `notes` | ⚪ | 为什么这样定（人读；门禁忽略） |

**"aliases 不报错"是本方案的关键取舍**：若把"所有非首选写法"都判违规，会命中 53+67+18 键（见 §C.3），门禁首日即红且大量误报（`保存` 在"保存项目/保存CSV"中是**正确**用法）。故门禁只拦 `forbidden` 明确列举的**词组**（如 `保存完成`），而非单字（如 `保存`）。

**初始术语条目草案（24 条，≤30 约束内）**：

| # | id | zh_CN | forbidden（命中即 FAIL） | 依据 |
|---|----|-------|------------------------|------|
| 1 | `archive` | 归档 | `保存完成`、`已归档但` | 同义键冲突 §1.3 |
| 2 | `archive_done_title` | 归档完成 | `保存完成` | 键 A/B 冲突 |
| 3 | `abolished` | 已废止 | `已作废`、`已失效` | 同行并用 §1.3 |
| 4 | `expire_folder` | 过期作废 | — | **保留**（目录名，非状态词） |
| 5 | `unrecognized` | 无法识别 | `未识别`、`识别失败` | §1.2 |
| 6 | `not_found` | 未查询到 | `未命中`、`查无` | §1.2 |
| 7 | `failed` | 失败 | `出错`、`不成功` | 边界：业务失败 |
| 8 | `error_system` | 系统异常 | `系统错误` | 边界：系统级异常 |
| 9 | `notice` | 通知 | `消息`（作为通知义时） | §1.2 |
| 10 | `reminder` | 提醒 | `通知`（日期场景误用） | 子语义保留 |
| 11 | `security_alert` | 安全告警 | `安全通知` | 第 2 批新增键族 |
| 12 | `site` | 站点 | `适配器` | §1.5 内部代号 |
| 13 | `remove` | 删除 | `移除` | §1.2 |
| 14 | `cancel` | 取消 | `终止`、`中止` | §1.2 |
| 15 | `token_static` | 令牌 | — （`bot_token` 等字段名豁免） | §1.5 |
| 16 | `webhook_field` | Webhook 地址 | — （**豁免词**，用户需对应渠道文档） | §1.5 |
| 17 | `not_configured` | 未配置 | `没有配置` | 句式统一 |
| 18 | `quota` | 配额 | `额度` | 句式统一 |
| 19 | `credential` | 凭证 | `凭据` | 二选一，取 `凭证`（既有键已用） |
| 20 | `scan_done_title` | 扫描完成 | —（另见 §D 标题歧义修复） | — |
| 21 | `scan_empty_title` | 扫描完成，无新增文件 | `扫描完成`（与上条**值相同**时） | §1.4 |
| 22 | `query_empty_body` | 共 {total} 条标准，均未查询到结果 | `全部未命中` | §1.3 |
| 23 | `system_log_hint` | 详细错误已记录至系统日志。 | `堆栈`、`请联系管理员查看`（此句内） | §1.5 |
| 24 | `aggregated_header` | 📦 聚合通知（{n} 条） | — （信息类，emoji 保留） | §1.5 |

### B. 禁用词清单与白名单

**阻断级（命中即 FAIL）**：`forbidden` 字段全部条目 —— 上表第 3/5/6/12/13/14/23 条等，共约 **14 个词组**。

**白名单机制（三层，均为显式登记，禁止无理由豁免）**：

| 层 | 机制 | 用途 |
|----|------|------|
| **L1 键级豁免** | `glossary.json` 的 `exempt_keys: ["notification.channel.config.webhook_url", ...]` | 该键整体不参与术语校验（配置字段名场景） |
| **L2 词级豁免** | `exempt_terms: ["Webhook", "bot_token", "chat_id", "API", "corpid", "agentid", "corpsecret"]` | 这些词在任何键内出现都**不算禁用词**（含英文技术标识） |
| **L3 行内标记** | 若语言包值需临时保留旧词，加 `"_allow_legacy": true` 同键旁注 | 避免"永远红的门禁"（与 `check_i18n_hardcoded.py` 的基线策略同源） |

**明确不做**：不提供"整包豁免"（如豁免整个 `zh_TW`）——那等于关掉门禁。

### C. 门禁脚本设计

**路径与命名**：`scripts/check_terminology.py`（对齐既有 `check_i18n_hardcoded.py` / `check_i18n_key_count.py` 命名）

**检测逻辑（三条，仅阻断第 1、2 条）**：

| # | 检测 | 阻断 | 说明 |
|---|------|------|------|
| 1 | **禁用词命中** | ✅ FAIL | 值内出现任一 `forbidden` 词组（按 `scope_keys` 与 L1/L2 白名单过滤） |
| 2 | **三语术语一致性** | ✅ FAIL | 术语表登记的键，其 `zh_CN`/`zh_TW`/`en` 值**必须**分别等于登记值（防"改了简体忘改繁体"） |
| 3 | **aliases 命中** | ❌ 仅报告 | 值内出现 `aliases` 写法 → 打印提示"建议改用首选写法"，不阻断（避免把 `保存项目` 这类正确用法判违规） |

**输出格式**（对齐既有门禁）：

```
::error::notification.system.quota_exhausted.title 命中禁用词「适配器」— 改用「站点」（术语 site）
  pilotstd/i18n/zh_CN.json:666
::error::术语不一致: notification.common.abolished 的 zh_TW 期望「已廢止」实际「已作廢」
```

**退出码**：`0` = 通过（可能带 aliases 提示）；`1` = 存在禁用词命中或术语不一致。

**集成方式**（与 G-043 同位置，紧跟 G-040）：

```bash
# scripts/check_all.sh（--fast 路径）
if python scripts/check_terminology.py; then
    log_pass "G-044 术语与禁用词检查"
else
    log_fail "G-044 术语与禁用词检查"
fi
```

```yaml
# .github/workflows/ci.yml（紧随 G-043）
      - name: G-044 — 术语与禁用词检查（notification.* 文案术语一致性）
        run: python scripts/check_terminology.py
```

**序号占用说明**：G-041 / G-042 已被设计文档 §1.3 / §3.2 预定（Python 语言包三语键门禁 / 文案风格门禁），但**均未实施**。本方案建议占用 **G-044**，并在 `gates.md` 中登记；若你希望按序实施 G-041/G-042，则本门禁改为 **G-042** 的合并实现。见 §F-1。

**作用域决策（关键）**：

| 方案 | 覆盖 | 优劣 |
|------|------|------|
| **A（推荐）** | 仅 `notification.*`（208 键） | 门禁首日可绿；文案责任人明确（通知模块）；与设计文档 §3.2 C 的"只查 notification.*"一致 |
| B | 全部 686 键 | 会命中 `保存项目`/`保存CSV`/`移除所选文件` 等**正确**用法 → 大量误报，门禁首日即红 |

**采用 A**。理由：界面标签（`btn_*` / `msg_*`）的主体是**操作提示**，其用词自由度天然高于**系统主动推送的通知文案**；通知文案是"系统对用户说话"，最需要一致性。

### D. 影响评估

#### D.1 需修改的 i18n 键（本批实际改动面：**9 键 / 3 文件**）

**按文件分组**：

| 文件 | 键 | 现 → 改 | 理由 |
|------|-----|---------|------|
| `zh_CN` / `zh_TW` / `en` | `notification.scan.scan_complete.body.stats` | 「失败：{f} 个」→「无法识别 {f} 个」 | §1.3 口径统一 |
| 同上 | `notification.scan.scan_complete.title` | 「扫描完成」→「扫描完成（{failed} 个无法识别）」 | §1.4 消除标题歧义（**需为 failed=0 时提供无后缀变体**，见 §E-3） |
| 同上 | `notification.scan.scan_empty.title` | 「扫描完成」→「扫描完成，无新增文件」 | §1.4 |
| 同上 | `notification.query.query_empty.body` | 「全部未命中」→「均未查询到结果」 | §1.2 禁用词 |
| 同上 | `notification.system.quota_exhausted.title` | 「适配器日配额已耗尽」→「站点日配额已耗尽」 | §1.5 内部代号 |
| 同上 | `notification.announce.announce_fetch_summary.body.others_count` | 「等共 {total} 个适配器」→「等共 {total} 个站点」 | §1.5 |
| 同上 | `notification.validity.validity_system_failed.body.hint` | 「💡 详细错误堆栈已记录至系统日志，请联系管理员查看。」→「详细错误已记录至系统日志。」 | §1.5 技术黑话+去 emoji |
| 同上 | `notification.archive.archive_complete.body.count` | 「已归档：{n} 个文件」→「已归档 {n} 个文件」 | §1.3 冒号口径 |
| 同上 | `notification.scan.scan_complete.body.failed_header` | 「失败文件：」→「无法识别的文件：」 | §1.3 |

**未纳入本批的漂移（有意延后）**：`归档`/`保存` 的 UI 侧统一（53 键，涉及 `save_results_*` / `toolbar_save` / `msg_save_*`）——属**界面标签**范畴，作用域外，且改动会波及大量 GUI 测试。记为后续专项。

#### D.2 需更新的测试断言清单（**7 处 / 4 文件**）

| 文件:行 | 断言 | 是否受影响 |
|---------|------|-----------|
| [test_notification_core.py:53](tests/test_notification_core.py#L53) | `assertIn("已归档：0", msg.blocks[0].text)` | 🔴 **受影响**（`已归档：` → `已归档 `） |
| [test_message_builders_snapshot.py:231](tests/unit/core/notification/test_message_builders_snapshot.py#L231) | `assert any("系统异常已记录日志" in b.text …)` | 🔴 **受影响**（该句在 `validity_system_failed.body.hint` 内） |
| [test_message_builders_snapshot.py:232](tests/unit/core/notification/test_message_builders_snapshot.py#L232) | `assert any("💡 详细错误堆栈已记录至系统日志" in b.text …)` | 🔴 **受影响**（去 emoji + 去"堆栈"） |
| [test_aggregate_buffer.py:238](tests/test_aggregate_buffer.py#L238) | `assertIn("已归档 3 个目录", result)` | 🟢 不受影响（`archive_complete` 的**目录**句，非本批改动键） |
| [test_monitor_scheduler.py:139](tests/test_monitor_scheduler.py#L139) | `assert "未识别到标准号，未归档" in caplog.text` | 🟢 不受影响（日志文本，非 i18n） |
| [test_archive_worker.py:88](tests/gui/test_archive_worker.py#L88) | `assert "已归档" in statuses` | 🟢 不受影响（GUI 状态串，测试自造） |
| [test_archive_worker.py:116](tests/gui/test_archive_worker.py#L116) | 同上 | 🟢 不受影响 |

> **与设计文档预估的差异**：设计文档 §3.3 注 3 预估"约 14 处快照断言"。实测**精确匹配仅 3 处需改**，其余 4 处经逐条核对**不受影响**（它们是 GUI 状态串、日志文本或未改动键）。这是本轮收窄带来的收益——**改动面比预估小 4 倍**。

#### D.3 预估改动行数

| 项 | 行数 |
|----|------|
| `glossary.json`（新建，24 条术语 + 白名单） | ~120 |
| `scripts/check_terminology.py`（新建） | ~150 |
| `gates.md` 登记 + 章节 | ~25 |
| `check_all.sh`（+8）+ `ci.yml`（+3） | ~11 |
| i18n 三语 × 9 键（含 zh_TW/en 补齐） | ~54 |
| 测试断言更新（3 处） | ~6 |
| **合计** | **~366 行** |

### E. 风险与缓解

| # | 风险 | 类型 | 缓解 |
|---|------|------|------|
| **E-1** | **误报**：`forbidden` 命中正确用法 | 高影响 | ① 只登记**词组**（`保存完成`）不登记单字（`保存`）；② `aliases` 只报告不阻断；③ 白名单三层；④ 首轮上线前用 `--report` 模式在真实语言包上跑一遍，人工确认零误报后再接 CI（复刻 `check_i18n_hardcoded.py` 的基线策略） |
| **E-2** | **`zh_TW` 缺 83 键**导致"术语一致性"检测大面积失败 | 阻断级 | 二选一：**A**（推荐）本批门禁只校验**术语表登记的 24 条**对应键，不要求全量三语齐备（全量齐备属 G-041 范畴）；**B** 先补 83+4 键再开门禁。见 §F-2 |
| **E-3** | `scan_complete.title` 需按 `failed` 数分支（0 个时的文案） | 中 | 需新增 `title.clean` 变体键（与既有 `title.normal`/`title.expired` 同模式），并在构建器中按 `failed==0` 选择。**这会触及 `_builders_task_results.py`**，超出"纯文案"范围 → 见 §F-3 |
| **E-4** | 漏报：新增文案绕开术语表 | 中 | 门禁**只**能拦已登记词。补一条配套检查：`notification.*` 新增键若命中 `aliases` 内的词 → 提示"请核对术语表"（不阻断） |
| **E-5** | 门禁使 i18n 修改变重（每次改文案都要过术语表） | 低 | 作用域限 `notification.*`（208 键），不影响 478 个界面标签键 |
| **E-6** | 回滚 | — | 纯新增文件 + 文案值修改，`git revert` 单提交即可；无 schema / 无接口变更 |

---

## Task 5.3：声明

- **本轮零代码改动**：未修改任何文件（侦察脚本已删除，`git status` 清洁）。
- 所有结论基于对 `pilotstd/i18n/*.json`（三语共 1971 键）与 `tests/**/*.py`（210 文件）的实读扫描。
- 未使用"可能""大概"；每处引号内的文案均为语言包原文。
- 未编写任何实现代码。

---

## Task 5.4：待人类裁决事项

| ID | 决策点 | 选项 | 我的建议 |
|----|--------|------|---------|
| **F-1** | 门禁编号 | A. 占用 **G-044**（G-041/G-042 留给设计文档预定的两个门禁）；B. 按序把本门禁做成 **G-042**（文案风格门禁）的合并实现 | **A**：本门禁只做"禁用词 + 术语一致性"，与设计文档 §3.2 B 的"key 命名门禁"、§1.3 的"三语键完整性门禁"职责不同，合并会让一个脚本做三件事 |
| **F-2** | `zh_TW` 缺 83 键 vs 术语一致性检测 | A. 门禁只校验术语表登记的 24 条键（不要求全量齐备）；B. 先补 87 键（83+4）再开门禁 | **A**。理由：本批目标是"术语治理"，补键是"完整性治理"（G-041 范畴）；先做 B 会把这批从 ~366 行推到 ~520 行，且 87 键的 zh_TW 翻译质量需你审校 |
| **F-3** | `scan_complete.title` 的 `failed` 分支 | A. 本批只改**值**不动构建器（标题保持"扫描完成"，靠正文区分）；B. 同时改 `_builders_task_results.py` 加 `failed==0` 分支 | **B**（能真正消除歧义），但需你确认本批范围可扩到构建器；若坚持"纯文案"，选 A 并把标题歧义留给后续 |
| **F-4** | 作用域 | A. 仅 `notification.*`；B. 全量 686 键 | **A**（理由见 §C.4） |
| **F-5** | `聚合通知` 头的 emoji（`📦`） | A. 保留（信息类）；B. 一并去掉（全库统一无 emoji） | **A**。错误类去 emoji 是原则，信息类保留可提升可扫读性 |
| **F-6** | `安全告警` 文案里的"联系管理员" | A. 保留（多用户已支持，`ADR-012`）；B. 改为"联系超级用户" | **A**：`管理员` 在安全提示场景是**正确**角色（系统确实有 `ADMIN_ROLE`），仅有效性检查场景该删（因那里"管理员"无意义） |
