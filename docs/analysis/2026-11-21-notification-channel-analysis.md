# 通知渠道现状分析（阶段 1）

> 2026-11-21 ｜ 范围：企业微信 / Telegram / 钉钉 / 飞书（四渠道）｜ 性质：**只分析现状，不含实现方案**
>
> **已查阅**：`docs/reference/notification-user-guide.md`（§一 事件清单、§二 模板结构、§四 复用与新增步骤）、
> `docs/governance/notification_coverage.md`（§一 审计方法、§一-B 渠道派生一致性、§三 缺口分类、§四 新增事件清单）、
> `docs/onboarding/08-known-boundaries.md`（#9 通知聚合现状、#16 重试覆盖不均、#18 铃铛重复）、
> `docs/analysis/notification-stage2.md`（同题前作，2026-11-19）。
>
> **取证方式**：读代码 + 用真实构建器→渲染器跑出四渠道输出（未改任何代码），结论一律附 `文件:行号`。
> 拿不到证据的一律写「未取证」，不推测。

---

## 1. 结论摘要

1. **不是各自为战——有统一的语义层，但只统一到"内容"为止。**
   所有事件先被构建成同一个消息对象 `NotificationMessage`（字段定义 `pilotstd/core/notification/channel.py:33-108`），
   正文由四种语义块拼成（文本 / 字段对照 / 状态变化 / 列表，`pilotstd/core/notification/blocks.py:20-59`）；
   四个渠道拿的是**同一份消息对象**，各自翻译成自己的格式。所以「同一事件在四个渠道内容不一致」不存在，
   **但「同一事件在四个渠道能表达什么」确实不一致**（见 §3）。

2. **有注册表/工厂，没有"渠道能力"的统一定义。**
   渠道由一张声明表派生注册（`channel_spec_data.py:20-411` → `manager.py:34`），加渠道不用再改注册代码；
   但"能不能发图片、能不能 @人、有没有按钮、有没有回执"**没有进入这张声明表**
   （`interaction.py:20-31` 只有"能否回调/能否编辑/锚点"三个字段，且无图片、无 @）。

3. **同一事件在四渠道：正文一致，排版与"语义可见性"不一致。**
   级别（信息/警告/错误）只有飞书（标题颜色，`renderer.py:187-191`）和钉钉卡片（`level` 字段，`renderer.py:350-355`）能看到；
   企微 markdown、Telegram、桌面**看不到级别**（`renderer.py:144-179`、`renderer_telegram.py:75-116`、`renderer.py:359-388`）。
   消息里的站内链接字段 `message.link` 四渠道**一个都不渲染**（实测四渠道输出均无 `/standards/...`，字段只在 `_manager_ops.py:92` 落库）。

4. **默认投递不统一：44 个事件里，15 个出厂只发企微、28 个没有任何出厂渠道、只有 1 个四渠道全开。**
   证据：`event_spec_data.py` 各条 `default_channels`（例 `:25` 仅 `("wechat",)`、`:193` 空、`:443` 四家）+
   `defaults.py:101` + `_policy.py:127-132` + `_dispatcher.py:111-113`。新装用户实际只能收到 16/44 个事件。

5. **加一个新渠道不是"加一个类"，至少要动 8~9 处，其中 3 处漏了不报错。**
   注册/实例化/前端表单已由声明表派生（零改动）；但分片上限表、限流码表、测试发送、安全告警直连、
   回调验签、渠道菜单六处仍是逐渠道写死的 `if/elif`（逐处见 §4）。

---

## 2. 渠道清单

四家走**同一条发送主干**：`NotificationManager.send_event`（`manager.py:235`）→ `_dispatcher.send_event`（`_dispatcher.py:70`）
→ `do_send`（`_dispatcher.py:210`）→ `send_now`（`_dispatcher.py:236`）→ `channel.send(msg)`（`_dispatcher.py:290`）。
差别只在 `channel.send()` 这一层。

