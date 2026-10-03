# 步 A 实施设计：渠道端到端收敛

> **本轮性质**：只设计，**不实施**。行号均为 2026-10-03 实测。
> **上游（已定稿）**：[06-spec-and-phasing.md](06-spec-and-phasing.md)（commit `a3269c98`，✅ 定稿）、[04-refactor-P.md](04-refactor-P.md)、[05-refactor-decision.md](05-refactor-decision.md)
> **本轮裁决**：① **G-045 就地扩展**（不新增 G-048）；② **遗留项 2、4 本轮必须处理**（`schema` 与 `get_config_schema()` 对接、`spec_hash` 算法与放置）。
> **约束**：禁止新增 mixin（`tests/test_architecture_mixin_guard.py:9,27-35`）；G-010 上限 500 不放宽（`scripts/check_g_010_code_size.py:29`）；**步 A 零行为变更**；与 06 定稿不冲突。

---

## 摘要（决策者读）

**一、本轮最重要的三个实证发现（均会改变实施方式）**
1. **`get_config_schema()` 不只是死代码，而且不完整**：`wechat` 只声明了 `webhook_url`（`channels/wechat.py:87-95`），而前端企微表单有 **5 个字段**（`NotificationConfig.vue:329-355`）；`feishu` 缺 `secret`（`channels/feishu.py:96-104` vs 前端 `:358-370`）。⇒ **激活它之前必须补齐 5 个字段声明，否则前端表单丢字段＝功能回退**。这也解释了它为何一直没被激活。
2. **"敏感字段"有两份互不一致的硬编码清单**：后端掩码清单含 `webhook_url`（`docker/api/notification.py:129`），而 schema 标 `webhook_url: secret=False`（`wechat.py:94`）；前端另有一份 `SENSITIVE_FIELDS`（`NotificationConfig.vue:173`）。⇒ spec 必须把 **`mask`（API 是否掩码）与 `secret`（是否敏感值）分成两个字段**，且**默认保持现状**（`webhook_url` 继续掩码）。
3. **步 A 预计无需改任何现有测试**（反直觉但可论证）：`tests/test_notification_stage1c_fields.py` 的三处锁（`:418` 硬断言 4 名集合、`:424-426` 从 `manager` 导入 `_CHANNEL_CLASSES` 并断言相等、`:435-443` 断言 `channel.py` 源码含 `CHANNEL_KEY_WHITELIST` 与既有短语 `未投递的渠道不出现在 dict 中`）**全部可被"派生赋值"满足**（名字与集合都不变）。⇒ 原子性风险从"测试红"转为"**行为回归**"，须靠回归测试兜底（§五、§六）。

**二、收敛面比 06 号文档记的更大（实测）**
4. 后端 **5 处**（含 `_policy.py:9` 是**零使用的死重复**，可直接删）+ 前端 **3 类共 52 行**硬编码；另外发现 **2 处**：前端 `SENSITIVE_FIELDS`（`:173`）、前端 `channelOpen`（`:103-108`）。**且 `manager._init_channels` 有按渠道名的 if/elif 构造分支**（`manager.py:256-272`）——若 spec 不表达"构造参数映射"，**加渠道仍必改 `manager.py`**。

**三、契约与两个遗留项**
5. **`GET /api/notification/channels`**：返回 `{spec_hash, channels:[{name,label_key,icon,enabled_default,fields[],status_rule}]}`；**无 URL 版本**（沿用 `/api/notification/*` 风格），用 **`spec_hash` 做内容级失效**。
6. **遗留项 4（`spec_hash`）**：`sha256(规范化 JSON(响应体去掉 hash 字段))[:16]`，**放在响应体**（不放 header/模块常量），前端比对不一致即刷新缓存。
7. **遗留项 2（schema 对接）**：**单一来源 = `CHANNEL_SPECS[].fields`**；`get_config_schema()` 改为**由 spec 派生**（渠道类内**延迟 import** 打破环，与 `channel.py:107` 既有口径一致）。

**四、G-045 就地扩展**
8. 扩展后 = **A 类覆盖度（原有 4 维不动）** + **B 类派生一致性（新增）**；输出用 `[A]`/`[B]` 前缀区分，`[覆盖摘要]` 分段计数；实现**仍在 `scripts/audit_notification_coverage.py`**（现 337 行 → 约 417 行，**未越 500 阻断线**）；同批更新 `docs/governance/gates.md:30,417` 与 `notification_coverage.md` §一/§五。

**五、工作量与风险**
9. 步 A 细化为 **19h**（06 号估 16h，**+3h 来自本轮新发现的 schema 补齐与 mask/secret 分裂**）；最大风险 = 前端表单从 4 模板块改为 schema 驱动（无历史锚点）。

---

# 一、`channel_spec.py` 定义

## 1.1 字段清单（**全部由消费方实测反推**）

### 渠道级字段

