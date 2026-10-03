# manager.py 拆分方案重新评估（目标优先 + 权重分析）

> **本轮性质**：只设计、不实施。**不预设结论**；软约束按"可付费"处理并实测代价。
> **上游**：[04-refactor-P.md](04-refactor-P.md)（上轮方案，**未被采纳**）、[00-framework.md](00-framework.md)、[03-impl-design-D.md](03-impl-design-D.md)
> **决策者批评（本轮必须回应）**：① 方案 A 是"妥协方案"；② `MagicMock(spec=)` 与 19 处 patch **不应成为方案选择的决定性因素**；③ 上轮**未做限制条件的权重分析**，选"改动最小"＝投降式决策。
> **决策者原则**：**目标第一，其余限制条件你要分析**。项目初衷：**"加事件成本高"是本项目动机之一**。
> 口径：规模统计沿用 G-010（`scripts/check_g_010_code_size.py:73-110`）；行号 2026-10-03 实测。

---

## 摘要（决策者读）

**一、目标判据的现状（实测）与目标值**
1. **加一个渠道**：现状 **≈12 个文件**（后端 **4 份重复声明** + 前端 5 + 测试 1 + 新实现 1）→ 目标 **≤2 个代码文件**。
2. **加一个事件**：现状 **9 步 / ≈11 个文件**（权威清单 `docs/governance/notification_coverage.md:119-129`）→ 目标 **≤2 个代码文件**。
3. **加一个通知场景**（静默/聚合）：现状 **3 个文件** → 目标 ≤2（**这条已接近健康**）。
4. **补充判据（更能暴露病根）**：**删一个事件**与**改一个事件的文案**——现状与"加"同量级（**≈5–11 文件**），而 C+E 阶段正要下线 3 个、合并 5 个事件。

**二、根因（有代码证据）**
5. **`events.py` 自称 SSOT 但与实现不符**：其模块 docstring 写"新增事件只需在 `ALL_EVENTS` 中加一行，**defaults / manager / API 全部同步**"（`events.py:2-5`），但 `EventDef` **只有 2 个字段**（`key` + 已废弃的 `bypass_aggregation`，`events.py:15-23`）——`mapping.EVENT_MAPPINGS`(41 条)、`manager._init_event_builders`(41 条)、`defaults` 规则(16 条)、前端 `notification.event.*`(36 键)、e2e `EVENTS`(41 条) **全部手写**。
   ⇒ **加事件成本高的根因不是"注册表放在 manager.py"，而是"同一事实散布在 5 份手写清单 + 1 份半 SSOT"**。
6. **渠道同理，且有 4 份后端重复声明**：`channel.py:28`（whitelist）、`manager.py:80`（name→class）、`_policy.py:9`（**同名不同物的 tuple**）、`docker/api/notification.py:327`（硬编码 tuple）。

**三、软约束的真实代价（实测，远小于上轮判断）**
7. **19 处 `_CHANNEL_CLASSES` patch 全部集中在 1 个文件**（`tests/test_format_utils.py`）⇒ **19 行机械替换**，性质＝字符串替换，**表达力不变**。
8. **`MagicMock(spec=NotificationManager)` 共 6 处**（上轮只数到 2 处）⇒ 其中 `tests/test_aggregate_buffer.py:551,562,577` 的 3 处改为"直测纯函数"后**表达力变强**（不再需 mock 宿主，正是 ADR-010 的原始目标）。
9. **私有访问 121 行**（限定 NotificationManager 上下文）：其中**属性赋值/方法替换/方法调用**占绝大多数，**只要 `manager.py` 保留同名薄转发则成本为 0**；生产侧仅 10 行（`docker/api/notification.py` 7 + `_format_utils.py` 2 + `_manager_ops.py` 1）。

**四、结论（直接修正上轮）**
10. **按目标判据，A 与 B 都不命中**：A **明确不动** `_CHANNEL_CLASSES`（为保护 patch），事件侧完全不触及 ⇒ **加渠道/加事件的改动点数一处不减**；B 只把后端渠道声明 4→1，事件侧同样不动。
11. **按目标优先，B 严格优于 A**（B 至少收敛渠道声明；A 完全不收敛）。**上轮"倾向 A"是拿代价当选择标准，属投降式决策，予以撤回。**
12. **提出方案 C（唯一命中目标的方案）**：`manager.py` 降为**装配 + 门面**（目标 ~150 行）；编排独立为 `_dispatcher.py`；**把半 SSOT 补全为完整 spec**（事件/渠道各一份声明，派生 mapping / 注册表 / 门禁基线 / e2e 元数据 / 前端清单）⇒ 加事件与加渠道均降到 **≤2–3 个代码文件**。
13. **附录撤回上轮的"约 150 行"**：该数字**无任何推算依据**；本轮逐阶段推算结果是 **manager.py 后续 5 阶段净增 ≈ 3–16 行**（中位约 10）。⇒ **余量维度无法区分 A/B/C**，选择只能由目标判据决定。

