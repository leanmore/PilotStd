# PilotStd vs MoviePilot 差距分析报告

> 对照对象：MoviePilot 后端 **v2.15.6**（commit `1528176b`）+ 前端 v3.1.1（commit `e999aa0`）
> 对照本体：PilotStd 工作区 `D:\PilotStd`（HEAD `f96b211e`，通知改造处于**阶段 2.5a 已完成**）
> 证据来源：「01-moviepilot-notification-report.md」的全部结论均为源码实测（含 `路径:行号`）
> **本报告只给差距与判断，不给改造方案**——方案按决策者要求另开一轮。

---

## 摘要（给决策者读）

**核心发现 7 条**

1. **两者不是"同一件事的两种实现"，而是两个不同的问题。** MoviePilot 解决的是"**消息要发得出去、用户的地址要能找到**"；PilotStd 解决的是"**每条业务事件都有确定文案、确定归属、可被订阅与审计**"。MoviePilot 的"加事件成本 ≈ 0"不是来自更好的抽象，而是来自**它放弃了事件身份**——它的 9 个类别粗到不构成"事件"，因此没有可登记、可漏登记的东西。
2. **决策者上一轮的核心质疑，答案是"层次不同"。** MoviePilot 的 **9 个 `NotificationType`** 对应 PilotStd 的 **7 个 `notify_event`**（通知视角的聚合层），而 MoviePilot 的 **116 个 `post_message` 调用点**才与 PilotStd 的 **41 个业务事件**同粒度。41 不是"太多"，而是**比 MoviePilot 更细一层的存在**；MoviePilot 不需要这一层，因为**它连类别都不让用户订阅**。
3. **"加事件成本高"的真因不是 41 这个数字，而是"同一份清单存在 4 份且互不校验"。** 后端 `events.py`、e2e 测试的 `EVENTS`、G-045 门禁、前端 `NotificationConfig.vue` 各一份。实测：**前端那一份已经漂移了 6 个事件**（35 vs 41），且漂移的正是最新加的 6 个（P0 + 安全批）。
4. **MoviePilot 有 4 样 PilotStd 完全没有的东西**：① 渠道动态发现与方法扇出；② 真渠道能力矩阵（12 能力 × 12 渠道 + 4 个量化上限）；③ 消息原地编辑的完整链路（4 渠道可用）；④ 免打扰时段队列。其中 ②③ 与 PilotStd 阶段 3 的计划重合，MoviePilot 提供了一份可参照的实现**连同它的腐化教训**。
5. **MoviePilot 有 3 处明显腐化，正好证明 PilotStd 的门禁不是过度设计**：① 能力声明与实际投递漂移（QQ 声明内联按钮但从不传 `buttons`）；② 两个渠道（`Web`/`WebAgent`）有矩阵条目却无模块，指定它们会**静默无投递**；③ 死代码（`should_use_fallback`、旧 `NotificationSwitch` 模型）。
6. **i18n 的反差最具说服力**：MoviePilot 有 826×2 的翻译量与三层查找（结构化键 + **中文原文查表** + **中文正则模板** 250 条），但**通知发送链路 0 处接线**——推出去的通知仍是写死中文。PilotStd 用三层键 + G-045 强制 **41/41 事件三语齐备**。前者证明"事后按中文原文补 i18n"可行，但成本高且**覆盖不到真正的痛点**。
7. **"不做模板机制"的代价是明确的、且已在 PilotStd 的现状里可量化**：失去"用户自行裁剪正文"与"改文案不发版"两项能力；但 PilotStd 用 `blocks`（结构化正文）+ 41 个构建器承载了 MoviePilot 用模板解决的"字段组合"问题。详见 §五。

**关键数字对照**

| 维度 | MoviePilot v2.15.6 | PilotStd（现状） |
|---|---|---|
| 用户可见的"事件"数 | 9 个类别 | **41 个业务事件** + 7 个通知事件层 |
| 发送调用点 | 116 处 / 14 文件 | 41 个构建器（`manager._EVENT_BUILDERS`）+ 41 事件灰测 |
| 渠道 | 12 枚举 / **10 有投递** | **4**（wechat/dingtalk/feishu/telegram）+ 桌面 Toast + Web |
| 渠道能力矩阵 | ✅ 12×12（含 4 处死/漂移声明） | ❌ 仅 `CHANNEL_KEY_WHITELIST`（消息 ID 键闭集） |
| 消息编辑 | ✅ 4 渠道（Telegram/Feishu/Slack/Discord） | ⏳ 阶段 3 计划；`channel_message_ids` + `delivery_status="edited"` 已预留 |
| 消息落库 | `message` 表 11 列；**无**聚合/身份/任务列 | `notification_log` **26 列**（含 message_id/correlation_id/delivery_status/ack_status/task_id/notify_event/content_type/task_context/task_kind/channel_message_ids） |
| 聚合 | ❌ 无通知聚合；3 处"沾边"（时段队列 / 60s 半成去重 / 2 处业务手写） | ✅ 服务端窗口聚合（5s 首延 / 300s 上限 / 50 条批量）+ 桌面聚合与熔断 + 桌面去重 |
| 投递健康监控 | ❌ 无 | ✅ 连败 + 窗口失败率双触发（**源于真实事故**） |
| 安全告警专用通道 | ❌ 无（凭证告警走普通链路，会流向新地址） | ✅ `security_notifier`（三条独立理由，见 §三） |
| i18n 覆盖通知 | ❌ 0 处接线（3 语言包 826/826/85） | ✅ 41/41 事件三键齐备（en 714 / zh_CN 718 / zh_TW 635 叶子） |
| 事件清单份数与校验 | 无清单、无校验（→ 已产生 6 处漂移） | **4 份清单**（`events.py` / e2e `EVENTS` / G-045 / 前端），后端三份有门禁，**前端那份已漂移 6 个** |
| 门禁数量（通知相关） | 0 | **5**（G-044 / G-045 / G-046 / G-047 + Schema 一致性） |
| 用户订阅能力 | ❌ 连类别都不能订阅（只能填地址） | ✅ 事件级规则表 `notification.rules.<event>` |

---

## 〇、阅读前提