| # | 字段 | 类型 | 用途 | 消费方（现状来源） |
|---|---|---|---|---|
| 1 | `name` | `str` | 渠道键 | `channel.py:28`（whitelist）、`manager.py:80`（class dict）、`_policy.py:9`（**死重复**）、`docker/api/notification.py:327`（硬编码）、前端 `CHANNELS`（`:96-101`） |
| 2 | `cls` | `type[NotificationChannel]` | 实现类 | `manager.py:80-85` |
| 3 | `label_key` | `str` | 渠道显示名 i18n 键（`notification.channel.<name>`） | 前端 `:97-100` 的 `labelKey` |
| 4 | `icon` | `str` | 前端图标类名（`pi pi-comments`） | 前端 `:97-100` 的 `icon` |
| 5 | `enabled_default` | `bool` | 配置页默认启用态（**wechat=True，其余=False**） | `docker/api/notification.py:149,157-159` |
| 6 | `fields` | `tuple[FieldSpec, ...]` | 表单字段（见下） | `get_config_schema()`（**不完整**）+ API defaults（`:146-159`）+ 前端 4 模板块（`:314-385`） |
| 7 | `ctor` | `tuple[str, ...]` | **构造参数映射**：按序取哪些凭证字段传给 `cls(...)` | `manager.py:256-272` 的 **if/elif 分支**（telegram→`bot_token,chat_id`；dingtalk/feishu→`webhook_url,secret`；wechat→`webhook_url`） |
| 8 | `status_rule` | `StatusRule` | 前端"已配置"判定（**渠道特有逻辑，无法纯数据化，须声明式表达**） | 前端 `chStatus`（`:233-246`）与 `chSeverity`（`:249-255`） |

### 字段级（`FieldSpec`）

| # | 字段 | 类型 | 用途 | 实测依据 |
|---|---|---|---|---|
| 1 | `name` | `str` | 字段名 | 各处 |
| 2 | `type` | `str` | 控件类型（`string`/`secret`） | schema `"type": "string"`（`wechat.py:91` 等） |
| 3 | `label_key` | `str` | 后端键空间标签键（`notification.channel.config.<field>`） | schema 的 `label: t("notification.channel.config.webhook_url")`（`wechat.py:92`） |
| 4 | `label` | `str` | 后端**已翻译**文本（兜底/现状兼容） | 同处 `t(...)` 的**调用期求值**结果 |
| 5 | `required` | `bool` | 必填标记 | schema `"required"` |
| 6 | **`mask`** | `bool` | **API 响应是否掩码** | 后端掩码清单 `("webhook_url","bot_token","secret","corpsecret")`（`docker/api/notification.py:129`） |
| 7 | **`secret`** | `bool` | **是否敏感值**（前端用 Password 控件 + 提交时跳过掩码回显） | 前端 `SENSITIVE_FIELDS = ['bot_token','webhook_url','secret','corpsecret']`（`:173`）+ 模板中 `Password` 控件（`:317,346,365,380`） |
| 8 | `placeholder` | `str` | 输入提示 | 前端硬编码 placeholder（`:317,321,333,338,342,346,350,361,365,376,380`，实测 11 处） |

**⚠️ `mask` 与 `secret` 必须分开**（本轮实测发现）：`webhook_url` 在 API 侧被掩码（`:129`）但在 schema 侧标 `secret=False`（`wechat.py:94`）。若合并为一项，**要么改变 API 响应（安全面变更）**、要么改变前端控件类型（交互变更）——**两者都违反"零行为变更"**。分开声明后默认取值保持现状（`webhook_url`: `mask=True, secret=True`；`corpid/agentid/chat_id/proxy_url`: `mask=False, secret=False`；`corpsecret/bot_token/secret`: `mask=True, secret=True`）。

## 1.2 静态可解析约束

- `channel_spec.py` **不被门禁 AST 读取**（G-045 只 AST 读 `events.py`，`audit_notification_coverage.py:60`）⇒ 允许 `cls` 引用与推导。
- **但** `CHANNEL_KEY_WHITELIST`（`channel.py:28`）**被测试文本断言**（`stage1c:435-440` 要求 `channel.py` 源码含该名字）⇒ 派生赋值**必须保留名字**，不得删除或改名。
- **环依赖处理**：`CHANNEL_SPECS` 引用 `cls`（渠道类）；渠道类若要反向引用 spec 会成环。⇒ 渠道类内**函数级延迟 import**（与 `channel.py:107` 的既有延迟导入同口径）。

## 1.3 结构示意（非实施代码）

```
# channel_spec.py（示意）
CHANNEL_SPECS: tuple[ChannelSpec, ...] = (
    ChannelSpec(
        name="wechat", cls=WechatChannel,
        label_key="notification.channel.wechat", icon="pi pi-comments",
        enabled_default=True,
        ctor=("webhook_url",),                       # manager 用它替代 if/elif
        fields=(
            FieldSpec("webhook_url", type="string", label_key="notification.channel.config.webhook_url",
                      label="Webhook URL", required=False, mask=True, secret=True,
                      placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="),
            FieldSpec("corpid",     ..., required=False, mask=False, secret=False, placeholder="ww..."),
            FieldSpec("agentid",    ..., required=False, mask=False, secret=False, placeholder="1000001"),
            FieldSpec("corpsecret", ..., required=False, mask=True,  secret=True,  placeholder="..."),
            FieldSpec("proxy_url",  ..., required=False, mask=False, secret=False, placeholder="http://proxy:8080"),
        ),
        status_rule=StatusRule(any_of=(("corpid","agentid","corpsecret"), ("webhook_url",))),
    ),
    ChannelSpec(name="telegram", cls=TelegramChannel, ...,
        ctor=("bot_token", "chat_id"),
        status_rule=StatusRule(all_of=("bot_token","chat_id"))),
    ChannelSpec(name="feishu",   ..., ctor=("webhook_url","secret"),
        status_rule=StatusRule(any_of=(("webhook_url",),))),
    ChannelSpec(name="dingtalk", ..., ctor=("webhook_url","secret"),
        status_rule=StatusRule(any_of=(("webhook_url",),))),
)
CHANNEL_NAMES: tuple[str, ...] = tuple(s.name for s in CHANNEL_SPECS)
```

---

# 二、五处后端收敛点（+2 处本轮新发现）