---

# 一、目标定义

## 1.1 可验证判据（现状 + 目标值）

### 判据 1：加一个新渠道 —— 现状 ≈12 个文件

| # | 落点 | 证据 |
|---|---|---|
| 1 | `CHANNEL_KEY_WHITELIST` | `pilotstd/core/notification/channel.py:28` |
| 2 | `_CHANNEL_CLASSES`（name→class） | `pilotstd/core/notification/manager.py:80-85` |
| 3 | `_CHANNEL_CLASSES`（**同名不同物的 tuple**） | `pilotstd/core/notification/_policy.py:9` |
| 4 | 硬编码白名单 | `docker/api/notification.py:327` |
| 5 | 渠道实现类（新建） | `pilotstd/core/notification/channels/*.py`（4 个现存） |
| 6 | 前端类型定义（×2 处） | `web/src/api/notification.ts:37,40,52,55` |
| 7 | 前端配置组件（**35 行含渠道名字面量**） | `web/src/components/NotificationConfig.vue`（`:46,49,97,100,104,107,115,123,134,168,189,192,197,218,220,241,253,329,373…`） |
| 8 | 前端日志视图（**6 行**，且 `:107-112` 已**漏掉 dingtalk**） | `web/src/views/NotificationLogsView.vue:109,120-121` |
| 9-10 | 前端语言文件（`notification.channel.<name>` + `notification.config.<channel>.*`） | `web/src/locales/zh-CN.json`（`notification.channel` 顶层 = `[dingtalk, feishu, telegram, wechat]`）、`en.json` |
| 11 | SSOT 一致性测试 | `tests/test_notification_stage1c_fields.py:418,424-426,440` |
| — | 后端 i18n | **渠道名键 0 个**（实测）；渠道名文案只在前端 |

**现状 = 11–12 个文件**（含新建渠道类）。
**目标值建议：≤2 个代码文件**（新渠道实现 + 渠道 spec 声明），文案类 JSON 单列（不可派生）。
**理由**：判据的目的是"改动点集中"；文案必须人写，故把**可派生的声明**收敛到 1 处是可达且足够的目标。

### 判据 2：加一个新事件 —— 现状 9 步 / ≈11 个文件

**权威清单**（`docs/governance/notification_coverage.md:119-129`，9 步）：

| 步 | 内容 | 落点 |
|---|---|---|
| 1 | 注册事件 | `pilotstd/core/notification/events.py`（`EVENT_X` + `ALL_EVENTS`） |
| 2 | 构建器 | 对应 `_builders_*.py` |
| 3 | **重导出与映射（2 处）** | `_message_builders.py` + `manager._init_event_builders` |
| 4 | i18n 三语 | `pilotstd/i18n/{zh_CN,zh_TW,en}.json` |
| 5 | 术语登记 | `docs/governance/glossary.json` |
| 6 | 默认渠道规则 | `pilotstd/core/config/defaults.py` |
| 7 | e2e 契约（8 字段） | `tests/test_notification_e2e.py` |
| 8 | 安全类额外 | 触发文件 + `SECURITY_EVENTS_BY_DESIGN_UNTRIGGERED` |
| 9 | 跑 3 个门禁 | — |

**清单未列但实际必需（实测）**：
- `pilotstd/core/notification/mapping.py:154` `EVENT_MAPPINGS`（41 条，阶段 2b 起生效）
- `web/src/locales/zh-CN.json` + `en.json` 的 `notification.event.*`（**各 36 键**）
- `web/src/components/NotificationConfig.vue` 的**硬编码事件清单**（实测 **35 行**形如 `'archive_complete',`，位于 `:59-93`）

⇒ **现状 = 9 步 / 11 个文件**（清单 7 个 + `mapping.py` + 前端语言 ×2 + 前端组件）。
**目标值建议：≤2 个代码文件**（事件 spec + builder；两者可同文件则 1）。