| 渠道 | 发送入口函数 | 消息格式 | 图片 | @人 | 按钮 | 回执 | 失败处理 |
|---|---|---|---|---|---|---|---|
| **企业微信** | `WechatChannel.send`<br>`channels/wechat.py:72` | 群机器人 → markdown（`:59`、`:91`，上限 2048 **字节**、按字节分段，见 `:88-92`）；<br>自建应用 → 模板卡片 `template_card`（`:172-175`，`renderer_wecom_card.py:38-76`），卡片被拒**自动降级为文本**（`:79-84`） | ✗ 无图片分支 | ✗ `touser="@all"` 是收件人不是 @提及（`wechat.py:50`） | 仅"跳转链接"：卡片 `jump_list`（`renderer_wecom_card.py:73-75`）；markdown 形态只能写文字链接（`renderer.py:129-140`） | 自述"不支持回调"（`wechat.py:240-242`），但验签实现已存在（`callback.py:219`）→ **是否真启用：未取证** | 3 次重试（`base.py:40-41`、`145-173`）；429/5xx 与限流码 45009（`base.py:98`、`wechat.py:159/170`）；网络异常可重试（`wechat.py:222`）；分段逐段发，任一段失败即整体失败（`wechat.py:92-95`） |
| **Telegram** | `TelegramChannel.send`<br>`channels/telegram.py:61` | `MarkdownV2`（`:109`），18 个保留字符逐字转义（`renderer_telegram.py:19`、`:120-128`） | ✗ 无图片分支 | ✗ 无 mention 实体 | ✓ `inline_keyboard`（`renderer_telegram.py:28-71`），只挂**最后一段**（`telegram.py:82-86`） | ✓ 可回调、可编辑（`telegram.py:196-202`、`204-223`） | 3 次重试，**服务端 `retry after` 优先**、上限 60 秒（`base.py:43-44`、`62-82`）；401/404 视为配置错误**不重试**（`telegram.py:166-177`）；分段各自独立重试（`telegram.py:89-94`） |
| **钉钉** | `DingTalkChannel.send`<br>`channels/dingtalk.py:92` | 双读：企业级字段齐 → 互动卡片 `cardParamMap{title,content,level}`（`renderer.py:332-356`）；否则群机器人 markdown（`:115-119`，标题截 50 字符 `:118`） | ✗ 无图片分支 | ✗ 无 mention 分支 | 卡片按钮由**租户模板**定义，代码只给 Markdown 链接（`renderer.py:341-349`） | 自述可回调（`dingtalk.py:320-322`）；**不可编辑**（`i18n/zh_CN.json:920`：更新接口未取证） | 3 次重试（`dingtalk.py:127-133`、`:218-225`）；429/5xx；限流码**未取证**→ 关键词兜底（`base.py:100`、`dingtalk.py:169`）；卡片"创建成功但投递失败"重试会**重复建卡**（`dingtalk.py:229-232` 自述） |
| **飞书** | `FeishuChannel.send`<br>`channels/feishu.py:244` | 交互式卡片（标题颜色 + elements，`renderer.py:230-236`）；列表→**表格**（`renderer.py:257-290`）；超长**按元素切卡**（`feishu.py:275-326`） | ✗ 无图片分支 | ✗ 无 mention 分支 | ✓ URL 按钮（`renderer.py:217-228`）；列表块另带"查看完整列表"按钮（`:292-308`） | ✓ 可回调（`feishu.py:392-404`）；**应用形态可 PATCH 编辑**（`:170-192`），Webhook 形态拿不到 message_id（`:178`） | 3 次重试（`feishu.py:328-334`、`:124-126`）；429/5xx 与限流码 99991400（`base.py:99`）；网络异常可重试（`feishu.py:376-379`） |

**四渠道共用的失败兜底（属于"已经做对"的部分）**：三处重试节奏/限流解析/错误去重已从 Telegram 提升到渠道基座
（`base.py:30-37`、`145-173`），四家复用；每个渠道失败都会写 `last_error`（`base.py:125`）并由 `_dispatcher.send_now`
回填日志（`_dispatcher.py:290-309`）；连败 5 次或窗口失败率 ≥50% 会触发"通知投递失败告警"，且**发给故障渠道以外**的渠道
（`delivery_health.py:99-120`、`_dispatcher.py:330-358`）。

