# 步 A 实施设计：渠道端到端收敛

> ## 🔧 本设计已修订（2026-10-03）
> **修订依据**：决策者五项裁决（§零 修订对照表）+ 两项核对数据（§十二/§十三）。
> **修订要点**：① 三处既有锁**判别力归零**（同源验证）⇒ 全部替换为**跨层验证**（§五、§七，含真代码）；② `ctor` **从 API 响应删除**（§三）；③ `secret` **不得删除**——实测其与 `mask` 非同集合（`webhook_url` 被掩码但用明文控件），**改名 `password`** 并明确唯一语义（§一、§九）；④ G-045 B 类**阻断**，且**重写为 4 项非恒真校验**（原第 1、2 项在派生后同样恒真，本轮更正）+ 逐项误报评估（§八）；⑤ N1/N2/N3/N5 已批，直接执行（§十四）。
> **⚠️ 本轮更正 07 号自身的两处设计错误**：**(a)** V6"`get_config_schema()` 字段集 == spec fields"在 §九 的派生实施后**恒真**（与裁决 1 指出的同一陷阱）⇒ 降为**单元测试**，门禁改锚定"声明类 vs 实现类"；**(b)** 原 §六 V7"零行为变更"缺少**呈现附加物**（wechat 的 hint/badge/分隔符）的表达 ⇒ spec 新增 3 个可选呈现字段，否则 schema 驱动后**视觉变更**。
>
> **本轮性质**：只修订设计，**不实施**。行号均为 2026-10-03 实测。
> **上游**：[06-spec-and-phasing.md](06-spec-and-phasing.md)（✅ 定稿 `a3269c98`）、[04-refactor-P.md](04-refactor-P.md)、[05-refactor-decision.md](05-refactor-decision.md)
> **约束**：禁止新增 mixin（`tests/test_architecture_mixin_guard.py:9,27-35`）；G-010 上限 500 不放宽（`scripts/check_g_010_code_size.py:29`）；步 A 零行为变更。

---

## 零、修订对照表（裁决 → 落点）

| 裁决 | 内容 | 落点 |
|---|---|---|
| **1** | 三处锁恒真 ⇒ 换跨层验证 | §五（原子性）、§七 7.2（真代码） |
| **2** | `ctor` 从 API 删除 | §一 1.1、§三 3.1、§九 |
| **3** | `mask`/`secret`：**保留掩码** ⇒ 删 `secret`？ | §一 1.1、§九 9.2（**结论文：不能删，改名 `password`**） |
| **4** | G-045 B 类**阻断** + 四项误报评估 | §八 8.2/8.3 |
| **5** | N1/N2/N3/N5 已批 | §十四 |

---

## 摘要（决策者读）

**一、五项裁决的执行结果**
1. **测试判别力（裁决 1）**：三处锁**逐处给出替换后的真代码**（§7.2）。核心原则=**跨层验证**：`spec ↔ API 响应 ↔ 前端渲染`，任一层漂移即 FAIL。其中 `:424-426` 的 `whitelist == _CHANNEL_CLASSES` 在 R1/R2 派生后**双方同源 ⇒ 恒真**，替换为**经 TestClient 取 API 响应**与 spec 对比（真正跨层）。
2. **`ctor` 删除（裁决 2）**：从 API 响应移除（§三）；**内部保留**供 `manager._init_channels` 使用（不入响应）。**实测结论：前端不需要 `kind`/`type` 判别符**——所有按渠道分支的逻辑（`:119-125`/`:217-220`/`:233-255`）均可由 `fields` + `status_rule` 派生。
3. **`mask`/`secret`（裁决 3）**：**"首次配置需明文输入"的场景确实存在**（首次配置时 8 个输入框需键入明文），**但该场景不需要 `secret`**。`secret` 的真实用途是**输入控件形态**，而它与 `mask` **不是同一集合**：`webhook_url` 被掩码（`docker/api/notification.py:129`）却用 **`InputText`**（`NotificationConfig.vue:333`）；`corpsecret` 用 **`InputText type="password"`**（`:346`）——**第三种形态**。⇒ **不能删**，**改名 `password`**（唯一语义：输入控件用密码形态）。**`mask` 必须保留**：它同时驱动 API 掩码与**前端"提交跳过掩码回显"**（`:177-179`，P1 修复，防掩码占位符覆盖真实凭据）。
4. **G-045 阻断（裁决 4）**：B 类**阻断**；并**重写为 4 项非恒真校验**（§8.2）——原设计的第 1、2 项在派生实施后**也恒真**（本轮更正）。四项误报风险评估中，**前端源码扫描为"中"风险**（现有 i18n 键字符串含 `wechat`）⇒ 给出"精确正则 + 白名单 + **缓阻断时限**"方案，**原则不变**。
5. **N1/N2/N3/N5（裁决 5）**：已批，逐条落地（§十四）。

**二、两项核对**
6. **核对 1（schema vs 前端，§十二）**：**不是完全等价**——**5 类差异**，其中 **(a) `wechat.webhook_url` 的 `required` 反向（schema=True vs 前端 optional）**、**(b) 5 个字段 schema 缺失** 是**必修**（否则交互/功能回退）；**(c) 11 处 placeholder**、**(d) `corpsecret` 控件形态**、**(e) 4 处标签来源** 需在 spec 显式表达或明确接受变更。
7. **核对 2（工时 §十三）**：16h → **23h（+7h）**逐项可追溯：spec +1h、**渠道 schema 补齐 +2h（全新）**、R6 +0.5h、端点 +0.5h、**G-045 B 类 +3h（全新）**；对比历史锚点（阶段 1a/1b/1c/2.5a 各 0.5–1 天）⇒ 23h ≈ **3 天（专注）**。

---

# 一、`channel_spec.py` 定义（修订）

## 1.1 字段清单

### 渠道级