### 判据 3：加一个通知场景 —— 现状 3 个文件（已接近健康）

| 场景 | 落点 | 文件数 |
|---|---|---|
| 静默规则 | `manager.py:340,436-448,450-480` + `defaults.py:106-108` + `NotificationConfig.vue:258-277,411-429` | **3** |
| 聚合策略 | `aggregate_buffer.py:113,253` + `manager.py:170,177` + `defaults.py:85-90` | **3** |

**目标值：≤2**（场景 spec + 实现）。
**判断**：本判据**不是主要矛盾**——3 → 2 的收益远小于判据 1/2 的 11 → 2。

### 补充判据 4（**本轮新增判断**）：改一个已有事件的文案/级别 —— 现状 2–4 个文件

文案改 3 个 i18n JSON（`pilotstd/i18n/*`）+ 前端 2 个 JSON；级别在 e2e 元数据（`level` 字段）与 builder 里**各存一份**（`notification_coverage.md:145` 明确"G-045 **未校验** `level`/`module`/`aggregation`/`builder_keys`"）。
⇒ **同一事实两处存、且门禁不校验一致性** —— 这是判据 2 的病根在"改"与"删"上的投影。

### 补充判据 5（**本轮新增判断，最重要**）：**删一个事件** —— 现状与"加"同量级（≈5–11 文件）

原因：需删 `events.py` 条目、builder、`_message_builders.py` 重导出、`manager._init_event_builders` 注册、i18n ×3、`defaults` 规则、e2e 条目、`mapping.EVENT_MAPPINGS`、前端语言 ×2、前端组件清单。
**为什么它最关键**：[02-framework-update.md](02-framework-update.md) §1.3 已判定 **3 个"多余事件"待下线、5 个"重复事件"待合并**（C+E 阶段）。**若删除成本与新增同量级（11 文件），C+E 的门禁与清单重组将极难推进** —— 这条判据把"拆分"与"后续阶段可行性"直接连起来。

### 判据汇总

| 判据 | 现状 | 目标值建议 | 主要矛盾？ |
|---|---|---|---|
| 1 加渠道 | **≈12 文件** | **≤2** | ✅ 是 |
| 2 加事件 | **9 步 / ≈11 文件** | **≤2** | ✅ 是（**项目初衷**） |
| 3 加场景 | 3 文件 | ≤2 | ❌ 否 |
| 4 改事件文案/级别 | 2–4 文件 | ≤2 | ⚠️ 次要 |
| 5 **删事件** | **≈5–11 文件** | **≤2** | ✅ 是（C+E 前置） |

## 1.2 `manager.py` 的核心职责（含对决策者版本的挑战）

**决策者的初步判断**：「**事件 → 投递的编排**」（决定走哪条路：渠道、聚合、静音、补发）；**不该管**：消息构建、策略查询、日志写入、健康度记录、构建器注册。

**我的版本（挑战）**：

> **`manager.py` 的唯一职责 = 装配（composition root）+ 公开门面**；**"编排"本身也应搬离**。

| 职责 | 应归属 | 理由（可验证） |
|---|---|---|
| **装配**：构造 `ops`/`aggregator`/`channels`/`health`/`policy`，注入依赖 | **`manager.py` 保留** | 它是唯一知道"有哪些组件"的地方；判据：新增组件时只改此处 |
| **公开门面**：`send_event`/`test_send`/`get_policies`/`save_policy`/`shutdown`/`enabled`/`release_suppressed_notifications` | **`manager.py` 保留**（转发） | 生产耦合点：`facade/_base.py:256,279`、`docker/api/notification.py:11,445,461`、`docker/scheduler.py` |
| **编排**（选路：策略→聚合→静音→投递） | **独立 `_dispatcher.py`** | **编排是变更最频繁的部分**：后续 **B 阶段（分档节流）改选路**、**S 阶段（形态差异）改选路**、**A 阶段（聚合键）改聚合决策**。留在门面里 ⇒ 门面反复长大（**这正是 manager.py 从早期长到 498 行的机制**） |
| 消息构建 / 校验 | `_event_registry.py` | 决策者已列（同意） |
| 构建器注册 | `_event_registry.py`（由 **event spec 派生**） | 决策者已列（同意） |
| 策略查询 | `_policy.py`（已是独立类） | 决策者已列（同意） |
| 日志写入 | `_manager_ops.py`（已是组合类） | 决策者已列（同意） |
| 健康度记录 | `_health.py` | 决策者已列（同意） |
| 静音与补发 | `_suppression_queue.py` | 决策者已列（同意） |
| **事件/渠道的声明（SSOT）** | **`_registry.py`（新增，容纳完整 spec）** | **决策者版本未提及**——但它是判据 1/2/5 的唯一解（§2.2 根因） |