**另外两条通路（不计入四渠道对比）**：桌面（`DesktopRenderer`，`renderer.py:359-388`；压成一行见 `desktop_formatter.py:39-70`）
与站内 Web（无后端推送通道，`channel.py:25-26` 说明）。

---

## 3. 事件与语义

### 3.1 事件种类

- 事件**唯一登记**在 `events.py:94-142`（`ALL_EVENTS`），实测 **44 个**；每个事件的规格（类别/内容类型/构建器/触发器/默认渠道）
  在 `event_spec_data.py:20-549`（44 条），两表由 `event_spec.py:126` 的断言强制一一对应。
- 面向用户的**类别**有 10 类（`mapping.py:61-72`：进行中/成功/失败/日常动作/批量汇总/异常/安全/提醒/系统健康/手动测试）。
- 事件按业务分 12 组写在说明文档里（`notification-user-guide.md:11`），与代码的 10 类用户类别**没有对照表**——两套分类并存。

> **数量漂移（已核实）**：说明文档与覆盖度矩阵都写 **41 个**（`notification-user-guide.md:11`、`:384`；
> `notification_coverage.md:31`、`:83`），代码实际 **44 个**——后加的 `task_progress`（`events.py:137`）、
> `desktop_toast`（`:139`）、`auto_pipeline_summary`（`:141`）未进矩阵，`event_spec_data.py:18` 的注释也还写着"41 条"。
> 实测命令：`python -c "from pilotstd.core.notification.events import ALL_EVENTS; print(len(ALL_EVENTS))"` → `44`。

### 3.2 同一事件在四渠道的实际表达差异（实测输出，非示意图）

用真实构建器 + 四个渲染器跑出来的结果（只读，未改代码）：

#### 例 1：标准状态变更 `standard_status_changed`（构建器 `_builders_validity.py:22-65`）

内容层只有**一个状态变化块**（`:33-35`），级别由"是否废止"决定（`:37-47`）。

| 渠道 | 实际输出 | 差异点 |
|---|---|---|
| 企微/钉钉（markdown） | `**GB/T 1234-2020 食品安全**` + 空行 + `现行 → 废止`（`renderer.py:157-158`） | **拆成两段**，像"标题 + 内容" |
| Telegram | `GB/T 1234\-2020 食品安全: 现行 → 废止`（`renderer_telegram.py:88-89`） | **压成一行**；标准号的点被反斜杠转义（`:120-128`） |
| 飞书卡片 | 标题栏 **橙色**（`renderer.py:187-191`）+ 一行 `**标签**` 换行 `旧 → 新`（`:250-255`） | 唯一"颜色即级别"的渠道 |
| 钉钉卡片 | `cardParamMap.content = "GB/T 1234-2020 食品安全: 现行 → 废止"` + `level="warning"`（`renderer.py:350-355`） | 用**半角冒号**，企微是**全角冒号**（`renderer.py:155`） |
| 桌面 | `标准状态变更 GB/T 1234-2020 食品安全：现行 → 废止`（`renderer.py:371-372`） | 全角冒号、单空格分隔 |

**关键差异**：① 同一条"变更"企微是两行、其余一行；② 级别 `warning` 在企微 / Telegram / 桌面**完全不可见**；
③ `message.link = /standards/GB/T 1234-2020`（`:62`）在四渠道输出里**一个都没有**。

#### 例 2：公告抓取完成 `announcement_fetch_complete`（构建器 `_builders_batch.py:82-117`）

| 渠道 | 实际输出 | 差异点 |
|---|---|---|
| 企微 / Telegram / 钉钉 / 飞书 | 四段文本：来源、`新增公告：2；其中国标：2…`、`本次新增公告：`、两行 `• 标题`（`:88-110`） | 四渠道内容**完全相同**，只有标题标记不同（`##` / `*…*` / 卡片头） |
| 桌面 | 合并成一行，只留第一条（`renderer.py:374-384`） | 明细被压缩 |

