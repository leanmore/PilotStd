# SSOT 重建方案：五处澄清 + 两处补充澄清 + 重做方案

> ## ✅ 本方案已定稿（2026-10-03）
> **定稿依据**：五项待确认（N1–N5）**全部裁决**（§三 1）；两处补充澄清（e2e 构成、工作量依据）**已完成并实证**（§1.6）；spec 字段清单经澄清后由 **15 → 16**（§1.1.1）；判据 1/2/5 达成路径明确（§2.2）；三步原子性边界明确（§1.4）。
> **遗留事项**：3 项，已标注"遗留到实施设计阶段"（§三 2），不阻塞定稿。
>
> **本轮性质**：只澄清 + 定案，**不实施**、**不含步 A 实施设计**。
> **上游**：[05-refactor-decision.md](05-refactor-decision.md)（目标优先评估）、[04-refactor-P.md](04-refactor-P.md)（P 阶段拆分设计）
> **硬约束**：禁止新增 mixin（`tests/test_architecture_mixin_guard.py:9,27-35`）；G-010 上限 500 不放宽（`scripts/check_g_010_code_size.py:29`）；业务行为不变。行号均为 2026-10-03 实测。

> ## 🔄 修订（2026-10-03，步 B 第一子步骤落地时）
>
> **裁决**：字段值一律**机器可读**——展示文案走 i18n 键，**不把中文散文当"契约数据"搬进 `pilotstd/`**。理由有二：① 会直接撞 G-047（Python 侧 i18n 硬编码中文）——该门禁对不在存量基线中的新文件"一处都不允许"；② 把中文硬编码包装成"契约数据"是给不做事找理由（决策者原话），i18n 该做就做。
>
> **本次改动（规范性）**：
> 1. 字段数 **16 → 15**：**删除 `mutual`**——互斥关系是设计文档的说明，不是数据；e2e 契约自留该字段用于自身比对，不进规格（§1.1.1 表下注）。
> 2. `module`（中文模块名）→ **`module_key`**（i18n 键族 `notification.module.*`，12 键 × 3 语在 `pilotstd/i18n/*.json`）。
> 3. `aggregation` 值域改 **ASCII 枚举**（`aggregate` / `bypass`）——系统内部状态标识，**不进 i18n**（做成键只多一层无意义的间接）。
> 4. **e2e 契约同批对齐**：`module` 值改 i18n 键、`aggregation` 值改 ASCII 枚举（`mutual` 原样保留）。
> 5. **D4 判据口径**：由"逐字段 == e2e 中文字面量"改为"**逐字段 == spec 定义值**"（§1.3 D4、§2.3 B1）。
> 6. **字段 #5 `builder` 表示法**（决策者 2026-10-03 裁决 §八.1）：由 `builder: Callable` 改为 **`builder_ref`（静态指针，指向构建器模块与函数名）+ `builder` 属性（延迟解析）**。**理由**：spec 模块只依赖标准库与 `.events`，**避免循环依赖**（`event_spec → _builders_* → channel.py → …` 这条重链只在真正取构建器时才加载；`mapping` / `defaults` 这类轻消费方取规格时不会被动拖入渲染链路）；与实现对齐。**D4 判据不受影响**：`spec.builder.__module__` / `__name__` 在两种形态下都成立（前者解析后再反射）。<br>**实现口径（2026-10-03 实测）**：`builder` 是 `EventSpec` 的只读属性 ⇒ 每次访问调用 `builder_callable(spec)`，内部 `importlib.import_module(...)` —— **首次访问才 import，其后命中解释器的 `sys.modules` 缓存**（进程内模块只真正加载一次），未另加显式缓存（`frozen=True` 数据类不允许回写属性）。
>
> **与上次修订的关系**：§1.6.1 记录的 **15 → 16**（新增 `aggregation`）**仍成立**；本次是 **16 → 15**（删 `mutual`），两次改动互不抵消 ⇒ 故 §1.6.1 / §2.5 中"16 字段"的历史表述**保留原文**，**规范性字段清单以 §1.1.1 为准**（表内编号已按新清单重排：`aggregation` 由 #16 → **#15**）。
> **附带结论**：§三 2 遗留 1 的"`levels` 序列化约定"已定为**严重度升序**（`info` → `warning` → `error`，与既有 6 个字面值同序，无需改写）。

---

## 摘要（决策者读）

**一、五项裁决（已录入，§三 1）**
1. **分步按实体端到端**（步 A 渠道 / 步 B 事件）——采纳；按层切会产生无门禁兜底的静默漂移。
2. **spec 两模块**（`events.py` 保轻 + `event_spec.py` 单向补全）——采纳；`events.py` 有 10 个消费方，塞重会拖累。
3. **前端清单运行时 API 拉取**——采纳；无第二重一致性风险。
4. **`payload_keys` 先显式声明**——采纳；G-046 的静态分析是审计能力，不作契约来源。
5. **步 A 顺带修 `NotificationLogsView.vue:107-112` 漏 dingtalk**——采纳。