**反方意见（诚实呈现）**：门面与编排合一可减少一层间接、调试调用栈更短；且项目已有"宿主 + 组合类"先例（`NotificationOps`，`_manager_ops.py:38-47`），把编排留在宿主并不违反现有风格。
**裁决依据**：判据不是"风格"，而是**"后续 5 阶段改 `manager.py` 几次"**——编排留在门面里，A/B/S 三阶段都要改它；编排独立后，这三阶段改 `_dispatcher.py`，`manager.py` 增量 ≈ 0（详见附录推算）。

---

# 二、约束条件分类

## 2.1 硬约束（不可协商）

| # | 硬约束 | 判据/证据 |
|---|---|---|
| H1 | **业务行为不变**（外部表现逐项一致） | [04](04-refactor-P.md) §3.2 的 Z1–Z4 判据可复用 |
| H2 | **不加 mixin**（含多重继承拼装） | `tests/test_architecture_mixin_guard.py:9,27-35`（类名 `*Mixin` 即 FAIL）；`ADR-010:74` |
| H3 | **G-010 上限 500 不放宽** | `scripts/check_g_010_code_size.py:29` |
| H4 | **外部接口签名不变** | `facade/_base.py:256,279`、`docker/api/notification.py:11,445,461`、`docker/scheduler.py:200` |
| H5 | **`__init__.py` 再导出面不变** | `pilotstd/core/notification/__init__.py:12,14-22`（`__all__` + `__getattr__` 惰性导出） |
| H6 | 平台层/桌面端事件的既有豁免不破坏 | `docs/governance/notification_coverage.md` 的 `[覆盖摘要]` 未覆盖声明 |

## 2.2 软约束 + 真实代价逐项实测

| # | 软约束 | 现状实测 | 改动量 | 改动性质 | 改完后测试表达力 | 可接受性 |
|---|---|---|---|---|---|---|
| **S1** | `mock.patch("…manager._CHANNEL_CLASSES")` | **19 处，全在 `tests/test_format_utils.py` 一个文件**（`:121,135,145,158,183,202,217,230,253,268,281,303,322,339,353,381,397,411,428`） | **19 行**（+ `_format_utils.py:103` 的 import 源 1 行） | **纯字符串替换**（改 patch 目标模块名） | **不变**（patch 语义相同） | ✅ **完全可接受**——决策者批评成立：成本集中在 1 文件 19 行，**不构成方案选择的决定性因素** |
| **S2** | `MagicMock(spec=NotificationManager)` | **6 处**：`tests/test_aggregate_buffer.py:551,562,577`；`tests/test_notification_combo_patch.py:128,160,190`（上轮只数到 `__get__` 的 2 处） | **6 处**（其中 3 处同类可批量） | 前 3 处：改为**直测纯函数**（重新设计，但更简单）；后 3 处：改 spec 目标或改用真实例 | **变强**（前 3 处不再需 mock 宿主——正是 `ADR-010:26-27` 记录的原始痛点） | ✅ 可接受，且**有正收益** |
| **S3** | `_CHANNEL_CLASSES` 常量位置 | 4 份后端重复声明（§1.1 判据 1） | 收敛为 1 处 + 3 处改为派生/引用 | 设计性（这正是目标本身） | **变强**（新增"渠道声明唯一性"断言可替代现有 `stage1c_fields.py:424-426` 的被动比对） | ✅ **应付**（它是判据 1 的主体） |
| **S4** | 内部私有属性/方法访问 | **121 行**（限定 NotificationManager 上下文）；生产侧仅 **10 行**；按成员：`_enabled` 17、`_send_now` 15、`_cred_helper` 13、`_validate_message` 11、`_record_delivery` 11、`_cfg` 10、`_db` 9、`_policy` 8、`_log` 7、其余 ≤5 | **只需保留同名薄转发 ⇒ 0 行**；若彻底取消私有名 ⇒ 约 60 行（属性赋值类不可消除） | 机械（属性赋值必须保留在宿主上）；方法类可改为对新类打桩 | **不变**（若保留转发）/ **变强**（若改为对新类打桩：测试更聚焦） | ✅ 可接受——**这也是"装配+门面"方案仍要保留薄转发的原因** |
| **S5** | `_QUEUE_MESSAGE_FIELDS` 被 5 处测试 import | `tests/test_notification_stage1a_identity.py:268`、`stage1b:292`、`stage1c:334`、`stage2b_wiring:314,338` | **0 行**（宿主再导出同一对象）或 5 行（改 import 源） | 机械 | 不变 | ✅ 可接受 |
| **S6** | `settings`/前端事件清单硬编码 | `NotificationConfig.vue` 35 行事件 + 35 行渠道字面量 | 约 70 行（若改为读后端 spec 导出的清单） | **重新设计前端清单来源** | **变强**（前端不再手维护，漂移风险消除——现在 `NotificationLogsView.vue:107-112` 已漏 dingtalk，是**已发生的漂移实例**） | ⚠️ 可接受但**需分步**（先代码侧 SSOT，再前端派生） |
| **S7** | `defaults.py` 的 `notification.rules.*`（16 条手写） | 16 条 | 改为由 event spec 派生 | 设计性 | **变强**（"注册了但发不出去"这类缺陷由派生保证消除，见 `notification_coverage.md:126` 第 6 步） | ✅ 可接受——它直接服务判据 2 |

