# MoviePilot 通知系统调查报告

> 调查对象：`jxxghp/MoviePilot`（后端）与 `jxxghp/MoviePilot-Frontend`（前端）
> 代码版本：后端 **v2.15.6**（commit `1528176b`，2026-09-26）｜前端 **v3.1.1**（commit `e999aa0`，2026-10-03）
> 调查方式：本地 clone 后**读源码 + 可复算脚本实测**（§〇 与方法声明，文末「可复算命令」）
> 本报告只回答「MoviePilot 是什么」，不回答「PilotStd 应该怎么做」。

---

## 摘要（给决策者读）

**核心发现 10 条**

1. **MoviePilot 没有"通知事件"这个概念。** 全库唯一枚举是 9 个**消息类别**（`资源下载/整理入库/订阅/站点/媒体服务器/手动处理/插件/智能体/其它`），粗到"一个类别管几十种业务情形"。发通知就是业务代码里直接 `post_message(Notification(mtype=..., title=..., text=...))`，**标题正文现场手写**。
2. **因此"加事件"成本 ≈ 0 个文件**：不登记、不注册、不校验，加一处调用即可（实测 116 处调用 / 14 个文件）。这是它"演化得动"的根本原因——代价是**没有任何地方能列出"系统会发哪些通知"**。
3. **没有任何"事件清单硬编码断言"，也没有防漏登记机制。** 全库对 `NotificationType/MessageChannel/EventType/ChannelCapability` 的成员数**零断言**（实测 grep 为空）。唯一相关代码是 `EVENT_TYPE_NAMES.get(event_type, event_type.name)` 这种"缺了就降级显示"。
4. **发送端是真动态发现**：`ModuleManager` 用 `pkgutil` 扫 `app/modules/*`，`run_module("post_message", ...)` 向"所有实现了该方法的模块"扇出；插件侧扫 `app/plugins/*/__init__.py`。新增渠道不碰核心代码。
5. **它有真正的"渠道能力矩阵"**（12 项能力 × 12 渠道 + 每渠道 4 个量化上限）。但**声明与实现已经漂移**：QQ 声明支持内联按钮与回调，其 `post_message` 却从不传 `buttons`；`should_use_fallback()` 全库无调用者；`MessageChannel.Web/WebAgent` 有声明但**没有模块**，`post_message` 指定这两个渠道会被静默丢弃。
6. **消息可原地编辑**，但只有 4 个渠道真能做（Telegram/Feishu/Slack/Discord；WebAgent 走专用编辑队列）。按钮交互同样集中在这 4 个渠道，QQ 是半成品，微信/企微机器人/群晖/VoceChat/WebPush **直接丢弃按钮且不发降级文本**。
7. **没有"任务进度"推送。** 进度是进程内 `TTLCache`，由 Web 端 SSE 拉取（`GET /system/progress/{type}`），**不进通知链路**。唯一"过程型"推送是 **Agent 流式回复**：首块发新消息，之后每 0.3s 原地编辑同一条。
8. **通知消息本身没有聚合/去重**。只有三样东西沾边：① 免打扰时段队列（延后发送）；② 系统/插件 Web 消息的 **60 秒**重复抑制（键含"当前分钟"，跨分钟即失效）；③ 两处**业务事件**侧手写聚合（整理批次刮削、失败重试 300s debounce）。**没有渠道限流退避**——`429` 处理只存在于站点请求与网盘存储。
9. **v2.15.x 新加了完整多语言**（`LocaleHelper` + 3 个语言包 + 295 条中文原文映射 + 250 条中文正则），但**通知发送链路 0 处调用**——推出去的通知仍是写死中文。i18n 只覆盖 API 响应、仪表盘、进度、搜索，且是"中文字段 + 平行 `*_i18n` 字段"的**补丁式**改造。
10. **用户配置粒度是类别级（9），不是事件级**；用户自己**不能**订阅/退订任何类别，只能填渠道地址。安全告警**没有专用通道**：唯一"绕过"是"定向消息跳过渠道类别开关"，站点 Cookie 失效这类告警与普通通知同路径、可被用户关掉。

**关键数字（均为实测）**

- 通知类别 `NotificationType` **9**（`app/schemas/types.py:305-323`）｜模板内容类型 `ContentType` **4**（`:326-338`）｜渠道 `MessageChannel` **12**（`:342-357`）｜**真正实现投递的渠道模块 10**
- 渠道能力项 **12**（`app/schemas/message.py:372-402`）｜能力矩阵条目 **12**（`:424`）｜`Notification` 字段 **24**（`:207-269`）｜消息历史表列 **11**（`app/db/models/message.py:14-36`）
- `post_message(` 调用点 **116 处 / 14 文件**｜`Notification(` 构造 **136 处 / 24 文件**｜内部广播事件 `EventType` **31**（`types.py:63`）｜同步链式事件 `ChainEventType` **19**（`:165`）
- 支持消息编辑的渠道 **4（+1 特例）**｜语言包叶子 en-US **826** / zh-TW **826** / zh-CN **85**｜**通知链路调用 i18n 0 处**｜通知相关测试文件 **24 个**（含 1492 行的 `test_feishu.py`）

---

## 〇、调查方法与证据可靠性声明

- **来源**：本地 clone 源码（非 web 抓取、非 README）。后端 = `C:\Temp\mp-v2`（git worktree，detached at `1528176b`，`APP_VERSION = 'v2.15.6'` 见 `version.py:1`）；前端 = `C:\Temp\mp-frontend`（`clone --depth 1`，HEAD `e999aa0`，`package.json` version `3.1.1`）。
- **为何不是"随手找的那份"**：机器上原有一份 clone 停在 **v2.13.0 / 2026-05-25** 的 fork 功能分支上。按决策者指示 `git fetch origin v2` 后钉住 **v2.15.6**，本报告所有行号对应该 commit。**v2.13.0 的结论已作废**（两版之间 `app/schemas/message.py` +144 行、`app/helper/progress.py` +79 行、`app/chain/__init__.py` +428 行，并新增了 `LocaleHelper`）。
- **置信度标注**：**高** = 直接读到实现并经脚本复核；**中** = 读到代码但结论含跨文件推断；**低** = 仅由相邻证据支持，已明确标注「推断」。
- **行号自检**：全部 `路径:行号` 经脚本回读校验（文件存在 + 行号在范围内）；另有 45 处关键引用做过**内容级**校验，并据此修正了 **25 处**从 v2.13.0 携带过来的过期行号。
- **未做的事**：未运行 MoviePilot；未连接任何 MoviePilot 实例（含 PilotStd 的 `192.168.1.18:9028`）；未以官方文档/Issue 作为结论来源；未修改被调查仓库任何文件。

---

## 一、A. 事件模型（最核心）

### Q1. 新增一个通知事件，需要改几个文件/几处代码？

**答案：正常情况下 0 个文件（加 1 处调用即可）；但若要"用户能开关它""能改文案"，成本立刻变成 2~7 处，且分散在三个彼此独立的枚举里。**