| # | 字段 | 类型 | 用途 | **是否入 API 响应** | 消费方 |
|---|---|---|---|---|---|
| 1 | `name` | `str` | 渠道键 | ✅ | 各处 |
| 2 | `cls` | `type` | 实现类 | ❌ **仅后端** | `manager._init_channels` |
| 3 | **`ctor`** | `tuple[str, ...]` | **构造参数映射**（按序取凭证字段） | ❌ **不入响应**（裁决 2） | 仅 `manager._init_channels`（§二 R6） |
| 4 | `label_key` | `str` | 渠道显示名 i18n 键 | ✅ | 前端 `CHANNELS[].labelKey`（`:97-100`）；`NotificationLogsView` |
| 5 | `icon` | `str` | 图标类名 | ✅ | 前端 `:97-100` |
| 6 | `enabled_default` | `bool` | 配置页默认启用态 | ✅ | `docker/api/notification.py:149,157-159` |
| 7 | `fields` | `tuple[FieldSpec, ...]` | 表单字段 | ✅ | schema / API defaults / 前端表单 |
| 8 | `status_rule` | `StatusRule` | "已配置"判定（声明式） | ✅ | 前端 `chStatus`（`:233-246`）+ `chSeverity`（`:249-255`） |
| 9 | **`hint_key`** | `str \| None` | **渠道级提示文案键**（可选） | ✅ | 前端 wechat 的 `<p>` 提示（`:330`）——**本轮新增，保零视觉变更** |

### 字段级（`FieldSpec`）

| # | 字段 | 类型 | 用途 | **是否入响应** | 实测依据 |
|---|---|---|---|---|---|
| 1 | `name` | `str` | 字段名 | ✅ | 各处 |
| 2 | `type` | `str` | 控件类型：`"string"` / `"password"` **/ `"text_password"`** | ✅ | 实测**三种**形态：`InputText`（`:321,333,338…`）、`Password`（`:317,365,380`）、**`InputText type="password"`**（`:346`） |
| 3 | `label_key` | `str` | 后端标签键 | ✅ | schema 的 `label: t("notification.channel.config.*")` |
| 4 | `label` | `str` | 后端译文（兜底） | ✅ | 同上（调用期求值） |
| 5 | `required` | `bool` | 必填标记 | ✅ | schema `"required"` |
| 6 | **`mask`** | `bool` | **API 响应是否掩码 + 前端提交是否跳过掩码回显** | ✅ | `docker/api/notification.py:129` + `NotificationConfig.vue:173,177-179` |
| 7 | **`password`** | `bool` | **输入控件是否用密码形态**（原 `secret`，**改名**） | ✅ | 前端 3 处 `Password` + 1 处 `InputText type="password"` |
| 8 | `placeholder` | `str` | 输入提示 | ✅ | 前端 **11 处**硬编码（`:317,321,333,338,342,346,350,361,365,376,380`） |
| 9 | **`badge_key`** | `str \| None` | 字段级徽标文案键（可选） | ✅ | wechat `webhook_url` 的"群机器人"徽标（`:332`）——**本轮新增** |
| 10 | **`divider_before`** | `bool` | 该字段前是否插入分隔符（可选） | ✅ | wechat 的 `field-sep`（`:335`，"自建应用"分段）——**本轮新增** |

**为什么 `mask` 与 `password` 必须分开（实证）**：

| 字段 | `mask` | `password` | 现状证据 |
|---|---|---|---|
| `webhook_url` | **True** | **False** | 被 API 掩码（`docker/api/notification.py:129`）但用 `InputText`（`:333,361,376`） |
| `bot_token` | True | True | 掩码 + `Password`（`:317`） |
| `secret`（feishu/dingtalk） | True | True | 掩码 + `Password`（`:365,380`） |
| `corpsecret` | True | **True**（形态为 `InputText type="password"`） | 掩码（`:129`）+ `:346` |
| `corpid` / `agentid` / `chat_id` / `proxy_url` | False | False | 明文 + `InputText` |

⇒ **两个集合不等价**（`webhook_url` 是反例）⇒ **合并二者会改变行为**（要么停止掩码＝安全面变更，要么把 webhook 变密码框＝交互变更）。

## 1.2 静态可解析约束（不变）

- `channel_spec.py` **不被门禁 AST 读取**（G-045 只 AST 读 `events.py`：`audit_notification_coverage.py:60`）⇒ 允许 `cls` 引用与推导；
- **但** `channel.py` 的 `CHANNEL_KEY_WHITELIST` **被测试文本断言**（`stage1c:435-440`）⇒ 派生赋值**必须保留该名字**（§7.2 保留该项）；
- **环依赖**：渠道类内**函数级延迟 import** `channel_spec`（与 `channel.py:107` 既有口径一致）。

---

# 二、六处后端收敛点（R1–R6）

| # | 位置 | 改什么 | 派生自 | 备注 |
|---|---|---|---|---|
| **R1** | `channel.py:28` | `CHANNEL_KEY_WHITELIST` → `= CHANNEL_NAMES` | spec | **保留名字**（`stage1c:435` 文本断言） |
| **R2** | `manager.py:80-85` | `_CHANNEL_CLASSES` → `{s.name: s.cls for s in CHANNEL_SPECS}` | spec | 必须仍从 `manager` 可导入（`stage1c:424` 的 import 行不变） |
| **R3** | `_policy.py:9` | **删除**（实测文件内零引用：`:14/:25/:29/:64/:84` 均不用它） | — | 零行为影响 |
| **R4** | `docker/api/notification.py:327` | 硬编码元组 → `CHANNEL_NAMES` | spec | |
| **R5** | `docker/api/notification.py:145-159` | 4 个 `build_channel` 字面量 → 由 `enabled_default` + `fields` 生成 | spec | 键集合须与现状**逐键相等** |
| **R5b** | `docker/api/notification.py:129` | 掩码清单 → 由 `FieldSpec.mask` 驱动 | spec | **取值保持现状**（`webhook_url` 继续掩码） |
| **R6** | `manager.py:256-272` | 按渠道名的 if/elif 构造 → 按 `s.ctor` 收集参数后 `cls(*args)` | spec | **`ctor` 仅内部使用**（裁决 2） |

**无需改**：`_persist_config_and_audit`（`:251-313`，委托 `_cred_helper.set_channel`，渠道无关）、`_credentials.py`（`:40/:60/:115/:155` 渠道无关）、`channels/__init__.py`。

---

# 三、`GET /api/notification/channels` 契约（修订）

## 3.1 响应（**已删 `ctor`**）