**代价合计（若取方案 C 的完整形态）**：约 **25 行测试机械改动（S1+S2）+ 6 处前端/后端派生改造（S6+S7+S3）**，其中 **S1/S2/S6 三项使测试表达力变强或不变，无一项变弱**。
⇒ **结论：软约束总代价在"为目标付费"的范围内，且不产生表达力损失。** 上轮把它当作决定性因素，是判断错误。

---

# 三、方案对比（按目标维度）

## 3.1 方案 A 实值（上轮方案：两块纯函数化）

| 维度 | 实值 |
|---|---|
| 职责清晰度 | **中**：`manager.py` 仍同时承担 生命周期装配(133) + 主发送链(69) + 静默队列(68) + 健康度(46) + 契约常量(23) = **5 类职责**（仅移走构建器 71 与静默 68） |
| 加渠道改几处 | **12 → 12**（**不动 `_CHANNEL_CLASSES`**，为保护 19 处 patch） |
| 加事件改几处 | **11 → 11**（注册表只是**搬家**：`manager._init_event_builders` → `_event_registry`，清单数量不变） |
| 删事件改几处 | **11 → 11** |
| 后续 5 阶段扩展余量 | `manager.py` ~318 ⇒ 余量 **182**；阶段净增 ≈3–16 行（附录） ⇒ **余量富余** |
| 拆完后 `manager.py` 行数 | **~318** |
| 测试改造成本 | **0 行** |
| 测试改造后表达力 | **不变** |

## 3.2 方案 B 实值（上轮方案：四块 + `_ManagerContext`）

| 维度 | 实值 |
|---|---|
| 职责清晰度 | **较高**：移走构建器/静默/生命周期/健康度 ⇒ `manager.py` 剩 **编排(69) + 契约常量(23) + 门面转发** = **3 类职责**，但**保留 15 个薄转发**（样板占比升高） |
| 加渠道改几处 | **12 → 9**（后端 4 份声明收敛为 1，前端 5 处仍手维护） |
| 加事件改几处 | **11 → 11**（同 A，注册表搬家不改清单数量） |
| 删事件改几处 | **11 → 11** |
| 后续 5 阶段扩展余量 | `manager.py` ~220 ⇒ 余量 **280**；净增 ≈3–16 行 ⇒ **余量更富余（但非必要）** |
| 拆完后 `manager.py` 行数 | **~220** |
| 测试改造成本 | **25 行**（S1 19 行机械 + S2 6 处） |
| 测试改造后表达力 | **部分变强**（S2 前 3 处改为纯函数直测） |

## 3.3 方案 C（**新提**：装配门面 + 编排独立 + 完整 spec SSOT）

**三件事**：