**两处结构性差异**：
① 规格声明它的事务类型是 **`list`**（`event_spec_data.py:292`），但构建器只产出 4 个 `TextBlock`（`_builders_batch.py:88-110`）
→ 飞书那条"列表渲染成表格"的高级路径（`renderer.py:257-290`）**根本不会被触发**，声明只被门禁读、不被渲染读。
② 它出厂**只投企微**（`event_spec_data.py:295` 的 `default_channels=("wechat",)`）→ 钉钉/飞书/Telegram 默认收不到这个事件。

#### 例 3：下载失败 `download_failed`（构建器 `_builders_batch_download.py:60-85`）

- 内容：标准号 / 名称 / 标准类型 / 错误（错误经 `translate_error_message` 归一，`:72-75`），级别固定 `error`（`:79`）。
- 飞书 = **红色**标题栏（`renderer.py:187-191`）；钉钉 = `level="error"`（靠租户模板决定显示）；
  **企微 / Telegram / 桌面看不出这是"错误"**（无级别渲染）。
- `link = /standards/GB/T 5678-2021`（`:83`）同样四渠道都不渲染。
- 出厂**没有任何默认渠道**（`event_spec_data.py:193` 的 `default_channels=()`）→ 策略表为空时**一条都不发**
  （`_policy.py:127-132` 回退读 config 取不到 → `_dispatcher.py:111-113` 只记一行 info 日志就返回）。

### 3.3 一句话总结语义现状

**内容统一、排版按格式族分化、语义字段（级别/链接）没有跨渠道落地。**
这三点中，第 1 点是这套设计最大的成绩（加事件不用改四个渲染器，`notification-user-guide.md:274`、`:346-351` 的说法与代码一致）；
第 2 点是格式差异的正常代价；**第 3 点是真正的缺口**。

---

## 4. 模块化评估：加一个新渠道要改几处

### 4.1 已经具备的能力（这部分做得好）

| 能力 | 证据 |
|---|---|
| **单一声明表**：4 个渠道的字段、表单形态、"是否已配置"判定规则集中一处 | `channel_spec_data.py:20-411` |
| **注册表由声明派生**，不需要单独维护渠道清单 | `manager.py:34`（`_CHANNEL_CLASSES = {s.name: channel_class(s) …}`）、`channel_spec_data.py:414`（`CHANNEL_NAMES` 派生） |
| **工厂/实例化由声明驱动**：按 `spec.ctor` 顺序取凭证、按 `forms` 判可用 | `_channel_registry.py:27-46` |
| **前端表单由 API 派生**，前端已无硬编码渠道键（基线 26 → 0） | `channel_spec.py:184-204`、`docker/api/notification_config.py:207-221`、`notification_coverage.md:169-171` |
| **渠道消息 ID 白名单派生**，不是手写四个键 | `channel.py:19-29` |

结论：**"注册"这一处已经不用改了**——这是相比早期明显的进步。

### 4.2 仍需改动的地方（逐处）

| # | 要改的地方 | 文件:行号 | 不改会怎样 |
|---|---|---|---|
| 1 | 新渠道实现类（发送 + 渲染） | 参照 `channels/wechat.py:23`、`telegram.py:48`、`dingtalk.py:34`、`feishu.py:27` | 没有发送能力 |
| 2 | 声明表加一条 `ChannelSpec`（字段/表单/状态规则） | `channel_spec_data.py:20-411` | 前端看不到、凭证存不进、渠道构造不出来 |
| 3 | **分片上限表** | `renderer_base.py:26-31` | 缺省回退 4096 字符（`:92`），**不报错**，但超长消息被平台拒收 |
| 4 | **限流错误码表** | `channels/base.py:97-102` | 缺省空集，只能靠关键词兜底（`:114-117`），限流会被当成普通失败 |
| 5 | **测试发送的构造分支** | `_format_utils.py:119-158` | 新渠道落到 else 分支（`:159-164`），只认 `webhook_url`，"测试连接"按钮失效 |
| 6 | 安全告警直连构造 | `security_notifier.py:72-106`（分支 `:80/92/96/101`） | 凭证被改这类告警发不到新渠道 |
| 7 | 回调验签分支 | `callback.py:175/183/199/219`，未知渠道直接拒绝（`:222-223`） | 新渠道的按钮/回执全部返回"不支持" |
| 8 | 渠道菜单（A-27，另一套并行实现） | `menu/model.py:16`、`menu/service.py:25` + `:51-62`、`menu/clients.py:100/197/289/338` | 菜单功能缺该渠道（不影响发消息） |
| 9 | 每个事件的默认渠道 | `event_spec_data.py`（例 `:25/:193/:295/:443`） | 新渠道出厂收不到任何事件 |
| 10 | 三语文案 `notification.channel.<name>.*` | `i18n/zh_CN.json:920-926` 同族键 | 界面上显示键名 |

