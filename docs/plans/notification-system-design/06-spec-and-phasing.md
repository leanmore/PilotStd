# SSOT 重建方案：五处澄清 + 重做方案

> **本轮性质**：只澄清 + 重做方案，**不实施**。
> **决策者裁决**：接受"SSOT 重建"；**先澄清五处、再重新给方案**；**不预设结论**（允许推翻上轮 C）。
> **上游**：[05-refactor-decision.md](05-refactor-decision.md)（目标优先评估）、[04-refactor-P.md](04-refactor-P.md)（P 阶段拆分设计）
> **硬约束**：禁止新增 mixin（`tests/test_architecture_mixin_guard.py:9,27-35`）；G-010 上限 500 不放宽（`scripts/check_g_010_code_size.py:29`）；业务行为不变。行号均为 2026-10-03 实测。

---

## 摘要（决策者读）

**一、五处澄清的核心答案**
1. **spec 定义**：**两个模块**——`events.py` 保持**零依赖的"键 SSOT"**（实测其唯一 import 是 `dataclasses`，且被 **10 个消费方** import）；新 `event_spec.py` **单向 import `events.py`** 补充其余字段。**关键约束**：门禁是 **AST 读**（`audit_notification_coverage.py:58-73`），故 spec 的键集合必须是**静态字面量**，不能运行时计算。**字段共 15 个**（实测反推：`mapping.EventMapping` 3 个 + e2e 元数据 **9 个** + `i18n_category` + `default_channels` + `security` + `branch_by`）。
2. **中间态**：上轮"C1 后端 / C2 前端"的分层切法**会产生无兜底的漂移**——因为**没有任何门禁校验前端清单**（实测在 `audit_notification_coverage.py` 内检索 `web/|locales|notification.event|前端` **零命中**）。⇒ **上轮 C 的分步假设被推翻**，改为**按实体端到端**切。另外**修正一处事实**：`notification.config.telegram` 缺块**不是漂移**（该表单只用通用键；实测 34 个引用键缺失 0），**真正的漂移是 `NotificationLogsView.vue:107-112` 漏 dingtalk**。
3. **六处派生改造**：精确行数已实测——`mapping.EVENT_MAPPINGS` **61 行/41 条**；`manager.py` 导入块 **44 行** + `_init_event_builders` **47 行**；`defaults.rules` **19 行/16 条**；**e2e `EVENTS` 479 行/41 条 × 9 字段**（最大一处）；前端事件清单 **35 行**；门禁读取源 1 处；渠道声明 **5 处**（比上轮多数出 `docker/api/notification.py:145-159`）。
4. **原子性**：**步 A（渠道）与步 B（事件）各自原子**——前者被 `tests/test_notification_stage1c_fields.py:418,424-426` 的双向断言锁定，后者被 `tests/test_notification_e2e.py:739 assert len(EVENTS) == 41` 锁定（[notification-redesign/03](../notification-redesign/03-实施路径.md) §3.5 已记录其"不可渐进"）。**步 A ∥ 步 B 可并行**；步 C（拆分）独立可渐进。
5. **判据分步达成**：**上轮 C1 达不到判据 1**（加渠道仍需改前端 3 文件 → 约 7-8 处）。改为**按实体端到端**后：**步 A 完成即判据 1 达标（11 → 2）**；**步 B 完成即判据 2/5 达标（11 → 2）**。

**二、重做后的方案（3 步，按实体端到端）**
6. **步 A｜渠道 SSOT 端到端** → 加渠道 **11 → 2 个代码文件**（判据 1 达标）
7. **步 B｜事件 SSOT 端到端** → 加事件/删事件 **11 → 2 个代码文件**（判据 2/5 达标）
8. **步 C｜编排独立 + `manager.py` 薄门面**（P 阶段既定，D 的前置）

**三、与上轮 C 的差异（5 条）**：分步由"按层"改"按实体"；spec 拆两个模块（保护 10 个轻量消费方）；明确"AST 可解析"约束；新增 `i18n_category` 字段（实测 `date_reminder` 的键在 `notification.validity.` 下，**不可机械推导**）；前端派生改为**复用已有 `get_config_schema()`**（`channels/base.py:43` + 4 实现，**当前零调用方＝死代码**，接线比新造便宜）。

**四、工作量**：步 A ≈ 2 天；步 B ≈ 3 天；步 C ≈ 2 天 → **合计 ≈ 7 天**。

---

# 一、五处澄清

## 1.1 spec 定义

### 1.1.1 字段清单（**由消费方反推，非设计臆想**）

