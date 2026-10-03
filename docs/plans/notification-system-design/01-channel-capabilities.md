# 四渠道双向形态能力调查

> **性质**：只读调查（任务 A）。**不写方案、不做实施设计。**
> **目的**：确认四个渠道"支持交互的形态"下**实际能做到什么**，为"阶段 3 双向改造范围"提供事实基础。
> **访问日期**：2026-10-03（所有外部 URL 均为当日访问）
> **证据等级**（后文逐项标注）：
> - **[全文]** 官方文档正文已取得
> - **[URL]** 官方文档标题/URL 已确认，**正文为 JS 渲染未取到**（不推断）
> - **[代码]** MoviePilot / PilotStd 源码实测
> - **[裁定]** 决策者本轮更正（2026-10-03）
> - **[未找到]** 无证据（不推断）
>
> 关联：[00-framework.md](00-framework.md)（方案框架）、[02-framework-update.md](02-framework-update.md)（框架更新）

---

## 摘要（决策者读）

1. **四个渠道都有支持交互的形态**，决策者更正成立：钉钉=企业内部应用机器人、企微=企业自建应用、飞书=企业自建应用、Telegram=Bot API。
2. **当前 PilotStd 的 4 个渠道全部是"低端形态"**（3 个 Webhook 群机器人 + 1 个单向 Bot），没有一个具备回调能力 —— 所以原判断"做不到"应改为"**当前部署形态做不到，升级后都能做到**"。
3. **证据强度不均**：Telegram 官方限流与能力**[全文]**最完整；飞书自建应用的编辑与 message_id 有**[代码]**实证；**钉钉互动卡片 [全文] 已取**（按钮=privateData、回调=callbackRouteKey、更新锚点=outTrackId）；**企微交互卡片与回调只有 [URL]，正文未取到**，是本次最大证据缺口。
4. **"返回 message_id"是交互的前提，但四家形态差异很大**：Telegram 与飞书**[代码]**明确返回；钉钉返回的是 `processQueryKey`（已读查询 key）与自生成的 `outTrackId`（**未见 message_id**）；企微 MP 实现只返回 bool（**[未找到]** 返回 ID 的证据）。
5. **结论（供阶段 3 定义用）**：**消息编辑的前置条件在"换成企业级形态"后并非全部成立**——飞书/TG 可直接编辑，钉钉需走"卡片更新"路径（本文档已取证锚点、未取证更新接口），企微**证据缺口未闭合**。
6. **限流只有 Telegram 有官方数字**（单聊 1 msg/s、群 20 msg/min、广播 ~30 msg/s、超限 429）；钉钉/企微/飞书的频率限制**均未取到**。
7. **本节新增：PilotStd 的 Telegram 渠道已实现 429 退避**（`pilotstd/core/notification/channels/telegram.py:32`），这是相对 MoviePilot 的一处**已有优势**，不要重复建设。

---

## 一、调查方法

| 项 | 说明 |
|---|---|
| 优先顺序 | ① MoviePilot 代码（已 clone 的 v2.15.6 worktree，`C:\Temp\mp-v2`）→ ② 官方文档 → ③ 未找到则如实标注 |
| MoviePilot 覆盖度 | **有**：`telegram`（Bot API 全双向）、`feishu`（自建应用，含 `edit_message`）、`wechat`（**企业自建应用**：corpid/agentid/secret + 菜单 + 媒体）｜**无**：`dingtalk`（MP 根本没有钉钉模块） |
| 官方文档可达性 | 钉钉 `open.dingtalk.com` 的 `.md` 路径返回**纯文本正文**（可取）；`core.telegram.org` 可取；**企微 `developer.work.weixin.qq.com` 与飞书 `open.feishu.cn` 为 JS 渲染，两次 fetch 均只得到导航壳** |
| 不推断原则 | 未取到的能力项一律写 **[URL]** 或 **[未找到]**，并在 §五 汇总为证据缺口清单 |

**MoviePilot 的模块形态对照（代码实测）**

| MP 模块 | 文件 | 形态判定依据 |
|---|---|---|
| `wechat` | `app/modules/wechat/wechat.py:54` | `WECHAT_CORPID` + `WECHAT_APP_SECRET` + `WECHAT_APP_ID`(=agentid) → **企业微信自建应用**（非群机器人） |
| `feishu` | `app/modules/feishu/feishu.py:71-91` | `FEISHU_APP_ID`/`APP_SECRET`/`VERIFICATION_TOKEN`/`ENCRYPT_KEY` → **自建应用（含回调验签与解密凭证）** |
| `telegram` | `app/modules/telegram/__init__.py:161-260` | `callback_query` 处理 + `answer_callback_query` + `edit_message` → **Bot API 全双向** |
| （无 dingtalk） | — | `Get-ChildItem app\modules -Directory` 无 `ding` 匹配 → **MP 无钉钉实现** |

