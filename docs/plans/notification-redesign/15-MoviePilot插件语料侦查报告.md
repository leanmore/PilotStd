# 15 MoviePilot 插件语料侦查报告（P5c-2）

> **性质**：外部开源实现取证（**零 PilotStd 代码改动**）。对象＝**82 个 MoviePilot 插件仓**（用户提供的清单）。
> **证据分级**：**[实现]**＝可运行第三方源码（附 `仓库/文件:行号`）；**[未找到]**＝全语料无证据（不推断）。

**语料**：82 仓浅克隆（`C:\Temp\mp_probe\plugins\`，`--depth 1`，**0 失败**）
　· 主仓参照：[`jxxghp/MoviePilot@43edef14`](https://github.com/jxxghp/MoviePilot)（见 `14-MoviePilot源码侦查报告.md`）
**侦查日期**：2026-10-06

---

## 一、语料级扫描结果（关键词 × 命中文件数）

| # | 焦点 | 关键词 | 命中 | 结论 |
|---|---|---|---|---|
| ① | **企微回调加密** | `msg_signature`/`MsgSignature`/`EncodingAESKey`/`WXBizMsgCrypt`/`echostr` | **1**（且经查为**无关**：插件自身引导逻辑） | **全插件生态无企微回调实现** ⇒ 我方"企微不启用回调"的判断**再次被独立佐证** |
| ② | **钉钉卡片/更新** | `outTrackId`/`interactiveCards`/`UpdateInteractiveCard` | **0** | 插件生态**完全不做**钉钉互动卡片 ⇒ 无第三方实现可抄（与我方 P5a 结论一致） |
| ③ | **飞书 SDK/编辑** | `lark_oapi`/`im.v1.message.patch`/`open_message_id` | 2（**`ui-beam-9/larkmessager`**） | ✅ **找到真实编辑实现**（见 §2.1） |
| ④ | **Telegram 交互** | `callback_query`/`reply_markup`/`editMessageText`/`answerCallbackQuery` | 12（**`clone-fan/signal`** 最完整） | ✅ 交互范式与我方同构（见 §2.2） |
| ⑤ | **交互框架（短码回调）** | `encode_action`/`callback_data`/`inline_keyboard` | 45（`DDSRem-Dev/p115strmhelper` 最完整） | ✅ **同样以 64 字节为限**（见 §2.3） |
| ⑥ | 通知聚合/限流 | `throttle`/`rate_limit`/`aggregate` | 228 | 泛命中，未逐个人工复核（本条**不作为结论依据**） |

---

## 二、三项决定性发现

### 2.1 飞书**确实可以编辑消息**，端点为 `PATCH /open-apis/im/v1/messages/{message_id}`

`ui-beam-9/MoviePilot-Plugins/plugins.v2/larkmessager/client.py`（**[实现]**）：

```python
# :435-478（原文摘录）
#  消息编辑（对标 Feishu.edit_message）
def edit_message(self, ...):
    ...
    url = f"{API_BASE}/im/v1/messages/{message_id}"
    resp = requests.patch(...)