- **A. 新增业务通知、复用已有类别** → 只在业务处加一处 `self.post_message(Notification(mtype=..., title=..., text=...))`，**1 处**。
- **B. 要让用户能按类别开关** → ① `app/schemas/types.py:305-323` 加 `NotificationType` 成员；② 前端 `src/api/constants.ts:241-278` 抄同名选项；③ 前端 3 个语言包加 `notificationSwitch.*` 文案；④ 前端 `AccountSettingNotification.vue:112-149` 加默认 scope 行 → **后端 1 + 前端 3**。
- **C. 要套 Jinja2 模板（用户可改标题正文）** → ① `app/schemas/types.py:326-338` 加 `ContentType`；② 默认模板写进 DB 迁移（范式见 `database/versions/89d24811e894_2_1_4.py:21-59`）；③ 前端模板入口 `AccountSettingNotification.vue:30-51`；④ 三语文案 → **4~6 处**。
- **D. 要让插件/工作流能订阅这个业务动作** → ① `app/schemas/types.py:63` 加 `EventType`；② 同文件 `EVENT_TYPE_NAMES`（`:129`）加中文名；③ 业务处 `eventmanager.send_event(...)` → **3 处**（同一文件 2 处）。

**关键点：A 与 D 是两条不相干的链。** 发通知**不经过**事件总线，事件总线**也不产生**通知（见 Q2）。

**证据**：发送入口不校验事件——`app/chain/__init__.py:1608`（`ChainBase.post_message` 只做"模板渲染 → 落库 → 路由 → 入队/扇出"，无任何事件名校验）；"加一处即可"的实例 `app/chain/site.py:86`、`app/chain/download.py:1000`、`app/startup/modules_initializer.py:120-123`；三套枚举各自独立 `app/schemas/types.py:305`（`NotificationType`）/`:326`（`ContentType`）/`:63`（`EventType`）/`:165`（`ChainEventType`）。**置信度：高**（B/C/D 的"处数"由枚举定义位置与前端引用点枚举得出）。

### Q2. "业务动作"和"通知事件"是几层？

**答案：是"抽象类别 + 现场文本"**，不是"每个业务动作一个事件"，也不是"事件 + 状态字段"。共三层，**前两层与通知有关，第三层与通知无关**：

- **L1 消息类别** `NotificationType`（9）：极粗（"资源下载"覆盖下载开始/失败/进度查询）；**值是中文硬编码**（`"资源下载"`，即线值）；用于用户开关、渠道订阅、权限范围。`app/schemas/types.py:305-323`
- **L2 内容形态** `ContentType`（4）：只有 4 种有模板；值用驼峰英文（`"downloadAdded"`）。`app/schemas/types.py:326-338`
- **L3 内部事件** `EventType`（31）/`ChainEventType`（19）：细粒度（`transfer.complete`、`subscribe.added`…），**面向上层（插件/系统模块）挂勾子**，与通知无关。`app/schemas/types.py:63,165`

**证据（L3 不产生通知）**：全库 `EventType.NoticeMessage` 只出现在 `app/chain/__init__.py:1703,1713`（同步）与 `:1819,1829`（异步）——都是通知**向外广播**事件供插件旁听，数据构造见 `:212`（`_build_notice_message_data`）；而 `EventType.TransferComplete`/`MetadataScrape` 的订阅方是 `app/chain/media.py` 等**业务模块**，**没有任何内置订阅方把事件转成通知**。**置信度：高**。

### Q3. 有没有"事件清单硬编码断言"？靠什么防漏登记？

**答案：没有任何数量断言，也没有防漏机制。这是全套设计里最"放任"的一环。**

**证据（实测，全库 grep 均为空）**：检索 `NotificationType.__members__` / `MessageChannel.__members__` / `EventType.__members__` / `ChannelCapability.__members__` / `len(EVENT_TYPE_NAMES)` / `len(_capabilities)` 的**断言 = 0 命中**；`tests/` 里唯一的枚举遍历是业务逻辑而非校验（`app/chain/system.py:205-207`，按值反查渠道枚举用于重启后回发消息）；唯一"清单"是 `EVENT_TYPE_NAMES`（`app/schemas/types.py:129`，31 条），但消费方写成 `EVENT_TYPE_NAMES.get(event_type, event_type.name)`（`app/api/endpoints/workflow.py:91`）——**缺了就降级显示英文名，不会失败**；通知类别那 9 个中文值被前端**再抄一遍**（`src/api/constants.ts:241-278`），两处漂移无人发现。

**它实际靠什么不出大错**（推断，依据上面三条事实）：① 类别只有 9 个且极少变动，抄错机会小；② 新通知默认落在已有类别里，不需要登记；③ 真正需要"不漏"的地方（用户可见的开关）由**配置数据**驱动而非代码清单。**置信度：高**（"无断言"为实测；第 ②③ 点为推断）。

### Q4. 事件是静态注册还是动态发现？

**答案：分两半——通知发送端全部动态发现；枚举常量本身是静态的。**

- **渠道（谁负责发）= 动态**：启动时 `pkgutil.iter_modules` 扫 `app.modules`，过滤"有 `init_module` + `init_setting` 的类"→ 实例化 → 受环境开关控制是否运行（`app/core/module.py:29-53`；`app/helper/module.py:26-55`）。
- **方法扇出（发给谁）= 动态**：`run_module("post_message", ...)` 遍历"所有 hasattr 该方法的运行态模块"，按 `get_priority()` 排序逐个调用（`app/core/module.py:118-128`；`app/chain/__init__.py:470-476`）。
- **插件 = 动态**：扫 `app/plugins/*/__init__.py` 载入；插件用 `get_module()` 返回 `{方法名: 函数}` 参与同一套扇出（`app/core/plugin.py:227-240`、`:933`；消费方 `app/chain/__init__.py:304` 同步 / `:337` 异步）。
- **事件监听 = 动态注册、静态枚举**：`@eventmanager.register(EventType.X)`；也可传枚举**类**批量注册全部成员（`app/core/event.py:776-809`）。
- **`NotificationType` 等枚举 = 静态**（Python Enum 字面量），无法运行时扩展（`app/schemas/types.py:305`）。

**置信度：高**。

### Q5. 事件的数量级？属于什么粒度？

**答案：可枚举的"事件"只有 9 个类别；真正的通知内容有 116 处手写调用点。粒度是"按业务场景手写"，不是"按事件类型注册"。**

| 口径 | 数量 | 粒度说明 | 证据 |
|---|---|---|---|
| 用户可开关的类别 | 9 | 一个类别 = 一整个业务域（"站点"涵盖新消息、低分享率、Cookie 失效） | `app/schemas/types.py:305-323` |
| 有模板的内容类型 | 4 | 只有"订阅添加/订阅完成/入库成功/开始下载"可定制 | `app/schemas/types.py:326-338` |
| 实际发消息的位置 | 116 | 每个位置自己拼 title/text | 实测 |
| 内部广播事件 | 31 | 面向插件/工作流，非面向用户 | `app/schemas/types.py:63` |
| 同步链式事件 | 19 | 用于拦截/改写业务参数 | `app/schemas/types.py:165` |