---

## 二、四渠道 × 七维度对照表（主表）

> 表内 `[n]` 对应 §四 的证据条目编号。

| 维度 | 钉钉 | 企微 | 飞书 | Telegram |
|---|---|---|---|---|
| **1. 形态名称** | 企业内部应用 + 机器人（**互动卡片**）`[D1]` | **企业自建应用** `[W1][裁定]` | **企业自建应用** `[F1]` | **Bot API**（BotFather）`[T1]` |
| **2. 所需凭证（字段名）** | `cardTemplateId`（模板ID，需先在开放平台创建）、`robotCode` **或** `chatBotId`（二选一）、`outTrackId`（开发者生成）、`x-acs-dingtalk-access-token` `[D1]` | `WECHAT_CORPID` / `WECHAT_APP_SECRET` / `WECHAT_APP_ID`(=agentid) `[W1]` | `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_VERIFICATION_TOKEN` / `FEISHU_ENCRYPT_KEY` `[F1]` | `bot_token` + `chat_id` `[T1]`；webhook 可选"密钥路径"`[T2]` |
| **3. 审批门槛** | 需应用具备"chat 相关接口的管理权限"；**企业内部应用支持、第三方个人应用暂不支持** `[D1]` | **[URL]**（管理后台建应用；具体审批项未取到）`[裁定]` | **[未找到]** | **无**（自助创建）`[T1]` |
| **4a. 交互卡片（按钮）** | **支持**：`privateData` 文档原文"指定用户可见的按钮列表" `[D1]` | **[URL]**（决策者裁定支持）`[裁定]` | **支持** `[裁定]`＋MP 自建应用含卡片与按钮渲染 `[F2]` | **支持**：inline keyboard（`InlineKeyboardButton`/`reply_markup`）`[T3]` |
| **4b. 按钮回调** | **支持**：`callbackRouteKey` 文档原文"可控制卡片回调时的路由Key，用于指定特定的 **callbackUrl**"；缺省用企业默认回调地址 `[D1]` | **[URL]**（回调配置文档，正文未取到）`[W2]` | **支持（有条件）**：凭证含 `VERIFICATION_TOKEN`+`ENCRYPT_KEY`（回调验签/解密所需）`[F1]`；回调接口文档 **[URL]** `[F3]` | **支持**：`callback_query` handler + `answer_callback_query` `[T4]` |
| **4c. 消息编辑（状态变更）** | **有条件**：`outTrackId` 是"唯一标示卡片的外部编码…钉钉帮助开发者对 **TrackId** 进行记录"→ **更新锚点可得**；**更新接口本文档未取证** `[D1]` | **[未找到]**（MP 未实现；官方正文未取到） | **支持**：MP `feishu/__init__.py:170 edit_message` + `feishu.py:1778 edit_message(message_id, …)` `[F4]` | **支持**：`editMessageText`（MP `__edit_message`，`telegram.py:1244`）`[T5]` |
| **4d. 消息编辑（动作回执）** | 同 4c | **[未找到]** | **支持**（同一接口）`[F4]` | **支持**（同一接口）`[T5]` |
| **4e. 附件/图片** | **支持**：`cardMediaIdParamMap`（"仅支持开放平台文件存储的 mediaId"）`[D1]` | **支持**：MP `send_image_message`/`_upload_temp_media`/`send_medias_msg` `[W3]` | **支持**（MP 有媒体发送路径）`[F5]` | **支持**：上限 **50 MB**（官方 FAQ "Bots can currently send files … up to 50 MB"）`[T6]` |
| **4f. 返回 message_id** | **未见 message_id**：返回 `processQueryKey`（"后续查看已读列表的查询key"）；`outTrackId` 为**自生成**业务锚点 `[D1]` | **不支持/未返回**：MP `send_msg → Optional[bool]` `[W4]` | **支持**：MP `message_id=result.get("message_id")` `[F6]` | **支持**：MP 多处回传 `message_id` `[T7]` |
| **5. 限流/配额** | **[未找到]**（官方"调用频率限制"页正文未取到）`[D2]` | **[未找到]** | **[未找到]** | **单聊 ≤1 msg/s；群 ≤20 msg/min；广播 ~30 msg/s**（付费可达 1000/s，需 100k Stars + 100k MAU）；**超限 429** `[T8]` |
| **6. 回调接收方式** | **webhook（callbackUrl）**，可经 `callbackRouteKey` 路由 `[D1]` | **webhook** `[URL]`（回调配置文档）`[W2]` | **webhook** `[URL]`（处理卡片回调文档）`[F3]` | **webhook（仅端口 443/80/88/8443，需有效 SSL，不支持重定向）** 或 **长轮询 `getUpdates`（最多 100 条未确认更新）；两者互斥** `[T9]` |