```json
{
  "spec_hash": "a1b2c3d4e5f60718",
  "channels": [
    {
      "name": "wechat",
      "label_key": "notification.channel.wechat",
      "icon": "pi pi-comments",
      "enabled_default": true,
      "hint_key": "notification.config.wechat.hint",
      "fields": [
        {"name": "webhook_url", "type": "string",
         "label_key": "notification.channel.config.webhook_url", "label": "Webhook URL",
         "required": false, "mask": true, "password": false,
         "placeholder": "https://qyapi.weixin.qq.com/...",
         "badge_key": "notification.config.wechat.group_robot_badge",
         "divider_before": false},
        {"name": "corpsecret", "type": "text_password", "required": false,
         "mask": true, "password": true, "placeholder": "..."},
        {"name": "corpid", "type": "string", "required": false, "mask": false, "password": false,
         "placeholder": "ww...", "divider_before": true}
      ],
      "status_rule": {"any_of": [["corpid","agentid","corpsecret"], ["webhook_url"]]}
    }
  ]
}
```
**删除项**：`ctor`（裁决 2）——它是后端实现细节（§二 R6）。
**新增项**：`hint_key`（渠道级）、`badge_key`/`divider_before`（字段级）——**为保零视觉变更**（实测 wechat 独有 `:330`/`:332`/`:335` 三处）。
**不含凭证值**（与 `GET /api/notification/config` 职责分离）。

## 3.2 前端是否需要 `kind`/`type` 判别符？—— **实测：不需要**

| 前端现有按渠道分支的逻辑 | 行号 | 可否由 spec 派生 |
|---|---|---|
| `loadConfig` 回填 | `:119-125+` | ✅ 按 `fields` 遍历 |
| `testChannel` 参数组装 | `:217-220` | ✅ 按 `fields` 收集 |
| `chStatus` | `:233-246` | ✅ `status_rule` |
| `chSeverity` | `:249-255` | ✅ `status_rule`（复用） |
| 4 个模板块 | `:314-385` | ✅ 按 `fields` + 呈现附加物 |
⇒ **不引入 `kind`**（裁决 2 的例外不成立）。

## 3.3 版本 / 缓存 / `spec_hash`（不变）

- **无 URL 版本**（沿用 `/api/notification/*` 风格：`docker/api/notification.py:110,342,386,404,441`）；
- 前端**模块级缓存** `{spec_hash, payload}`；mount 拉一次 + `saveConfig` 后强制重拉；**不轮询**；
- **`spec_hash`** = `sha256(规范化 JSON(响应体去掉 spec_hash))[:16]`，**放在响应体**，不写模块常量/不写 header；后端不缓存。

---

# 四、前端 schema 驱动改造清单（修订：13 处）

| # | 行号 | 现状 | 改为 |
|---|---|---|---|
| F1 | `:44-50` | `channels` 默认值：**每渠道 10 字段超集**（`enabled/webhook_url/bot_token/chat_id/secret/corpid/agentid/corpsecret/proxy_url/events`） | 由 `fields` 并集构建（保留 `events`） |
| F2 | `:96-101` | `CHANNELS` 4 项（含 `icon`/`labelKey`） | API 派生 |
| F3 | `:103-108` | `channelOpen` 4 键 | API 渠道名派生 |
| F4 | `:119-125+` | 按渠道 if/else 回填 | 通用遍历 |
| F5 | `:173` | `SENSITIVE_FIELDS` 4 项硬编码 | `fields.filter(f => f.mask).map(f => f.name)` |
| F6 | `:189-193` | 4 渠道显式传参 | 按 API 渠道名遍历 |
| F7 | `:197-200` | 策略保存循环 4 名 | 遍历 |
| F8 | `:217-220` | `testChannel` 4 分支参数 | 按 `fields` 收集 |
| F9 | `:233-246` | `chStatus` 渠道特有判定 | `evalStatusRule(spec.status_rule, form)` |
| F10 | `:249-255` | `chSeverity`（重复逻辑） | 复用 `evalStatusRule` |
| F11 | `:314-385` | **4 个 `v-if` 模板块** | 1 个 `v-for="f in ch.fields"`，按 `f.type` 选控件（`string`→`InputText`；`password`→`Password`；**`text_password`→`InputText type="password"`**）；处理 `f.badge_key`/`f.divider_before`；渠道级 `hint_key` |
| F12 | `:316,332,360,375` | 硬编码英文 `Bot Token`/`Chat ID`/`Webhook URL`×3 | 三级回退（N2）：前端 locales → `label_key` → `label`（**见 §十二 差异 (e)**） |
| F13 | 新增 | — | `evalStatusRule()` 工具（解释 `all_of`/`any_of`） |
| L1 | `NotificationLogsView.vue:107-112` | `channelOptions` **漏 dingtalk** ★ | API 派生（**顺带修复漂移**） |
| L2 | `NotificationLogsView.vue:120-124` | `CHANNEL_KEYS` 3 键（同缺） | API `label_key` 派生 |

---

# 五、原子性边界（修订）

## 5.1 **三处锁的判别力分析（裁决 1 的核心）**

| 原锁 | 位置 | 现状判别力（spec 化前） | **spec 化后判别力** | 处置 |
|---|---|---|---|---|
| `set(CHANNEL_KEY_WHITELIST) == {"wechat","dingtalk","feishu","telegram"}` | `:416-420` | ✅ 强（字面量 vs 常量） | ✅ **仍强**——若 `CHANNEL_KEY_WHITELIST` 派生自 spec，则测的是 **spec 内容**（字面量是独立锚点） | **改写为测 spec**（§7.2 T1） |
| `set(CHANNEL_KEY_WHITELIST) == set(_CHANNEL_CLASSES)` | `:422-426` | ✅ 强（两处独立声明） | ❌ **恒真**——R1/R2 后两者**同源**（都派生自 `CHANNEL_SPECS`） | **替换为跨层：API 响应 ↔ spec**（§7.2 T2） |
| `channel.py` 源码含 `CHANNEL_KEY_WHITELIST` + 短语 | `:435-441` | ✅ 中（源码文本） | ✅ **仍有效**（与派生无关） | **保留**（§7.2 T3，不动） |

## 5.2 必须同批的改动