**二、两处补充澄清的结果（§1.6）**
6. **e2e `EVENTS` 构成已精确拆解**：实测 **476 行**（不是 479）= **17**（框架/注释）+ **82**（41 条目的花括号）+ **377**（字段值，其中 `builder_keys` 占 49 行）。**9 个字段 100% 可覆盖或派生**：`builder_file`/`builder_method` 由 `builder.__module__`/`__name__` **反射（实测 41/41 一致，省 82 行）**；其余 7 个字段由 spec 提供。**但 `aggregation` 不是常量**（实测 38×"聚合" + **3×"绕过（直连旧渠道）"**）⇒ **spec 需新增第 16 个字段**（该字段现为 **#15**，见 §一 修订）。
7. **"改 10 行"的修正**：e2e 侧**确实**从 476 行降到约 12 行，**但代价转移到 spec**——总数据点 **625（分散 6 处）→ 656（1 处）**，**处数 6 → 1**。⇒ **收益是"单一来源"，不是"更少数据"**；上一轮把它说成"净收益 10 行"是**误导性表述，予以更正**。
8. **工作量 7 天已拆到小时级**（§2.4）：步 A 16h / 步 B 18h / 步 C 16h = **50h ≈ 6.3 天（专注）**，保守取 **7 天**；**且附了 4 个历史锚点**（阶段 1a/1b/1c/2.5a 各在 **0.5–1 个日历日**内完成，含迁移+测试+文档）证明"数据/契约类批次"的估算口径合理；**前端重设计与门禁改造无历史锚点**，是最大不确定性来源。

**三、方案（3 步）**
9. **步 A｜渠道 SSOT 端到端** → 加渠道 **11 → 2 个代码文件**（判据 1 达标）
10. **步 B｜事件 SSOT 端到端** → 加事件/删事件 **11 → 2 个代码文件**（判据 2/5 达标）
11. **步 C｜编排独立 + `manager.py` 薄门面**（P 阶段既定，D 的前置）

---

# 一、五处澄清 + 两处补充澄清

## 1.1 spec 定义

### 1.1.1 字段清单（**15 个**；由消费方反推，非设计臆想）

**反推依据**（逐个消费方实测其读取形状）：
- `mapping.EventMapping`（`pilotstd/core/notification/mapping.py:119-124`）：`notify_event` / `content_type` / `task_kind`
- e2e 元数据（`tests/test_notification_e2e.py:260-735`）：**9 字段**，各字段均出现 41 次（实测）
- `defaults`（`pilotstd/core/config/defaults.py:62-80`）：`notification.rules.<event>` → 渠道列表（16 条）
- i18n（`pilotstd/i18n/zh_CN.json`）：**扁平点号键**，240 个 `notification.*`；实测 `scan_complete → notification.scan.*` 而 **`date_reminder → notification.validity.*`**（**不可机械推导**）
- 分支事件（`mapping.py:108` `_BRANCH_PENDING`）：4 个事件需按 `data` 分支

| # | 字段 | 类型 | 用途 | 消费方 | 本次变更 |
|---|---|---|---|---|---|
| 1 | `key` | `str` | 事件键 | `events.ALL_EVENT_KEYS`、全部 | — |
| 2 | `notify_event` | `str` | 7 类通知事件之一 | `mapping.project()`、前端双层订阅 | — |
| 3 | `content_type` | `str` | 渲染形态 | `mapping` / `renderer` | — |
| 4 | `task_kind` | `str` | 任务视角 SSOT（可空） | `mapping` / 进度锚点 | — |
| 5 | `builder_ref` | `str` | 构建器位置的**静态指针**（`模块全名:函数名`）；配套只读属性 `builder` 给出解析后的可调用对象 | `manager._EVENT_BUILDERS`、e2e 的 `builder_file`/`builder_method`（**反射派生**） | **由 `Callable` 改静态指针 + 延迟解析属性**（2026-10-03 修订，见修订块） |
| 6 | `i18n_category` | `str` | 文案前缀 | 门禁 G-045、前端 locales | — |
| 7 | `default_channels` | `tuple[str, ...]` | 默认订阅渠道 | `defaults.notification.rules.*`（派生） | — |
| 8 | `levels` | `tuple[str, ...]` | 级别**有序**集合（分支取值） | e2e `level`（斜杠连接） | **需排序约定**（见 §1.6.1） |
| 9 | `module_key` | `str` | 业务模块名的 **i18n 键**（`notification.module.*`） | e2e `module`、前端分组 | **值由中文名改 i18n 键**（2026-10-03 修订） |
| 10 | `trigger_file` | `str` | 触发方文件路径 | e2e 契约（须真实存在） | — |
| 11 | `payload_keys` | `frozenset[str]` | 构建器读取的载荷键 | e2e `builder_keys` / G-046 | 先显式（裁决 4） |
| 12 | `security` | `bool` | 安全类（需 `write_audit`） | G-043 / G-045 | — |
| 13 | `branch_by` | `Callable[[dict], str] \| None` | 分支判据 | `mapping.project()` | — |
| 14 | `subscribable` | `bool` | 是否默认对用户可见 | `defaults` + 前端清单 | — |
| **15** | **`aggregation`** | `str` | 聚合策略（**ASCII 枚举**：`aggregate` / `bypass`；实测非常量——改造前 38 条聚合 + 3 条绕过） | e2e `aggregation` | **★ 新增字段**（#16 → #15；值域 2026-10-03 改 ASCII） |