**对比感受**：PilotStd 的 41 个事件若映射到 MoviePilot 的模型，最接近的是它的 **116 个调用点**（同粒度），**不是** 9 个类别。**置信度：高**。

---

## 二、B. 消息模型

### Q6. 通知消息有哪些字段？完整列出。

**答案：`Notification` 共 24 字段（`app/schemas/message.py:207-269`）**，按用途分组：

- **路由** `channel:213` / `source:215` / `userid:237` / `username:239` / `targets:245`
- **分类** `mtype:217`（9 类）/ `ctype:219`（4 类模板）
- **内容** `title:221` / `text:223` / `link:235` / `image:225`
- **附件式（标量）** `voice_path:227` / `voice_caption:233` / `file_path:229` / `file_name:231`
- **交互** `buttons:247`（二维数组）/ `force_reply:249` / `original_message_id:251` / `original_chat_id:253`
- **元信息** `date:241` / `action:243`（0=接收 1=发送）/ `disable_web_page_preview:255` / `parse_mode:257` / `save_history:259`

**另有两个相关模型**：`MessageResponse`（6 字段：`message_id`/`chat_id`/`channel`/`source`/`metadata`/`success`，`app/schemas/message.py:36-49`，用于"发完拿 ID 以便后续编辑"）；`CommingMessage`（**外来**消息，含 `callback_data`/`callback_query`/`images`/`audio_refs`/`files`/`reply_to_message_id`，`:86-205`）。**置信度：高**。

### Q7. 有没有 `message_id` / `callback_data` / `actions` / `attachments` 这类字段？

**答案**：
- **`message_id`：有，但只在"响应/外来消息"上**——`MessageResponse.message_id`（`app/schemas/message.py:42`）、`CommingMessage.message_id`（`:175`）。出站 `Notification` **没有** `message_id` 字段，改用 `original_message_id` 表达"我要编辑哪条"（`:251`）。
- **`callback_data`：有**，在 `CommingMessage.callback_data` 与按钮字典的 `callback_data` 键（`Notification.buttons:247` 注释明确格式 `{"text","callback_data","url"}`）。**出站消息没有独立的 callback_data 字段**。
- **`actions`：没有**这个字段，等价物是 `buttons`（`:247`）。
- **`attachments`：没有列表型字段**。附件能力拆成 4 个标量（`:225-233`）+ 消息历史表的 `note` JSON 列（`app/db/models/message.py:36`）。

**置信度：高**。

### Q8. 消息是否支持编辑/更新？怎么实现？

**答案：支持，而且是它交互体系的核心。机制 = "发送时把渠道返回的消息 ID 存下来，后续用该 ID 原地改写"。**

- **发送方拿 ID**：`ChainBase.send_direct_message()` 返回 `MessageResponse`（`app/chain/__init__.py:1953-1963`），**不进队列、不落历史**。
- **模型承载**：`Notification.original_message_id` + `original_chat_id`（`app/schemas/message.py:251,253`）。
- **统一入口**：`ChainBase.edit_message(...)`（`app/chain/__init__.py:1903-1951`）；删除入口 `delete_message`（`:1880`）。
- **优先编辑、失败回退新发**：`app/helper/interaction.py:180-227`（`update_or_post_message`：先判 `supports_editing(channel)` → 调 `edit_message` → 成功即返回；否则 `post_message` 且带 `save_history=False`）。

**真正实现 `edit_message` 的渠道**：Telegram / Feishu / Slack / Discord（各模块 `__init__.py`）；**WebAgent 是硬编码特例**：`app/chain/__init__.py:1926-1939` 里 `if channel == MessageChannel.WebAgent:` 直接调 `app/helper/agent.py::edit_web_agent_message`，绕过模块扇出。**最典型的应用是 Agent 流式输出**（见 Q16）。**置信度：高**。

### Q9. 消息模板机制是什么样的？

**答案：Jinja2 模板 + 上下文构建器 + DB 存储 + 前端编辑器，四位一体。只有 4 种消息走模板，其余 100+ 处全是硬编码字符串。**

- **渲染器** `MessageTemplateHelper`（`app/helper/message.py:538`）：`render(...)` 仅当 `message.ctype` 存在**且**有业务对象传入时套模板。
- **模板取值**：`SystemConfigOper().get(SystemConfigKey.NotificationTemplates)`（键见 `app/schemas/types.py:273`）→ `ctype.value → 模板串`。
- **上下文构建** `TemplateContextBuilder`（`app/helper/message.py:30`）：把 `MetaBase`/`MediaInfo`/`TorrentInfo`/`TransferInfo` 摊成 ~50 个模板变量（`title_year`/`season_episode`/`vote_average`/`file_count`/`size`…）。
- **渲染入口**：`post_message` 内第一件事（`app/chain/__init__.py:1630`），先渲染再落库路由。
- **默认模板**：4 个 ctype 的出厂 Jinja2 串写在 **Alembic 迁移**里（`database/versions/89d24811e894_2_1_4.py:21-59`）。
- **用户编辑**：前端 `NotificationTemplateEditorDialog.vue`（160 行）+ `AccountSettingNotification.vue:30-51,540-565`（Ace 编辑器，四张卡）。

**模板原文摘录**（`database/versions/89d24811e894_2_1_4.py:22-32`）：
```
{'title': '{{ title_year }}{% if season_episode %} {{ season_episode }}{% endif %} 已入库',
 'text': '{% if vote_average %}评分：{{ vote_average }}，{% endif %}类型：{{ type }}...共{{ file_count }}个文件，大小：{{ total_size }}'}
```
注意模板里的**中文标签也是写死的**（"已入库"、"评分："），所以模板解决的是"字段组合"而非"多语言"（见 Q22）。

**"为什么 MoviePilot 要做模板"（推断，依据下列代码事实）**：① 它有 100+ 处通知且用户群体庞大，反复被要求改文案；② 核心业务对象（媒体/种子/整理结果）字段多且稳定，天然适合"字段组合"；③ 它已有 DB 配置表与配置 UI，加一张模板表成本极低。**换来的**：文案改动**不用发版**，且用户能按口味裁剪冗长字段（`{% if seeders %}` 全是可选段）。**代价（代码里直接可见）**：默认模板在迁移、用户覆盖在 DB，形成**双份真相**；模板变量名与 `TemplateContextBuilder` 产出**靠约定对齐、无任何校验**——Jinja2 对未定义变量默认渲染空串，即**变量名写错只会静默少一行**。**置信度：高**（机制与代价为直接读数；"动机"段已标注推断）。

---

## 三、C. 渠道与交互

### Q10. 支持哪些渠道？逐个列出。