```
另见同文件：`/im/v1/messages/{message_id}/reply`（`:159`）、卡片**流式更新**
（`STREAM_CARD_TITLE_ELEMENT_ID`/`STREAM_CARD_BODY_ELEMENT_ID`、`update_multi: True`，`:31-32,462,795,870`）。

**对我方的意义**：
1. **飞书编辑能力成立**，且**不需要**官方 SDK——`PATCH + tenant_access_token` 即可（与我方现有 `urllib` 直连风格一致）；
2. 前提是**企业级/自建应用形态**（能拿到 `message_id`）⇒ 与我方设计文档"换成企业级形态后前提成立"的判断**一致**；
3. 当前我方走 **webhook 群机器人** ⇒ 拿不到 `message_id` ⇒ **不可编辑**（现状判断不变）；
4. ⇒ 飞书编辑属"**换成自建应用后可得**"，仍是 Q2 裁决里的"**后做**"项，但现在**有了可照抄的落地形态**。

### 2.2 Telegram 交互范式：**专用回调轮询 + 原地编辑 + 过期清理**（`clone-fan/signal`）

`clone-fan/MoviePilot-Plugins/plugins.v3/signal/presentation/tg_console_callback.py`（**[实现]**）：
- **独立回调轮询**：`poll_tg_console_updates()`（`:31`）；
- **动作键 + 会话态**：`_tg_console_start_background_action(action_key, label, user_id)`（`:80`）、
  `_fusion_update_action_worker(action_id, ...)`（`:239`）；
- **原地编辑与防抖**：文件头注释明确"`editMessageText`，若不标记就会在采集结束时让卡片连续闪两下；
  **按线程隔离**"（`:21`）——与我在 P5b 里"按钮只挂最后一段（避免重复交互面）"的思路同源；
- **过期/清理**：`_schedule_fusion_status_expiry(...)`（`:397`）、`cleanup()`（`:404`）
  ⇒ **与我方 410 `action_expired` 的降级语义一致**（旧交互面失效必须优雅收场）。

**对我方的意义**：我方阶段 3 的"回调 → 动作 → 状态回写 → 过期降级"链路与该独立实现**同构**，
说明该设计不是我方臆造，而是这类"长驻交互面"的通行做法。

### 2.3 交互回调的**短码 + 注册表**编码，且**同以 64 字节为限**

`DDSRem-Dev/MoviePilot-Plugins/plugins.v2/p115strmhelper/interactive/framework/`（**[实现]**）：
- `callbacks.py::encode_action(session, action, max_length: int = 64)` ⇒ **同样以 64 字节为硬限**；
- 编码形态：`c:<命令短码>` + `v:<值>` + `w:<视图短码>`，短码由
  `registry.py` 的 `command_registry`/`view_registry` 注册（**服务端映射**）；
- `schemas.py`：`BaseSession(session_id, plugin_id, default_view, last_active, history, view, business, message)`
  ＋ `BaseMessage.original_message_id` ＋ `update_message_context(event_data)`（从事件里取 `original_message_id`）；
- `manager.py`：`_generate_session_id(event_data)`、`get_or_create(event_data, plugin_id)`、
  `set_timeout(minutes)`、`end()`、`cleanup()`。

**对我方的意义（直接相关）**：
1. **64 字节硬限是生态共识**（第三方独立实现同样设限）⇒ 我方 P5b 的防御与其一致；
2. 当载荷可能超限时，生态通行做法是「**短码 + 服务端注册表**」——正是你曾建议的"短 ID + 服务端映射"方案；
   我方当前 `action:<log_id>:<user_id>`（十几字节）无需引入短码，但**若将来要携带更多上下文**，
   应改用短码注册表而非塞长载荷；
3. 会话态 + `last_active` + `set_timeout` ⇒ 与我方"token → 日志行"的定位方式**互补**：
   我方无会话概念（一次性动作），故**不需要**引入会话框架（保持最小实现）。

---

## 三、对 PilotStd 的可执行结论

| 渠道/主题 | 语料证据 | 结论与建议 |
|---|---|---|
| **企微** | ① 命中 1（无关）；主仓亦无回调实现 | 维持"**不启用回调**"；若将来启用，按 `14-...报告 §2.1` 的 XML+SHA1+AES 三件套**单独立批** |
| **钉钉** | ② **0 命中** | 钉钉互动卡片与限流策略**无第三方实现可借鉴** ⇒ 若要做，须自行按官方文档落地并**自定限流策略**（已登记） |
| **飞书** | ③ `larkmessager`：`PATCH /im/v1/messages/{message_id}` | **编辑可行**（自建应用形态）：可直接照抄"PATCH + tenant_access_token"；仍是"后做"项，但**技术路径已实证** |
| **Telegram** | ④ `signal` 控制台：轮询+编辑+过期 | 我方阶段 3 实现与之同构 ⇒ **无需改设计**；可在未来补"交互面过期清理"（我方已有 410 降级） |
| **交互编码** | ⑤ `p115strmhelper`：64 字节 + 短码注册表 | 我方 `action:token` **合规且更简**；**超限时改短码注册表**（登记为演进方向，不在本批） |

> **口径纪律**：以上均为第三方**实现证据**；实施前仍应对目标渠道官方文档做一次字段级确认。
> 本报告**不产生代码改动**，行动项为"阶段 3 的渠道取舍与演进方向"。