**不计入 spec**：

- `builder_file` / `builder_method`——可由 `builder.__module__` / `__name__` 反射派生（**实测 41/41 一致**）。
- `mutual`（互斥说明）——**2026-10-03 裁决删除**：互斥关系是设计文档里的说明文字，不是数据；e2e 契约自留该字段用于自身比对，规格不复制中文散文。（该字段原为 #12，删除后其后字段编号前移。）

### 1.1.2 两个模块（**有硬证据**）

| 模块 | 内容 | 依赖 | 理由 |
|---|---|---|---|
| **`events.py`（保留，保轻）** | `EventDef` + `ALL_EVENTS` + `ALL_EVENT_KEYS` + `BYPASS_EVENTS` | **零内部依赖**（实测唯一 import 是 `dataclasses`，`events.py:12`） | **10 个消费方**只需键列表：`docker/api/notification.py:13`、`__init__.py:7,48`、`manager.py:164`、`core/notification_aggregator.py:317` + 5 处测试；不应被迫加载 41 个构建器 + i18n + blocks |
| **`event_spec.py`（新增）** | 15 字段 × 41 条声明 | **只 `import .events`**（构建器以 `builder_ref` 静态指针登记、**运行期延迟解析**，不在 import 期加载 `_builders_*`） | 需要完整 spec 的消费方本来就重；但 `mapping` / `defaults` 这类只取数据的轻消费方**不应被动拖入渲染链路**（2026-10-03 修订 #6） |

**依赖方向（实测无环）**：`event_spec.py → events.py`（零依赖）；**取 `builder` 时**才走 `event_spec.py → _builders_* → channel.py → blocks.py/specs.py`（延迟解析，import 期不发生）；`mapping.py` 零内部依赖。**实测确认无反向依赖**（`_builders_task_results.py:17-25`、`_builders_system.py:7-17`、`channel.py:9-16`、`mapping.py:39-42` 均不 import `events.py`/`manager.py`）。

**护栏（必需）**：`assert set(ALL_EVENT_KEYS) == {s.key for s in EVENT_SPECS}`。

### 1.1.3 读取方式：**运行期直接读** + **门禁 AST 读**

| 消费方 | 方式 | 理由 |
|---|---|---|
| `manager` / `mapping` / `defaults` | 运行期 import `event_spec` | 同进程零成本 |
| **门禁 G-045/G-046** | **AST 解析**（现状即如此：`audit_notification_coverage.py:60`） | 门禁不应因重依赖失败 |
| e2e 元数据 | 运行期 import | 测试进程可加载 |
| 前端清单 | **新增 API + 前端拉取**（裁决 3） | 前端不能 import Python；渠道表单已有 `get_config_schema()` 设计意图 |

**⇒ 硬设计约束**：spec 的**键与标量元数据必须是静态字面量**（AST 可解析），**不得用运行时计算构造**。
**不采用构建期生成物**：会引入"生成物 vs spec"的第二重一致性风险。

### 1.1.4 声明式 vs 可执行：**可执行（数据 + 指针），受 §1.1.3 约束**

`builder`（经 `builder_ref` **延迟解析**的函数引用）/ `branch_by` 是函数引用；其余为纯数据。**实测无环** ⇒ 不需特殊处理，但须加**方向守护测试**（断言 `events.py` 不 import 内部模块、`_builders_*`/`channel.py` 不 import `events.py`/`manager.py`）。**2026-10-03 修订 #6**：函数引用改"静态指针 + 延迟解析"，import 期本模块不加载 `_builders_*`。

## 1.2 中间态（**上轮的"按层切"假设被推翻**）

**实测证据**：在 `scripts/audit_notification_coverage.py` 内检索 `web/|locales|notification\.event|frontend|前端` → **零命中**。即 **G-045 只校验后端 `events.py` 与 e2e，从不校验前端清单**。

| 场景（若按层切） | C1 期间后果 | 可接受？ |
|---|---|---|
| 后端加事件到 spec | 前端配置页看不到该事件；**无门禁报警** | ❌ |
| 后端删事件（C+E 的 3 个多余事件） | 前端仍显示 → 用户可订阅**不存在的事件** | ❌ |

**⇒ 改为按实体端到端**（步 A 渠道整体 / 步 B 事件整体），每步内部自洽。**唯一过渡风险**：步 A 与步 B 之间"渠道已派生、事件仍硬编码"——二者**无交叉**（渠道清单与事件清单互不引用）⇒ **不产生不一致**。

**中间态的加事件成本**：现状 11 → **步 A 后仍 11**（诚实标注）→ 步 B 后 **2** ✅。

## 1.3 七处派生改造逐条明细（含渠道侧 D7）