| # | 位置 | 改什么 | 从哪派生 | 性质 |
|---|---|---|---|---|
| **R1** | `pilotstd/core/notification/channel.py:28` | `CHANNEL_KEY_WHITELIST: tuple[str, ...] = ("wechat","dingtalk","feishu","telegram")` → `= CHANNEL_NAMES`（延迟 import 或直接赋值） | `CHANNEL_SPECS` | 派生（**保留名字**，满足 `stage1c:435`） |
| **R2** | `pilotstd/core/notification/manager.py:80-85` | `_CHANNEL_CLASSES = {…4 项字面量…}` → `= {s.name: s.cls for s in CHANNEL_SPECS}` | `CHANNEL_SPECS` | 派生（**必须仍从 `manager` 可导入**，满足 `stage1c:424-426`） |
| **R3** | `pilotstd/core/notification/_policy.py:9` | `_CHANNEL_CLASSES = ("wechat","telegram","feishu","dingtalk")` → **删除** | — | **删除死代码**（实测文件内零引用：`:14/:25/:29/:64/:84` 均不使用它） |
| **R4** | `docker/api/notification.py:327` | `if channel not in ("wechat","telegram","feishu","dingtalk"):` → `if channel not in CHANNEL_NAMES:` | `CHANNEL_SPECS` | 派生 |
| **R5** | `docker/api/notification.py:145-159` | 4 个 `build_channel(name, {字面量 defaults})` → 由 spec 生成 `{f.name: "" for f in s.fields} \| {"enabled": s.enabled_default}` | `CHANNEL_SPECS` | 派生 |
| **R5b** | `docker/api/notification.py:129` | 掩码清单 `if k in ("webhook_url","bot_token","secret","corpsecret")` → `if field_by_name[k].mask` | `FieldSpec.mask` | 派生（**保持现状取值**） |
| **R6** | `pilotstd/core/notification/manager.py:256-272` | 按渠道名的 if/elif 构造分支 → 按 `s.ctor` 收集参数后 `cls(*args)` | `ChannelSpec.ctor` | 派生（**否则加渠道仍必改 `manager.py`**） |

**实证备注**：
- `R3` 之所以安全：`_policy.py` 的 5 个成员（`_log_trace_id:14`、`__init__:25`、`get_channels_for_event:29`、`get_policies:64`、`save_policy:84`）**都不引用** `_CHANNEL_CLASSES`（`_policy.py:9`）⇒ 删它零行为影响。
- **PUT 侧无需改**：`_persist_config_and_audit`（`:251-313`）把 `channels` 整体委托给 `nmgr._cred_helper.set_channel(user_id, ch_name, ch_cfg)`（`:283`），**不含渠道名硬编码**；`_credentials.py` 的 `get_all/get_channel/set_channel/delete_channel`（`:40/:60/:115/:155`）也**渠道无关** ⇒ **收敛面比预期小**。
- **`channels/__init__.py`**（4 类导出）与**凭证层**均无需改。

---

# 三、`GET /api/notification/channels` 契约

## 3.1 请求 / 响应

**请求**：`GET /api/notification/channels`（无参数；需登录态，沿用既有 `_get_user_id` 依赖）

**响应**：
```json
{
  "spec_hash": "a1b2c3d4e5f60718",
  "channels": [
    {
      "name": "wechat",
      "label_key": "notification.channel.wechat",
      "icon": "pi pi-comments",
      "enabled_default": true,
      "ctor": ["webhook_url"],
      "fields": [
        {"name": "webhook_url", "type": "string",
         "label_key": "notification.channel.config.webhook_url", "label": "Webhook URL",
         "required": false, "mask": true, "secret": true,
         "placeholder": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="}
      ],
      "status_rule": {"any_of": [["corpid","agentid","corpsecret"], ["webhook_url"]]}
    }
  ]
}
```
**不含凭证值**（纯元数据）⇒ 与 `GET /api/notification/config`（含掩码值）职责分离，前端两者都拉。

## 3.2 版本策略

**无 URL 版本**（与既有 `/api/notification/*` 一致：`config`/`logs`/`read`/`unread-count`/`policy` 均无版本段，`docker/api/notification.py:110,342,386,404,441`）。变更靠 **`spec_hash` 内容级失效**，不引入版本号。

## 3.3 缓存策略

| 项 | 设计 |
|---|---|
| 前端缓存 | **模块级** `{ spec_hash, payload }`（`NotificationConfig.vue` 与 `NotificationLogsView.vue` 共用） |
| 拉取时机 | 组件 `mount` 时拉一次；`saveConfig` 成功后**强制重拉**（渠道 enabled/字段可能变） |
| 失效判定 | `resp.spec_hash !== cache.spec_hash` → 替换缓存并重建表单状态 |
| 不引入轮询 | 配置页非高频；避免与既有 30 秒通知轮询（`useNotification.ts:16`）叠加请求 |
| 失败降级 | 拉取失败 → 用缓存（若有）；无缓存 → 显示 `notification.config.load_failed`（既有键，`:274` 实测存在） |

## 3.4 `spec_hash` 设计（**遗留项 4**）

| 项 | 设计 | 理由 |
|---|---|---|
| **哈希内容** | **响应体自身去掉 `spec_hash` 字段后的规范化 JSON**（不是"spec 源码文本"、不是"字段名清单"） | ① 语义精确：任何**影响前端渲染**的变更都会变 hash；② 不会漏字段（新增字段自动纳入）；③ 不依赖源码格式（重排/注释不影响） |
| **规范化** | `json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` | 消除键序与空白差异 |
| **算法** | `hashlib.sha256(...).hexdigest()[:16]` | 16 hex 足够（碰撞概率可忽略），响应体积小 |
| **放置** | **响应体字段**（`spec_hash` 与 `channels` 同级） | 不放 header：避免与 CORS/代理缓存头混淆、便于前端统一读取；**不放 spec 模块常量**：模块常量会与响应脱节 |
| **失效机制** | 前端比对不一致 → 刷新缓存 + 重建表单；**后端不缓存**（每次请求现算，成本为一次 sha256 over ~5KB） | 无状态、无失效遗漏 |