**合计**：上表 10 类改动中，第 8 项（渠道菜单）只在"该渠道也要支持菜单"时才算 ⇒ **实际 8~9 处**
（代码 7 处 + 声明/文案 2~3 处）。其中第 3、4、5 项是"漏了不报错"的软肋，第 6、7 项是"漏了只在新场景暴露"的软肋。

### 4.3 顺带发现的两处"模块内不一致"

- **能力自述没人用**：四个渠道都写了 `capabilities`（`wechat.py:240-242`、`telegram.py:196-202`、`dingtalk.py:320-322`、
  `feishu.py:392-404`），但全库**没有运行时消费者**（只有 `tests/test_channel_capabilities.py:27/62` 读它），
  前端也没有 `capability_note` 的渲染（`web/src` 无命中）→ 用户看不到"为什么飞书 Webhook 不能编辑"这类说明。
- **菜单模块另有一套渠道清单且仍读 config.json**：`menu/service.py:29-31` 读 `notification.channels.<channel>`，
  而渠道基座明确写"config.json 运行时不再读取"（`channels/base.py:9-10`）——两处口径不一致。

### 4.4 与同题前作的差异（对齐与更正）

`docs/analysis/notification-stage2.md`（2026-11-19）已经问过同样的问题，本报告在其基础上补了行号级证据，
并按代码实测做了三处对齐/更正：

1. 事件数：前作未给数字，**代码实测 44**（用户说明文档与覆盖矩阵仍写 41，见 §3.1 的漂移说明）；
2. 前作称 Telegram 用 **HTML**（`notification-stage2.md:10`），实测用的是 **MarkdownV2**（`telegram.py:109`）；
3. 前作估"加渠道约 3~5 处"（`notification-stage2.md:23`），实测仍需 **8~9 处**，其中 3 处漏了不报错（§4.2）。

---

## 5. 阶段 1 缺口清单（按"影响面 × 修复成本"排序）