| 项 | 说明 |
|---|---|
| 判断口径 | 每条给 **适用 / 不适用 / 需改造** 之一 + **依据**。依据一律写成"因为 MoviePilot 是 X 场景、PilotStd 是 Y 场景" |
| "不适用"的两种含义 | ① 业务差异（如多用户路由、WebPush 广播）→ 不需要；② **反面教材**（MoviePilot 的做法在 PilotStd 会退步）→ 不可取。文中会区分 |
| 证据边界 | MoviePilot 侧全部为源码实测；PilotStd 侧为当前工作区实测（含运行 `audit_notification_coverage.py` 的真实输出） |
| 未做的事 | 没有评价"哪边工程质量更高"；没有给实施顺序、工作量或批次划分 |

---

## 一、逐条判断（按 01 报告的 A–H 组）

### A 组：事件模型

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| A1 | **动态发现渠道 + 方法扇出**：`ModuleManager` 扫包，`run_module("post_message")` 调所有实现者（`app/core/module.py:29,118`；`app/chain/__init__.py:470`） | **不适用**（业务形态差异） | MoviePilot 是"渠道会持续增加"的开放生态（12 渠道、插件也能发消息），故必须免登记；PilotStd 是**封闭的 4 渠道**，且 `CHANNEL_KEY_WHITELIST` 是**闭集**并有契约测试锁定（`pilotstd/core/notification/channel.py:28`、`_policy.py:10` 的 `_CHANNEL_CLASSES` 元组）。扫描式发现在 PilotStd 会**削弱**闭集性，收益为零 |
| A2 | **放弃事件身份**：只有 9 个类别，正文现场手写 | **不适用**（反面教材） | MoviePilot 能放弃，是因为**它的用户不能按事件订阅**（见 G 组）；PilotStd 的用户可见性**就绑在事件上**——41 事件同时是订阅粒度（`notification.rules.<event>`）、i18n 层级键、e2e 契约与 G-045 校验单元。放弃即同时丢掉这四样 |
| A3 | **无任何事件清单断言**（实测 0 命中） | **不适用**（反面教材） | MoviePilot 因此产生的漂移是**可观测的**：QQ 能力声明与实现不一致、前端清单与后端不一致、两个渠道有声明无实现。PilotStd 的 `assert len(EVENTS) == 41`（`tests/test_notification_e2e.py:739`）正是为阻止这类漂移而存在 |
| A4 | 内部事件总线（`EventType` 31 + `ChainEventType` 19）供插件挂勾子 | **不适用** | PilotStd 的扩展点是 PyQt 桌面端与 Docker API，**没有第三方插件生态**；且 MoviePilot 的事件总线**不产生通知**（01 报告 §一 Q2），与 PilotStd "事件 → 文案 → 投递"的因果链不是一回事 |
| A5 | 事件粒度 = 9 类别（粗） | **需改造**（判断在 §四） | 层次不同，不能直接对照；结论是**保留 41** |

### B 组：消息模型

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| B1 | `buttons` 二维数组承载交互（`app/schemas/message.py:247`） | **适用**（形态已具备） | PilotStd 已有 `actions: list[ActionSpec]`（`channel.py:85`）+ `callback_data` 长度约束契约（`v1\|message_id\|action\|arg`，`channel.py:86-89`），比 MoviePilot 的裸 dict 更强类型；可借鉴的是其"按钮行/列上限"与渠道降级（见 C2） |
| B2 | **消息编辑链路**：发送拿 `MessageResponse` → 存 `message_id`/`chat_id` → 用 `original_message_id` 原地改写（`app/chain/__init__.py:1953,1903`；`app/helper/interaction.py:180-227`） | **适用** | 这正是 PilotStd 阶段 3 的目标能力，且**前置件已就位**：`channel_message_ids` 闭集（"键缺席 = 该渠道不可编辑"，`channel.py:91-94`）、`delivery_status` 已预留 `edited` 取值（`channel.py:54-56`）。MoviePilot 的"先发后改 + 失败回退新发"顺序是可照抄的链路形态 |
| B3 | 附件 = `image`/`voice_path`/`file_path`/`file_name` 4 个标量 + 历史表 `note` JSON | **不适用** | MoviePilot 要发海报图、语音（Agent 语音消息）、种子文件；PilotStd 的 `AttachmentSpec` 目前**只承载不发送**（`channel.py:90`），且无任何语音/文件业务需求证据。引入会扩大渠道适配面而收益不明 |
| B4 | Jinja2 模板 + DB 存储 + 前端 Ace 编辑器 | **不适用**（决策者已定，动机见 §五） | 见 §五专项 |
| B5 | `MessageResponse.metadata: dict`（渠道私有上下文，如飞书流式卡片 `card_id`/`element_id`/`sequence`） | **需改造** | 同一需求 PilotStd 用 `dict[str, str]` **闭集白名单**表达，比 MoviePilot 的任意 dict 更严——这点应保持。但 MoviePilot 的 `metadata` 揭示了**一个必须承认的事实**：飞书这类渠道的编辑能力依赖渠道私有状态（`app/schemas/message.py:24, 566-580` WebAgent 条目同理），因此"编辑"不可能只靠一个消息 ID 完成 |