---

## 三、逐渠道详述

### 3.1 钉钉（企业内部应用 + 互动卡片）——**[全文] 证据最完整的一家**

- **发送接口**：`POST /v1.0/im/interactiveCards/send`，Header 需 `x-acs-dingtalk-access-token`。
- **按钮**：由 `privateData`（按 userId 指定"**用户可见的按钮列表**"）与卡片模板共同决定；`cardParamMap`/`cardMediaIdParamMap` 提供文本与媒体参数。
- **回调**：`callbackRouteKey` 决定回调落到哪个 `callbackUrl`（不填走企业默认回调地址）→ **回调形态是 webhook，且可多路由**。
- **更新锚点**：`outTrackId`（开发者生成，"唯一标示卡片的外部编码"，钉钉代记 TrackId）→ 这是"卡片更新"最可能的锚点，但**本文档没有出现"更新卡片"接口**，故 4c/4d 记为**有条件**。
- **返回**：仅 `success` + `result.processQueryKey`（已读列表查询 key）→ **没有 message_id**，与飞书/TG 的模型不同。
- **权限差异**：企业内部应用**支持**，第三方个人应用**暂不支持**（`[D1]` 权限表）。

### 3.2 企微（企业自建应用）——**证据缺口最大的一家**

- **形态与凭证**：MP 代码确证自建应用形态（`corpid` + `appsecret` + `appid`=agentid），且实现 **access_token 获取 → 发送 → 菜单创建/删除 → 媒体上传**。
- **菜单**：`cgi-bin/menu/create?access_token={token}&agentid={agentid}`，payload 含 `button`/`sub_button`（最多 3 个一级 + 每个 5 个二级）`[W5]`。
- **交互卡片与回调**：**仅 [URL]**——官方"回调配置"与"结构体说明"页面正文为 JS 渲染，两次 fetch 均只得到导航壳 → **不推断、标缺口**。
- **消息编辑**：**[未找到]**（MP 无实现、官方正文未取到）。注意：**这不等于不支持**，只是本轮未取证。
- **返回 ID**：MP `send_msg` 返回 `Optional[bool]` → **未见返回消息 ID 的实现**。

### 3.3 飞书（企业自建应用）——**代码实证充分，官方正文缺失**

- **凭证四件套**（`APP_ID`/`APP_SECRET`/`VERIFICATION_TOKEN`/`ENCRYPT_KEY`）表明**回调（验签 + 解密）是设计内能力**。
- **编辑**：`feishu/__init__.py:170 def edit_message(...)` 与 `feishu.py:1778 def edit_message(self, message_id, title=None, text=None, …)` → **以 message_id 为锚的编辑已实现**。
- **返回 ID**：`message_id=result.get("message_id")`。
- **回调接口**：官方"处理卡片回调"文档 URL 已确认，正文未取到。
- **注意**：PilotStd 现状的飞书渠道是 **Webhook 机器人**，与 MP 的自建应用**不是同一形态**（见 §四 现状对照）。

### 3.4 Telegram（Bot API）——**官方限流唯一可取**

- **全双向**：MP 实现含 `callback_query` 分发、`answer_callback_query`、`edit_message`、`message_id` 回传、inline keyboard、force_reply。
- **限流（官方原文）**：
  - 单聊"避免超过 **1 条/秒**"；短突发可能被容忍，但最终会收到 429；
  - 群"**不超过 20 条/分钟**"；
  - 广播"**约 30 条/秒**"，超出即 429；付费广播可提至 1000 条/秒（需 ≥100,000 Stars 且 ≥100,000 MAU）。
- **回调**：webhook（**端口仅 443/80/88/8443**、需有效 SSL、**不支持重定向**、CN 必须匹配域名）或长轮询 `getUpdates`（返回最早 100 条未确认更新；**设置 webhook 后不可用长轮询**）。
- **附件**：单文件上限 50 MB（下载 `getFile` 上限 20 MB）。