- **后端**：`channel_spec.py` + R1–R6 + 渠道类 schema 补齐（§十二 必修项）**必须同批**——否则出现"部分读 spec、部分读字面量"的双源态；
- **API + 前端**：`GET /channels` 与前端 13+2 处**同批**（否则前端读不到新端点）；
- **G-045 B 类**：与 R1–R6 同批（B 类校验的对象就是这些），否则门禁先红。

## 5.3 回滚粒度与中间态

| 项 | 内容 |
|---|---|
| 整步回滚 | `git revert`；**无 schema 变更、无迁移号、无配置变更** |
| 建议拆分 | **A1**（spec + R1–R6 + schema 补齐 + G-045 B 类）／**A2**（API 端点 + 前端 15 处） |
| 中间态 | A1 后：后端全派生、**前端仍硬编码** ⇒ 渠道集合一致，但**新渠道不会自动出现在前端** ⇒ **此时不得宣称判据 1 达标**（决策者已接受此中间态） |

---

# 六、验收判据（修订：V6 去恒真、V7 加呈现项）

| # | 判据 | 断言形式 |
|---|---|---|
| **V1** | 渠道声明收敛 | `set(CHANNEL_KEY_WHITELIST) == set(CHANNEL_NAMES) == set(_CHANNEL_CLASSES) == {s.name for s in CHANNEL_SPECS}` |
| **V2** | 加渠道 ≤2 代码文件 | 实测演练（临时分支加假渠道 → `git status --porcelain` 中 `.py/.ts/.vue` 计数 ≤2） |
| **V3** | 前端零渠道字面量 | 见 §7.2 T5（**精确正则 + 白名单**，避免误报） |
| **V4** | `spec_hash` 判别力 | 两次调用同 hash；追加一个 `FieldSpec` → hash **必须变化** |
| **V5** | API 契约 | 含 4 渠道 + 必备字段；**断言 `ctor` 不在响应中**；无凭证值 |
| **V6** | **（修订）spec 自洽 + 声明 vs 实现** | ① spec 内部：字段名唯一、`ctor ⊆ fields 名`、每渠道 `fields` 非空、`type ∈ {string,password,text_password}`；② **声明 vs 实现**：`{s.cls for s in CHANNEL_SPECS}` == AST 扫 `channels/*.py` 得到的 `NotificationChannel` **直接子类集合**。**⚠️ 原 V6"`get_config_schema()` == spec.fields"在 §九 派生后恒真，已降为单元测试**（§7.2 T4） |
| **V7** | 零行为变更回归 | ① `GET /config` → `PUT /config` 往返：**逐字段键集合与掩码态相等**（含 `webhook_url` 仍掩码）；② `POST /test` 的 `params` 组装**快照一致**；③ 既有通知/渠道测试全绿；④ **（新增）呈现回归**：wechat 的 `hint`/`badge`/分隔符在 schema 驱动后**仍渲染**（否则视觉变更） |
| **V8** | G-045 B 类可判别 | 注入"声明有 fake 渠道但无实现类" → **断言门禁 FAIL**；注入"某事件缺 zh_TW" → **断言门禁 FAIL**（A 类不退化） |
| **V9** | G-010 未越线 | `check_g_010_code_size.py` 退出码 0；`audit_notification_coverage.py` 有效行 **≤500** |

---

# 七、测试策略（修订：含真代码）

## 7.1 现有测试的改动面

| 文件 | 是否必改 | 说明 |
|---|---|---|
| `tests/test_notification_stage1c_fields.py` | **必改 2 处**（`:416-420` 改写、`:422-426` 替换） | `:435-443` **保留不动**（源码文本断言仍有判别力） |
| `tests/unit/core/notification/test_channels_base.py` | **需复核** | 是否断言 `get_config_schema()` 字段数（补齐 5 字段可能破坏） |
| `tests/test_notification_api.py` | **需复核** | `GET /config` 响应键集合快照 |
| `tests/test_notification_credentials.py` | **需复核** | 是否断言掩码字段清单 |

## 7.2 三处锁的替换（**真代码**）

**T1 — 替换 `:416-420`（验证 spec 内容，独立字面量锚点）**

```python
    def test_spec_contains_all_four_channels(self):
        """spec 必须恰好声明 4 个已知渠道；桌面/Web 不计入（无句柄 / 无推送）。"""
        from pilotstd.core.notification.channel_spec import CHANNEL_SPECS

        self.assertEqual({s.name for s in CHANNEL_SPECS},
                         {"wechat", "dingtalk", "feishu", "telegram"})
        for excluded in ("desktop", "web", "desktop_toast"):
            self.assertNotIn(excluded, {s.name for s in CHANNEL_SPECS})
```
**判别力**：spec 少一个渠道、多一个渠道、改名 → **FAIL**。
**测不到**：spec 与 whitelist/实现类/API 的一致性（由 T2/T4/门禁 B 类承担）。

**T2 — 替换 `:422-426`（跨层：API 响应 ↔ spec）**

```python
@pytest.mark.xdist_group("notification")
def test_channels_endpoint_matches_spec(notif_client_and_db, notif_cookies):
    """跨层：`GET /api/notification/channels` 的渠道集合必须等于 spec 声明。"""
    from pilotstd.core.notification.channel_spec import CHANNEL_SPECS

    client, _ = notif_client_and_db
    r = client.get("/api/notification/channels", cookies=notif_cookies)
    assert r.status_code == 200, f"应返回 200，实际 {r.status_code}: {r.text}"
    body = r.json()
    assert {c["name"] for c in body["channels"]} == {s.name for s in CHANNEL_SPECS}
    # 字段级跨层：API 每渠道字段名集合 == spec 每渠道字段名集合
    spec_by_name = {s.name: {f.name for f in s.fields} for s in CHANNEL_SPECS}
    for c in body["channels"]:
        assert {f["name"] for f in c["fields"]} == spec_by_name[c["name"]]
    # 裁决 2：ctor 不得出现在响应中
    assert all("ctor" not in c for c in body["channels"])
```
（复用既有 fixture `notif_client_and_db`（`tests/test_notification_api.py:175-238`）与 `notif_cookies`（`:241-252`），无需新建基建。）
**判别力**：API 硬编码渠道列表、漏渠道、字段漂移、`ctor` 回流 → **FAIL**。
**测不到**：spec 自身是否正确（由 T1 承担）。