**验收（可断言）**：`GET …/channels` 两次调用返回同一 `spec_hash`；对 spec 注入一个字段（monkeypatch `CHANNEL_SPECS`）后 hash **必须变化**（§六 V4）。

---

# 四、前端 schema 驱动改造清单

## 4.1 `web/src/components/NotificationConfig.vue`（**13 处**）

| # | 行号 | 现状 | 改为 |
|---|---|---|---|
| F1 | `:44-50` | `channels` 默认值为**每渠道 8 字段超集**字面量 | 由 `spec.fields` 并集构建（`{f.name: ""}` + `enabled`） |
| F2 | `:96-101` | `CHANNELS` 常量（4 项 `key/labelKey/icon`） | 由 API `channels[].{name,label_key,icon,enabled_default}` 构建 |
| F3 | `:103-108` | `channelOpen` 硬编码 4 键 | 由 API 渠道名列表构建 |
| F4 | `:115-160` | `loadConfig` 内**按渠道 if/else 回填** | 通用遍历 `spec.fields` 回填 |
| F5 | `:173` | `SENSITIVE_FIELDS = ['bot_token','webhook_url','secret','corpsecret']` | `spec.fields.filter(f => f.secret).map(f => f.name)` |
| F6 | `:189-193` | `saveConfig` 显式列 4 渠道 | 按 API 渠道名遍历 |
| F7 | `:197-200` | 策略保存循环硬编码 4 名 | 按 API 渠道名遍历 |
| F8 | `:217-220` | `testChannel` 按渠道拼 `params`（4 分支） | 按 `spec.fields` 收集 `params` |
| F9 | `:233-246` | `chStatus` 按渠道判定（telegram/wechat/其余） | 通用 `evalStatusRule(spec.status_rule, formState)` |
| F10 | `:249-255` | `chSeverity` 同一判定（重复实现） | 复用 `evalStatusRule` |
| F11 | `:314-385` | **4 个 per-channel `v-for` 模板块** | **1 个** `v-for="f in ch.fields"` 动态表单（按 `f.type` 选 `InputText`/`Password`） |
| F12 | `:316,332,360,375` | 硬编码英文字面量 `Bot Token` / `Webhook URL` | 由 `t(label_key)` 或既有 `notification.config.<ch>.<field>` 渲染 |
| F13 | 新增 | — | `evalStatusRule(rule, state)` 工具函数（解释 `all_of` / `any_of`） |

## 4.2 `web/src/views/NotificationLogsView.vue`（**2 处 + 顺带修 dingtalk**）

| # | 行号 | 现状 | 改为 |
|---|---|---|---|
| L1 | `:107-112` | `channelOptions` **缺 dingtalk**（只列 wechat/telegram/feishu）★ | 由 API 渠道列表生成（**顺带修复已发生漂移**） |
| L2 | `:120-124` | `CHANNEL_KEYS` 硬编码 3 键（同样缺 dingtalk） | 由 API 的 `label_key` 映射 |

## 4.3 语言文件

| 项 | 结论（**实测支撑**） |
|---|---|
| 是否需要新增键 | **不需要**——前端 label 采用**三级回退**：`notification.config.<channel>.<field>`（前端 locales **已有**，实测 34 个引用键缺失 0）→ `label_key`（后端键，若前端已补）→ `label`（后端译文兜底） |
| 理由 | 保持**零文案 diff**；前端 locales 的 `notification.config.wechat.*`（`:295-301` 实测 7 键）等继续生效 |
| 新增键（可选，后续批次） | 若要让标签跟随前端语言完全由后端键驱动，需把 `notification.channel.config.*` 镜像到 `web/src/locales/*`（**不在步 A 范围**） |

---

# 五、原子性边界

## 5.1 必须同批的改动（否则测试红）

**实测结论：步 A 预计无需修改任何现有测试。** 逐条论证：

| 现有锁 | 位置 | 是否被"派生赋值"满足 |
|---|---|---|
| 硬断言 4 名集合 | `tests/test_notification_stage1c_fields.py:418` | ✅ 满足（spec 仍是这 4 个渠道） |
| 从 `manager` 导入 `_CHANNEL_CLASSES` 并断言 == whitelist | `:424-426` | ✅ 满足（`manager` 保留该名字，派生自同一 spec） |
| `channel.py` 源码含 `CHANNEL_KEY_WHITELIST` | `:435-440` | ✅ 满足（派生赋值仍含该名字） |
| `channel.py` 源码含短语 `未投递的渠道不出现在 dict 中` | `:441` | ✅ 满足（该短语在 `channel.py:22`，属 `channel_message_ids` 注释块，**不在改动面**） |
| 抽象基类契约 | `tests/unit/core/notification/test_channels_base.py` | ⚠️ **需复核**（若断言 `get_config_schema` 返回形状/字段数，补 5 字段后可能需同批更新） |

**⇒ 步 A 的原子性不是因为"测试会红"，而是因为"行为必须同时对齐"**：spec 一旦成为来源，`channel.py`/`manager.py`/`api`/前端必须**同一批次切换**，否则出现"部分读 spec、部分读字面量"的双源状态（那正是本步要消灭的东西）。