### C 组：渠道与交互

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| C1 | **真渠道能力矩阵**：`ChannelCapability` 12 项 + `ChannelCapabilities`（含 4 个量化上限）+ 12 渠道全登记（`app/schemas/message.py:372,404,424`） | **适用** | PilotStd 现在只有"消息 ID 键闭集"，**没有任何"这个渠道能做什么"的声明**。4 渠道差异（钉钉/企微群机器人不支持按钮、飞书支持卡片编辑）目前只能靠**调用点各自判断**——这正是 MoviePilot 用矩阵统一掉的东西 |
| C2 | 量化上限：`max_buttons_per_row`/`max_button_rows`/`max_button_text_length`/`max_message_length`（`app/schemas/message.py:404-417`） | **适用** | 与 PilotStd 的 G-010（单文件规模）取向一致：把"渠道差异"表达为**数据**而非分支代码。MoviePilot 的 Telegram `3500`（为 MarkdownV2 转义留余量）是实测得出的具体数值，可作参照 |
| C3 | 矩阵**无"声明 vs 实现"校验** | **需改造** | PilotStd 若要引入矩阵，必须同时引入校验，否则会复现 MoviePilot 的 QQ 漂移（声明 `INLINE_BUTTONS` 于 `app/schemas/message.py:587`，而模块从不传 `buttons`：`app/modules/qqbot/__init__.py:372-379`）。PilotStd 已有同款手法的先例可循（`CHANNEL_KEY_WHITELIST` 由契约用例锁定） |
| C4 | 只有 4 个渠道真能原地编辑（Telegram/Feishu/Slack/Discord） | **适用** | 这是**同一物理事实**：PilotStd 的 4 渠道里，钉钉/企微群机器人同样不能编辑已发消息。PilotStd 的"键缺席 = 不可编辑"约定与 MoviePilot 的 `supports_editing()` 是同构表达——说明这个降级模型是对的 |
| C5 | **每渠道各写一份管理员校验**（8 份重复 + 8 个 `*_ADMINS` 配置项，MoviePilot 仓 `tests/test_message_channel_permissions.py:19-399`） | **不适用** | PilotStd **是单用户**（`NotificationManager` 由门面硬编码 `user_id=1` 构造，见 `security_notifier.py` 模块说明第 3 条）。多用户权限在 PilotStd 无落点 |
| C6 | 新增渠道 = 建模块目录（自动发现） | **不适用** | PilotStd 的渠道是显式注册：`_CHANNEL_CLASSES`（`_policy.py:10`）+ `channels/` 实现类 + `CHANNEL_KEY_WHITELIST` + 契约测试。它**故意**要"加渠道必须同时改 4 处"，因为渠道是安全边界（凭证、限流、内容转义） |

### D 组：进度与过程通知

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| D1 | 任务进度**不进通知链路**：`ProgressHelper` 用进程内 TTLCache，由 Web SSE 拉取（`app/helper/progress.py:18,86`；`app/api/endpoints/system.py:770-793`） | **不适用** | MoviePilot 走 SSE 是**因为它没有任务实体**（无 Task 表、无 task_id），只能"当前在跑什么就推什么"。PilotStd 恰恰**有 Task 实体**且已把 `task_id` 定义为"**进度型通知的原地更新锚点**"（`channel.py:62`），`content_type` 值域里也已有 `task_progress`（`channel.py:66`）。照抄 MoviePilot 等于放弃已落地的能力 |
| D2 | **Agent 流式：首块新发 → 后续原地编辑同一条**（0.3s 刷新，`app/agent/callback/__init__.py:22-43,146,502`） | **适用** | 这是 MoviePilot 唯一真正的"过程型"推送，且它的形态（先 `send_direct_message` 拿 ID，再反复 `edit_message`）与 PilotStd 阶段 3 需要的"进度原地更新"**完全同构**；其"接近渠道长度上限就冻结当前消息、另发一条续写"的处理也是可复用的模式 |
| D3 | 刷新间隔 0.3 秒 | **不适用** | MoviePilot 是 **LLM token 流**（生成即推）；PilotStd 是低频业务通知，且**有 Telegram 限流事故记录**（`delivery_health.py:1-19`：599 条因限流失败）。0.3s 级的编辑频率在 PilotStd 会直接撞上已知风险 |
| D4 | 无"任务进度为什么不做"的任何说明 | **不适用**（无从借鉴） | 01 报告 Q17 已标注为"未找到"，属证据缺口而非设计参考 |

### E 组：聚合与去重

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| E1 | **免打扰时段队列**：不在时段内则入队、后台线程补发（`app/helper/message.py:602,690,757`） | **适用**（PilotStd 已有同构实现） | PilotStd 的 `manager.py` 自述"静音时段暂存队列表定时补发"（`manager.py:2-4`），语义一致。可借鉴的是 MoviePilot 把"起止时间窗"做成**用户可配的多段列表**（`_parse_schedule` 支持多段与跨零点，`app/helper/message.py:631-708`） |
| E2 | 系统/插件 Web 消息 **60 秒去重**（key 含"当前分钟"） | **不适用**（半成品） | 键里塞了 `time.strftime("%Y-%m", ...)` 的分钟粒度（`app/helper/message.py:799-815`）→ **跨分钟即失效**，且只作用于 Web SSE、不影响渠道投递。PilotStd 桌面链路已有独立的 `_check_dedup`（`notification_aggregator.py` 模块说明），更严格 |
| E3 | 业务级"聚合"= 两处手写实现：整理批次刮削等批次关闭再发（`app/chain/transfer.py:1509-1612`）、失败重试 300s debounce（`:806,846`） | **不适用** | 它们是**业务事件**的聚合，不是通知的聚合；且每个场景手写一遍。PilotStd 用**通用聚合器**（`aggregate_buffer.py`，5s 首延 / 300s 上限 / 50 条批量）覆盖同一需求——这是 PilotStd 更强的一处，应保留（见 §三） |
| E4 | **无渠道限流退避**：`429` 处理只在站点/网盘（`app/helper/torrent.py:184`、`u115.py:353`、`alipan.py:273`），Telegram 只按 3s/6s 盲重试且不读 `retry_after`（`app/utils/common.py:11`；`app/modules/telegram/telegram.py:1388`） | **不适用**（反面教材） | PilotStd **已经为这个缺口付过代价**：`delivery_health.py:1-19` 记录 32 天窗口 1,148 条通知中 629 条失败（54.8%），其中 **599 条是 Telegram 限流**，且连续 7 天无人知晓。MoviePilot 至今没有等价机制 |