| # | 派生目标 | 现状（实测） | 改动量 | 性质 | 可断言验证 | 前置 |
|---|---|---|---|---|---|---|
| **D1** | `mapping.EVENT_MAPPINGS` | `mapping.py:154-214` = **61 行 / 41 条** | 删 61 → **+4 行** | 机械 | `set(EVENT_MAPPINGS) == set(ALL_EVENT_KEYS)`；∀e：`notify_event ∈ NOTIFY_EVENTS`、`content_type ∈ CONTENT_TYPES`、`task_kind ∈ TASK_KINDS ∪ {""}` | spec #2/#3/#4 |
| **D2** | `manager` 构建器注册 | `manager.py:18-61`（**44 行**）+ `:523-569`（**47 行**）= **91 行** | 删 91 → **+6 行** | 机械 | `set(_EVENT_BUILDERS) == set(ALL_EVENT_KEYS)` 且 `callable` 每项 | spec #5 |
| **D3** | `defaults.notification.rules.*` | `defaults.py:62-80` = **19 行 / 16 条** | 删 19 → **+3 行** | 机械 | 键集合 == `{s.key \| s.default_channels}`；取值 == `list(s.default_channels)` | spec #7 |
| **D4** | e2e `EVENTS` 元数据 | `tests/test_notification_e2e.py:260-735` = **476 行** | 删 476 → **+12 行** | **重新设计**（详见 §1.6.1） | `{e["name"] for e in EVENTS} == set(ALL_EVENT_KEYS)`；**逐字段 == spec 定义值**（2026-10-03：e2e 侧 `module` 存 i18n 键、`aggregation` 存 ASCII 枚举，**不再比对中文散文**；`mutual` 只留契约自用） | spec #8/#9/#10/#11/**#15**；`e2e:739` 硬断言须同批改 |
| **D5** | 前端事件清单 | `NotificationConfig.vue:59-93` = **35 行** | 删 35 → **+8 行** | **重设计**（新端点 + 拉取） | 组件测试：渲染选项 == API 返回集合 | `GET /api/notification/spec` |
| **D6** | 门禁读取源 | `audit_notification_coverage.py:58-73`（AST 读 `events.py`） | 改读 `event_spec.py`；`level`/`module`/`aggregation`/`builder_keys`（对应 spec `levels`/`module_key`/`aggregation`/`payload_keys`）由**未覆盖**升级为**校验** | 设计 | ① 退出码 0 且"未覆盖说明"不再含四字段；② **判别力测试**：注入"spec 缺 `trigger_file`" → **断言门禁 FAIL** | spec #8/#9/#10/#11/#15；D4 后 |
| **D7** | **渠道声明收敛**（步 A） | **5 处**：`channel.py:28`、`manager.py:80`、`_policy.py:9`、`docker/api/notification.py:327`、`:145-159` | 5 处 → `channel_spec.py` **1 处** | 设计 | `set(CHANNEL_KEY_WHITELIST) == set(CHANNEL_SPECS) == set(_CHANNEL_CLASSES)`；`build_channel` 默认值 == spec | — |

### 前端改造：**是重设计，不是机械替换**

| 问 | 答（实证） |
|---|---|
| 性质 | **重设计**：`NotificationConfig.vue` 有 **4 个 per-channel 模板块**（`:314` telegram、`:329` wechat、`:358` feishu、`:373` dingtalk），需改为 **1 个 schema 驱动表单** |
| 需要新端点吗 | **需要，但不新造 schema**：`channels/base.py:43` 已有抽象 `get_config_schema()`，4 渠道均已实现（`dingtalk.py:129`、`feishu.py:96`、`telegram.py:223`、`wechat.py:87`）而**全库零调用方**（实测仅测试 docstring 命中）⇒ **接线已有抽象** |
| 缓存 | 启动拉一次 + 配置页打开刷新；不引入构建期生成物 |
| 变更感知 | 返回体带 **`spec_hash`**，不一致时刷新缓存；**不引入轮询** |

## 1.4 原子性边界

| 步 | 原子性 | 为什么 | 涉"不可渐进"批次？ |
|---|---|---|---|
| **步 A（渠道）** | **原子** | `tests/test_notification_stage1c_fields.py:418`（硬断言 4 渠道名）+ `:424-426`（**双向**断言 `set(CHANNEL_KEY_WHITELIST) == set(_CHANNEL_CLASSES)`） | 否（可同批改） |
| **步 B（事件）** | **原子**（B1） | `tests/test_notification_e2e.py:739` `assert len(EVENTS) == 41` 是硬编码数字；EVENTS 改派生后该断言 + 门禁 `[覆盖摘要]` 文案（`notification_coverage.md:142-151`）+ 9 步清单（`:119-129`）必须同批 | **是**（[03](../notification-redesign/03-实施路径.md) §3.5 已记录） |
| **步 C（拆分）** | **可渐进**（按块） | [04](04-refactor-P.md) §3.1 的 P1/P2/P3 各可独立交付 | 否 |

**顺序**：步 A ∥ 步 B1 → 步 B2（前端事件清单）→ 步 C；**D6 必须在 D4 之后**。
**回滚**：步 A/B 各 `git revert`（无 schema 变更、无迁移号）；步 C 按块 revert。

## 1.5 判据 1 的分步达成

**判据现值（修正上轮"12"）**：**11 个文件** = 后端 **4 文件/5 处** + 新渠道实现 1 + 前端 3 + locales 2 + 测试 1。