## 5.2 回滚粒度

| 层 | 回滚方式 |
|---|---|
| 整步 | `git revert <步 A commit>`（**1 个 commit**，无 schema 变更、无迁移号、无配置变更） |
| 子集 | 建议拆 **2 个 commit**：**A1**（后端 spec + R1–R6 + 渠道实现 schema 补齐）／**A2**（API 端点 + 前端 13+2 处）——A1 独立可交付（后端自洽），A2 依赖 A1 |
| 残留 | 无（`channel_spec.py` 若单独 revert 掉即无引用；A1 回滚后前端仍读旧 `GET /config`） |

## 5.3 中间态是否可达

| 时点 | 状态 | 自洽？ |
|---|---|---|
| A1 完成、A2 未做 | 后端从 spec 派生；**前端仍硬编码**（渠道名/字段/状态判定） | ⚠️ **半自洽**：渠道集合一致（都还是 4 个），但**新增渠道时前端不会自动出现** ⇒ 若在此时加渠道，前端需手工改（**判据 1 未达成**）。**可接受**（决策者已接受中间态），但**A1 后不得宣称判据 1 达标** |
| A2 完成 | 全链路派生 | ✅ |

---

# 六、验收判据（可断言）

| # | 判据 | 断言形式 |
|---|---|---|
| **V1** | **渠道声明已收敛** | `python -c "from pilotstd.core.notification.channel_spec import CHANNEL_SPECS, CHANNEL_NAMES; from pilotstd.core.notification.channel import CHANNEL_KEY_WHITELIST; from pilotstd.core.notification.manager import _CHANNEL_CLASSES; assert set(CHANNEL_KEY_WHITELIST)==set(CHANNEL_NAMES)==set(_CHANNEL_CLASSES)=={s.name for s in CHANNEL_SPECS}"` |
| **V2** | **加一个渠道只需改 ≤2 个代码文件** | **实测演练**：临时分支加假渠道 `fake`（spec 一条 + 渠道类一个）→ `git status --porcelain \| grep -E '\.(py\|ts\|vue)$' \| wc -l` **≤2** |
| **V3** | **前端不再是硬编码** | ① `grep -cE "'(wechat\|telegram\|feishu\|dingtalk)'" web/src/components/NotificationConfig.vue` == **0**；② 同命令对 `NotificationLogsView.vue` == **0**；③ 组件测试：渲染出的渠道集合 == `GET /api/notification/channels` 返回集合 |
| **V4** | **`spec_hash` 生效** | 两次 `GET /api/notification/channels` 返回**同一** hash；monkeypatch 追加一个 `FieldSpec` → hash **必须变化**（判别力：注入不改变即 FAIL） |
| **V5** | **API 契约完整** | 响应含 4 渠道；每渠道含 `name/label_key/icon/enabled_default/ctor/fields/status_rule`；**不含任何凭证值**（`assert "***" not in json.dumps(resp)` 且不含真实值） |
| **V6** | **schema 不再缺字段**（本轮新发现） | 前端表单渲染字段集合 == `get_config_schema()` 键集合 == `spec.fields` 名集合（**三方相等**，wechat 必须为 **5** 字段、feishu **2**、telegram **2**、dingtalk **2**） |
| **V7** | **零行为变更回归** | ① 4 渠道的 `GET /config` → `PUT /config` 往返：字段集合与掩码态**逐字段相等**（含 `webhook_url` **仍被掩码**）；② `POST /notification/test` 对 4 渠道的 `params` 组装**与改造前一致**（快照比对）；③ 既有通知/渠道测试全绿 |
| **V8** | **G-045 扩展后可判别** | 注入"spec 与 whitelist 差一个渠道" → **断言门禁 FAIL**（B 类）；注入"某事件缺 zh_TW 键" → **断言门禁 FAIL**（A 类，原有能力不退化） |
| **V9** | **G-010 未越线** | `python scripts/check_g_010_code_size.py` 退出码 0；`scripts/audit_notification_coverage.py` 有效行 **≤500** |

---

# 七、测试策略

## 7.1 现有测试：**预计 0 处必改**（§5.1 论证）

**必须复核的 3 个文件**（可能因 schema 补齐而需同批更新）：

| 文件 | 复核点 |
|---|---|
| `tests/unit/core/notification/test_channels_base.py` | 是否断言 `get_config_schema()` 的**字段数/形状**（补 5 字段会破坏"字段数=1"类断言） |
| `tests/test_notification_api.py` | `GET /config` 的响应快照是否含渠道 defaults 键集合 |
| `tests/test_notification_credentials.py` | 是否断言掩码字段清单 |

## 7.2 新增测试清单

| 类 | 用例 | 断言 |
|---|---|---|
| **契约锁定（4）** | `test_spec_names_match_whitelist` | `set(CHANNEL_NAMES) == set(CHANNEL_KEY_WHITELIST)` |
| | `test_manager_classes_derived_from_spec` | `{s.name: s.cls for s in CHANNEL_SPECS} == _CHANNEL_CLASSES` |
| | `test_schema_matches_spec_fields` | 4 渠道：`set(ch.get_config_schema()) == {f.name for f in spec.fields}`（**V6 的锁定**） |
| | `test_mask_and_secret_are_independent` | `webhook_url`: `mask=True` **且** `secret=True`（防止未来有人把两者合并导致行为漂移） |
| **API 契约（3）** | `test_channels_endpoint_shape` | 4 渠道 + 必备字段齐全；无凭证值 |
| | `test_spec_hash_stable_and_sensitive` | 同 spec 两次一致；spec 变则变（**V4**） |
| | `test_config_defaults_from_spec` | `GET /config` 的每渠道键集合 == `{f.name for f in spec.fields} \| {"enabled"}` |
| **回滚/派生守卫（2）** | `test_no_channel_literal_in_manager_init` | 源码级：`manager._init_channels` 内**不含** `== "telegram"` 之类渠道名字面量 |
| | `test_no_channel_literal_in_frontend` | 源码级：两个 Vue 文件不含渠道名字面量（**V3 的可执行化**） |
| **前端（2）** | 渠道列表来自 API | mock API 返回 2 渠道 → 组件渲染 2 个 |
| | `status_rule` 解释器 | 对 wechat 的 `any_of` 三种输入组合 → `configured`/`group_robot`/`pending` 与现状一致 |