**T3 — `:435-443` 保留（不动）**：源码文本断言（`channel.py` 含 `CHANNEL_KEY_WHITELIST` 与短语 `未投递的渠道不出现在 dict 中`，短语实测位于 `channel.py:22`）+ 02 文档含 `channel_message_ids`。**判别力**：派生赋值若改名/删除常量 → FAIL。

**T4（新增，替代原 V6 的恒真部分）— spec ↔ 渠道实现（单元测试）**

```python
def test_get_config_schema_matches_spec_fields():
    """跨层：渠道类实现的 get_config_schema() 与 spec 字段集合一致。

    注意：§九 后 get_config_schema() 由 spec 派生，本用例退化为"派生正确性"回归；
    真正的"声明 vs 实现"由门禁 B 类（类集合）与 V6② 承担。
    """
    from pilotstd.core.notification.channel_spec import CHANNEL_SPECS

    for s in CHANNEL_SPECS:
        inst = s.cls(*_dummy_args_for(s))          # 用假凭证实例化
        assert set(inst.get_config_schema()) == {f.name for f in s.fields}, s.name
```

**T5（新增）— 前端零渠道字面量（**精确正则 + 白名单**，见 §8.3 误报评估）**

```python
def test_frontend_has_no_channel_literals():
    """前端不得硬编码渠道键；允许 i18n 键字符串（含渠道名）与注释。"""
    import re
    from pathlib import Path

    pattern = re.compile(r"""(?<![\w.])['"](wechat|telegram|feishu|dingtalk)['"](?![\w])""")
    allow = re.compile(r"notification\.(channel|config)\.")
    for rel in ("web/src/components/NotificationConfig.vue",
                "web/src/views/NotificationLogsView.vue"):
        for i, line in enumerate(Path(rel).read_text(encoding="utf-8").splitlines(), 1):
            if allow.search(line) or line.lstrip().startswith(("<!--", "//", "*")):
                continue
            assert not pattern.search(line), f"{rel}:{i} 含渠道名字面量"
```

## 7.3 新增测试清单（合计 9）

| 类 | 用例 | 断言 |
|---|---|---|
| 契约（3） | `test_spec_contains_all_four_channels` | T1 |
| | `test_channels_endpoint_matches_spec` | T2（跨层） |
| | `test_get_config_schema_matches_spec_fields` | T4 |
| 自洽（3） | `test_spec_field_names_unique_per_channel` | 每渠道字段名无重复 |
| | `test_ctor_refs_exist_in_fields` | `set(s.ctor) ⊆ {f.name for f in s.fields}` |
| | `test_field_types_are_known` | `f.type ∈ {"string","password","text_password"}` |
| 守卫（2） | `test_frontend_has_no_channel_literals` | T5 |
| | `test_mask_and_password_are_independent` | `webhook_url`: `mask=True, password=False`；`corpsecret`: `mask=True, password=True` |
| API（1） | `test_spec_hash_stable_and_sensitive` | 同 spec 同 hash；改 spec 则变 |

## 7.4 回滚后测试如何恢复

纯 `git revert`（A1/A2 两 commit）；替换后的测试随同批回退 ⇒ 回归基线不变。

---

# 八、G-045 就地扩展（修订：阻断 + 4 项非恒真校验）

## 8.1 扩展后的校验范围

| 类 | 管 | 不管 |
|---|---|---|
| **A 类（原有，不动）** | 每事件：i18n 三语、e2e 覆盖 + `trigger_file` 存在、安全类 `write_audit` | 事件语义、文案质量、`level/module/aggregation/builder_keys` 一致性（阶段 B） |
| **B 类（新增，**阻断**）** | 见 §8.2 四项 | 前端**运行时**行为、渠道连通性、`spec_hash` 稳定性（属 API 测试） |

## 8.2 B 类四项校验（**已重写为非恒真**）

> **⚠️ 本轮更正**：07 号原设计的 B 类第 1 项（`whitelist == _CHANNEL_CLASSES`）与第 2 项（`get_config_schema() == spec.fields`）在 R1/R2/§九 实施后**双双恒真**——与裁决 1 指出的陷阱同源。故重写为下列四项，全部锚定**非派生**对象。

| # | 校验 | 锚定物（**非派生**） | 判定 |
|---|---|---|---|
| **B1** | **声明 vs 实现**：`{s.cls for s in CHANNEL_SPECS}` == AST 扫 `pilotstd/core/notification/channels/*.py` 得到的 `NotificationChannel` **直接子类**集合（排除基类自身） | 真实存在的渠道类（源码） | 差集非空 → FAIL |
| **B2** | **spec 自洽性**：每渠道 `fields` 非空；字段名渠道内唯一；`type ∈ {string,password,text_password}`；`set(ctor) ⊆ 字段名`；`label_key` 以 `notification.` 开头 | spec 自身结构（唯一来源的**内部**一致性） | 任一项违反 → FAIL |
| **B3** | **后端无渠道名字面量**：AST 检查 `manager._init_channels` 与 `docker/api/notification.py` 中**不含**"与渠道名常量比较"的 `if/elif`、也不含"含渠道名的 `in` 元组" | 源码结构（AST，非文本） | 命中 → FAIL |
| **B4** | **前端无渠道名字面量**：精确正则 + i18n 键白名单（同 T5） | 前端源码 | 命中 → FAIL |

## 8.3 四项误报风险评估

| 项 | 误报源 | 风险 | 处置（**不改变"必须阻断"原则**） |
|---|---|---|---|
| **B1** | 新增渠道类但暂未登记 spec（**这正是要拦的漂移**）；或渠道类定义在别的目录/间接继承 | **低** | 判定锁定"`channels/*.py` 中 `class X(NotificationChannel)` 直接子类"；间接继承暂不检测（登记在"未覆盖说明"） |
| **B2** | 无（纯 spec 内部数据检查） | **零** | 无需处置 |
| **B3** | **中文/英文渠道名出现在注释或文档字符串**（如 `channel.py:22`、`channels/base.py:7,40`） | **低**（AST 只取 `Compare`/`In` 节点中的 `Constant`，天然跳过注释与 docstring） | 用 AST 而非文本匹配 |
| **B4** | **现有 i18n 键字符串含渠道名**（`NotificationLogsView.vue:121` `'notification.channel.wechat'`）+ 模板注释（`:328` `<!-- 企业微信 -->`） | **中** | ① 精确正则（要求渠道名**独占**字符串字面量或 `key:` 位置）；② **白名单** `notification.(channel|config).`；③ 跳过注释行；④ **若首版误报仍高 → 缓阻断**：先以**警告**上线一个迭代并记录，正则收紧后**转阻断**（**时限：同一阶段内，不得跨步**） |