---

## 四、与"当前部署形态"的差距（PilotStd 现状）

| 渠道 | PilotStd 现有形态 | 代码证据 | 是否具备回调能力 | 目标形态 |
|---|---|---|---|---|
| `wechat` | **企业微信机器人 Webhook** | `pilotstd/core/notification/channels/wechat.py:2`（docstring）、`:21`（`__init__(webhook_url)`） | **否** | 企业自建应用 |
| `dingtalk` | **钉钉群机器人 Webhook**（支持加签） | `pilotstd/core/notification/channels/dingtalk.py:2`、`:26`（`webhook_url, secret`） | **否** | 企业内部应用 + 互动卡片 |
| `feishu` | **飞书机器人 Webhook** | `pilotstd/core/notification/channels/feishu.py:2`、`:21`（`__init__(webhook_url)`） | **否**（渲染层有 URL 按钮，见 01-现状盘点 §1.3） | 企业自建应用 |
| `telegram` | **Bot API 单向发送**（`bot_token` + `chat_id`），**已实现 429 退避** | `pilotstd/core/notification/channels/telegram.py:2`、`:64`、`:32`（"从 Telegram 的 429 响应文本里解析「建议等待秒数」"） | **形态上支持，实现上单向** | 增加回调与编辑 |

**渠道白名单（闭集）**：`CHANNEL_KEY_WHITELIST = ("wechat", "dingtalk", "feishu", "telegram")`（`pilotstd/core/notification/channel.py:28`）。

**三条对阶段 3 有直接影响的结论**：
1. **"升级形态"是阶段 3 的前置**，不是阶段 3 的内容——四个渠道都要先换形态（凭证模型随之变更）。
2. **Telegram 是唯一"形态已就绪、只差回调实现"的渠道** → 与决策者更正（"所有支持双向的渠道都做，基础先行"）一致：**TG 可先行**。
3. **消息编辑的锚点在四家并不统一**：飞书/TG 用 message_id；钉钉用 `outTrackId`（卡片更新路径未取证）；企微**未找到** → **低频编辑的抽象层必须按渠道分别提供"改写句柄"**，不能假设统一 `message_id`。

---

## 五、证据缺口清单（本轮未取到，不推断）

| # | 缺口 | 已确认的部分 | 建议补齐方式 |
|---|---|---|---|
| 1 | **企微交互卡片（模板卡片）能力** | 官方文档 URL、决策者裁定（支持） | 取官方"模板卡片类型"正文（`developer.work.weixin.qq.com/document/path/101839`） |
| 2 | **企微回调配置细节**（是否需要 Token/EncodingAESKey、事件回调类型） | 官方"回调配置"URL（`path/90930`） | 同上（正文为 JS 渲染） |
| 3 | **企微消息更新能力** | 无 | 同上 |
| 4 | **企微审批门槛** | 无 | 管理后台文档 |
| 5 | **飞书卡片回调请求/响应格式** | 官方 URL（`feishu-cards/handle-card-callbacks`）+ 凭证含验签字段 | 同上 |
| 6 | **钉钉卡片更新接口** | `outTrackId` 锚点已取证 | 钉钉"更新互动卡片"接口文档 |
| 7 | **钉钉/企微/飞书的调用频率限制** | 仅 Telegram 有数字 | 各自"频率限制"文档正文（钉钉 `help.dingtalk.io/zh/open/development/call-frequency-limit` 正文未取到） |
| 8 | **四个企业级形态的完整字段级凭证清单** | 钉钉（正文）、企微/飞书（代码实测） | 官方凭证文档 |

---

## 六、证据条目（URL 均为 2026-10-03 访问）