### F 组：i18n

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| F1 | **三层查找**：结构化键 + **中文原文精确查表**（295 条）+ **中文正则模板**（250 条，`app/helper/locale.py:116,141,214,271`） | **不适用** | 后两层是**为"代码里已经写死 295 处中文"做的补丁**。PilotStd 的中文**本来就在语言包里**（`pilotstd/i18n/*.json`），代码里没有待翻译的存量字符串——补丁对象不存在。正则方案还带来运行期编译与缓存成本（`_load_pattern_matchers` 每次缺键都要遍历 250 条） |
| F2 | 平行 `*_i18n` 字段，**中文字段保留**（`locale.py:12-13` 明文约定） | **不适用** | 这是"不敢改旧字段"的妥协：每个 API 响应同时下发两种语言。PilotStd 是"键即真相"，无旧中文字段需要保留 |
| F3 | 语言协商：query → `x-moviepilot-locale` → `Accept-Language`（q 值排序）→ 默认；别名表 `zh-hant→zh-TW`（`app/helper/locale.py:34-85`） | **需改造** | PilotStd 是桌面应用，语言来自 UI 设置而非 HTTP 头，故协商部分不适用；但**别名表**（`zh`/`zh-hans`/`zh-hant`/`en` 之类的归一）与 `SUPPORTED_LOCALES` 闭集声明值得借鉴——PilotStd 的 `pilotstd/i18n` 已有 ContextVar 与 `SUPPORTED_LANGUAGES`，与 MoviePilot 的 `ContextVar` 方案同构（`locale.py:97-113`），说明这条路线已被两个项目独立验证 |
| F4 | **通知链路 0 处接线**（实测 28 个 `LocaleHelper.` 调用点，`app/chain/**`、`app/helper/message.py`、`app/modules/**` 全为 0） | **不适用**（反面教材） | 它证明"事后补 i18n"的成本结构：投入 826×2 个叶子 + 250 条正则，**痛点（推给用户的通知）仍然没覆盖**。PilotStd 的 G-045 把"构建器用到的 t() 键三语齐备"设为**阻断项**（实测 41/41），从机制上避免了同样的结果 |
| F5 | 前端有**叶子键路径**对齐与孤儿键门禁（前端仓 `tests/config/locale-orphans.spec.ts`） | **适用** | PilotStd 已有 `scripts/check_i18n_key_count.py`，其 v1.1.0 版本说明明确记录了"v1.0.x 只比顶层，看不见 `nav.archive` 这类叶子漂移——实测三语 142/143/143 时仍报 PASS"的教训——与 MoviePilot 增加叶子路径检查是**同一个修复**，可互相印证 |

### G 组：用户配置

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| G1 | 两层配置：渠道 `switchs`（该渠道接收哪些类别）+ 类别 → 范围 `action`（`app/schemas/system.py:83-108`） | **需改造** | PilotStd 的策略表是 `notification.rules.<event> → [渠道]`（**事件 → 渠道**方向，`docker/api/notification.py:161`），比 MoviePilot 的"渠道 → 9 类别"**更细一维**（事件级 vs 类别级）。因此不需要引入 MoviePilot 的新维度；可借鉴的只是"同一份订阅关系能从两个方向查看"的配置 UI 表达 |
| G2 | 9 类 × 4 档范围（`user`/`admin`/`user,admin`/`all`） | **不适用** | 纯多用户概念；PilotStd 单用户（同 C5） |
| G3 | 4 个 Jinja2 模板的 Ace 编辑器 | **不适用**（见 §五） | 见 §五专项 |
| G4 | 免打扰时段 UI（起止时间输入） | **适用**（PilotStd 已有后端语义） | PilotStd 有静音时段与暂存队列（`manager.py:2-4`）与配置层（`_policy.py` 负责策略表读写），MoviePilot 的时间窗 UI（`AccountSettingNotification.vue:609-640`）是可参照的交互形态 |
| G5 | **通知中心**：按 全部/系统/媒体 三类记录清理时间点，分页读 `message` 表（`app/api/endpoints/message.py:172-189`；`app/schemas/message.py:10-33`） | **适用** | PilotStd 已有 `notification_log`（26 列）+ 已读/未读计数（`_manager_ops`：`mark_logs_read`/`get_unread_count`/`cleanup_logs`）+ 前端 30s 轮询（`useNotification.ts`）。MoviePilot 的"**按范围分别记录清理时间**"是一个 PilotStd 尚无的细节：PilotStd 的 `cleanup_logs` 是按时间整体清理，没有"系统类清了、媒体类保留"的语义 |
| G6 | 用户只能填地址，**不能订阅** | **不适用**（且是 PilotStd 的镜像优势） | PilotStd 的订阅粒度是**事件级且全局可配**（41 条规则），MoviePilot 的粒度是**类别级且用户不可配** |

### H 组：安全与权限

| # | MoviePilot 的做法 | 判断 | 依据 |
|---|---|---|---|
| H1 | **没有安全告警专用通道**；凭证类告警与普通通知同路径 | **不适用**（反面教材 → 必须保留 PilotStd 现状） | PilotStd 的 `security_notifier.py` 给出三条**具体**理由（模块 docstring 第 1-3 条）：① 聚合缓冲会把告警推迟到窗口到期，**此时新凭证已落库，告警流向新地址**；② 静音时段会把它写进 `notification_queue` 延后；③ `send_event` 首行判 `notification.enabled`（默认 False 直接返回）且 manager 由门面硬编码 `user_id=1`，会发给错误用户。MoviePilot 的 `post_message` **三条全中**（聚合/时段/门控分别对应 `app/helper/message.py:710`、`:690`、`app/chain/__init__.py:1646`） |
| H2 | "定向消息跳过渠道类别开关"（`if not message.userid and message.mtype:`，`app/modules/__init__.py:238`） | **不适用** | 这是**隐式**绕过：任何带 `userid` 的消息都无视渠道配置，而它并非为安全设计（01 报告 Q27 已确认无 `force`/`bypass` 语义字段）。PilotStd 的对应能力是**显式**的（`PILOTSTD_SECURITY_NOTIFY_ENABLED` 环境变量，且刻意不放在配置文件里——`security_notifier.py:37` 附近说明了理由：能写配置的端点等于给攻击者一个关告警的把手） |
| H3 | 多用户路由（`targets.<channel>_userid` + `action` 拆分 + 管理员回滚） | **不适用** | PilotStd 单用户（同 C5）。MoviePilot 的 `targets` 机制本身是它"用户表当地址簿"的产物（`app/db/models/user.py:33`） |
| H4 | 每渠道 `*_ADMINS` 拦截命令型回调（8 份实现） | **不适用** | 同上；且 MoviePilot 的实现是**同一逻辑抄 8 遍**（`tests/test_message_channel_permissions.py` 用 8 个近乎相同的用例覆盖），属反向清单 |
| H5 | `immediately=True` 跳过免打扰时段 | **需改造** | 需求真实（安全/凭证类通知必须能穿透时段限制），但 MoviePilot 的触发条件是错的（`immediately=True if dispatch_message.userid else False`，`app/chain/__init__.py:1720`——"有人点名"就立即发）。PilotStd 已有更正确的绑定：`security_notifier` **整体**绕过聚合与时段，而不是给任意消息开一个"立即"开关 |