| 序 | 缺口 | 影响面 | 修复成本 | 关键证据 |
|---|---|---|---|---|
| 1 | **28 个事件没有出厂默认渠道**，策略表为空时静默不发 | 高（新装用户只能收到 16/44 个事件，含 `download_failed`、`scan_complete`、`favorite_created`） | 低（改声明表字段 + 一份出厂订阅） | `event_spec_data.py:193`/`:47`；`defaults.py:101`；`_policy.py:127-132`；`_dispatcher.py:111-113` |
| 2 | **`message.link` 只落库、四渠道都不渲染** | 高（"某标准失败"无法一键定位） | 中（渲染器统一消费 + 降级口径） | `channel.py:43`；`_builders_validity.py:62`；`_builders_batch_download.py:83/108/141`；`_manager_ops.py:92`；渲染器无消费（`renderer.py`、`renderer_telegram.py`、`renderer_wecom_card.py`） |
| 3 | **级别只在飞书/钉钉可见** | 中高（告警在企微/TG/桌面被当成流水） | 中低（各渲染器加前缀/图标） | `renderer.py:187-191`、`:350-355`；`renderer.py:144-179`；`renderer_telegram.py:75-116`；`renderer.py:359-388` |
| 4 | **渠道能力无统一声明、也无出口给用户** | 中（用户不理解能力缺失，加渠道也无法声明"我不支持X"） | 中（扩声明 + 接口 + 前端） | `interaction.py:20-31`；四家 `capabilities` 各自硬写；`web/src` 无 `capability_note` |
| 5 | **"内容类型"声明与实际块类型无人校验** | 中（飞书表格/卡片列表等高级表达实际很少被用上） | 中（规格侧加一条可验证约束） | `event_spec_data.py:292` vs `_builders_batch.py:88-110`；G-046 只查空值/静默吞错（`notification_coverage.md:260-275`） |
| 6 | **跨渠道回归网是"事件级"不是"渠道级"** | 中（改一个渲染器，多数事件无跨渠道断言） | 中高（逐渠道补渲染断言） | `notification_coverage.md:104`（B-3 原文） |
| 7 | **"测试连接"对双形态渠道构造错/不全** | 中低（用户点"测试"得到错误结论） | 低 | `_format_utils.py:150` 传 `cls(corpid, agentid, corpsecret)`，与 `wechat.py:43-51` 的 6 参数签名**位置错位**；`:131-136` 钉钉忽略企业级字段；`:137-142` 飞书只支持 Webhook |
| 8 | **文档与代码数量/位置漂移** | 低（对不上账） | 低 | 文档写 41（`notification-user-guide.md:11`、`notification_coverage.md:31`）vs 代码 44（`events.py:137/139/141`）；`event_spec_data.py:18` 注释仍"41 条"；多处注释引用已不存在的 `docs/plans/notification-redesign/`（`channel.py:26`、`interaction.py:3-10`、`channel_spec.py:4`） |
| 9 | **分段口径不统一，同一条长消息在各渠道"条数"不同** | 低（用户看到的消息条数不一致） | 低中 | `renderer_base.py:26-31`（企微按字节 2048、其余按字符 4096/4000），其中飞书/钉钉上限**代码自己注明"未验证"**（`renderer.py:81-86`） |

**为什么这么排**：第 1、2 条是"用户真的会漏收/真的点不开"，且都能在不动架构的前提下改掉；第 3 条之后是"表达力/可维护性"问题，
不解决不会立刻出事，但会持续制造"改完不知道影响谁"的成本。

---

## 6. 附：与阶段 2 的边界

以下属于**阶段 2**，本阶段只登记、不设计、不实现：

1. **统一的"渠道能力 + 渲染适配器"**（声明支持 markdown/卡片/图片/按钮、单条上限，由统一渲染器选降级格式）；
2. **业务结果与投递结果分离**——现在 `NotificationMessage` 里 `status`（业务结果，`channel.py:46`）与
   `delivery_status`（投递，`:58`）两个字段并存但仍混用，日志页容易把"发成功了"读成"事情成功了"；
3. **跨渠道降级/回退**（当前只有同渠道 3 次重试 + 告警，没有"这个渠道挂了换那个"）；
4. **统一分片/截断策略**（现在按各渠道上限切，且有两家上限未取证）；
5. **消息就地更新/编辑的统一编排**（现在只有 Telegram 与飞书应用形态支持 `edit_message`，`base.py:194-202` 其余返回不支持）；
6. **模板/文案的可视化编辑**。

**本阶段（阶段 1）已经做完的**：把现状讲清、把 44 个事件与四渠道的实际表达对齐、把"加渠道的成本"量到行号级别。
本报告**不提议**修改任何一行业务代码。

---

## 附：未取证项（明确留白，不作结论）

| # | 项 | 原因 |
|---|---|---|
| 1 | 钉钉 markdown 4000 字符、飞书 4096 字符的真实上限 | 代码注释自述未取到官方条款（`renderer.py:81-86`） |
| 2 | 钉钉的限流业务错误码 | 官方文档为 JS 渲染、取不到正文（`base.py:100`） |
| 3 | 企业微信回调是否在生产真正启用 | 能力自述为"不支持"（`wechat.py:240-242`），但验签实现存在（`callback.py:219`）——两处口径未对齐，实际启用状态未核实 |
| 4 | 各渠道平台侧对图片、@提及、按钮的真实支持范围 | 本仓四个渠道实现里**没有任何图片/@ 代码路径**，平台能力本身未做外部取证 |
| 5 | 第 5 节第 7 条（测试连接参数错位）的实际运行后果 | 代码层可确定传参错位；未调用真实企业微信接口验证失败形态 |