## 8.4 输出格式 / 文档更新点 / 兼容性 / 文件位置

- **错误分类**：`[A]` / `[B]` 前缀；`main` 返回码 = `A_blocking + B_blocking > 0 → 1`；既有 `❌ 阻断缺口`/`✅ 无阻断缺口` 前缀**保留**；
- **`[覆盖摘要]`**：在"检查项/检查口径"里**分开计数**（A 类 41 事件 / B 类 4 渠道 × 4 校验）；
- **文档更新点（同批 5 处）**：`docs/governance/gates.md:30`（表行加 B 类 + 阻断条件）、`:417`（详述节加 B 类判定与示例）；`docs/governance/notification_coverage.md:9`（§一加 B 类小节）、`:31`（§二矩阵加 B 类矩阵）、`:133`（§五更新 G-045 描述与摘要口径）；
- **兼容性**：`_audit_one_event`（`scripts/audit_notification_coverage.py:169`）**不动**；B 类为**新增函数**在 A 类之后追加；
- **文件与编号**：仍为 `scripts/audit_notification_coverage.py`（现 **337 行** → 预计 **≈430 行**，**未越 500**）；挂载点 `check_all.sh:137-146` 与 `ci.yml:450-451` 不变。

---

# 九、遗留项 2：`schema` 与 `get_config_schema()` 对接（修订）

## 9.1 派生方向与实现方式

- **单一来源** = `CHANNEL_SPECS[].fields`；
- `get_config_schema()` **由 spec 派生**：`{f.name: {"type": f.type, "label": f.label, "required": f.required, "secret": f.password} for f in fields}`（**保留 `secret` 键名以兼容既有抽象契约**——`channels/base.py:44` 与 4 个实现现用该键名）；
- 渠道类内**函数级延迟 import**（破环）；
- **保留该方法**（N3 已批）：它是 ABC 契约（`channels/base.py:42-44`）。

## 9.2 `mask` / `password`（原 `secret`）的最终处理（裁决 3 的执行）

| 问题 | 回答（**事实**） |
|---|---|
| 有没有"用户首次配置需明文输入"的场景？ | **有**——首次配置时 DB 无值，用户须在 8 个输入框（`:317,321,333,338,342,346,350,361,365,376,380` 中除只读项外）键入明文。**但该场景与 `secret` 字段无关**：输入框一律接受明文键入，"是否需要 `secret`"取决于**控件形态**。 |
| 那 `secret` 能删吗？ | **不能**（但应改名）：实测 `webhook_url` **被掩码却用 `InputText`**（`docker/api/notification.py:129` vs `NotificationConfig.vue:333`），而 `bot_token`/`secret`/`corpsecret` 用密码形态（`:317,365,380,346`）⇒ **两个集合不等价**。 |
| 最终方案 | **改名 `password`**（语义：输入控件用密码形态），在 API 响应中保留；**`mask` 保留**（驱动响应掩码 + 提交跳过掩码回显） |
| `mask` 的必要性 | 删除它会导致：① API 明文返回凭据（安全面变更）；② 前端把掩码占位符 `***` 写回 DB（`:177-179` 的 P1 修复失效）⇒ **凭据被占位符覆盖** |
| `get_config_schema()` 的 `secret` 键 | **保持该键名**（值取 `f.password`）——避免改动 ABC 契约与 4 个既有实现的调用方 |

---

# 十、遗留项 4：`spec_hash`（不变，摘要）

`sha256(规范化 JSON(响应体去掉 spec_hash 字段))[:16]`；**放响应体**（不放 header / 模块常量 / DB）；前端比对不一致即刷新缓存；后端不缓存；阶段 B 可把事件+渠道合并进同一 hash。

---

# 十一、风险（修订）

| # | 风险 | 影响 | 对策 |
|---|---|---|---|
| R-1 | 前端 4 模板块 → 动态表单（无历史锚点） | +0.5~1 天；`vue-tsc` 摩擦 | 保留 `ChannelFormState` 为宽松形状；先跑 `vue-tsc` |
| R-2 | **schema 补齐遗漏/取值错**（§十二的 (a)(b)） | **高**（功能回退） | V6① + 逐渠道字段数断言（wechat **5**/feishu **2**/telegram **2**/dingtalk **2**）+ `required` 逐字段比对 |
| R-3 | **`corpsecret` 控件形态**（`InputText type="password"` vs `Password` 组件） | 中（视觉） | spec 的 `type="text_password"` 显式表达；V7④ 呈现回归 |
| R-4 | 文案来源切换引入 diff（§十二 (e)） | 中 | 三级回退**优先前端 locales**（N2）；4 处硬编码英文**保持字面量**或同批补 i18n（见待裁决 N6） |
| R-5 | **B4 前端扫描误报**（i18n 键/注释含渠道名） | 中 | 精确正则 + 白名单 + 跳注释；必要时**缓阻断（限本阶段内）** |
| R-6 | `manager._init_channels` 改派生后**构造顺序错** | 高 | `ctor` 显式声明 + 逐渠道实例化单测 |
| R-7 | G-045 扩展误伤既有 PASS | 中 | B 类不触碰 A 类逻辑；本地全绿再提交 |

---

# 十二、核对 1：schema 补齐后的**逐字段差异清单**

> 对比对象：**补齐后的 `get_config_schema()`**（spec 派生） vs **前端现有硬编码**（`NotificationConfig.vue:314-385`）。