---

## 二、反向清单：不值得照抄的部分

### 2.1 过度工程（在 MoviePilot 的规模下未必过度，在 PilotStd 的规模下是）

| # | 项 | 为什么在 PilotStd 是过度工程 |
|---|---|---|
| 1 | **Jinja2 模板全套**：渲染器 + 上下文构建器（~50 个变量）+ DB 存储 + 前端 Ace 编辑器 + 出厂默认模板写在 Alembic 迁移里（`app/helper/message.py:30,538`；`database/versions/89d24811e894_2_1_4.py`） | 只服务 **4 个** `ContentType`。PilotStd 的对应需求（41 个事件的文案）已由 41 个构建器 + 三层 i18n 键覆盖，且它是 3 语言 × 718 键规模——再叠一层"用户可编辑模板"会引入"模板串与 i18n 键双重真相"，与 G-045/G-047 直接冲突 |
| 2 | **三层 i18n 查找**（结构键 + 中文原文表 + 250 条中文正则） | 补丁层；PilotStd 无"代码里写死的中文"这一补丁对象（G-047 正在守住这一点） |
| 3 | **12 渠道 × 12 能力** 的矩阵，其中 4 处是死声明或漂移 | 矩阵本身适用（C1），但**规模**不适配：PilotStd 4 渠道 × 需要的 5~6 项能力足够；照抄 12 项会引入 `MENU_COMMANDS`（PilotStd 无命令菜单体系）、`AUDIO_OUTPUT`（无语音需求）等无落点项 |
| 4 | 60 秒系统消息去重（键含"当前分钟"） | 半成品；跨分钟失效，且只覆盖 Web SSE。PilotStd 的桌面链路已有 `_check_dedup` |

### 2.2 历史包袱（MoviePilot 自己在还的债）

| # | 项 | 证据 |
|---|---|---|
| 5 | **两代渠道开关模型并存**：旧 `NotificationSwitch`（每渠道一个布尔，仅列 8 个渠道、缺 Discord/Web/WebAgent）与现役 `NotificationSwitchConf`（类别 → 范围） | `app/schemas/message.py:272-295`，全库**无任何使用**（实测）→ 纯死代码 |
| 6 | **枚举线值用中文/品牌名**：`MessageChannel.Wechat = "微信"`、`NotificationType.Download = "资源下载"` | `app/schemas/types.py:305-357`。后果直接可见：前端必须**再抄一遍同样的中文串**才能比对（`src/api/constants.ts:241-278`），这是"清单有 4 份"的根源之一 |
| 7 | **渠道私有消息 ID 形态泄进通用模型**：`original_message_id: Union[str, int]` | `app/schemas/message.py:251`（Slack 是 `ts` 字符串、Telegram 是整数、Discord 是 snowflake） |
| 8 | **`EVENT_TYPE_NAMES` 与 `EventType` 双份清单**，靠 `.get(..., event_type.name)` 降级 | `app/schemas/types.py:129`；`app/api/endpoints/workflow.py:91` |
| 9 | **8 份管理员校验 + 8 个 `*_ADMINS` 配置项** | MoviePilot 仓 `tests/test_message_channel_permissions.py:19-399`（8 个渠道各一条用例，逻辑几乎相同） |
| 10 | **两处手写业务聚合**（整理批次刮削 / 失败重试 debounce 300s） | `app/chain/transfer.py:806,1509-1612` |

### 2.3 单用户/低频场景下不值得（业务差异）

| # | 项 | 为什么不需要 |
|---|---|---|
| 11 | 多用户路由全家桶：`targets` 字典、`action` 四档、管理员回滚、`user.settings` 地址簿、每渠道 `*_userid` | PilotStd 单用户；引入后所有通知都要多一层"发给谁"的判定，而答案永远是"当前用户" |
| 12 | WebPush（向"全局浏览器订阅集合"广播 + `WEBPUSH_USERNAME` 白名单） | PilotStd 是 PyQt 桌面端，已有桌面 Toast 与 Web 前端；浏览器推送没有落点 |
| 13 | `Web`/`WebAgent` 这类"有矩阵条目但无投递模块"的伪渠道 | 它们的实际投递靠 3 处硬编码特例（`app/chain/__init__.py:1926`、`app/helper/interaction.py:201`、`app/api/endpoints/message.py:140`）。这种"声明在矩阵里、实现在特例里"的模式不该复制 |
| 14 | 116 处手写 `title`/`text` | MoviePilot 能承受是因为它**不要求任何归属**；在 PilotStd 抄它等于同时放弃 G-045 覆盖度、G-044 术语、i18n 事件键与事件级订阅 |

---

## 三、保留清单：PilotStd 应保留的自研部分