## 7.3 回滚后测试如何恢复

纯 `git revert`（1 或 2 个 commit）；新增测试随同批提交一起回退；**无数据迁移、无配置变更** ⇒ 回滚后测试基线与本轮一致。

---

# 八、G-045 就地扩展设计（**已裁决：不新增 G-048**）

## 8.1 扩展后的确切校验范围

| 类 | 管什么 | **不管什么** |
|---|---|---|
| **A 类（原有，不动）** | 每事件：i18n 三语齐备、出现在 e2e `EVENTS` 且 `trigger_file` 物理存在、安全类触发文件含 `write_audit` | 事件语义正确性、文案质量、`level/module/aggregation/builder_keys` 的一致性（**06 号已列为阶段 B 的事项**） |
| **B 类（新增）** | ① `set(CHANNEL_NAMES) == set(CHANNEL_KEY_WHITELIST) == set(manager._CHANNEL_CLASSES)`；② 每渠道 `set(get_config_schema()) == {f.name for f in spec.fields}`；③ `channel_spec` 的字段名不重复、`ctor` 引用的字段都存在于 `fields`；④ （可选）`docker/api/notification.py` 不含渠道名字面量 | **前端运行时行为**（静态门禁无法验证 Vue 渲染）、渠道连通性、`spec_hash` 的稳定性（属 API 测试，不入门禁） |

## 8.2 错误分类与输出格式

| 类 | 前缀 | 条目示例 | 阻断 |
|---|---|---|---|
| A | `[A]` | `[A] archive_complete: 缺 i18n 键 notification.archive.archive_complete.title (zh_TW)` | ✅ 阻断（现状即阻断） |
| B | `[B]` | `[B] CHANNEL_KEY_WHITELIST vs CHANNEL_SPECS: 差集 {'fake'}` | ✅ 阻断（**与 A 同级**，见待裁决 N4） |

**输出结构**（沿用既有五段式，`scripts/_gate_coverage_summary.py:33` `print_coverage_summary`）：
```
通知系统覆盖度审计：41 个事件
...
❌ 阻断缺口 2 项：
   [A] <event>: ...
   [B] <不一致项>: ...
[覆盖摘要]
  范围: notification/events.py 的 ALL_EVENTS（41）+ channel_spec.CHANNEL_SPECS（4）
  检查项: 总计 45 ｜ 通过 45 ｜ 阻断 0 ｜ 豁免 40
  检查口径:
    - A 类 覆盖度：i18n 三语 / e2e 覆盖 + trigger_file 存在 / 安全审计（41 事件）
    - B 类 派生一致性：渠道三方一致 / schema 字段一致 / 字段名唯一（4 渠道）
  跟踪项明细: ...
  未覆盖说明: 未覆盖 —— EVENTS 的 level/module/aggregation/builder_keys 未校验（阶段 B 处理）；前端运行时渲染不在门禁范围
```
⇒ **A/B 两类在"检查项"与"检查口径"里分开计数**，读者一眼可辨。

## 8.3 文档更新点（**同批**）

| 文件 | 位置 | 改什么 |
|---|---|---|
| `docs/governance/gates.md` | `:30`（G-045 表行） | "检查内容"追加 B 类；"阻断条件"追加派生不一致 |
| 同上 | `:417`（G-045 详述节） | 补 B 类判定标准与输出格式示例 |
| `docs/governance/notification_coverage.md` | `:9`（§一 审计方法） | 增加"B 类：派生一致性"小节 |
| 同上 | `:133`（§五 门禁接入状态） | 更新 G-045 描述与 `[覆盖摘要]` 口径说明（现文写"只覆盖清单内路由"等） |
| 同上 | `:31`（§二 矩阵） | 标题加"（A 类）"，并新增 B 类矩阵（4 渠道 × 3 维度） |

## 8.4 兼容性（不破坏现有断言）

- `_audit_one_event`（`audit_notification_coverage.py:169`）**保持不动**；
- B 类校验作为**新增函数**（如 `audit_derivations()`）在 A 类之后追加；
- `main`（`:281`）的返回码逻辑由"仅 A 类阻断"扩为 `A_blocking + B_blocking > 0 → return 1`（`:332` 的 `return 1` 位置不变，只改判定条件）；
- 输出前缀 `❌ 阻断缺口` / `✅ 无阻断缺口` **保留**（既有断言/文档引用不破），条目内用 `[A]`/`[B]` 区分。

## 8.5 门禁编号与文件位置

- **编号**：**G-045**（就地扩展，裁决已定）；
- **实现文件**：**仍为 `scripts/audit_notification_coverage.py`**（不新建）。现状 **337 行**（实测），预计 **+约 80 行 → ≈417 行** ⇒ **未越 G-010 的 500 阻断线**（仍处 >400 警告档，与现状同档）；
- **挂载点不变**：`scripts/check_all.sh:137-146` 与 `.github/workflows/ci.yml:450-451` **无需改动**。