| # | 内容 | 落点 |
|---|---|---|
| **C-1** | `manager.py` 降为**装配 + 门面**（目标 **~150 行**） | `manager.py`（只留 `__init__` 装配 + 公开 API 转发 + 少量薄转发） |
| **C-2** | **编排独立**：选路（策略→聚合→静音→投递）搬入新类 | 新 `_dispatcher.py`（宿主引用 + 回调宿主可替换方法，同 `_manager_ops.py:47` 口径） |
| **C-3** | **★ 完整 spec SSOT**：把 `events.py` 的半 SSOT 补全，并新增渠道 spec | 扩展 `events.py`（或新 `_registry.py`）：每条事件声明 `key / notify_event / content_type / task_kind / builder / i18n 前缀 / 默认规则 / e2e trigger_file`；渠道声明 `name / class / 凭证字段` |

**C-3 的派生关系**（把 5 份手写清单降为 1 份）：

```
                    ┌── ALL_EVENTS / ALL_EVENT_KEYS      （events.py 内派生）
                    ├── mapping.EVENT_MAPPINGS           （41 条手写 → 派生）
   事件 spec ────────┼── manager._EVENT_BUILDERS           （41 条手写 → 派生）
   （单一来源）      ├── defaults.notification.rules.*    （16 条手写 → 派生）
                    ├── G-045 门禁基线                   （已是 AST 读 events.py：audit_notification_coverage.py:58-73）
                    ├── tests/test_notification_e2e.py 的 EVENTS 元数据（41 条手写 → 派生/校验）
                    └── 前端 notification.event.* 清单     （36 键手写 → 由 spec 导出）

   渠道 spec ───────┬── CHANNEL_KEY_WHITELIST             （channel.py:28）
   （单一来源）      ├── _CHANNEL_CLASSES                  （manager.py:80）
                    ├── _policy.py:9 的 tuple             （删除重复）
                    ├── docker/api/notification.py:327    （改为引用）
                    └── 前端渠道表单/类型                  （由 spec 导出）
```

**可行性证据**：G-045 门禁**已经**用 AST 从 `events.py` 读 `ALL_EVENTS`（`scripts/audit_notification_coverage.py:58-73`）⇒ "把 events.py 变成真 SSOT"与门禁现有方向**一致**，改造成本低于上轮估计。

**方案 C 的代价与风险**：
- 代价：S1(19) + S2(6) + S3/S6/S7（派生改造，约 6 处消费方）
- 风险 1：触及**门禁基线与 e2e 元数据来源** ⇒ 属 `04-影响面.md` §六 的"无法渐进迁移"批次（原子性）
- 风险 2：若"派生"采用**代码生成**（写文件），会引入生成物同步问题；采用**运行时读取 spec** 更干净（门禁已是此模式）
- **建议分两步**：**C1**（C-1 + C-2 + C-3 的后端部分，消费方**运行时读 spec**，前端暂不动）→ 立即达成"加事件代码文件 ≤3"；**C2**（前端清单与 defaults/门禁基线改为派生）→ 达成 ≤2

## 3.4 对比表（每格为数字或具体判断）

| 维度 | 方案 A | 方案 B | **方案 C** |
|---|---|---|---|
| 职责清晰度（`manager.py` 承担几类职责） | **5 类** | **3 类** + 15 薄转发 | **1 类**（装配+门面）+ 少量转发 |
| **加渠道改几处** | **12**（不改善） | **9**（后端 4→1） | **3–4**（后端 1 + 新类 + 前端派生 1–2）→ C2 后 **≤2** |
| **加事件改几处** | **11**（不改善） | **11**（不改善） | **≤3**（spec + builder + i18n 文案）→ C2 后 **≤2** |
| **删事件改几处** | **11** | **11** | **≤2**（spec 删一行 + builder 删函数） |
| 后续 5 阶段 `manager.py` 净增 | ≈3–16 | ≈3–16 | **≈0–3**（编排已独立） |
| 拆完后 `manager.py` 行数 | ~318（余量 182） | ~220（余量 280） | **~150（余量 350）** |
| 测试改造成本（真实） | 0 | **25 行**（S1 19 机械 + S2 6 处） | **25 行 + 6 处派生改造** |
| 测试改造后表达力 | 不变 | 部分变强 | **变强**（事件契约由"多处手维护"变为"一处声明 + 派生一致性断言"） |
| 命中判据 1（加渠道 ≤2） | ❌ 12 | ❌ 9 | ✅ **≤2（C2 后）** |
| 命中判据 2（加事件 ≤2） | ❌ 11 | ❌ 11 | ✅ **≤2（C2 后）** |
| 命中判据 5（删事件 ≤2） | ❌ 11 | ❌ 11 | ✅ **≤2** |
| 与 ADR-010 契合度 | 纯函数化 | 纯函数化 + 组合注入 + Context | 纯函数化 + 组合注入 + **数据驱动（spec）** |