**答案：枚举 12 个（`app/schemas/types.py:342-357`），实际实现投递 10 个，另 2 个是"形态特殊"的 Web 侧通道。**

- **有投递模块的 10 个**：`Wechat`("微信")、`Feishu`("飞书")、`WechatClawBot`、`Telegram`、`Slack`、`Discord`、`SynologyChat`、`VoceChat`、`WebPush`、`QQ` → 各对应 `app/modules/<name>/__init__.py` 的 `post_message`。
- **无模块的 2 个**：`Web`——仅用于**入站**（`app/api/endpoints/message.py:140-147`），出站"通知中心"是读 `message` 表（`:172-189`）；`WebAgent`——出站投递由 `app/helper/agent.py`（编辑队列）+ `app/api/endpoints/agent.py` 专线处理。

**实测**：`app/modules/*/__init__.py` 中 `def post_message` = **10 个**；声明 `self._channel = ...` 也正好 **10 个**（1:1，缺 `Web`/`WebAgent`）。因此 `post_message(Notification(channel=MessageChannel.Web))` 会被所有模块在"渠道不等即返回 False"处过滤（`app/modules/__init__.py:232-233`），**静默无投递**。**置信度：高**。

### Q11. 每个渠道的能力差异怎么表达？有没有"渠道能力矩阵"？

**答案：有，而且是完整实现：12 项能力 × 12 渠道 + 每渠道 4 个量化上限 + 降级开关。**

- **`ChannelCapability`（12 项）**：`app/schemas/message.py:372-402`——`INLINE_BUTTONS`/`MENU_COMMANDS`/`MESSAGE_EDITING`/`MESSAGE_DELETION`/`CALLBACK_QUERIES`/`RICH_TEXT`/`MARKDOWN`/`IMAGES`/`LINKS`/`AUDIO_OUTPUT`/`FILE_SENDING`/`PROCESSING_STATUS`
- **`ChannelCapabilities`（dataclass）**：`:404-417`——`channel` + `capabilities: Set` + `max_buttons_per_row` + `max_button_rows` + `max_button_text_length` + `max_message_length` + `fallback_enabled`
- **`ChannelCapabilityManager._capabilities`**：`:424` 起，**12 个渠道全登记**（实测条目数 = 12）
- **查询 API**：`supports_capability` / `supports_buttons:617` / `supports_callbacks` / `supports_editing:631` / `supports_markdown` / `supports_deletion` / `get_max_buttons_per_row` / `get_max_button_rows` / `get_max_button_text_length` / `get_max_message_length:676` / `should_use_fallback:684`

**它有而多数实现缺的两样**：① **量化上限**（Telegram `max_message_length=3500` 为 MarkdownV2 转义留余量、Feishu `max_buttons_per_row=3`、Discord `1800`、Slack `39000`），流式输出据此自动分段；② **能力驱动的流程分支**（`PROCESSING_STATUS` 决定是否发 typing/reaction，`app/chain/__init__.py:128-192`；`INLINE_BUTTONS && CALLBACK_QUERIES` 决定交互用按钮还是纯文本，`app/helper/interaction.py:114-122`；`MESSAGE_EDITING` 决定要不要原地改写，`:195-198`）。

**但矩阵本身有三处腐化（实测）**：① **声明 ≠ 实现（QQ）**——QQ 声明 `INLINE_BUTTONS`+`CALLBACK_QUERIES`（`app/schemas/message.py:581-588`），客户端也**确实**支持从 kwargs 取 `buttons`（`app/modules/qqbot/qqbot.py:351`），但模块层 `post_message` 调 `send_msg(...)` 时**没传 `buttons`**（`app/modules/qqbot/__init__.py:372-379`）→ 按钮在标准通知路径上永远不生效；② **死代码**——`should_use_fallback():684` 与 `supports_deletion`（`delete_message` 全库仅 1 处调用）在 `app/` 与 `tests/` 中**无任何调用者**；③ **两个渠道只有声明没有实现**（`Web`/`WebAgent`）。**置信度：高**。

### Q12. 按钮/回调在各渠道上真的能工作吗？

**答案：只有 Telegram/Feishu/Slack/Discord 四个渠道端到端可用（QQ 半成品，其余直接丢弃且无降级文本）。**

| 渠道 | 能力声明 | 实际把 `buttons` 传到客户端？ | 端到端 |
|---|---|---|---|
| Telegram / Feishu / Slack / Discord | ✅ | ✅ | ✅ |
| QQ | ✅（v2.15.x 新加） | ❌ **未传** | ❌ 声明与实现漂移 |
| Wechat / WechatClawBot / SynologyChat / VoceChat / WebPush | ❌ | ❌（`send_msg` 连参数都没有） | ❌ **静默丢弃** |
| WebAgent | ✅ | 特例（前端卡片专用通路） | ✅（仅 Web 前端） |

**证据**：传 `buttons=message.buttons` 的模块实测为 `app/modules/discord/__init__.py:415,444,467`、`app/modules/slack/__init__.py:555,578,601`、`app/modules/telegram/__init__.py:534,561,586`；QQ 漂移见上；**无降级文本机制**——`should_use_fallback()` 无调用者，唯一"降级"是**业务代码自己写在正文里**（`app/chain/transfer.py:1203` 与 `:1875` 手写"如果按钮不可用，可回复：`/redo {id}`"），即**降级文案靠人肉记忆**；渠道回调解析与权限见 MoviePilot 仓 `tests/test_message_channel_permissions.py:19-399`（8 个渠道的"非管理员点命令按钮"拦截）。**置信度：高**。

### Q13. 消息原地更新在哪些渠道真能做到？

**答案：4 个渠道真能做（Telegram/Feishu/Slack/Discord）+ WebAgent 特例。**

| 渠道 | 声明 `MESSAGE_EDITING` | 实现 `edit_message` | 底层做法 |
|---|---|---|---|
| Telegram | ✅ | ✅ `app/modules/telegram/__init__.py:620` | 客户端 `telegram.py:648`：`if original_message_id and original_chat_id:` 走编辑分支（ID 为整数） |
| Feishu | ✅ | ✅ `app/modules/feishu/__init__.py:170` | 客户端 `feishu.py:1778 def edit_message`（卡片更新，支持流式卡片 card_id/element_id/sequence） |
| Slack | ✅ | ✅ `app/modules/slack/__init__.py:634` | 客户端 `slack.py:377-381`：`ts=original_message_id`（ID 是时间戳字符串） |
| Discord | ✅ | ✅ `app/modules/discord/__init__.py:500` | 客户端 `discord.py:730-734` |
| WebAgent | ✅ | ✅ 特例 | `app/chain/__init__.py:1926-1939` → `app/helper/agent.py::edit_web_agent_message`（前端事件队列） |
| 其余 7 个 | ❌ | ❌ | 只能重新发一条 |