---

# 九、遗留项 2 处理：`schema` 与 `get_config_schema()` 的对接

| 问题 | 结论 |
|---|---|
| 谁派生谁 | **`CHANNEL_SPECS[].fields` 是唯一来源**；`get_config_schema()` **由它派生**（`return {f.name: {"type":…, "label":…, "required":…, "secret":…} for f in fields}`） |
| 单一来源位置 | `pilotstd/core/notification/channel_spec.py` |
| 环依赖 | 渠道类内**函数级延迟 import** `channel_spec`（不新增模块级 import）⇒ 与 `channel.py:107` 既有延迟导入口径一致，**不引入 mixin、不引入环** |
| 既有 4 个渠道实现是否需改 | **需要**：4 处 `get_config_schema` 改为派生（`wechat.py:87`、`dingtalk.py:129`、`feishu.py:96`、`telegram.py:223`）；**并补齐 5 个缺失字段**（wechat 4 + feishu 1） |
| 是否保留该方法 | **保留**——它是 `NotificationChannel` 的抽象契约（`channels/base.py:42-44`）；删除会破坏 ABC 与 `tests/unit/core/notification/test_channels_base.py` |
| `label` 的调用期求值问题 | 现状 `label: t("notification.channel.config.webhook_url")`（`wechat.py:92`）在**调用期求值**，返回**后端当前语言**文本。⇒ spec 保留 `label_key` + `label`（后端译文）；**前端优先用前端 locales 键**（§4.3），故步 A **不改变可见文案**（零文案 diff） |
| `telegram.py:226` 的硬编码 `"label": "Bot Token"` | 补为 `label_key="notification.channel.config.bot_token"`（若三语缺该键则保留字面量兜底）→ **列入实施时的核对项** |

---

# 十、遗留项 4 处理：`spec_hash`

见 §3.4（算法 / 放置 / 失效机制 / 验收 V4）。补充三点：

| 项 | 说明 |
|---|---|
| **不做的事** | 不写进 `channel_spec.py` 作为模块常量（会与响应脱节）；不写 HTTP header（避免代理/缓存语义混淆）；不落库（无状态更简单） |
| **性能** | 每次请求计算一次 sha256（约 5KB JSON）→ 微秒级，无需缓存 |
| **扩展性** | 阶段 B 的 `event_spec` 上线后，同一 `spec_hash` 机制可**合并事件与渠道两个 spec**（响应体变大为 events+channels，hash 逻辑不变） |

---

# 十一、工作量与风险

## 11.1 工作量（在 06 号 16h 基础上细化，**+3h 来自本轮新发现**）

| 项 | 小时 | 说明 |
|---|---|---|
| `channel_spec.py`（8+8 字段 × 4 渠道，含 placeholder 11 处搬运） | 3 | 06 号估 2h → **+1h**（placeholder 与 mask/secret 分裂） |
| 渠道实现补齐 schema（**wechat +4、feishu +1**）+ 4 处改派生 | 2 | **本轮新增项**，06 号未计 |
| R1–R6 六处收敛（含删 `_policy.py:9`、`manager._init_channels` if/elif 改造） | 2.5 | 06 号估 2h → **+0.5h**（`_init_channels` 改造原未识别） |
| 新端点 + `spec_hash` + 契约测试 | 2.5 | 06 号估 2h → +0.5h |
| **前端 13 处改造（含 4→1 模板块）** | **6** | 与 06 号一致，**最大不确定项** |
| `NotificationLogsView` 2 处 + 修 dingtalk | 1 | 06 号估 1h |
| 测试（契约 4 + API 3 + 守卫 2 + 前端 2）+ 复核 3 个既有文件 | 2 | 06 号估 2h |
| 文档联动（`gates.md` 2 处 + `notification_coverage.md` 3 处 + capabilities 重生成） | 1 | 06 号估 1h |
| G-045 B 类实现（≈80 行）+ 判别力测试 | 3 | 06 号列在步 B；**裁决要求本轮写清，实施仍属步 A 的 G-045 扩展** ⇒ 计入本步 |
| **合计** | **23h ≈ 3 天** | 06 号定稿估 16h（2 天）→ **本轮修正为约 3 天** |

## 11.2 风险

| # | 风险 | 影响 | 对策 |
|---|---|---|---|
| R-1 | **前端 4 模板块 → 动态表单**（无历史锚点） | 可能 +0.5~1 天；`vue-tsc` 类型摩擦 | 保留 `ChannelFormState` 为 `Record<string, any>` 形状（现状即 `:45-50` 超集对象）；先跑 `vue-tsc` |
| R-2 | **schema 补齐遗漏字段** → 前端丢字段（功能回退） | 高（用户可见） | V6 三方相等断言 + 逐渠道字段数断言（wechat 5 / feishu 2 / telegram 2 / dingtalk 2） |
| R-3 | **`mask`/`secret` 合并**导致 `webhook_url` 不再掩码 | 中（安全面） | `FieldSpec` 分两字段 + 专项测试（§7.2）；V7① 逐字段掩码态比对 |
| R-4 | 文案来源切换引入**文案 diff** | 中 | 前端三级回退**优先前端 locales**（§4.3）⇒ 步 A 零文案 diff |
| R-5 | `get_config_schema()` 的 `label` 是**调用期译文**，前端若直接用会**固化后端语言** | 低（步 A 不因此变更） | 保留 `label_key`，前端优先自身键；后续批次再切 |
| R-6 | G-045 扩展后误伤既有 PASS | 中 | B 类**只校验新增维度**，不触碰 A 类逻辑；先在本地跑 `--fast` 全绿再提交 |
| R-7 | `manager._init_channels` 改派生后**构造参数顺序错**（如给 wechat 传了 2 个参数） | 高 | `ctor` 显式声明 + 单测逐渠道实例化（用假凭证） |
| R-8 | `_policy.py:9` 删除后若有**动态引用**（`getattr`） | 低（实测零引用） | 删除前全库 grep `_CHANNEL_CLASSES`（已在 §二 实证） |