**反推依据**（逐个消费方实测其读取形状）：
- `mapping.EventMapping`（`pilotstd/core/notification/mapping.py:119-124`）：`notify_event` / `content_type` / `task_kind`（3 字段）
- e2e 元数据（`tests/test_notification_e2e.py:262-272`）：**9 字段**——`name`/`module`/`level`/`aggregation`/`trigger_file`/`builder_file`/`builder_method`/`builder_keys`/**`mutual`**（各字段均出现 41 次，实测）
- `defaults`（`pilotstd/core/config/defaults.py:62-80`）：`notification.rules.<event>` → 渠道列表（16 条）
- i18n（`pilotstd/i18n/zh_CN.json`）：**扁平点号键**，240 个 `notification.*`（实测：`notification.scan.scan_complete.title`；但 `date_reminder` 的键在 **`notification.validity.date_reminder.*`** 下）
- 分支事件（`mapping.py:108` `_BRANCH_PENDING`）：`auto_backup`/`image_update_available`/`validity_batch_report`/`validity_round_summary` 需**按 `data` 内容分支**
- `level` 是**分支集合**而非单值（实测 `_builders_task_results.py:66`：`level="warning" if failed > 0 else "info"`；e2e 记为 `"info/warning/error"` 字符串）

| # | 字段 | 类型 | 用途 | 消费方 |
|---|---|---|---|---|
| 1 | `key` | `str` | 事件键 | `events.ALL_EVENT_KEYS`、全部消费方 |
| 2 | `notify_event` | `str` | 7 类通知事件之一 | `mapping.project()` → 聚合键、前端双层订阅 |
| 3 | `content_type` | `str` | 渲染形态（`CONTENT_TYPES` 成员） | `mapping` / `renderer` |
| 4 | `task_kind` | `str` | 任务视角 SSOT（`TASK_KINDS` 成员，可空） | `mapping` / 进度锚点 / `TASK_KIND_TO_TASK_TYPE` |
| 5 | `builder` | `Callable[[dict], NotificationMessage]` | 构建器函数 | `manager._EVENT_BUILDERS`（**由 spec 派生**） |
| 6 | `i18n_category` | `str` | 文案前缀 | 门禁 G-045 校验三语键；前端 locales 生成；**实测不可由 `key` 机械推导** |
| 7 | `default_channels` | `tuple[str, ...]` | 默认订阅渠道（空 = 默认不订阅） | `defaults.notification.rules.*`（**派生**） |
| 8 | `levels` | `frozenset[str]` | 可能出现的级别集合（分支取值） | e2e `level`；G-045 由"跟踪项"升级为"校验项" |
| 9 | `module` | `str` | 业务模块名（中文，如"时效性检查"） | e2e `module`；前端分组（外层 8 业务域） |
| 10 | `trigger_file` | `str` | 触发方文件路径 | e2e 契约（必须真实存在，`notification_coverage.md:127`） |
| 11 | `payload_keys` | `frozenset[str]` | 构建器读取的载荷键 | e2e `builder_keys` / G-046 审计；**可由静态分析派生**（`scripts/audit_notification_chain_scan.py` 已有该能力） |
| 12 | `mutual` | `str` | 互斥事件（e2e 第 9 字段） | e2e |
| 13 | `security` | `bool` | 安全类（需 `write_audit`） | G-043 / G-045（`SECURITY_EVENTS_EXTRA`，`audit_notification_coverage.py:48`） |
| 14 | `branch_by` | `Callable[[dict], str] \| None` | 分支判据（成功/失败 → 不同 `notify_event`） | `mapping.project()`（解决 `_BRANCH_PENDING`） |
| 15 | `subscribable` | `bool` | 是否默认对用户可见（`False` = "多余事件"，见 [02](02-framework-update.md) §1.3） | `defaults` + 前端清单（**为 C+E 的清单处置预留**） |

**不计入 spec 的字段（避免混淆）**：`builder_file` / `builder_method` 可由 `builder` 函数**反射推导**（`builder.__module__` / `builder.__name__`）；`builder_keys` 同理由静态分析派生（若 `payload_keys` 采信自动派生，则该字段可省，但**建议先显式声明再逐步自动化**——因为 G-046 的静态分析只是"审计"，不能作为契约来源）。

### 1.1.2 一个文件还是多个？—— **两个**（**有硬证据**）

| 模块 | 内容 | 依赖 | 为什么这样切 |
|---|---|---|---|
| **`events.py`（保留，保持轻）** | `EventDef` + `ALL_EVENTS` + `ALL_EVENT_KEYS` + `BYPASS_EVENTS` | **零内部依赖**（实测唯一 import 是 `dataclasses`，`events.py:12`） | 它有 **10 个消费方**：`docker/api/notification.py:13`、`__init__.py:7,48`、`manager.py:164`、`core/notification_aggregator.py:317` + 5 处测试。**这些消费方只需要"键列表"，不应被迫加载 41 个构建器 + i18n + blocks 层** |
| **`event_spec.py`（新增）** | 15 字段的声明表 | **单向 `import .events`** | 需要完整 spec 的消费方（`manager`/`mapping`/`defaults`/门禁/前端 API）本来就重，可接受 |

**依赖方向（实测无环）**：
```
event_spec.py ──► events.py（零内部依赖）
      │
      ├─► _builders_* ──► channel.py ──► blocks.py / specs.py
      │                        └─► channels/base.py（函数内延迟导入，channel.py:107）
      └─► mapping.py（零内部依赖）
```
**实测确认无反向依赖**：`_builders_task_results.py:17-25`、`_builders_system.py:7-17`、`channel.py:9-16`、`mapping.py:39-42` **均不 import `events.py` 或 `manager.py`**。

**一致性护栏（必需）**：`assert set(ALL_EVENT_KEYS) == {s.key for s in EVENT_SPECS}` —— 加一个"spec 与 events 键集合一致"的断言，防止两处漂移。**这条护栏本身是 spec 拆两模块的代价**（若单模块则无此风险）。

### 1.1.3 读取方式：**运行期直接读**为主 + **门禁 AST 读**

| 消费方 | 读取方式 | 理由 |
|---|---|---|
| `manager` / `mapping` / `defaults` | **运行期 import `event_spec`** | 同进程，零成本 |
| **门禁 G-045/G-046** | **AST 解析**（**不是 import**） | 现状即如此：`audit_notification_coverage.py:60` `ast.parse((NOTIF/"events.py").read_text())`。**理由**：门禁不应因 spec 的重依赖而失败 |
| **e2e 元数据** | 运行期 import `event_spec` | 测试进程可加载 |
| **前端清单** | **新增 API 端点** + 前端启动拉取 | 前端不能 import Python；且渠道表单**已有 `get_config_schema()` 的设计意图**（见 §1.3 的 A-3） |

**⇒ 由此得出一条硬设计约束**：`event_spec.py` 的**键与元数据必须是静态字面量**（AST 可解析），**不得用运行时计算构造**（如 `[x for x in ... if ...]`、拼接、从 JSON 载入）。`builder`/`branch_by` 这类callable 字段可以是指针（AST 只取 `Name`/`Attribute`），但**键集合与标量元数据必须字面化**。

**不采用"构建期生成静态产物"**：会引入"生成物 vs spec"的第二重一致性风险，而项目已有 **`audit_notification_coverage.py` 的 AST 直读先例**与 `scripts/generate_capabilities.py` 的生成先例——**此处选前者（直读）风险更低**（生成物需要"重生成时机"规则与门禁）。

### 1.1.4 声明式 vs 可执行：**可执行（数据 + 指针），但受 §1.1.3 约束**

- `builder` / `branch_by` 是**函数引用**（可执行部分）
- 其余字段是**纯数据**
- **循环依赖处理**：实测**不存在环**（§1.1.2 的方向图）⇒ **不需要特殊处理**；但仍须加**方向守护测试**（断言 `events.py` 不 import 任何内部模块、`_builders_*` / `channel.py` 不 import `events.py` / `manager.py`），防止未来回归。

### 1.1.5 spec 示例（结构示意，非实施代码）

```
# event_spec.py（示意）
EVENT_SPECS: tuple[EventSpec, ...] = (
    EventSpec(
        key=EVENT_SCAN_COMPLETE,              # → events.py 的常量（单向引用）
        notify_event="task_lifecycle",
        content_type="task_result",
        task_kind="scan",
        builder=_build_scan_complete_message, # 函数指针
        i18n_category="scan",                 # 实测：scan_complete → notification.scan.*
        default_channels=("wechat",),
        levels=frozenset({"info", "warning"}),
        module="导入",
        trigger_file="pilotstd/manager/facade/_scan.py",
        payload_keys=frozenset({"count", "failed", "unrecognized"}),
        mutual="",
        security=False,
        branch_by=None,
        subscribable=True,
    ),
    EventSpec(
        key=EVENT_DATE_REMINDER,
        …
        i18n_category="validity",             # ★ 实测：date_reminder → notification.validity.*
        …
    ),
)
```

## 1.2 C1 → C2 的中间态（**上轮假设被推翻**）

### 1.2.1 上轮 C1/C2 中间态的确切描述（若按上轮方案执行）

| 项 | C1 完成时 | C2 完成时 |
|---|---|---|
| 后端 6 处派生 | ✅ 从 spec 派生（`mapping`/`manager`/`defaults`/门禁/e2e） | — |
| 前端事件清单（`NotificationConfig.vue:59-93`，35 行） | ❌ **仍硬编码** | ✅ 从 API 读 |
| 前端渠道字面量（3 文件，47+8+6 行） | ❌ 仍硬编码 | ✅ 派生 |
| 门禁基线 | ⚠️ 部分（读 events.py，未校验 spec 全字段） | ✅ 校验全字段 |

### 1.2.2 一致性风险（**实测：无门禁兜底**）

**实测证据**：在 `scripts/audit_notification_coverage.py` 内检索 `web/|locales|notification\.event|frontend|前端` → **零命中**。即 **G-045 只校验后端 `events.py` 与 e2e，从不校验前端清单**。

| 场景 | C1 期间会发生什么 | 可接受？ |
|---|---|---|
| 后端加事件到 spec | 后端能发通知；**前端配置页看不到该事件的订阅开关**（仍硬编码 35 项） | ❌ **不可接受**（用户无法订阅/关闭新事件；且**无任何门禁会报警**） |
| 后端删事件（C+E 的 3 个多余事件） | 前端仍显示已删事件 → 用户开启订阅后**订阅一个不存在的事件** | ❌ **不可接受** |
| 后端改事件名 | 前后端静默不一致 | ❌ 不可接受 |

**⇒ 结论：上轮"按层切"（后端先、前端后）在**当前门禁覆盖下**会产生**静默漂移**，必须放弃。**

### 1.2.3 因此改为**按实体端到端**切（重做方案的核心修正）

| 步 | 覆盖范围 | 中间态是否自洽 |
|---|---|---|
| **步 A｜渠道整体** | 后端 5 处 + 前端 3 文件 + locales，**同批完成** | ✅ 自洽（渠道集合前后端一致） |
| **步 B｜事件整体** | 后端 6 处 + 前端事件清单 + 门禁，**同批完成** | ✅ 自洽（事件集合前后端一致） |

**唯一残留的过渡风险**：步 A 与步 B 之间，**渠道已派生、事件仍硬编码**——二者**无交叉**（渠道清单与事件清单互不引用）⇒ **不产生不一致**。

### 1.2.4 中间态的"加事件成本"

| 时点 | 加事件改几处 |
|---|---|
| 现状 | 11 |
| **步 A 后** | **11**（事件侧未动） |
| 步 B 后 | **2** ✅ |

⇒ **判据 2 只能在步 B 达标**；步 A 期间不可声称判据 2 改善（避免上轮"注册表搬家却称改善"的错误）。

### 1.2.5 C1 能否独立验证

**能**，但验证对象是**判据 1（渠道）**而非判据 2：步 A 的独立验收 = "加一个渠道只改 2 个代码文件"的**实测演练**（在临时分支加一个假渠道并计数）。

## 1.3 六处派生改造逐条明细

> 行数均为实测；"改动量"指**净变化**（删旧 + 加派生）。

| # | 派生目标 | 现状（实测） | 改动量 | 性质 | 可断言验证 | 前置依赖 |
|---|---|---|---|---|---|---|
| **D1** | `mapping.EVENT_MAPPINGS` | `pilotstd/core/notification/mapping.py:154-214` = **61 行 / 41 条**手写 | 删 61 行 → **+4 行**派生 | **机械** | `set(EVENT_MAPPINGS) == set(ALL_EVENT_KEYS)`；∀e：`EVENT_MAPPINGS[e].notify_event ∈ NOTIFY_EVENTS` 且 `content_type ∈ CONTENT_TYPES` 且 `task_kind ∈ TASK_KINDS ∪ {""}` | spec 的 #2/#3/#4 |
| **D2** | `manager` 构建器注册 | `manager.py:18-61` 导入块 **44 行** + `:523-569` `_init_event_builders` **47 行** = **91 行** | 删 91 行 → **+6 行** | **机械** | `set(_EVENT_BUILDERS) == set(ALL_EVENT_KEYS)`；`callable(_EVENT_BUILDERS[k])` | spec 的 #5 |
| **D3** | `defaults.notification.rules.*` | `pilotstd/core/config/defaults.py:62-80` = **19 行 / 16 条** | 删 19 行 → **+3 行**（或保留显式 + 加一致性断言） | **机械** | `{k[len("notification.rules."):] for k in FACTORY_DEFAULTS if …}` == `{s.key for s in EVENT_SPECS if s.default_channels}`；且每条取值 == `list(s.default_channels)` | spec 的 #7 |
| **D4** | e2e `EVENTS` 元数据 | `tests/test_notification_e2e.py:260-738` = **479 行 / 41 条 × 9 字段** | 删 479 行 → **+10 行**（由 spec 构造） | **重新设计**（最大一处） | `{e["name"] for e in EVENTS} == set(ALL_EVENT_KEYS)`；∀e 逐字段 == spec 对应字段（含 `builder_method == spec.builder.__name__`） | spec 的 #9/#10/#11/#12；**且 `assert len(EVENTS)==41`（`e2e:739`）须同批改为 `== len(ALL_EVENT_KEYS)`** |
| **D5** | 前端事件清单 | `web/src/components/NotificationConfig.vue:59-93` = **35 行** | 删 35 行 → **+8 行**（拉取 + 渲染） | **重新设计**（需新 API 端点 + 拉取策略） | 前端组件测试：`renderedEventOptions === apiResponse.map(x => x.key)`（快照对比） | 需 `GET /api/notification/spec`（读 spec 的 #1/#6/#15） |
| **D6** | 门禁读取源与覆盖 | `scripts/audit_notification_coverage.py:58-73`（AST 读 `events.py` 的 `ALL_EVENTS`） | 改读 `event_spec.py`；把 `level`/`module`/`aggregation`/`builder_keys` 由**未覆盖**升级为**校验** | **设计** | ① 门禁退出码 0 且 `[覆盖摘要]` 的"未覆盖说明"不再含这四个字段；② 注入"spec 缺 `trigger_file`"的错误实现 → 断言门禁 FAIL（**判别力测试**） | spec 的 #8/#9/#10/#11；D4 完成后才能校验 e2e 侧 |
| **D7** | **渠道声明收敛**（同类派生，步 A） | **5 处**：`channel.py:28`、`manager.py:80`、`_policy.py:9`、`docker/api/notification.py:327`、`:145-159`（4 个 `build_channel` defaults） | 5 处 → `channel_spec.py` **1 处** | **设计** | `set(CHANNEL_KEY_WHITELIST) == set(CHANNEL_SPECS)`；`set(CHANNEL_SPECS) == set(_CHANNEL_CLASSES)`；`docker/api` 的 `build_channel` 默认值 == `spec.defaults` | — |

### 特别针对前端（**澄清 3 的问题**）

| 问 | 答（**实证**） |
|---|---|
| 改"读后端 spec"是机械替换还是重设计？ | **重设计**——不是替换常量，而是**改变渲染模型**：`NotificationConfig.vue` 目前有 **4 个 per-channel 模板块**（`:314` telegram、`:329` wechat、`:358` feishu、`:373` dingtalk） | 
| 需要新增 API 端点吗？ | **需要**——但**不是新造 schema**：`channels/base.py:43` 已有抽象方法 `get_config_schema()`，4 个渠道均已实现（`dingtalk.py:129`、`feishu.py:96`、`telegram.py:223`、`wechat.py:87`），而**全库零调用方**（实测：仅测试 docstring 命中）。⇒ **接线已有抽象即可**，新增 `GET /api/notification/channels` 返回 `{name, schema, defaults}` |
| 缓存策略？ | **前端启动拉一次 + 配置页打开时刷新**；不引入构建期生成物（理由见 §1.1.3） |
| 后端 spec 变更前端怎么感知？ | 返回体带 **spec 版本号/摘要**（如 `spec_hash`）；前端在响应头或 body 比对，不一致时刷新缓存。**不引入轮询**（配置页非高频） |

## 1.4 C 的原子性边界

| 步 | 原子性判据 | 为什么原子 | 涉及"不可渐进"批次？ |
|---|---|---|---|
| **步 A（渠道）** | **原子** | `tests/test_notification_stage1c_fields.py:418`（硬断言 4 个渠道名）+ `:424-426`（**双向**断言 `set(CHANNEL_KEY_WHITELIST) == set(_CHANNEL_CLASSES)`）——收敛声明必须**同批**改该测试与 5 处声明，否则红 | 否（该测试可同批改） |
| **步 B（事件）** | **原子** | `tests/test_notification_e2e.py:739` `assert len(EVENTS) == 41` 是**硬编码数字**；一旦 EVENTS 改派生，该断言 + 门禁 `[覆盖摘要]` 文案（`notification_coverage.md:142-151`）+ `notification_coverage.md:119-129` 的 9 步清单**必须同批更新** | **是**——[notification-redesign/03](../notification-redesign/03-实施路径.md) §3.5 已记录"`assert len(EVENTS)==41` 属无法渐进的原子批次" |
| **步 C（拆分）** | **可渐进**（按块剥离） | [04](04-refactor-P.md) §3.1 的 P1/P2/P3 每块独立可交付 | 否 |

**顺序依赖**：
```
步 A（渠道）──┐
              ├──► 互相独立，可并行
步 B（事件）──┘
      │
      └──► D6（门禁校验 spec 全字段）必须在 D4 之后
步 C（拆分）—— 独立，可在任意时刻做（D 阶段的前置）
```

**回滚粒度**：

| 步 | 回滚手段 | 残留 |
|---|---|---|
| 步 A | `git revert`（1 个 commit，含 5 处声明 + 前端 3 文件 + 测试断言同批） | **无**（无 schema 变更、无迁移号） |
| 步 B | `git revert`（建议拆 2 个 commit：**B1** = spec + 后端 4 处派生 + 门禁/D4；**B2** = 前端事件清单 D5；但 **B1 内的 5 处必须同批**） | **无** |
| 步 C | 按块 revert（P1/P2/P3） | 新文件残留无害（与 [04](04-refactor-P.md) §3.3 同口径） |

## 1.5 判据 1 的"分步达成"定义

| 问 | 答（**基于实测**） |
|---|---|
| C1 完成时判据 1 是几处？ | **上轮 C1（只做后端 spec）后仍约 7-8 处**——因为前端 3 文件（`notification.ts` 8 行、`NotificationConfig.vue` 47 行含渠道名 + **4 个模板块**、`NotificationLogsView.vue` 6 行）仍手改。⇒ **上轮"C1 后判据 1 = 3-4"是低估**（漏算了前端模板块与 locales） |
| "目标达成"= 每步接近还是最终达成？ | **建议按"最终达成、每步自洽"**：中间态**不得引入不一致**（§1.2.2 已证按层切会引入），但不要求每步都命中全部判据 |
| 能否在 C1 先把渠道收敛到 ≤2？ | **能，且这正是重做方案的选择**——把它定义为**步 A（渠道端到端，含前端）**。前提是**接受前端重设计进同一步** |
| 需要额外工作量吗？ | **需要**：前端渠道表单改造（从 4 个模板块 → 1 个 schema 驱动渲染）+ 新端点 ≈ **0.7 天**（详见 §2.4） |

**判据 1 的实测现值（修正上轮"12"）**：**11 个文件**——
后端 **4 个文件 / 5 处**（`channel.py:28`、`manager.py:80`、`_policy.py:9`、`docker/api/notification.py:327` 与 `:145-159`）+ 新渠道实现 1 + 前端 3 + locales 2 + 测试 1 = **11**。

---

# 二、重做的方案

## 2.1 最终形态

```
pilotstd/core/notification/
├── events.py            【轻·零依赖】EventDef + ALL_EVENTS + ALL_EVENT_KEYS + BYPASS_EVENTS
├── event_spec.py        【新·重】EVENT_SPECS（15 字段/41 条）→ 单向 import events.py
├── channel_spec.py      【新】CHANNEL_SPECS（name/class/defaults/schema）→ 派生 5 处渠道声明
├── mapping.py           EVENT_MAPPINGS 由 EVENT_SPECS 派生（D1）
├── manager.py           【薄门面】装配 + 公开 API 转发 + _EVENT_BUILDERS 由 spec 派生（D2）
├── _dispatcher.py       【新·步 C】编排（策略→聚合→静音→投递）
├── _manager_ops.py      （既有组合类）
├── _health.py           【新·步 C】投递健康度
├── _suppression_queue.py【新·步 C】静音与补发
└── _event_registry.py   【新·步 C】消息构建 + 校验（纯函数）
```

**职责边界**（`manager.py` 一句话）：**装配 + 门面**（见 [05](05-refactor-decision.md) §1.2 的挑战论证）。

**三条护栏（防两处漂移）**：
1. `set(ALL_EVENT_KEYS) == {s.key for s in EVENT_SPECS}`
2. `set(CHANNEL_KEY_WHITELIST) == set(CHANNEL_SPECS) == set(_CHANNEL_CLASSES)`
3. **方向守护**：`events.py` 不 import 内部模块；`_builders_*`/`channel.py` 不 import `events.py`/`manager.py`

## 2.2 分步路径

| 步 | 目标 | 内容 | 原子性 |
|---|---|---|---|
| **步 A｜渠道 SSOT 端到端** | **判据 1 达标** | ① `channel_spec.py`；② 后端 5 处收敛为引用；③ 新增 `GET /api/notification/channels`（接线已有 `get_config_schema()`）；④ 前端 3 文件改为 schema 驱动渲染（4 个模板块 → 1 个动态表单）；⑤ 修 `NotificationLogsView.vue:107-112` 漏 dingtalk（**顺带修复已发生漂移**）；⑥ 同批改 `stage1c_fields.py:418,424-426` | **原子** |
| **步 B｜事件 SSOT 端到端** | **判据 2/5 达标** | **B1**：`event_spec.py` + D1/D2/D3/D4/D6（后端 4 处 + e2e 479 行 + 门禁）；**B2**：D5（前端事件清单 35 行 → API） | **B1 原子**（含 `assert len(EVENTS)==41` 改动）；B2 独立 |
| **步 C｜编排独立 + 薄门面** | D 阶段前置（**不直接影响判据 1/2/5**） | 按 [04](04-refactor-P.md) 的按块剥离（+ 编排独立） | **可渐进**（按块） |

**推荐顺序**：**步 A ∥ 步 B1** → **步 B2** → **步 C**（步 C 亦可提前，与 A/B 无冲突）。

## 2.3 验收判据（可断言）

| 步 | 判据 | 断言形式 |
|---|---|---|
| **A** | 判据 1 达标 | **实测演练**：临时分支加一个假渠道 `fake`，`git status --porcelain` 中**代码文件（.py/.ts/.vue）计数 ≤2**；另：`set(CHANNEL_SPECS) == set(CHANNEL_KEY_WHITELIST) == set(_CHANNEL_CLASSES)` |
| **A** | 前端渠道渲染正确 | 组件测试：渲染出的渠道集合 == `GET /api/notification/channels` 返回集合；`NotificationLogsView` 的 filter 选项含 4 渠道（**修复漏 dingtalk**） |
| **B1** | spec↔events 一致 | `set(ALL_EVENT_KEYS) == {s.key for s in EVENT_SPECS}` |
| **B1** | 4 处派生正确 | D1/D2/D3 的集合断言（§1.3 表）+ D4 的逐字段断言 |
| **B1** | 门禁判别力 | 注入"spec 缺 `trigger_file`" → **断言门禁 FAIL**（不是"跑通即通过"） |
| **B2** | 判据 2/5 达标 | **实测演练**：① 加假事件 → 代码文件 ≤2；② 删假事件 → 代码文件 ≤2 |
| **A/B/C** | 零行为变更 | 复用 [04](04-refactor-P.md) §3.2 的 Z1–Z4（测试三元组不变 / 签名快照 / 调用序列 / 类属性契约） |
| **全部** | G-010 | `manager.py` 有效行：步 A/B 后 ≤ 400；步 C 后 ≤ 250 |

## 2.4 代价与工作量

| 项 | 内容 | 量 | 性质 |
|---|---|---|---|
| 测试改造 | S1 19 处 patch 目标（`test_format_utils.py`） | 19 行 | 机械 |
| 测试改造 | S2 6 处 `spec=` mock | 6 处（3 处改为纯函数直测 → **表达力变强**） | 半重设计 |
| 测试改造 | 步 A：`stage1c_fields.py:418,424-426` | 2 处 | 机械 |
| 测试改造 | 步 B：`e2e:260-738`（479 行）+ `:739` 硬断言 | **479 → ~10 行** | **重新设计**（最大一处） |
| 前端重设计 | `NotificationConfig.vue`：4 个渠道模板块（`:314-380+`）→ 1 个 schema 驱动表单 | ~120 行 | **重新设计** |
| 前端重设计 | `NotificationConfig.vue:59-93` 事件清单 35 行 → API | 35 行 | 半重设计 |
| 前端重设计 | `notification.ts`（8 行）+ `NotificationLogsView.vue`（6 行） | 14 行 | 机械 |
| 门禁调整 | `audit_notification_coverage.py` 读取源 + 覆盖摘要 + 判别力测试 | ~40 行 | 设计 |
| 后端 | `channel_spec.py`(~50 行) + `event_spec.py`(~200 行) + 5 处渠道收敛 + 4 处事件派生 | ~300 行 | 设计 |

**工作量**：**步 A ≈ 2 天**（渠道 spec 0.4 + 后端收敛 0.3 + 端点 0.3 + 前端重设计 0.7 + 测试 0.3）；**步 B ≈ 3 天**（spec 0.8 + 4 处派生 0.7 + e2e 重建 0.8 + 前端 0.4 + 门禁 0.3）；**步 C ≈ 2 天**（[04](04-refactor-P.md) §3.6 既有估算）→ **合计 ≈ 7 天**。

## 2.5 与上轮 C 的差异（逐条）

| # | 上轮 C | 本轮修正 | **修正依据（实证）** |
|---|---|---|---|
| 1 | 分 **C1（后端）/ C2（前端）** | 改为**按实体端到端**（步 A 渠道 / 步 B 事件） | **门禁不校验前端**（`audit_notification_coverage.py` 内 `web/|locales|notification.event|前端` **零命中**）⇒ 分层切会静默漂移（§1.2.2） |
| 2 | "把半 SSOT 补全"（未定几个模块） | **两个模块**：`events.py` 保轻 + `event_spec.py` 单向依赖 | `events.py` 有 **10 个消费方**（含 `docker/api/notification.py:13`、`core/notification_aggregator.py:317`），塞进 builder 会让它们被迫加载构建器层（§1.1.2） |
| 3 | 未提 AST 约束 | **明确"spec 必须 AST 可解析"** | 门禁用 `ast.parse` 读（`audit_notification_coverage.py:60`），不能 import 重模块（§1.1.3） |
| 4 | spec 字段未定义 | **15 字段**，含新增 `i18n_category` | **实测不可机械推导**：`date_reminder` 的键在 `notification.validity.date_reminder.*`（§1.1.1） |
| 5 | "前端 70 行硬编码 → 读 spec" | **复用已有 `get_config_schema()`**（`channels/base.py:43` + 4 实现，**零调用方**） | 实测该抽象**已存在且是死代码**（仅测试 docstring 命中）⇒ 接线成本低于新造（§1.3 特别段） |
| 6 | 判据 1 在 C1 为"3-4 处" | **修正为 7-8 处**（上轮低估：漏算 4 个前端模板块与 locales） | §1.5 逐项实测 |
| 7 | 未提渠道声明是 **5 处** | 补上 `docker/api/notification.py:145-159`（`build_channel` 默认值） | 实测（§1.5） |
| 8 | — | **新增**：渠道侧同构改造（D7）并入步 A | 判据 1 的 5 处后端 + 前端 3 文件必须在同一步（§1.4 原子性） |

---

# 三、待决策者确认的点

| # | 待确认 | 备选 | 建议 + 理由 |
|---|---|---|---|
| **N1** | **分步方式**：按实体端到端（步 A 渠道 / 步 B 事件）还是按层（后端先/前端后） | (a) 按实体 (b) 按层 | **(a)**：按层会产生**无门禁兜底的静默漂移**（§1.2.2 实测）；按实体每步自洽 |
| **N2** | **spec 模块数**：`events.py` 保轻 + `event_spec.py`（2 模块，需一致性护栏）vs 合并为 1 模块（简单但拖重 10 个消费方） | (a) 2 模块 (b) 1 模块 | **(a)**：`events.py` 被 `docker/api/notification.py:13`、`core/notification_aggregator.py:317` 等 10 处 import，且它们**只需要键列表**；代价是 1 条一致性断言 |
| **N3** | **前端事件清单的更新方式**：运行时 API 拉取 vs 构建期生成 | (a) API (b) 生成物 | **(a)**：无第二重一致性风险；且渠道侧本来就该走 API（复用 `get_config_schema`） |
| **N4** | **`payload_keys` 是否采信自动派生**（静态分析构建器） | (a) 先显式声明 (b) 直接自动派生 | **(a)**：G-046 的静态分析目前是"审计"能力，作为**契约来源**会使契约不可见；先显式，后续再自动化 |
| **N5** | **步 A 是否顺带修复 `NotificationLogsView.vue:107-112` 漏 dingtalk** | (a) 顺带修 (b) 单独工单 | **(a)**：该漂移正是"多处手维护"的产物，步 A 的改造会重写这段（`:109-111` 的 `channelOptions`），顺带修复零成本 |

---

## 附：可复算命令

```powershell
# ── 澄清 1：字段需求（逐个消费方）──
Select-String -Path pilotstd\core\notification\mapping.py -Pattern 'class EventMapping' -Context 0,8
Get-Content tests\test_notification_e2e.py | Select-Object -Skip 259 -First 14
python -c "import json,pathlib;d=json.loads(pathlib.Path('pilotstd/i18n/zh_CN.json').read_text(encoding='utf-8'));print(type(list(d.values())[0]).__name__, len([k for k in d if k.startswith('notification.')]));print([k for k in d if 'date_reminder' in k][:3])"
# ── 澄清 1：依赖方向（无环）──
python -c "import re,pathlib;[print(f.name, [l.strip() for l in f.read_text(encoding='utf-8').splitlines() if re.match(r'\s*(from|import) ', l)][:6]) for f in [pathlib.Path('pilotstd/core/notification/events.py'),pathlib.Path('pilotstd/core/notification/channel.py'),pathlib.Path('pilotstd/core/notification/mapping.py')]]"
Get-ChildItem pilotstd,docker,tests -Recurse -File -Filter *.py | Select-String 'from pilotstd\.core\.notification\.events import|from \.events import'
# ── 澄清 2：门禁是否校验前端（应为空）──
Select-String -Path scripts\audit_notification_coverage.py -Pattern 'web/|locales|notification\.event|前端'
# ── 澄清 3：六处派生的精确行数 ──
Select-String -Path pilotstd\core\notification\mapping.py -Pattern '^EVENT_MAPPINGS'
Select-String -Path pilotstd\core\notification\manager.py -Pattern '_message_builders import|def _init_event_builders|def _build_message'
Select-String -Path pilotstd\core\config\defaults.py -Pattern 'notification\.rules\.'
(Select-String -Path tests\test_notification_e2e.py -Pattern '^\s+"name":').Count
(Select-String -Path web\src\components\NotificationConfig.vue -Pattern "^\s*'[a-z_]+',\s*$").Count
(Select-String -Path web\src\components\NotificationConfig.vue -Pattern "wechat|telegram|feishu|dingtalk").Count
# ── 澄清 3：get_config_schema 是死代码 ──
Get-ChildItem pilotstd,docker,tests,web -Recurse -File -Include *.py,*.ts,*.vue | Select-String 'get_config_schema|config_schema'
# ── 澄清 4：原子耦合点 ──
Select-String -Path tests\test_notification_e2e.py -Pattern 'assert len\(EVENTS\)'
Select-String -Path tests\test_notification_stage1c_fields.py -Pattern 'CHANNEL_KEY_WHITELIST|_CHANNEL_CLASSES'
# ── 澄清 5：渠道声明的 5 处后端 ──
Select-String -Path pilotstd\core\notification\channel.py,pilotstd\core\notification\manager.py,pilotstd\core\notification\_policy.py,docker\api\notification.py -Pattern 'CHANNEL_KEY_WHITELIST|_CHANNEL_CLASSES\s*[=:]|not in \("wechat"|build_channel\('
# ── 门禁 ──
python scripts/check_g_010_code_size.py
bash scripts/check_all.sh --fast
```

**自检**：代码引用 70+ 处（`路径:行号`，内容级回读见提交前脚本）；所有行数与计数均为脚本实测、可复算；**本轮未改任何代码**。**过程中修正两处上轮事实**：① `notification.config.telegram` 缺块**不是漂移**（该表单只用通用键，实测 34 个引用键缺失 0）；② 上轮"C1 后判据 1 = 3-4 处"低估，实为 **7-8 处**。