**工程细节**：Slack/Feishu 的消息 ID 形态不同（Slack `ts` 字符串、Telegram 整数、Discord snowflake），`Notification.original_message_id` 因此声明为 `Union[str, int]`（`app/schemas/message.py:251`）——**把渠道差异泄进了通用模型**。**置信度：高**。

### Q14. 新增一个渠道，需要改几个文件？

**答案：核心代码 3 处 + 前端 2~3 处（不含渠道自身的协议实现）。**

1. **新建模块** `app/modules/<name>/__init__.py`，实现 `_channel` / `init_module` / `init_setting` / `get_name` / `get_type` / `get_subtype` / `stop` / `test` / `post_message`（可选 `edit_message`/`delete_message`/`send_direct_message`/`message_parser`/`mark_message_processing_started`）——基类契约 `app/modules/__init__.py:14-101`（`_ModuleBase`）、`:199-244`（`_MessageBase`）
2. **加枚举成员** `MessageChannel.<Name>`——`app/schemas/types.py:342-357`
3. **加能力声明** `ChannelCapabilityManager._capabilities[MessageChannel.<Name>]`——`app/schemas/message.py:424` 起
4. 前端渠道卡片/配置表单——`src/components/cards/NotificationChannelCard.vue`、`src/components/dialog/NotificationChannelInfoDialog.vue`（1292 行）；5. 前端类型 `src/api/types.ts`
- **不用改**：`ModuleManager` 会自动发现（`app/core/module.py:29-53`），`run_module` 自动扇出。

**一处已腐化的残留**：`app/schemas/message.py:272-295` 的 `NotificationSwitch`（旧的"每渠道一个布尔开关"模型）只列 8 个渠道，且**全库无任何使用**——纯死代码。**置信度：高**。

---

## 四、D. 进度与过程通知（必须明确回答）

### Q15. 有没有"进度通知"？

**答案：没有推送到渠道的进度通知。进度是**进程内缓存 + Web 端 SSE 拉取**，完全不进通知链路。**

**证据**：`ProgressHelper` 的存储是 **TTLCache（进程内）**（`app/helper/progress.py:18`，`TTLCache(region="progress", maxsize=1024, ttl=24h)`），接口只有 `start:31`/`update:64`/`end:42`/`get:86`；消费方是 **HTTP SSE 端点**（`app/api/endpoints/system.py:770-793`，`GET /system/progress/{process_type}` 每 0.5s 推一次 `progress.get()`）；使用方全是业务执行链 + Web API（`app/chain/search.py`、`app/chain/transfer.py`、`app/api/endpoints/history.py`、`app/api/endpoints/storage.py`）；**通知模块 `app/modules/*` 与 `ChainBase.post_message` 全库 0 处引用 ProgressHelper**（20 处引用中 0 处属通知链路）。**置信度：高**。

### Q16. 如果有，怎么实现的？"多次发送"还是"编辑同一条"？

**答案：任务进度没有；但存在真正"过程型"的推送——Agent 流式回复，用"首块新发 + 后续原地编辑同一条"实现，刷新间隔 0.3 秒。**

`StreamingHandler`（`app/agent/callback/__init__.py`）自述即完整机制（`:28-40` 原文）：① 开始时 `start_streaming():146` **先查渠道能力**，不支持编辑则不发流式；② 每产生 token 调 `emit()` 累积到缓冲区；③ 定时器每 `FLUSH_INTERVAL = 0.3`（`:43`）调 `_flush:502`——**第一次有内容 → `send_direct_message` 发新消息并拿 `message_id`；后续有新内容 → `edit_message` 编辑同一条**（`:525` 判 `_message_response is None` 决定发还是改）；**接近渠道长度上限 → 冻结当前消息 + 发新消息续写**（用 Q11 的 `max_message_length`）；④ 结束时 `stop_streaming():200` 做最后一次刷新。

**关键点**：它依赖 Q11 的 `MESSAGE_EDITING` 能力位与 `get_max_message_length()`（`:190` 附近），**能力不足的渠道自动退化为"多次发送"**。测试覆盖：`tests/test_web_agent_stream.py`（1015 行）、`tests/test_message_processing_status.py`。**置信度：高**。

### Q17. 如果没有（任务进度推送）——为什么？

**答案：未找到任何"为什么不做进度推送"的设计说明或 TODO。只能给两点观察，其中第 2 点是推断。**

1. **不是技术做不到**：它已有能力矩阵、有 `edit_message`、有 0.3s 流式编辑的现成机制——把任务进度推给渠道没有障碍。
2. **推断（低置信度）**：更可能是**产品选择**——① 它的通知语义是"发生了一件事"（开始/完成/失败），进度是"正在发生的事"，用户可在 Web 仪表盘看（`app/schemas/dashboard.py:126-185` 里有 `progress_text_i18n` 字段）；② 渠道对高频编辑有限制与观感代价（通知会反复置顶打扰）；③ **它没有任何"任务实体"**（无 Task 表、无 task_id），因而**没有"哪个任务的进度"这个锚点**——这条依据是全库不存在 Task 模型，仅有下载器侧的任务列表（`app/chain/download.py:1759 downloading()`）与前端展示。

**置信度：低**（明确标注为推断；"未找到说明"是实测）。

### Q18. 有没有"过程类"通知（开始/进行中）？还是只有"结果类"？

**答案：以结果类为主，有明确的"开始类"，没有"进行中"类（除 Agent 流式）。**

| 类别 | 是否存在 | 实例与证据 |
|---|---|---|
| 开始类 | ✅ | `downloadAdded` 出厂模板标题 = `'{{ title_year }} ... 开始下载'`（`database/versions/89d24811e894_2_1_4.py:33-48`） |
| 结果类 | ✅ | `organizeSuccess`（入库）、订阅完成、整理失败等（同上 `:22-32,50-58`；`app/chain/transfer.py:1195-1216`） |
| 进行中类（任务） | ❌ | 见 Q15/Q17 |
| 进行中类（Agent） | ✅ | 流式输出（`app/agent/callback/__init__.py`） |
| "处理中"提示 | ✅ | typing / reaction（`PROCESSING_STATUS`；`start/finish_message_processing_status`，`app/chain/__init__.py:128-192`） |
| 用户主动查询进度 | ✅ | `remote_downloading()` 查下载器后拼一条"N 个任务正在下载…xx%"文本（`app/chain/download.py:1723-1757`） |

**置信度：高**。

---

## 五、E. 聚合与去重

### Q19. 有没有聚合/去重机制？

**答案：通知消息**没有**内容聚合；有三样"沾边"的机制，都不是通知聚合器。**