---

## 待决策者裁决清单

| # | 待裁决 | 备选 | 建议 + 理由 |
|---|---|---|---|
| **N1** | `webhook_url` 在 API 响应中**是否继续掩码** | (a) 保持掩码（现状） (b) 按 schema 的 `secret=False` 改为明文 | **(a)**：现状即掩码（`docker/api/notification.py:129`），改为明文是**安全面变更**，违反步 A"零行为变更"；用 `mask`/`secret` 双字段表达分歧即可 |
| **N2** | 前端字段标签的**来源优先级** | (a) 前端 locales `notification.config.<ch>.<field>` 优先 → `label_key` → `label` (b) 直接以后端 `label` 为准 | **(a)**：零文案 diff，且不把前端语言固化在后端 |
| **N3** | `get_config_schema()` 的去留 | (a) 保留并改为由 spec 派生 (b) 删除，改由 API 直接读 spec | **(a)**：它是 `NotificationChannel` 的抽象契约（`channels/base.py:42-44`），删除破坏 ABC 与既有渠道契约测试 |
| **N4** | G-045 的 **B 类是否阻断** | (a) 阻断（与 A 类同级） (b) 只警告 | **(a)**：派生不一致会让"单一来源"名存实亡（正是本步的目的）；若只警告，漂移会像 `NotificationLogsView` 漏 dingtalk 一样长期潜伏 |
| **N5** | `placeholder`（11 处硬编码）是否进 spec | (a) 进 spec (b) 留在前端 | **(a)**：schema 驱动表单要求字段提示也可派生；否则每加渠道仍要改前端模板（违背判据 1） |

---

## 附：可复算命令

```powershell
# ── 渠道声明 5 处 + 死重复 ──
Select-String -Path pilotstd\core\notification\channel.py,pilotstd\core\notification\manager.py,pilotstd\core\notification\_policy.py,docker\api\notification.py -Pattern 'CHANNEL_KEY_WHITELIST|_CHANNEL_CLASSES\s*[=:]|not in \("wechat"|build_channel\('
Select-String -Path pilotstd\core\notification\_policy.py -Pattern '_CHANNEL_CLASSES'   # 仅 :9 定义，无使用
# ── schema 缺口（本轮核心发现）──
Select-String -Path pilotstd\core\notification\channels\wechat.py -Pattern 'def get_config_schema' -Context 0,10
Select-String -Path pilotstd\core\notification\channels\feishu.py -Pattern 'def get_config_schema' -Context 0,10
Select-String -Path web\src\components\NotificationConfig.vue -Pattern "ch\.key === '(wechat|telegram|feishu|dingtalk)'"
(Select-String -Path web\src\components\NotificationConfig.vue -Pattern 'wechat|telegram|feishu|dingtalk').Count
# ── mask vs secret 分歧 ──
Select-String -Path docker\api\notification.py -Pattern 'webhook_url", "bot_token", "secret", "corpsecret"'
Select-String -Path web\src\components\NotificationConfig.vue -Pattern 'SENSITIVE_FIELDS'
Select-String -Path pilotstd\core\notification\channels\wechat.py -Pattern '"secret": False'
# ── manager 的构造 if/elif（加渠道的隐藏成本）──
Get-Content pilotstd\core\notification\manager.py | Select-Object -Skip 255 -First 18
# ── 原子锁（三处断言）──
Get-Content tests\test_notification_stage1c_fields.py | Select-Object -Skip 415 -First 28
Select-String -Path pilotstd\core\notification\channel.py -Pattern '未投递的渠道不出现在 dict 中'
# ── get_config_schema 零调用（死代码）──
Get-ChildItem pilotstd,docker,tests,web -Recurse -File -Include *.py,*.ts,*.vue | Select-String 'get_config_schema'
# ── G-045 结构与挂载 ──
(Get-Content scripts\audit_notification_coverage.py).Count
Select-String -Path scripts\audit_notification_coverage.py -Pattern '^def |return 1|阻断缺口'
Select-String -Path scripts\check_all.sh -Pattern 'audit_notification_coverage|G-045'
Select-String -Path docs\governance\gates.md -Pattern 'G-045'
Select-String -Path docs\governance\notification_coverage.md -Pattern '^#'
# ── 前端漂移（顺带修复项）──
Get-Content web\src\views\NotificationLogsView.vue | Select-Object -Skip 106 -First 24
# ── 门禁 ──
python scripts/check_g_010_code_size.py
bash scripts/check_all.sh --fast
```

**自检**：代码引用 90+ 处（`路径:行号`，内容级回读见提交前脚本）；所有行数与计数为脚本实测、可复算；**本轮未改任何代码**。**与 06 号定稿的冲突与修正共 3 处**（已在正文标注）：① 06 号未识别 `manager._init_channels` 的构造 if/elif（加渠道的隐藏成本）⇒ 新增 R6；② 06 号未识别 `mask`/`secret` 分裂与 schema 缺字段 ⇒ 新增 §1.1 的 `mask` 字段与 V6 判据；③ 步 A 工时由 16h 修正为 **23h**。