| 编号 | 证据等级 | 来源 |
|---|---|---|
| `[D1]` | **[全文]** | 钉钉《发送钉钉互动卡片》 <https://open.dingtalk.com/document/robots/send-interactive-dynamic-cards.md> |
| `[D2]` | **[URL]** | 钉钉《调用频率限制》 <https://help.dingtalk.io/zh/open/development/call-frequency-limit>（正文未取到） |
| `[W1]` | **[代码]** | `C:\Temp\mp-v2\app\modules\wechat\wechat.py:54-62,200`（`WECHAT_CORPID`/`WECHAT_APP_SECRET`/`WECHAT_APP_ID`→`agentid`） |
| `[W2]` | **[URL]** | 企微《回调配置》 <https://developer.work.weixin.qq.com/document/path/90930>（正文未取到） |
| `[W3]` | **[代码]** | `wechat.py:217,410,498`（图片/临时素材/媒体消息） |
| `[W4]` | **[代码]** | `wechat.py:253`（`send_msg → Optional[bool]`） |
| `[W5]` | **[代码]** | `wechat.py:46,621,662,692`（`cgi-bin/menu/create`、`button`/`sub_button`） |
| `[F1]` | **[代码]** | `C:\Temp\mp-v2\app\modules\feishu\feishu.py:71-91`（四件套凭证） |
| `[F2]` | **[代码]** | `feishu/__init__.py:170,187`（`edit_message`）＋渲染层卡片 |
| `[F3]` | **[URL]** | 飞书《处理卡片回调》 <https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/handle-card-callbacks>（正文未取到） |
| `[F4]` | **[代码]** | `feishu/__init__.py:170` + `feishu.py:1778` |
| `[F5]` | **[代码]** | `feishu.py:1913,1944`（媒体批量循环） |
| `[F6]` | **[代码]** | `feishu/__init__.py:252-253`（`message_id=result.get("message_id")`） |
| `[T1]` | **[全文]** | Telegram《Bots FAQ》 <https://core.telegram.org/bots/faq>（创建方式、webhook 要求） |
| `[T2]` | **[全文]** | 同上（"secret path in the URL"建议） |
| `[T3]` | **[代码]** | `telegram/telegram.py:19-20,1046-1066`（`InlineKeyboardMarkup`/`InlineKeyboardButton`） |
| `[T4]` | **[代码]** | `telegram/__init__.py:161-260`、`telegram.py:166-212`（回调分发 + `answer_callback_query`） |
| `[T5]` | **[代码]** | `telegram/telegram.py:1244`（`__edit_message`）、`__init__.py:620` |
| `[T6]` | **[全文]** | 《Bots FAQ》"Uploading large files"节（50 MB） |
| `[T7]` | **[代码]** | `telegram/__init__.py:692,767`、`telegram.py:660-699` |
| `[T8]` | **[全文]** | 《Bots FAQ》"Broadcasting to Users"节（1/s、20/min、~30/s、429、付费广播） |
| `[T9]` | **[全文]** | 《Bots FAQ》"Getting Updates"/"Webhooks"节（443/80/88/8443、SSL、不支持重定向、100 条、互斥） |

---

## 附：可复算命令

```powershell
# ── MoviePilot 侧的形态与能力（只读）──
Get-ChildItem "C:\Temp\mp-v2\app\modules" -Directory | Where-Object { $_.Name -match 'ding|wecom|wechat' }
Select-String -Path "C:\Temp\mp-v2\app\modules\wechat\wechat.py" -Pattern 'CORPID|APP_SECRET|AGENTID|menu/create|template_card|callback'
Select-String -Path "C:\Temp\mp-v2\app\modules\feishu\feishu.py" -Pattern 'APP_ID|VERIFICATION_TOKEN|ENCRYPT_KEY|def edit_message'
Select-String -Path "C:\Temp\mp-v2\app\modules\telegram\__init__.py","C:\Temp\mp-v2\app\modules\telegram\telegram.py" -Pattern 'callback_query|edit_message|message_id|reply_markup'
# ── PilotStd 现状形态（只读）──
Get-ChildItem pilotstd\core\notification\channels -File -Filter *.py | Select-String -Pattern 'def __init__|webhook_url|bot_token|corpid'
Select-String -Path pilotstd\core\notification\channel.py -Pattern 'CHANNEL_KEY_WHITELIST'
Select-String -Path pilotstd\core\notification\channels\telegram.py -Pattern '429|retry'
# ── 外部文档（2026-10-03）──
#   钉钉互动卡片（纯文本可取）：https://open.dingtalk.com/document/robots/send-interactive-dynamic-cards.md
#   Telegram Bots FAQ：https://core.telegram.org/bots/faq
#   企微回调配置（JS 渲染）：https://developer.work.weixin.qq.com/document/path/90930
#   钉钉频率限制（JS 渲染）：https://help.dingtalk.io/zh/open/development/call-frequency-limit
#   飞书卡片回调（JS 渲染）：https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/handle-card-callbacks
```

**自检**：外链 5 处（均注明访问日期）；代码引用 14 处（`路径:行号`）；证据缺口 8 项已单列，未对缺口做任何推断。