| # | 项 | 位置 | 为什么保留（MoviePilot 的对照） |
|---|---|---|---|
| 1 | **安全告警独立投递路径** | `pilotstd/core/notification/security_notifier.py`（278 行） | MoviePilot **没有**等价物。PilotStd 的三条理由都是具体的、可验证的（聚合推迟→凭证已落库→告警流到新地址；静音时段延后；门控默认 False + 硬编码 user_id=1）。且它把紧急开关放在**环境变量**而非配置里（`ENV_NOTIFY_ENABLED`），理由写明了：能写配置的端点等于给攻击者关告警的把手 |
| 2 | **服务端聚合器** | `pilotstd/core/notification/aggregate_buffer.py`（485 行；`DEFAULT_WINDOW_SECONDS=5.0` / `MAX_WINDOW_SECONDS=300.0` / `DEFAULT_BATCH_SIZE=50`，`:45-47`） | MoviePilot **没有通知聚合**（只有 2 处业务侧手写聚合）。PilotStd 的聚合器还带明确的**职责边界声明**（"三套聚合/去重机制之一，禁止越界"，模块 docstring）——这种边界声明本身是 MoviePilot 缺失的治理手段 |
| 3 | **桌面聚合与熔断暂停** | `pilotstd/core/notification_aggregator.py`（主题分组 + 30 秒内 3 条警告/错误→暂停 5 分钟 + 暂停持久化） | MoviePilot 无桌面端，无等价物。这是"通知风暴"的第一道闸；与聚合器**独立链路、不共享状态**（两边 docstring 都写明） |
| 4 | **投递健康度监控** | `pilotstd/core/notification/delivery_health.py`（连败 + 窗口失败率**双触发**；告警去重；**不回环**；`REASON_CONSECUTIVE`/`REASON_RATE`） | MoviePilot **完全没有**：无健康度、无失败率统计、无 429 专门处理。而 PilotStd 的这个模块是**真实事故驱动**的（32 天 1,148 条中 629 条失败、599 条 TG 限流、连续 7 天无人知晓）。它还有一条 MoviePilot 绝不会有的设计：**告警自身的投递结果不计入健康度**（避免告警失败触发新告警） |
| 5 | **术语表门禁 G-044** | `scripts/check_terminology.py` + `docs/governance/glossary.json` | MoviePilot 没有"术语"概念，只有一张展示用的 `EVENT_TYPE_NAMES`。PilotStd 的 G-044 管的是"`notification.*` 作用域文案不得命中禁用词组 + 术语三语值严格一致"——MoviePilot 的 826×2 译文里没有任何一致性校验 |
| 6 | **覆盖度基线 G-045** | `scripts/audit_notification_coverage.py`（4 维度） | MoviePilot 的等价物是**零**。实测 PilotStd：`i18n 41/41 ｜ e2e 41/41 ｜ 安全事件审计 4/4 ｜ 术语 1/41（跟踪项）`，退出码 0；并且它**主动声明未覆盖项**（`desktop_toast` 与"EVENTS 的 level/module/aggregation/builder_keys 未校验"）——"PASS 不掩盖盲区"是 MoviePilot 完全没有的自觉 |
| 7 | **链路审计 G-046（零基线）** | `scripts/audit_notification_chain.py` + `audit_notification_chain_scan.py` | MoviePilot 无对应物；PilotStd 用它拦"空文本风险 / 缺空值守卫 / 静默吞错"——这三类正是 MoviePilot `post_message` 路径上真实存在的风险（空标题正文、`_send` 只记日志） |
| 8 | **Python 硬编码中文基线 G-047** | `scripts/check_i18n_hardcoded_python.py` + `i18n_hardcoded_python_baseline.json` | MoviePilot 走的正是"先写死中文、事后按原文翻译"的路，代价是 250 条正则。G-047 从源头阻止 PilotStd 走同一条路 |
| 9 | **层级翻译键 + `t()` fail-loud（无跨语言回退）** | `pilotstd/i18n/__init__.py:123-130`；键规范 `notification.{category}.{event}.{field}` | 与 MoviePilot 相反：它缺键就**返回键本身**（测试可捕获），而 MoviePilot 会**回退到 zh-CN 或原文**（`locale.py:134-138`）——回退会把"漏翻"变成静默可接受。PilotStd 的 fail-loud + G-045 组合是更严的一侧 |
| 10 | **阶段开关 `NOTIFY_REDESIGN_STAGE`** | `pilotstd/core/notification/stage.py`（`HIGHEST_STABLE_STAGE`、非法值回退+告警、不抛异常） | MoviePilot 无版本化演进机制：它的 12 渠道/9 类别/4 模板是"直接改"。PilotStd 的分阶段 + 环境变量一键回滚（不改代码、不迁移数据）是这次改造能安全推进的前提 |
| 11 | **双 SSOT（`task_kind` / `task_type`）+ 单向翻译** | `channel.py:67-73`；`mapping.py`（`TASK_KIND_TO_TASK_TYPE` + `task_kind_to_task_type()`，**无反向函数**） | MoviePilot 没有"任务"概念，故无对照。PilotStd 的做法（明确"两个不同轴"、只做单向翻译、用 `test_no_reverse_function` 锁死不许出现反向函数）避免了"两个词表互相污染" |
| 12 | **`CHANNEL_KEY_WHITELIST` 闭集 + 契约用例** | `channel.py:18-28`；`tests/test_notification_stage1c_fields.py` | MoviePilot 的对应物是一个**任意 dict**（`MessageResponse.metadata`）。PilotStd 用"键必须取自元组 / 值恒为 str / 未投递就键缺席（不是 None）"三条契约把"消息 ID"钉死——这正好补上 MoviePilot 的 `Union[str,int]` 缺口 |
| 13 | **`_json_codec` 空槽约定** | `_json_codec.py`（`dumps` 把 None/`{}`/`[]` 统一写 `""`；读回一律 `{}`，**显式声明不可区分**） | SQLite 无原生 JSON 类型的现实约束下的显式契约。MoviePilot 用 SQLAlchemy `JSON` 列规避了这个问题，但代价是"哪些字段是 JSON"隐含在模型里，没有读写契约文档 |
| 14 | **41 个业务事件本身** | `events.py:81-123` | 见 §四——它不是"太多"，而是 PilotStd 独有的一层 |
| 15 | **桌面 Toast 通道** | `desktop_formatter.py` + `core/notification_aggregator.py` | MoviePilot 是纯服务端 + Web/移动端，无桌面通道；这是 PilotStd 的形态优势（本地即时反馈不需要走渠道限流） |

---

## 四、核心问题回答：MoviePilot 的事件粒度与 PilotStd 的 41 事件是否同一层次？

### 4.1 层次对照（结论：**不同层次，差一级**）

| 层次 | MoviePilot | PilotStd | 是否同层 |
|---|---|---|---|
| 用户可配/可订阅的最小单位 | 9 个 `NotificationType`（粗类别） | **41 个业务事件** | ❌ 不同层 |
| 通知视角的聚合层 | **无此层**（类别是最粗的层） | **7 个 `notify_event`**（`mapping.NOTIFY_EVENTS`） | ❌ MoviePilot 缺此层 |
| 实际"发一条消息"的位置 | **116 处** `post_message` 调用（14 文件） | **41 个构建器**（`manager._EVENT_BUILDERS`） | ✅ **同层** |
| 内部事件（供扩展方挂勾子） | 31 `EventType` + 19 `ChainEventType` | 无等价物（无插件生态） | ❌ PilotStd 不需要 |
| 内容形态 | 4 个 `ContentType`（仅模板用） | 6 个 `content_type`（`channel.py:66`） | ⚠️ 形似神不同（前者只管模板，后者管渲染形态） |