| 时点 | 加渠道文件数 | 判据 1 |
|---|---|---|
| 现状 | **11** | ❌ |
| 上轮"仅后端 C1" | **7–8**（上轮误报 3–4：漏算 4 个前端模板块与 locales） | ❌ |
| **本轮步 A（渠道端到端）** | **2**（`channel_spec.py` + 新渠道类；文案 JSON 单列） | ✅ |

## 1.6 补充澄清（本轮新增）

### 1.6.1 澄清 1：e2e `EVENTS` 476 行的完整构成

**AST 精确解析结果**（`tests/test_notification_e2e.py:260-735`）：

```
476 行 = 17（框架与注释）+ 82（41 个条目的花括号 { / },）+ 377（字段值）
```

- **非条目 17 行**：`:260` `EVENTS: ... = [`、**13 行分组注释**（`:261,328,362,396,419,442,487,540,552,608,620,632,688`）、3 行安全类说明注释（`:689-690`）、`:735` `]`
- **条目**：41 条，40 条 = 11 行、1 条 = 19 行（`builder_keys` 多行那条）
- **字段值行数分布**：`builder_keys` **49 行**（8 条多行），其余 8 字段各 **41 行**

| e2e 字段 | 行数 | 归属 | spec 覆盖 |
|---|---|---|---|
| `name` | 41 | spec 字段 #1 | ✅ 直接 |
| `module` | 41 | spec #9（`module_key`） | ✅ 直接（**值为 i18n 键**，2026-10-03 修订） |
| `level` | 41 | spec #8 | ✅ 需**排序约定**（实测 6 个唯一值：`error`/`info`/`info/error`/`info/warning`/`info/warning/error`/`warning` — **排序不统一**） |
| `aggregation` | 41 | **spec #16（本次新增，现 #15）** | ❌ 上轮无此字段；实测 **38 条聚合 + 3 条绕过**（值域 2026-10-03 改 ASCII 枚举），**不是常量** |
| `trigger_file` | 41 | spec #10 | ✅ 直接 |
| `builder_file` | 41 | `builder.__module__` 反射 | ✅ **派生**（实测 41/41 一致） |
| `builder_method` | 41 | `builder.__name__` 反射 | ✅ **派生**（实测 41/41 一致） |
| `builder_keys` | **49** | spec #11 | ✅ 直接 |
| `mutual` | 41 | **spec 已删（2026-10-03）** | ⚠️ 只留在 e2e 契约自用（互斥关系是设计说明，不是数据）；规格不再登记 |
| **合计** | **377** | — | **9 字段 100% 可覆盖或派生** |

**结论（"改 10 行"是否成立）**：

| 说法 | 判定 |
|---|---|
| e2e 从 476 行 → 约 12 行 | ✅ **成立**（`EVENTS = [{…9 个字段…} for s in EVENT_SPECS]`，其中 2 个字段来自反射） |
| **"必须手写的部分"** | **0 行**——9 字段全部可由 spec 提供或反射（**这是本轮最强结论**） |
| **"改 10 行"作为收益表述** | ❌ **误导，予以更正**：代价**转移到 spec**。数据点总量 **625（分散 6 处）→ 656（1 处）**：<br>`mapping` 123 + `manager` 41 + `defaults` 16 + e2e **369** + 前端清单 35 + i18n 前缀 41 = **625**<br>spec = 41 × 16 = **656**（字段数于 2026-10-03 改为 15 ⇒ 现为 **615**） |
| **真实收益** | **处数 6 → 1**（单一来源），**不是"更少数据"**（数据点 +31） |

**⇒ 对方案的影响**：① spec 字段 **15 → 16**（新增 `aggregation`；此行是当时的历史结论，**现行字段数为 15**——2026-10-03 删 `mutual`，见 §一 修订）；② `levels` 与 `aggregation` 需**序列化约定**（`levels` 用固定顺序元组，e2e 侧同批改那 6 个字面值）；③ **"e2e 省 464 行"不能算作净收益**——它是"搬家"，必须与 spec 的增量一同看。

### 1.6.2 澄清 2：7 天工作量的依据

**（a）小时级拆解**（详见 §2.4 表）：步 A **16h** / 步 B **18h** / 步 C **16h** = **50h ≈ 6.3 天**，取整 **7 天**。

**（b）口径假设：专注做**（约 8h/日历日）。**若夹着做**（2–3h/日）→ **日历 17–25 天**。

**（c）历史锚点（用 git 实测校准，本轮新增）**：

| 历史批次 | 范围 | 实际耗时 | 证据 |
|---|---|---|---|
| **阶段 0**（WS 死代码清理 + 前端轮询改造） | 预估"**半天**" | 2026-10-02 完成 | `06-阶段0-1实施方案.md:23`；commit `29075b3f`（2026-10-02） |
| **阶段 1a**（4 字段 + 迁移 62 + 聚合器搬运 + 补发白名单） | 1 批 | **2026-10-02** | `59387bb2` + 2 个 fix（`be1de8a7`、`63f8ab7d`，均 10-02） |
| **阶段 1b**（4 字段 + 迁移 63） | 1 批 | **2026-10-03** | `74cff175` + 2 个 fix（均 10-03） |
| **阶段 1c**（4 字段 + 迁移 64 + 规格类型） | 1 批 | **2026-10-03** | `35193ada` + 3 个 commit（均 10-03） |
| **阶段 2.5a**（task_kind 落地 + 迁移 65 + 双向映射表 + 防腐化测试） | 1 批 | **2026-10-03** | `900864a3`/`639b6ba3`/`f96b211e`（均 10-03） |
| **阶段 1 收尾报告** | 1 份 | 2026-10-03 | `debda610` |