---

# 四、结论与建议

## 4.1 目标达成度分析

| 方案 | 判据 1（渠道） | 判据 2（事件） | 判据 5（删事件） | 判定 |
|---|---|---|---|---|
| A | **未命中**（12→12） | **未命中**（11→11） | **未命中** | **只减行数，不降改动成本** |
| B | **未命中**（12→9） | **未命中**（11→11） | **未命中** | 同上，仅渠道侧小幅收敛 |
| **C** | **命中** | **命中** | **命中** | **唯一命中目标** |

**必须写明的事实**：**A 与 B 的差别只在"行数"与"职责分类数"上，两者对项目的初衷（加事件成本高）都没有实质改善**。上轮以"182 行余量足够"论证 A，而本轮推算显示：**即使完全不拆，余量也够 5 个阶段**（净增 3–16 行）——**"余量"根本不是本次拆分的理由**，理由是**改动成本的集中度**。

## 4.2 代价可接受性

| 代价 | 金额（行/处） | 是否为目标所允许支付 |
|---|---|---|
| S1 19 处 patch | 19 行（1 文件机械替换） | ✅ 允许（表达力不变） |
| S2 6 处 spec mock | 6 处（3 处**表达力变强**） | ✅ 允许 |
| S3/S6/S7 派生改造 | 约 6 处消费方 | ✅ 允许（消除已有漂移，如 `NotificationLogsView.vue:107-112` 漏 dingtalk） |
| C 的原子性风险 | 门禁基线 + e2e 元数据同批 | ⚠️ 允许，但**须分 C1/C2 两步**以控制风险 |

**结论：代价可接受。** 且**没有一项软约束的改造会导致表达力下降**——其中 3 项（S2、S6、S7）**变强**。

## 4.3 建议方案

**建议方案 C（并分两步：C1 → C2）。理由（按目标优先，不按代价）**：

1. **A 与 B 都不命中目标**——判据 2（项目初衷）上二者与现状完全一致（11→11），不存在"选哪个更好"的问题，只存在"是否真的要解决"的问题。
2. **C 是唯一命中判据 1/2/5 的方案**，且其可行性有既有证据支撑（G-045 门禁**已经**从 `events.py` 读事件清单：`audit_notification_coverage.py:58-73`）。
3. **C 的额外收益**：`manager.py` 降到 ~150 行后，**后续 5 阶段的净增 ≈0–3 行**（编排已独立、注册已派生）——这比 A/B 的"余量够用"更接近"根治"。
4. **若决策者要求本批控制范围**：则在 A 与 B 之间**应选 B**（B 至少把后端渠道声明 4→1，A 完全不收敛；两者代价差仅 25 行测试）——**这是对上轮"倾向 A"的直接纠正**。
5. **不建议**：把"加事件成本"完全留给后续阶段——C+E 阶段本就要下线 3 个、合并 5 个事件（[02](02-framework-update.md) §1.3），**删事件现价 11 文件会使该阶段极难推进**（判据 5）。

**待决策者批准**：方案 C（C1/C2 分步）／ 退而取 B ／ 其他。

---

## 附：上轮"约 150 行"的推算依据（**声明撤回**）

**上轮原文**（`04-refactor-P.md:288`）：
> 「**余量已足够**：182 行 > 后续 5 个阶段预估增量（**约 150 行**）之和」

**结论：该 150 行无任何推算依据，属拍脑袋数字，予以撤回。** 本轮逐阶段推算如下（依据各阶段设计文档中的改动范围）：