**读法**：MoviePilot 的 `NotificationType`（9）应与 PilotStd 的 `NOTIFY_EVENTS`（7）对比，而**不是**与 41 对比；与 41 同层的是它的 116 个调用点。

### 4.2 结论：**保留 41，不收敛**（收敛的是"清单份数"，不是"事件数"）

**理由一：MoviePilot 之所以只需要 9 个，是因为它的用户不能订阅。**
它的路由是"类别 → 范围（all/user/admin）"（`app/chain/__init__.py:1646-1710`），用户侧只能填渠道地址（`UserAddEditDialog.vue:95-103`、`UserProfileView.vue:499-598`）——**没有"我要/不要哪类"的开关**。也就是说，"9 个类别"是**运维配置粒度**，不是**用户订阅粒度**。
PilotStd 的订阅粒度是事件级：`notification.rules.<event> → [渠道]`（`docker/api/notification.py:161`），41 条规则一一对应。**把 41 收敛成 9，等于把订阅粒度整体降一级**——用户会失去"归档通知关掉、安全告警留着"这类表达能力。

**理由二：41 同时是四样东西的载体，收敛会连带失去。**
同一个 key 在 PilotStd 里同时是：① 订阅规则名；② i18n 层级键的中间段（`notification.{category}.{event}.{field}`）；③ e2e 契约条目 + `trigger_file`（G-045 校验其**物理存在**）；④ `_EVENT_BUILDERS` 的注册键。MoviePilot 这四样一样都没有（无订阅、无 i18n 接线、无 e2e 契约、构建器不注册）。**"41 太多"的感觉来自它要维护四份一致性，而不是来自事件数本身。**

**理由三：真正该收敛的是"清单份数"——实测已经出问题。**
`ALL_EVENT_KEYS`（41）在仓库里被**四份清单**表达：

| 清单 | 位置 | 是否有门禁 | 实测状态 |
|---|---|---|---|
| 后端 SSOT | `pilotstd/core/notification/events.py:81-123` | — | 41 |
| e2e 契约 | `tests/test_notification_e2e.py:260,739`（`assert len(EVENTS) == 41`） | 断言（阻断） | 41 |
| G-045 门禁 | `scripts/audit_notification_coverage.py`（AST 解析 `ALL_EVENTS`，非手抄） | ✅ 已接入 CI | 41/41 |
| **前端订阅 UI** | `web/src/components/NotificationConfig.vue:58`（`const EVENTS = [...]`） | ❌ **无** | **35** |

实测差异（脚本比对，非目测）：
```
后端 ALL_EVENTS: 41  前端 EVENTS: 35
后端有 / 前端缺 (6): favorite_abandoned_summary, notification_credential_changed,
                     notification_delivery_failed, security_login_failed,
                     security_password_changed, security_token_refreshed
前端有 / 后端无: 无
```
**缺的正好是最后加的 6 个**（2 个 P0 + 4 个安全批）。这正是"加事件成本高"的**真实病灶**：不是 41 这个数字，而是**第 4 份清单没有任何门禁**，且它漂移的方式（只缺新的、不缺旧的）说明**每次加事件都会再漂一次**。
（`docs/governance/notification_coverage.md:224,228` 也记录了同源问题：`desktop_toast` 至今不登记，因为"登记会必然即红……需一次性改 6 个文件"。）

**理由四：MoviePilot 的"低成本"来自去掉约束，不是来自更好的抽象。**
它的成本账单在同一份代码里可见：无清单 → 前端与后端必然分叉（它靠"9 个类别极少变"侥幸）；能力矩阵无校验 → QQ 漂移；两代模型并存 → `NotificationSwitch` 死代码；事件名与展示名双份 → 靠 `.get` 降级。**这些正是 PilotStd 用 5 个门禁换掉的东西**——把 41 收敛成 9 只能减少"要同步的条目数"，不能消除"多份清单"这个结构问题。

### 4.3 附带回答："41 是否足够/适用"（决策者的另一半质疑）

**结论：业务域内足够；且 MoviePilot 比 PilotStd 多出的类别，PilotStd 大多不需要。**

| MoviePilot 的 9 类别 | PilotStd 是否有对应业务 | 判断依据 |
|---|---|---|
| 资源下载 / 整理入库 / 订阅 / 站点 / 手动处理 / 插件 / 其它 | ✅ 有（`download_*`/`archive_*`/`normalize_*`/`announcement_*`/`favorite_*`/`validity_*`/`quota_exhausted`/`worker_error` 等 41 事件覆盖 6 个 `notify_event` 类别） | `events.py:81-123`；`mapping.EVENT_MAPPINGS` 41 键 |
| **媒体服务器** | ❌ 无 | 该类别服务 Emby/Jellyfin/Plex 的播放事件（`app/modules/jellyfin/jellyfin.py:625` 的 `PlaybackStart`）；PilotStd 无媒体服务器模块 |
| **智能体** | ❌ 无 | 该类别服务 LLM Agent（`app/agent/**`、`app/modules/feishu/feishu.py:1540` 的 `NotificationType.Agent`）；PilotStd 无 Agent 子系统 |
| **站点**（细分） | ⚠️ 部分 | MoviePilot 的站点消息=新站内信/低分享率（`app/chain/site.py:86-104`）；PilotStd 的对应物是公告解析与收藏订阅（`announcement_*`/`favorite_*`），业务不同但同属"站点侧" |

反向看也一样：MoviePilot 的 9 类别里**没有** PilotStd 的"标准有效性/到期"域（`validity_*`/`standard_expired`/`expire_standard_moved`/`replacement_not_found`）。**两边业务域不同，41 vs 9 的对照本身不构成"谁更合理"的证据**——这也解释了为什么"照 MoviePilot 的路线改造"无法通过"减少事件数"来降低加事件成本。

---

## 五、专项：MoviePilot 为什么做模板机制，PilotStd 不做会失去什么

**（按决策者要求：理解动机，不引入机制）**