⇒ **校准结论**：**"数据/契约类批次"≈ 0.5–1 个日历日/批**（每个含迁移 + 聚合器/白名单同步 + 测试 + 文档），且 10-03 单日完成 **1b + 1c + 2.5a + 收尾报告**（即**专注时单日 2–3 批**）。⇒ 本方案把"数据搬运 + 派生改造"部分按 **0.5–1 天/块**估算是**有锚点的**；**7 天总估的主要成分不是数据工作，而是两项无锚点工作**（见 (d)）。

**（d）不确定性**：

| 步 | 最大不确定项 | 依据 | 风险增量 |
|---|---|---|---|
| **A** | **前端 4 模板块 → schema 驱动表单**（约 120 行重写 + 拉取/缓存/hash） | **无历史锚点**（阶段 0 只改了 `useNotification.ts` 的轮询） | **+0.5 ～ 1 天**（Vue 类型/`vue-tsc` 摩擦） |
| **B** | **门禁 D6**（读 spec + 覆盖摘要 + 判别力测试） | **有摩擦史**：`notification_coverage.md:142-151` 记"三处门禁共用，改动须同步三处"，契约由 `tests/test_gate_coverage_summary.py`（12 例）锁定 | **+0.5 ～ 1 天** |
| **B** | spec 41 × 16 = **656 数据点搬运与核对** | 数据量大但机械 | +0 ～ 0.5 天 |
| **C** | 纯重构（无同类锚点） | 按 [04](04-refactor-P.md) 既有估算 | 保持 2 天 |

**（e）含 / 不含清单**：

| 含 | 不含 |
|---|---|
| 代码改造（后端 + 前端 + spec） | **决策者 review 往返**时间 |
| **门禁调整**（D6 + 判别力测试 + `gates.md` 登记） | **生产部署与验证**（本轮约束"不连生产"） |
| **文档联动**（G-031/G-037 要求的 `docs/` 同步 + `capabilities_registry.md` 重生成） | 灰度观察期 / 生产回归观察 |
| 测试改造与新增（S1 19 行、S2 6 处、步 A 2 处、D4 派生） | "前端重设计引发方案再评审"的时间 |
| `git` 提交整理与门禁跑通 | 三语文案的**人工翻译**（按每事件 3–6 键计，见遗留项 3） |

---

# 二、重做的方案

## 2.1 最终形态

```
pilotstd/core/notification/
├── events.py            【轻·零依赖】EventDef + ALL_EVENTS + ALL_EVENT_KEYS + BYPASS_EVENTS
├── event_spec.py        【新·重】EVENT_SPECS（15 字段 × 41 条）→ 单向 import events.py
├── channel_spec.py      【新】CHANNEL_SPECS（name/class/defaults/schema）
├── mapping.py           EVENT_MAPPINGS 由 EVENT_SPECS 派生（D1）
├── manager.py           【薄门面】装配 + 公开 API 转发 + _EVENT_BUILDERS 派生（D2）
├── _dispatcher.py       【新·步 C】编排（策略→聚合→静音→投递）
├── _manager_ops.py      （既有组合类）
├── _health.py           【新·步 C】投递健康度
├── _suppression_queue.py【新·步 C】静音与补发
└── _event_registry.py   【新·步 C】消息构建 + 校验（纯函数）
```

**三条护栏**：① `set(ALL_EVENT_KEYS) == {s.key for s in EVENT_SPECS}`；② `set(CHANNEL_KEY_WHITELIST) == set(CHANNEL_SPECS) == set(_CHANNEL_CLASSES)`；③ **方向守护**（`events.py` 不 import 内部模块；`_builders_*`/`channel.py` 不 import `events.py`/`manager.py`）。

## 2.2 分步路径与判据达成

| 步 | 目标 | 内容 | 原子性 | 判据 1 | 判据 2 | 判据 5 |
|---|---|---|---|---|---|---|
| **步 A｜渠道端到端** | 判据 1 达标 | ①`channel_spec.py`；②后端 5 处收敛；③新增 `GET /api/notification/channels`（接线 `get_config_schema()`）；④前端 3 文件改 schema 驱动（4 模板块 → 1 表单）；⑤修 `NotificationLogsView.vue:107-112` 漏 dingtalk；⑥同批改 `stage1c_fields.py:418,424-426` | **原子** | 11 → **2 ✅** | 11 | 11 |
| **步 B｜事件端到端** | 判据 2/5 达标 | **B1**：`event_spec.py` + D1/D2/D3/D4/D6；**B2**：D5（前端事件清单） | **B1 原子** | 2 | **B1 后 11；B2 后 2 ✅** | **B2 后 ≤2 ✅** |
| **步 C｜编排独立 + 薄门面** | D 前置 | [04](04-refactor-P.md) 按块剥离 + 编排独立 | 可渐进 | 2 | 2 | ≤2 |