| 渠道 | 字段 | spec/schema 值 | 前端值（`路径:行号`） | 一致？ | 差异与影响 |
|---|---|---|---|---|---|
| telegram | `bot_token` | `type=password, required=True, mask=True, password=True` | `Password`, `required`, `placeholder="123456:ABC-DEF"`, label 字面量 `Bot Token`（`:316-317`） | ⚠️ 部分 | 缺 `placeholder`；label 来源不同（schema 亦为字面量 `Bot Token`，`telegram.py:226`，**文案一致**） |
| telegram | `chat_id` | `required=True, mask=False` | `InputText`, `required`, `placeholder="-1001234567890"`, label `Chat ID`（`:320-321`） | ⚠️ 部分 | 缺 `placeholder`；label：schema 用 i18n 键（`notification.channel.config.chat_id`）→ 中文界面显示中文，**前端现为英文** ⇒ **文案差异 (e)** |
| wechat | `webhook_url` | **`required=True`**（`wechat.py:93`）, `mask=False`（`wechat.py:94`） | `InputText`, **optional**（`:332` 显示 `group_robot_badge` 徽标）, `placeholder="https://qyapi.weixin.qq.com/..."`（`:333`） | ❌ **不一致** | **(a) `required` 反向**——按 schema 渲染会出现必填星号 ⇒ **交互变更**；**(b) `mask` 反向**——前端 `InputText` 但 API 掩码，**spec 必须设 `mask=True`**（否则响应变明文＝安全面变更）；缺 `placeholder`、`badge_key` |
| wechat | `corpid` | **schema 缺失** | `InputText`, optional, `placeholder="ww..."`, label i18n（`:336-338`） | ❌ **缺失** | **(b) 必须补齐** `required=False, mask=False` |
| wechat | `agentid` | **schema 缺失** | `InputText`, optional, `placeholder="1000001"`（`:340-342`） | ❌ | (b) 补齐 |
| wechat | `corpsecret` | **schema 缺失** | **`InputText type="password"`**, optional, `placeholder="..."`（`:344-346`） | ❌ | **(b) 补齐** + **(d) 控件形态第三种**（`type="text_password"`） |
| wechat | `proxy_url` | **schema 缺失** | `InputText`, optional, `placeholder="http://proxy:8080"`（`:348-350`） | ❌ | (b) 补齐 |
| wechat | — | 无渠道级提示 | `hint` 提示段落（`:330`）+ `app_sep` 分隔符（`:335`） | ❌ | **(f) 呈现附加物** ⇒ spec 新增 `hint_key` / `divider_before` |
| feishu | `webhook_url` | `required=True`（`feishu.py:102`） | `InputText`, `required`, `placeholder="https://open.feishu.cn/..."`（`:360-361`） | ✅（除 placeholder） | 缺 `placeholder` |
| feishu | `secret` | **schema 缺失** | `Password`, optional, `placeholder=i18n`（`:363-365`） | ❌ **缺失** | **(b) 必须补齐** `required=False, mask=True, password=True` |
| dingtalk | `webhook_url` | `required=True`（`dingtalk.py:135`） | `InputText`, `required`, `placeholder="https://oapi.dingtalk.com/robot/..."`（`:375-376`） | ✅（除 placeholder） | 缺 `placeholder` |
| dingtalk | `secret` | `required=False, secret=True`（`dingtalk.py:141-142`） | `Password`, optional, `placeholder="SEC..."`（`:379-380`） | ✅（除 placeholder） | 缺 `placeholder` |

## 结论：**不完全等价**——5 类差异

| 类 | 内容 | 必修？ | 影响 |
|---|---|---|---|
| **(a)** | `wechat.webhook_url.required`：schema `True` vs 前端 optional | **必修** | 否则渲染出必填星号（交互变更） |
| **(b)** | schema **缺 5 个字段**（wechat 4 + feishu 1） | **必修** | 否则 schema 驱动后**这 5 个输入框消失** ⇒ **功能回退** |
| **(c)** | **11 处 `placeholder`** 未在 schema | 必修（N5 已批） | 缺则提示丢失 |
| **(d)** | `corpsecret` 控件形态（`InputText type="password"`）需第三种 `type` | 必修（保零视觉变更） | 否则换成 `Password` 组件（多出眼睛图标） |
| **(e)** | **4 处标签**：`Bot Token`/`Chat ID`/`Webhook URL`×3 —— schema 侧 1 处字面量一致、3 处为 i18n 译文 | 待裁决 **N6** | 若按 schema 译文渲染，中文界面标签由英文变中文（**属改进但非零 diff**） |
| **(f)** | wechat 的 `hint`/`badge`/`divider` 三项呈现附加物无 schema 表达 | 必修（已加入 spec） | 否则视觉变更 |

---

# 十三、核对 2：工时涨幅明细（16h → 23h，**+7h**）

| 项 | 06 号定稿 | 修订后 | 涨幅 | **原因** | 依据 |
|---|---|---|---|---|---|
| 渠道 spec 定义 | 2h | **3h** | **+1h** | ① 字段数增至 8+10，新增 `placeholder`（**11 处搬运**）、`badge_key`、`divider_before`、`hint_key`；② `mask`/`password` 分裂（需逐渠道判定，含 `corpsecret` 第三种形态） | §一 1.1、§十二 |
| **渠道实现补齐 schema** | — | **2h** | **+2h（全新）** | wechat **+4 字段**、`required` 修正（`webhook_url` True→False）；feishu **+1 字段**；4 处 `get_config_schema` 改派生 | §十二 (a)(b)、§九 9.1 |
| 后端收敛 R1–R6 | 2h | **2.5h** | **+0.5h** | 新增 **R6**（`manager._init_channels:256-272` 的 if/elif 改按 `ctor` 派生）——06 号未识别 | §二 R6 |
| API 端点 + `spec_hash` | 2h | **2.5h** | **+0.5h** | 新增呈现附加物字段的序列化 + `spec_hash` **判别力测试**（注入 spec 变更断言 hash 变化） | §三、§六 V4 |
| **G-045 B 类实现** | — | **3h** | **+3h（全新）** | ① 4 项校验（B1 AST 扫类、B2 spec 自洽、B3 后端 AST、B4 前端正则）；② **误报抑制**（白名单/跳注释）；③ **判别力测试**（注入 2 类错误断言 FAIL）；④ 文档 5 处同步 | §八 |
| 前端 13 处（含 4→1 模板块） | 6h | 6h | 0 | — | §四 |
| `NotificationLogsView` + 修 dingtalk | 1h | 1h | 0 | — | §四 L1/L2 |
| 测试（含替换的三处锁） | 2h | 2h | 0 | 替换 `stage1c` 2 处的工时已含在"契约锁定"内 | §7.2/7.3 |
| 文档联动 + capabilities | 1h | 1h | 0 | — | — |
| **合计** | **16h** | **23h** | **+7h** | — | — |