- **免打扰时段队列**（作用域：全部通知）：时间窗（`NotificationSendTime`，默认 00:00–23:59），不在窗内则入 `queue.Queue`，后台线程每 10s 轮询补发——`app/helper/message.py:602`（`MessageQueueManager`）、`:631 init_config`、`:690 _is_in_scheduled_time`、`:757 _monitor_loop`。
- **系统/插件 Web 消息 60 秒重复抑制**（作用域：仅 Web SSE，**不影响渠道投递**）：key = `json({role,title,text,note,当前分钟})`，TTLCache ttl=60 / maxsize=500——`app/helper/message.py:789`（`MessageHelper`）、`:799-827`（`_build_system_notification_key` / `_is_recent_system_notification`）、`:829-850`（`put`）。
- **业务级事件聚合（两处手写）**：① 整理批次刮削事件按"批次全部结束"再发，键 = `transfer_batch_id` × `(storage, path)`（`app/chain/transfer.py:953,1509-1612`）；② 失败重试按 `group_key` 做 **300 秒 debounce**（`:801-806,846`，`RETRY_TRANSFER_DEBOUNCE_SECONDS = 300`）。

**结论**：渠道通知**逐条发送**，没有"把 N 条合并成 1 条"的能力。这与它没有"事件"概念自洽——**没有事件就没有可聚合的维度**。实测 `aggregate`/`dedup`/`聚合`/`去重` 的全库命中里，**没有一处**是对渠道通知做聚合。**置信度：高**。

### Q20. 有没有限流/退避机制？

**答案：没有针对通知渠道的限流退避。只有通用重试装饰器，`429` 处理全部在"非通知"路径上。**

- **通用重试**：`@retry(ExceptionToCheck, tries=3, delay=3, backoff=2)`——3 次、间隔 3s 起、每次 ×2；`ImmediateException` 可中断（`app/utils/common.py:11-56`）。用于 Telegram 发送（`app/modules/telegram/telegram.py:1388,1411,1449`）与微信 access_token/发送（`app/modules/wechat/wechat.py:84,591`）。
- **`429` 处理点（v2.15.6 全库实测）**：站点请求 `app/helper/torrent.py:184`、阿里云盘 `app/modules/filemanager/storages/alipan.py:273`、115 `app/modules/filemanager/storages/u115.py:353`、端点探测 `app/api/endpoints/system.py:1274`。
- **Telegram `RetryAfter`：全库 0 命中**。
- **队列节流**：免打扰时段 + 每 10s 一个队列消费批次，仅此（`app/helper/message.py:757-775`）。

**风险陈述（事实）**：Telegram 返回 429 时 `@retry` 只按 3s/6s 退避重试、**不读 `retry_after`**，重试大概率继续撞限流；三次失败后消息静默丢弃（`_send` 的 `except Exception` 只记日志，`app/helper/message.py:746-755`）。**置信度：高**。

---

## 六、F. i18n

### Q21. 有没有多语言支持？

**答案：后端有（v2.15.x 新增，v2.13.0 时还没有），前端也有。**

- **后端实现**：`app/helper/locale.py`（302 行，`LocaleHelper`），`SUPPORTED_LOCALES = ("zh-CN","zh-TW","en-US")`（`:17`）+ 别名表（`:22-32`）。
- **后端资源**：`app/locales/{zh-CN,zh-TW,en-US}.json`——叶子值 **en-US 826 / zh-TW 826 / zh-CN 85**；结构 `{system, messages, message_patterns}`；`messages` **295**（en/zh-TW）vs **14**（zh-CN）；`message_patterns` **250** vs **20**（实测）。
- **语言解析**：查询参数 `locale` → 请求头 `x-moviepilot-locale`/`x-locale` → `Accept-Language`（含 q 值排序）→ 默认 `zh-CN`（`app/helper/locale.py:44-85`）。
- **请求级上下文**：`ContextVar` + FastAPI 中间件 set/reset（`app/helper/locale.py:97-113`；`app/factory.py:86-92`）。
- **前端**：`src/locales/{en-US,zh-CN,zh-TW}.ts` + `src/plugins/i18n.ts`，另有孤儿键门禁（前端仓 `tests/config/locale-orphans.spec.ts`）。

**置信度：高**。

### Q22. 如果有，事件文案怎么组织？

**答案：与 PilotStd 完全不同——它**不按"事件键"组织，而是按"中文原文"反向查表**，且产出"平行字段"而非"替换"。**

**三层查找（`LocaleHelper`）**：① `translate(key)`——点分结构键（如 `system.modules.xxx`），从 `system` 段取（`:116-138`）；② `translate_text(text)`——**拿中文原文去 `messages` 字典精确查**（`:141-163`、`_lookup_message:202-211`）；③ `_lookup_pattern(locale, text)`——**把中文模板编译成正则**（`{name}` → `(?P<name>.+?)`）再匹配，动态段可再翻译（`:214-225`、`_compile_pattern:271-283`、`_build_pattern_values:227-244`）。

**关键设计（原文注释 `app/helper/locale.py:12-13`）**："该类只为需要返回给前端展示的文本生成**并行多语言字段**，旧有中文字段仍由调用方保留。"即 API 返回 `{message: "模组不支持测试", message_i18n: "Module does not support testing"}`——**中英文同时下发**，由前端决定用哪个。实测所有调用点都遵循此模式（`app/schemas/response.py:26-27`、`app/schemas/dashboard.py:126-185`、`app/helper/progress.py:100-115`、`app/api/endpoints/search.py:123-127`、`app/api/endpoints/agent.py:601`）。**回退策略**：目标语言缺失 → 回退 `zh-CN` → 再回退原文（`:134-138,155-163`）。

**对照 PilotStd（只陈述差异）**：键形态它用"①结构键 ②中文原文 ③中文正则"，PilotStd 用层级键 `notification.{category}.{event}.{field}`（`pilotstd/i18n/__init__.py:123-130`）；叶子数它 826/826/85，PilotStd en 714 / zh_CN 718 / zh_TW 635；缺键行为它**回退**，PilotStd `t()` **返回键本身**（fail-loud，`pilotstd/i18n/__init__.py:120,130`）；覆盖强制它无通知相关强制，PilotStd 由 G-045 按事件强制（实测 41/41）。**置信度：高**。

### Q23. 如果没有——它怎么管理"事件 → 文案"映射？

**答案：前提不成立（有 i18n），但更重要的发现是**通知链路上 i18n 完全没接线**，所以"推送给用户的通知文案"仍等同于"代码里写死的中文"。**

**实测证据（v2.15.6 全库 `LocaleHelper.` 调用点共 28 处）**：`app/schemas/dashboard.py` 11 处、`app/api/endpoints/search.py` 3、`app/helper/progress.py` 3、`app/factory.py` 3、`app/schemas/response.py` 2、`app/api/endpoints/agent.py` 2、`app/api/endpoints/system.py` 2、`app/helper/locale.py` 3（自身）——**全部不属于通知链路**；而 **`app/chain/**`（含 `post_message`）= 0、`app/helper/message.py`（模板/队列）= 0、`app/modules/**`（10 个渠道）= 0**。

**因此**：通知的 `title`/`text` 要么是调用点硬编码中文（100+ 处），要么来自 Jinja2 模板——而**模板串里的中文也是写死的**（`database/versions/89d24811e894_2_1_4.py:22-58`）。**置信度：高**。