**MoviePilot 为什么做模板（动机，含标注）**
代码事实是：它的模板只服务 **4 个** `ContentType`，但每个 ctype 对应**一类高频通知**（入库成功、开始下载、订阅添加、订阅完成——`app/schemas/types.py:326-338`），而出厂模板里塞满了可选字段（`{% if seeders %}`、`{% if volume_factor %}`、`{% if description %}`……见 `database/versions/89d24811e894_2_1_4.py:22-58`）。据此**推断**（依据即上面两条代码事实）其动机有二：① 这些通知的字段组合长、且**不同用户对"要多详细"的偏好差异大**（有人要种子做种数/促销/描述，有人只想要一行标题）；② 文案改动需求频繁，而模板存在 `systemconfig` 表里、有现成配置 UI 与 DB 表可挂（`SystemConfigKey.NotificationTemplates`，`app/schemas/types.py:273`），**改文案不用发版**。换言之：模板是为了把"正文组装权"从开发者手里**交给用户**。**注意**：这些推断在仓库里**找不到设计文档或 ADR 佐证**（01 报告 Q9 已列为"未找到"）。

**PilotStd 不做会失去什么（四项，逐条）**

1. **失去"用户自行裁剪正文"的能力。** PilotStd 的正文由 41 个构建器决定；用户若觉得某条通知太啰嗦（例如聚合摘要里的耗时/条数明细），唯一的表达方式是**关掉整个事件**，不能"要这条但少一点"。MoviePilot 的对应能力就是 `{% if %}` 条件段。
2. **失去"改文案不发版"。** PilotStd 的文案在 `pilotstd/i18n/{zh_CN,zh_TW,en}.json`（718/635/714 个叶子）里，改一个字就是改代码、过门禁、发版；MoviePilot 是改 DB 记录。**并且这项失去在 PilotStd 更严重**：G-047（Python 硬编码中文基线）与 G-045（三语齐备）让"临时改文案"这条路更贵。
3. **失去"同一事件、不同偏好"的表达。** MoviePilot 的模板是**全局一份**（用户各自覆盖自己的），PilotStd 连"全局一份可调"都没有——正文是代码常量。
4. **失去"正文格式的用户侧自愈"能力。** 若某渠道（如 Telegram MarkdownV2）因转义导致排版问题，MovieMilot 用户可以自己改模板规避；PilotStd 只能等改代码。

**同时必须说清"不做并没有失去什么"（否则会高估代价）**
MoviePilot 用模板解决的核心问题是"**从业务对象拼出一段正文**"。PilotStd 已经用另外两样东西承载了同一件事：① `blocks: list[NotificationBlock]`——结构化的正文载体（`TextBlock`/`KeyValueBlock`/`StatusChangeBlock`/`ListBlock`），渲染器按渠道渲染（`renderer.py` 的模板方法模式）；② 41 个构建器 + `_format_utils`。也就是说，**"拼正文"这件事 PilotStd 有解，只是"拼法"写在代码里而非模板里**。因此不引入模板失去的是**用户可编辑性**与**免发版**，而不是"表达力"。

**另一项代价（MoviePilot 已付、PilotStd 若引入也会付）**
模板机制在 MoviePilot 里产生了**双份真相**：默认模板在 Alembic 迁移（`database/versions/89d24811e894_2_1_4.py`），用户覆盖在 DB；模板变量名（`season_episode`/`file_count`…）与 `TemplateContextBuilder` 的产出**靠约定对齐，无任何校验**——Jinja2 对未定义变量默认渲染为空串，即**变量名写错不会报错，只会静默少一行**。PilotStd 的门禁体系（G-045/G-046/G-047）会把这种静默降级视为缺陷。

---

## 附：可复算命令

> `$W` = MoviePilot 后端 worktree（v2.15.6），`$F` = 前端 clone，`$P` = `D:\PilotStd`。

```powershell
$W = "C:\Temp\mp-v2"; $F = "C:\Temp\mp-frontend"; $P = "D:\PilotStd"

# A) MoviePilot 侧（01 报告的可复算命令已含全部脚本，此处只列本报告用到的）
python C:\Temp\mp_probe\probe.py "$W"                 # 9 类别 / 12 渠道 / 116 调用点 / 10 模块
Get-ChildItem "$W\app\modules" -Recurse -Filter __init__.py | Select-String '_channel\s*='
Get-ChildItem "$W\app" -Recurse -Filter *.py | Select-String 'LocaleHelper\.'   # 通知链路 0 命中

# B) PilotStd 侧
cd $P
python -c "import sys;sys.path.insert(0,'.');from pilotstd.core.notification.events import ALL_EVENT_KEYS as k;print(len(k))"   # 41
python scripts\audit_notification_coverage.py            # i18n 41/41 | e2e 41/41 | 安全审计 4/4 | 术语 1/41；exit 0
python scripts\check_i18n_key_count.py                   # 前端 locale 键对齐（叶子路径）

# C) 「前端清单已漂移 6 个」的复算（本报告 §四 的实测）
python -c @"
import re, pathlib, sys
sys.path.insert(0, r'$P')
from pilotstd.core.notification.events import ALL_EVENT_KEYS
s = pathlib.Path(r'$P/web/src/components/NotificationConfig.vue').read_text(encoding='utf-8')
fe = re.findall(r\"'([a-z_]+)'\", re.search(r'const EVENTS = \[(.*?)\n\]', s, re.S).group(1))
print('后端', len(ALL_EVENT_KEYS), '前端', len(fe))
print('后端有前端缺:', sorted(set(ALL_EVENT_KEYS) - set(fe)))
"@

# D) PilotStd 通知相关事实
Get-Content "$P\pilotstd\core\notification\delivery_health.py" -TotalCount 19    # 629/1148 = 54.8% 事故
Get-Content "$P\pilotstd\core\notification\security_notifier.py" -TotalCount 20 # 三条独立理由
Get-Content "$P\pilotstd\core\notification\aggregate_buffer.py" -TotalCount 40  # 职责边界 + 三套机制
Get-Content "$P\pilotstd\core\notification_aggregator.py" -TotalCount 18        # 桌面聚合 + 熔断暂停
Select-String -Path "$P\docs\governance\notification_coverage.md" -Pattern 'L-22' -Context 0,8
```

**本报告未做的事**：未给出改造方案、批次划分、工作量估算或实施顺序；未修改 PilotStd 任何代码/配置/既有文档；未连接任何生产环境。