## 历史锚点校准

| 历史批次 | 范围 | 实际耗时 | 证据 |
|---|---|---|---|
| 阶段 0 | WS 死代码清理 + 前端轮询（预估"半天"，`06-阶段0-1实施方案.md:23`） | 2026-10-02 完成 | commit `29075b3f` |
| 阶段 1a | 4 字段 + 迁移 62 + 聚合器搬运 + 白名单 | 2026-10-02 | `59387bb2` + 2 fix |
| 阶段 1b / 1c | 各 4 字段 + 迁移 | 2026-10-03 | `74cff175` / `35193ada` |
| 阶段 2.5a | task_kind 落地 + 迁移 65 + 双向映射表 + 防腐化测试 | 2026-10-03 | `900864a3`/`639b6ba3`/`f96b211e` |

**校准结论**：历史"数据/契约类批次"≈ **0.5–1 天/批**（含迁移 + 同步 + 测试 + 文档）。**步 A = 23h ≈ 3 天（专注）**，约为单个历史批次的 **3 倍**，差额来自三处**历史批次没有的成分**：① **前端重设计 6h（无锚点）**；② **跨三层**（spec + API + 前端）的原子切换；③ **G-045 扩展 3h（有摩擦史：`notification_coverage.md:142-151` 记"改动须同步三处"）**。

---

# 十四、裁决 5 的执行确认（N1/N2/N3/N5）

| # | 裁决 | 执行落点 |
|---|---|---|
| **N1** | 保持掩码 | §一 1.1（`mask` 保留且 `webhook_url.mask=True`）；§九 9.2；V7① 断言掩码态不变 |
| **N2** | 前端 locales 优先 | §四 F12 三级回退；§十二 (e) 的文案差异据此**限定为 4 处硬编码英文**（前端 locales 无对应键者才回落 `label_key`） |
| **N3** | 保留 `get_config_schema()` 并派生 | §九 9.1（保留方法；`secret` 键名不变，值取 `password`） |
| **N5** | `placeholder` 进 spec | §一 1.1 字段级 #8；§十二 (c) 列为必修 |

---

## 待决策者裁决清单

| # | 待裁决 | 备选 | 建议 |
|---|---|---|---|
| **N6**（新增） | **4 处硬编码英文标签**（`Bot Token`（`:316`）、`Chat ID`（`:320`）、`Webhook URL`（`:332,360,375`））在 schema 驱动后如何处理？ | (a) spec 的 `label` 保持**与现状相同字面量**（零文案 diff） (b) 改为 i18n 键，接受"英文→本地化"的改进 | **(b)**：现状的硬编码英文在中文界面下本就是缺陷；但若坚持"步 A 零变更"，则取 (a) 并在后续批次改进。**这是唯一的"零变更 vs 改进"取舍点。** |
| **N7**（新增） | B4（前端渠道名扫描）若首版误报偏高，是否接受**缓阻断**（先警告一个迭代再转阻断）？ | (a) 接受缓阻断（**限本阶段内**） (b) 坚持首版即阻断（宁可误报） | **(a)**：误报会阻塞无关提交；但须**写明时限**，否则"缓"会变"永久"（正是 `NotificationLogsView` 漏 dingtalk 长期潜伏的成因）。 |

---

## 附：可复算命令

```powershell
# ── 三处锁的原文（替换对象）──
Get-Content tests\test_notification_stage1c_fields.py | Select-Object -Skip 412 -First 32
# ── API 测试基建（T2 复用）──
Select-String -Path tests\test_notification_api.py -Pattern 'def notif_client_and_db|def notif_cookies|dependency_overrides|TestClient\(app\)'
# ── 前端模板块（核对 1 的对照物）──
Get-Content web\src\components\NotificationConfig.vue | Select-Object -Skip 313 -First 72
Get-Content web\src\components\NotificationConfig.vue | Select-Object -Skip 43 -First 8
Get-Content web\src\components\NotificationConfig.vue | Select-Object -Skip 28 -First 15
# ── schema 现状（缺口实证）──
Select-String -Path pilotstd\core\notification\channels\wechat.py -Pattern 'def get_config_schema' -Context 0,9
Select-String -Path pilotstd\core\notification\channels\feishu.py -Pattern 'def get_config_schema' -Context 0,9
Select-String -Path pilotstd\core\notification\channels\telegram.py -Pattern 'def get_config_schema' -Context 0,5
# ── 掩码清单 vs 前端 SENSITIVE_FIELDS ──
Select-String -Path docker\api\notification.py -Pattern 'webhook_url", "bot_token"'
Select-String -Path web\src\components\NotificationConfig.vue -Pattern 'SENSITIVE_FIELDS|type="password"|Password'
# ── G-045 现状 ──
(Get-Content scripts\audit_notification_coverage.py).Count
Select-String -Path scripts\audit_notification_coverage.py -Pattern '^def |return 1'
Select-String -Path docs\governance\notification_coverage.md -Pattern '^#'
# ── 历史锚点 ──
git log --date=short --pretty="%h %ad %s" -25 -- pilotstd/core/notification
Select-String -Path docs\plans\notification-redesign\06-阶段0-1实施方案.md -Pattern '预估半天'
# ── 门禁 ──
python scripts/check_g_010_code_size.py
bash scripts/check_all.sh --fast
```

**自检**：代码引用 90+ 处（`路径:行号`，内容级回读见提交前脚本）；所有行数与计数为脚本实测、可复算；**本轮未改任何代码**。**本轮更正 07 号自身设计错误 2 处**（恒真陷阱的残留、呈现附加物缺失）；**与 06 定稿无冲突**（06 未涉及 `ctor`/`password`/呈现附加物细节）。