| 阶段 | 改什么（`manager.py` 侧） | `manager.py` 净增 | 依据 |
|---|---|---|---|
| **D** 可见性解耦 | `:294-296` **3 行换 3 行**；新增逻辑落 `_manager_ops.py` | **0** | [03-impl-design-D.md](03-impl-design-D.md) §2.3.1（并已给出 G-010 净增 0 的约束设计） |
| **A** 聚合键二元 | 改动在 `aggregate_buffer._group_key`（`aggregate_buffer.py:253`）；`manager.py:170-175` 构造参数不变 | **0** | [00](00-framework.md) §2.3；[notification-redesign/03](../notification-redesign/03-实施路径.md) §3.3 |
| **S** 形态升级 | 渠道类与凭证（`channels/*`、`_credentials.py`）；`manager.py:80-85` 的**值**可能变 | **0 ～ 3**（若引入"渠道形态"注册维度则 2～5） | [01-channel-capabilities.md](01-channel-capabilities.md) §四 |
| **B** 交互 + 分档节流 | 分档节流需在选路处加判定 | **+3 ～ 8** | [02](02-framework-update.md) §三（四档规则） |
| **C+E** 治理 + 清单处置 | 门禁/清单主要在 `events.py`/`mapping.py`/脚本 | **0 ～ 3** | [00](00-framework.md) §2.3；[02](02-framework-update.md) §1.3 |
| **合计** | — | **≈ 3 ～ 16 行（中位约 10）** | 上表逐项加总 |

**由此得出的两条推论**：
1. **"180 行余量足够"这一论据不成立**（它既不需要 180 行，也不需要 150 行——只需要约 10 行）。⇒ 上轮用余量论证 A 的推理链无效。
2. **"扩展余量"无法区分 A / B / C**（三者都富余）。⇒ 方案选择**只能**由目标判据（判据 1/2/5）决定。

---

## 附：可复算命令

```powershell
# ── 判据 1：渠道声明点 ──
Get-ChildItem pilotstd,docker,web -Recurse -File -Include *.py,*.ts,*.vue | Select-String 'CHANNEL_KEY_WHITELIST|_CHANNEL_CLASSES\s*[=:]|not in \("wechat"'
Select-String -Path pilotstd\core\notification\channel.py -Pattern 'CHANNEL_KEY_WHITELIST'
Select-String -Path pilotstd\core\notification\_policy.py -Pattern '_CHANNEL_CLASSES'
Select-String -Path docker\api\notification.py -Pattern 'not in \("wechat"'
(Get-Content web\src\components\NotificationConfig.vue | Select-String "wechat|dingtalk|feishu|telegram").Count
Get-Content tests\test_notification_stage1c_fields.py | Select-Object -Skip 415 -First 12
# ── 判据 2：事件清单（9 步）与手写清单数 ──
Get-Content docs\governance\notification_coverage.md | Select-Object -Skip 116 -First 15
Select-String -Path pilotstd\core\notification\events.py -Pattern 'class EventDef' -Context 0,9
(Select-String -Path pilotstd\core\notification\manager.py -Pattern '^\s+"[a-z_]+": _build_').Count
(Select-String -Path pilotstd\core\notification\_message_builders.py -Pattern '^\s+_build_').Count
Select-String -Path pilotstd\core\notification\mapping.py -Pattern 'EVENT_MAPPINGS'
(Select-String -Path tests\test_notification_e2e.py -Pattern '^\s+"name":').Count
(Select-String -Path web\src\components\NotificationConfig.vue -Pattern "^\s*'[a-z_]+',\s*$").Count
python -c "import json,pathlib;print(len(json.loads(pathlib.Path('web/src/locales/zh-CN.json').read_text(encoding='utf-8'))['notification']['event']))"
# ── 判据 3：场景落点 ──
Select-String -Path pilotstd\core\notification\manager.py -Pattern '_is_quiet_hours|aggregator|register_formatter'
Select-String -Path pilotstd\core\notification\aggregate_buffer.py -Pattern 'def _group_key|def register_formatter'
Select-String -Path pilotstd\core\config\defaults.py -Pattern 'quiet_hours|aggregate_'
# ── 软约束 S1/S2 ──
Get-ChildItem tests -Recurse -File -Filter *.py | Select-String 'notification\.manager\._CHANNEL_CLASSES' | Measure-Object
Get-ChildItem tests -Recurse -File -Filter *.py | Select-String 'MagicMock\(spec=NotificationManager\)'
Get-ChildItem tests -Recurse -File -Filter *.py | Select-String '__get__\(mgr\)'
# ── 门禁已从 events.py 读清单（C 的可行性证据）──
Get-Content scripts\audit_notification_coverage.py | Select-Object -Skip 56 -First 20
# ── 门禁 ──
python scripts/check_g_010_code_size.py
bash scripts/check_all.sh --fast
```

**自检**：代码/文档引用 60+ 处（`路径:行号`，内容级回读见提交前脚本）；规模与清单计数均为脚本实测，可复算；本轮**未改任何代码**。