**推荐顺序**：**步 A ∥ 步 B1** → **步 B2** → **步 C**。

## 2.3 验收判据（可断言）

| 步 | 判据 | 断言形式 |
|---|---|---|
| **A** | 判据 1 达标 | **实测演练**：临时分支加假渠道 → `git status --porcelain` 中 **代码文件（.py/.ts/.vue）计数 ≤2**；同时 `set(CHANNEL_SPECS) == set(CHANNEL_KEY_WHITELIST) == set(_CHANNEL_CLASSES)` |
| **A** | 前端渠道渲染正确 | 组件测试：渲染渠道集合 == `GET /api/notification/channels` 返回集合；`NotificationLogsView` 筛选选项含 4 渠道（**修好漏 dingtalk**） |
| **B1** | spec↔events 一致 | `set(ALL_EVENT_KEYS) == {s.key for s in EVENT_SPECS}` |
| **B1** | 4 处派生正确 | D1/D2/D3 集合断言 + D4 逐字段断言（含 `builder_file == spec.builder.__module__.replace('.','/') + '.py'`；**比对基准是 spec 定义值**，e2e 侧 `module` 存 i18n 键、`aggregation` 存 ASCII 枚举） |
| **B1** | 字段值机器可读 | 声明的字符串字面量**无中文**（与 G-047 同口径）；`module_key` 在三语包中均有实体键；`aggregation ∈ {aggregate, bypass}`；`levels` 按严重度升序（旧字段值"零行为变更"口径废止——展示文案一律走 i18n） |
| **B1** | **门禁判别力** | 注入"spec 缺 `trigger_file`" → **断言门禁 FAIL**（不是"跑通即通过"） |
| **B2** | 判据 2/5 达标 | **实测演练**：加假事件 → 代码文件 ≤2；删假事件 → 代码文件 ≤2 |
| **A/B/C** | 零行为变更 | 复用 [04](04-refactor-P.md) §3.2 的 Z1–Z4 |
| **全部** | G-010 | `manager.py`：步 A/B 后 ≤400；步 C 后 ≤250 |

## 2.4 代价与工作量（小时级）

| 步 | 项 | 小时 | 备注 |
|---|---|---|---|
| **A** | 渠道 spec + schema 复用（~50 行） | 2 | 读现状 1h + 写 1h |
| **A** | 后端 5 处收敛 + 一致性断言 | 2 | |
| **A** | 新端点 `GET /api/notification/channels` + 测试 | 2 | |
| **A** | **前端 4 模板块 → schema 驱动表单** | **6** | **最大不确定项**（无锚点） |
| **A** | `notification.ts` 类型 + `NotificationLogsView` 修 dingtalk | 1 | |
| **A** | 测试（`stage1c_fields` 2 处 + 端点 + 组件） | 2 | |
| **A** | 文档联动 + capabilities 重生成 | 1 | |
| | **小计** | **16h = 2 天** | |
| **B** | `event_spec.py` 656 数据点搬运与核对 | 6 | 从 5 处汇总，机械但量大 |
| **B** | D1 mapping 派生 + 断言 | 1 | |
| **B** | D2 manager 派生（G-010 净增 0 约束） | 1.5 | |
| **B** | D3 defaults 派生 | 0.5 | |
| **B** | D4 e2e 476 → 12 行 + `levels` 排序约定 + `aggregation` 字段 | 2 | |
| **B** | **D6 门禁读 spec + 覆盖摘要 + 判别力测试** | **3** | **有摩擦史** |
| **B** | D5 前端事件清单 + 组件测试 | 2 | |
| **B** | 测试改造 S1（19 行）+ S2（6 处） | 1 | |
| **B** | 文档联动 | 1 | |
| | **小计** | **18h = 2.25 天 → 保守 3 天** | |
| **C** | 按 [04](04-refactor-P.md) §3.6 的 P1–P5 | **16h = 2 天** | 纯重构，无锚点 |
| | **合计** | **50h ≈ 6.3 天 → 取 7 天（专注）** | 夹着做：日历 17–25 天 |

**结论**：7 天 = **数据/派生工作 24h（有 4 个历史锚点）** + **前端重设计 6h（无锚点）** + **门禁 3h（有摩擦史）** + **重构 16h（无锚点）** + **文档/测试 5h**。

## 2.5 与上轮 C 的差异（逐条）

| # | 上轮 C | 本轮定稿 | 依据 |
|---|---|---|---|
| 1 | C1 后端 / C2 前端（按层） | **按实体端到端**（步 A 渠道 / 步 B 事件） | 门禁不校验前端（实测零命中） |
| 2 | spec 模块数未定 | **两模块** | `events.py` 有 10 个消费方 |
| 3 | 未提 AST 约束 | **spec 必须 AST 可解析** | 门禁用 `ast.parse` |
| 4 | spec 15 字段 | **16 字段**（新增 `aggregation`） | 实测 `aggregation` 非常量（38 + 3） |
| 5 | "e2e 479 → 10 行" | **476 → ~12 行，但代价转移到 spec**；收益是**处数 6→1** 而非数据点减少 | §1.6.1 |
| 6 | "前端 70 行改读 spec" | **复用已有 `get_config_schema()`**（死代码接线） | `channels/base.py:43` 零调用方 |
| 7 | 判据 1 在 C1 为 3–4 | 修正为 **7–8** | §1.5 |
| 8 | 渠道声明 4 处 | **5 处** | `docker/api/notification.py:145-159` |
| 9 | 7 天无依据 | **小时级拆解 + 4 个历史锚点 + 不确定性表 + 含/不含清单** | §1.6.2、§2.4 |