---

## 七、G. 用户配置

### Q24. 用户能配置什么？

**答案：分两层且极不对称——管理员配一切，"用户"只能填自己在各渠道的 ID。**

- **管理员（设置 → 通知，`src/views/setting/AccountSettingNotification.vue`，728 行）**：渠道实例 CRUD（名称/类型/配置/启用/**场景开关 `switchs`**，模型 `NotificationConf` 见 `app/schemas/system.py:83-97`）；9 类 × 4 档投递范围表（UI `:567-608`，模型 `NotificationSwitchConf` 见 `app/schemas/system.py:100-108`）；4 个 Jinja2 模板（UI `:30-51,540-565`）；免打扰时段（UI `:609-640`，存储 `app/schemas/types.py:267`）；通知中心清理范围与时间。
- **管理员代填的用户渠道 ID（`src/components/dialog/UserAddEditDialog.vue`）**：**7 个**——`wechat_userid`/`wechatclawbot_userid`/`telegram_userid`/`slack_userid`/`discord_userid`/`vocechat_userid`/`synologychat_userid`（默认值 `:95-103`；表单 `:575,584,593,602,611,620,629`）。
- **用户自助（个人资料 → 账号绑定，`src/views/user/UserProfileView.vue:499-598`）**：**10 个**字段——上述 7 个 + `qq_userid`/`qq_openid`/`feishu_openid`（另有非通知用的 `douban_userid`）。
- **两处都配不了**：任何"我要/不要哪类通知"的订阅开关（前端无此类 UI；后端 `User.settings` 只被当"地址簿"读，`app/db/user_oper.py:162-170`）。**置信度：高**。

### Q25. 配置的粒度是什么？

**答案：类别级（9 类），**不是事件级**；且有"双层过滤"：类别范围（全局）× 渠道场景开关（每渠道）。**

**投递判定链（实测三处）**：① `post_message` 先查**类别 → 范围**——`ServiceConfigHelper.get_notification_switch(mtype)`（`app/helper/service.py:73-81`）→ 拿 `action` 拆 `admin`/`user` → 构造 `targets` → 逐份投递（`app/chain/__init__.py:1646-1710`）；② 渠道侧再查**该渠道是否接收此类别**——`_MessageBase.check_message()`，`conf.switchs` 不含 `mtype.value` 即 False（`app/modules/__init__.py:223-244`）；③ **定向消息跳过第 ② 步**——`if not message.userid and message.mtype:`（`:238`），只要指定 `userid`，渠道类别开关失效（见 Q27）。

**默认值也在前端**：`AccountSettingNotification.vue:112-149` 写死 9 行（资源下载/整理入库/订阅 = `all`，其余 = `admin`）。**置信度：高**。

### Q26. 配置的存储在哪里？

**答案：三处——系统配置表（键值 JSON）、用户表 JSON 列、消息历史表。**

| 存什么 | 存哪 | 键 / 列 | 证据 |
|---|---|---|---|
| 渠道实例（含 `switchs`） | `systemconfig` 表 | `SystemConfigKey.Notifications`（`app/schemas/types.py:213`） | 读取 `app/helper/service.py:59-63`；UI `AccountSettingNotification.vue:301,374` |
| 类别 → 范围 | 同上 | `SystemConfigKey.NotificationSwitchs`（`:215`） | `app/helper/service.py:66-71`；UI `:419-445` |
| 模板 | 同上 | `SystemConfigKey.NotificationTemplates`（`:273`） | `app/helper/message.py`（`_get_template`） |
| 免打扰时段 | 同上 | `SystemConfigKey.NotificationSendTime`（`:267`） | `app/helper/message.py:631` 起 |
| 通知中心清理时间 | 同上 | `SystemConfigKey.NotificationClearBefore` | `app/api/endpoints/message.py:39-63` |
| 用户渠道 ID | `user` 表 **JSON 列 `settings`** | `app/db/models/user.py:33` | 读写 `app/db/user_oper.py:162-170` |
| 消息历史（通知中心数据源） | `message` 表 **11 列** | `app/db/models/message.py:14-36` | 写入 `app/db/message_oper.py:20-64`；读取 `GET /message/notification`（`app/api/endpoints/message.py:172-189`） |

**注意**：配置**全部是数据库数据，不是代码清单**——这是"加类别不用改后端逻辑"的另一半原因；但前端选项列表仍是硬编码（`src/api/constants.ts:241-278`）。**置信度：高**。

---

## 八、H. 安全与权限

### Q27. 有没有"安全告警"类事件的特殊处理（绕过用户配置、强制送达）？

**答案：没有安全告警专用通道，也没有"强制送达"开关。唯一的"绕过"是**定向消息跳过渠道类别开关**，而它并非为安全设计。**

- **定向消息跳过渠道类别开关**：`if not message.userid and message.mtype:` 才查 `switchs`；带 `userid` 的消息**无视渠道类别开关**（`app/modules/__init__.py:238-243`）。但它仍受"类别 → 范围"的 `action` 影响（若 `action` 里没该用户，消息根本不投给该用户）。
- **`immediately=True`（跳过免打扰时段）**：只在 `userid` 非空时用（`immediately=True if dispatch_message.userid else False`，`app/chain/__init__.py:1720`，异步路径 `:1836,1857,1877`），即"有人点名收"才立即发。
- **安全类通知走普通路径**：站点 Cookie 失效/低分享率 = `NotificationType.SiteMessage`，用户可在类别开关里关掉（`app/chain/site.py:86-118`）。
- **系统级错误**：走事件广播 + Web SSE（`role="system"`），**不经渠道通知**，因此不受渠道开关影响——但也不会推到 Telegram/微信（`app/core/event.py:753-775`；`app/chain/__init__.py:234-276`）。
- **管理员权限拦截**：每渠道**各自实现**（8 份重复代码 + 8 个 `*_ADMINS` 配置项，MoviePilot 仓 `tests/test_message_channel_permissions.py:19-399`）。
- **无"绕过配置强制送达"标志**：`Notification` 24 字段里没有 `force`/`bypass` 语义字段（`app/schemas/message.py:207-269`）。

**风险陈述（事实，非建议）**：凭证/登录类告警在 MoviePilot 里**没有脱离用户配置的投递路径**；这与 PilotStd 的 `security_notifier`（专用直连通道，见 02 报告）是相反的设计取向。**置信度：高**（"无专用通道"为穷举实测）。

### Q28. 多用户场景下，通知怎么路由到正确的用户？

**答案：MoviePilot 是多用户设计，路由由"类别范围（`action`）× 用户渠道 ID 绑定"共同决定，用户本人无订阅权。**

**路由算法（`app/chain/__init__.py:1646-1710`，逻辑原样复述）**：
```
若 消息无 userid 且 有 mtype:
    action = 该类别配置的范围字符串（'all' | 'user' | 'admin' | 'user,admin'）
    for 每个 action 片段:
        admin  → targets = useroper.get_settings(SUPERUSER)      # 超级管理员的渠道 ID 集
        user   → targets = useroper.get_settings(消息.username)  # 发消息的用户
                 若该用户不存在:
                     若管理员还没发 → 回滚发给管理员
                     否则          → 本条不发（continue）
        else   → 按原消息发给全体（send_orignal）
        投递：send_event(NoticeMessage) + messagequeue.send_message(...)
```

**渠道侧如何用 `targets`（各渠道取自己的键）**：Telegram `telegram_userid`（`app/modules/telegram/__init__.py:497`，`:734` 同）；微信 `wechat_userid`（`app/modules/wechat/__init__.py:341`）；微信 ClawBot `wechatclawbot_userid`（`app/modules/wechatclawbot/__init__.py:217`）；QQ `qq_userid`/`qq_openid`，无则退化到群 `qq_group_openid`（拼 `group:` 前缀，`app/modules/qqbot/__init__.py:363-368`）；Slack `slack_userid`（`app/modules/slack/__init__.py:534`，`:806` 同）；Discord `discord_userid`（`app/modules/discord/__init__.py:387`，`:665` 同）；VoceChat `vocechat_userid`（`app/modules/vocechat/__init__.py:360`，`:395` 同）；SynologyChat `synologychat_userid`（`app/modules/synologychat/__init__.py:366`）；Feishu `feishu_userid`（另有 `feishu_openid`/`feishu_chat_id`，`app/modules/feishu/__init__.py:65`）。

**找不到 ID 怎么办**：Telegram/微信等会 `logger.warn` 并 **`return`（整条消息不投给该渠道）**（`app/modules/telegram/__init__.py:499-500`、`app/modules/wechat/__init__.py:342-343`）；QQ 退化为"向曾发过消息的用户/群广播"（`app/modules/qqbot/__init__.py:369-370` + `qqbot.py:332-340`）。**WebPush 又不一样**：不看 `targets`，而是向**全局浏览器订阅集合**广播，另按 `conf.config["WEBPUSH_USERNAME"]` 做用户名白名单（`app/modules/webpush/__init__.py:62-72`）。

**结论**：路由是"按类别决定发给谁 + 按用户绑定的 ID 找地址"，**用户没有"我只要哪几类"的表达能力**；且 `action` 是**全局单例**（同一类别对所有人都一样）。**置信度：高**。

---

## 九、未找到答案的问题（如实列出）

| # | 问题 | 状况 |
|---|---|---|
| 1 | "为什么不做任务进度推送" | **未找到**任何设计说明、注释或 TODO。只能给推断（Q17），已标注低置信度 |
| 2 | "为什么引入 Jinja2 模板机制" | **未找到**设计文档/ADR/提交说明层面的动机陈述。Q9 的动机段为推断 |
| 3 | `NotificationType` 用**中文**作线值（而非英文键）的原因 | **未找到**说明。事实层面可确认：前端 `src/api/constants.ts:241-278` 用同一批中文串比对 |
| 4 | 是否有意让 `Web`/`WebAgent` 不进模块扇出 | **未找到**说明。只能确认现状（无模块、有特例分支） |
| 5 | QQ 按钮"声明了却没接线"是 bug 还是未完成 | **未找到** Issue/注释。代码层面两者都可能 |
| 6 | 通知渠道是否曾因限流被投诉/修复过 | **未找到**——仓库内无相关测试或注释 |
| 7 | `app/locales/zh-CN.json` 只有 85 个叶子是否为有意设计 | **推断**：默认语言即代码中的中文，故 zh-CN 只需覆盖少数例外。**未找到**明文说明（`locale.py:16` 只写了 `DEFAULT_LOCALE = "zh-CN"`） |
| 8 | 前端"孤儿键"门禁是否覆盖到通知文案粒度 | **未查证**到该粒度（仅确认门禁文件存在：前端仓 `tests/config/locale-orphans.spec.ts`） |

---

## 附：可复算命令

```powershell
# 0) 取得/钉住调查版本（本次实际执行）
git -C "D:\mp插件\MoviePilot-src" fetch origin v2
git -C "D:\mp插件\MoviePilot-src" worktree add --detach "C:\Temp\mp-v2" origin/v2
git -C "C:\Temp\mp-v2" log -1 --format="%h %ci %s"     # → 1528176b 2026-09-26
Get-Content "C:\Temp\mp-v2\version.py" -TotalCount 3   # → APP_VERSION = 'v2.15.6'
git clone --depth 1 https://github.com/jxxghp/MoviePilot-Frontend.git "C:\Temp\mp-frontend"
$W = "C:\Temp\mp-v2"; $F = "C:\Temp\mp-frontend"

# 1) 本报告全部数字与行号的生成脚本（只读）
python C:\Temp\mp_probe\probe.py "$W"      # 枚举/字段/模块/调用点统计
python C:\Temp\mp_probe\lines.py           # 消息模型、渠道能力、编辑入口行号
python C:\Temp\mp_probe\lines2.py          # 模块发现、事件注册、进度、队列行号
python C:\Temp\mp_probe\lines3.py          # 前端选项、能力矩阵条目、429 命中点行号
python C:\Temp\mp_probe\verify_cites.py    # 45 处关键引用的内容级校验
python C:\Temp\mp_probe\scan_report.py     # 本报告所有 `路径:行号` 的存在性/范围校验

# 2) 手工复核（示例）
Select-String -Path "$W\app\schemas\types.py" -Pattern '^class NotificationType|^class MessageChannel|^class ContentType'
Get-Content "$W\app\schemas\message.py" | Select-Object -Skip 206 -First 63      # Notification 24 字段
Get-ChildItem "$W\app\modules" -Recurse -Filter __init__.py | Select-String 'def post_message\('
Get-ChildItem "$W\app\modules" -Recurse -Filter __init__.py | Select-String '_channel\s*='
Get-ChildItem "$W\app" -Recurse -Filter *.py | Select-String 'LocaleHelper\.'   # 通知链路 0 命中
Get-ChildItem "$W\app\modules" -Recurse -Filter *.py | Select-String '429|RetryAfter'

# 3) 前端选项与用户配置
Get-Content "$F\src\api\constants.ts" | Select-Object -Skip 239 -First 48        # notificationSwitchOptions（9 类）
Get-Content "$F\src\views\setting\AccountSettingNotification.vue" | Select-Object -Skip 110 -First 40
Get-Content "$F\src\components\dialog\UserAddEditDialog.vue" | Select-Object -Skip 93 -First 12
```

**调查未做的事（证据边界）**：未运行 MoviePilot；未连接任何 MoviePilot 实例（含 PilotStd 的 `192.168.1.18:9028`）；未以官方文档/Issue 作为结论来源；未修改被调查仓库任何文件（`git status` 零差异，worktree 与 clone 均为一次性产物）。