---

# 三、裁决与遗留

## 三 1、五项待确认 → 全部裁决（2026-10-03）

| # | 原待确认 | 裁决 |
|---|---|---|
| **N1** | 分步方式：按实体端到端 vs 按层 | ✅ **按实体端到端** |
| **N2** | spec 模块数：2 vs 1 | ✅ **2 模块**（`events.py` 保轻 + `event_spec.py`） |
| **N3** | 前端清单更新：API 拉取 vs 构建期生成物 | ✅ **运行时 API 拉取** |
| **N4** | `payload_keys`：先显式 vs 直接自动派生 | ✅ **先显式声明**，后续自动化 |
| **N5** | 步 A 是否顺带修 `NotificationLogsView.vue:107-112` 漏 dingtalk | ✅ **顺带修** |

## 三 2、遗留到实施设计阶段的事项（**不阻塞定稿**）

| # | 事项 | 归属 | 说明 |
|---|---|---|---|
| 1 | `levels` 与 `aggregation` 的**序列化约定**（固定顺序元组 / 斜杠连接 / 排序规则） | 步 B1 实施设计 | 实测 `level` 6 个唯一值排序不统一（`info/error` vs `info/warning/error`），须定一个并同批改这 6 个字面值 |
| 2 | `channel_spec.py` 的 `schema` 字段如何与 `get_config_schema()` 对接（直接引用实现 vs 声明后校验） | 步 A 实施设计 | 涉及"声明 vs 实现"是否加断言（延伸 [00](00-framework.md) §七 #9 的门禁议题） |
| 3 | **三语文案的撰写工时**（每新事件 3–6 键 × 3 语言） | 所有步 | 本方案的时间表**不含人工翻译**；现 240 个 `notification.*` 键为存量 |
| 4 | `spec_hash` 的具体算法与放置位置（body / header） | 步 A 实施设计 | 仅影响缓存失效机制 |
| 5 | D6 门禁的**名称与编号**（是否沿用 G-045 还是新增 G-048） | 步 B 实施设计 | 与 [04](04-refactor-P.md) §3.7 的防膨胀门禁 G-048 编号存在潜在冲突，须一并决定 |

---

## 附：可复算命令

```powershell
# ── 澄清 1：e2e EVENTS 构成（AST）──
python -c "import ast,pathlib;s=pathlib.Path('tests/test_notification_e2e.py').read_text(encoding='utf-8');t=ast.parse(s);n=[x for x in ast.walk(t) if isinstance(x,ast.AnnAssign) and getattr(x.target,'id','')=='EVENTS'][0];print('lines',n.lineno,n.end_lineno,n.end_lineno-n.lineno+1,'entries',len(n.value.elts))"
(Select-String -Path tests\test_notification_e2e.py -Pattern '^\s+"name":').Count
(Select-String -Path tests\test_notification_e2e.py -Pattern '^\s+"aggregation":').Count
Select-String -Path tests\test_notification_e2e.py -Pattern '^\s+"aggregation":' | Group-Object { $_.Line.Trim() } | ForEach-Object { "$($_.Count) × $($_.Name)" }
Select-String -Path tests\test_notification_e2e.py -Pattern '^\s+"mutual":' | Where-Object { $_.Line -notmatch '""' } | ForEach-Object { $_.Line.Trim() }
Select-String -Path tests\test_notification_e2e.py -Pattern 'assert len\(EVENTS\)'
# ── 澄清 2：历史锚点 ──
git log --date=short --pretty="%h %ad %s" -25 -- pilotstd/core/notification tests/test_notification_e2e.py
Select-String -Path docs\plans\notification-redesign\06-阶段0-1实施方案.md -Pattern '预估半天'
# ── spec 字段反推的既有依据 ──
Select-String -Path pilotstd\core\notification\mapping.py -Pattern 'class EventMapping' -Context 0,8
Select-String -Path pilotstd\core\notification\channels\base.py -Pattern 'get_config_schema'
Get-ChildItem pilotstd,docker,tests,web -Recurse -File -Include *.py,*.ts,*.vue | Select-String 'get_config_schema|config_schema'
# ── 门禁 ──
python scripts/check_g_010_code_size.py
bash scripts/check_all.sh --fast
```

**自检**：代码引用 70+ 处（`路径:行号`，内容级回读见提交前脚本）；所有行数与计数为脚本实测、可复算；**本轮未改任何代码**。**本次定稿修正上轮两处**：① "e2e 479 行"实为 **476 行**、且"改 10 行"是**误导性收益表述**（数据点实际 625 → 656）；② spec 字段由 15 修正为 **16**（`aggregation` 实测非常量）。
