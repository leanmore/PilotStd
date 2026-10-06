# 14 MoviePilot 源码侦查（P5c）

> **性质**：外部开源实现取证（**零 PilotStd 代码改动**）。目的：绕开"官方文档正文 JS 渲染取不到"的死结，
> 用**真实落地实现**回答 `01-channel-capabilities.md` §五 的缺口。
> **证据分级**：**[实现]**＝可运行的第三方源码（附 `文件:行号`）；**[全文]**＝官方正文；**[未找到]**＝无证据（不推断）。

**侦查对象**：[`jxxghp/MoviePilot`](https://github.com/jxxghp/MoviePilot) · 分支 `v3`
**快照**：`43edef140f52539b2fa9c7b91e678d8fbff04919`（2026-10-06，浅克隆，2185 个 `.py`）
**侦查日期**：2026-10-06

---

## 一、结论速览（逐条对应你指定的三个重点）

| # | 重点 | 结论 | 证据 |
|---|---|---|---|
| **1** | **企微**：回调接口真实 JSON/签名结构 | ✅ **已闭合（[实现]）**：`VerifyURL(msg_signature, timestamp, nonce, echostr)`＝**SHA1(token,timestamp,nonce,echostr)** ＋ **AES 解密**（`EncodingAESKey`、`sReceiveId`），XML 信封含 `<MsgSignature>` | `app/adapters/external/wechat.py:239-254`、`:81`、`:111` |
| **2** | **钉钉**：失败/限流重试与休眠参数 | ⚠️ **无可借鉴物**：钉钉模块**没有**任何重试/退避/429 处理（单次 `POST`，`timeout=30`）；退避只存在于通用 HTTP 层且**仅针对代理 TLS1.2 / 幂等方法** | `app/modules/dingtalk/dingtalk.py:28,111,120`；`app/adapters/network/http.py:171,587,597,1329` |
| **2b** | 钉钉**加签口径**（顺带交叉验证我方实现） | ✅ **与我方实现逐字一致**：`HMAC-SHA256(secret, "<timestamp>\\n<secret>") → base64`，查询串 `timestamp`+`sign` | `app/modules/dingtalk/dingtalk.py:37-51` ↔ 我方 `callback.py::verify_callback` 的 dingtalk 分支 |
| **3** | **飞书**：是否实现消息编辑（patch）／如何拿 `message_id` | ⚠️ **不编辑**：全仓**未找到** `im.v1.message.patch` 调用；但**回调事件里确实带 `open_message_id`**（企业级/SDK 形态）⇒ **"编辑的前提"在该形态下成立**，只是 MoviePilot 没做 | 事件处理 `app/modules/feishu/feishu.py:385-406`（`card.action.trigger`）；`message_id` 提取 `:175,398` |
| **3b** | 飞书**交互回调结构体**（顺带取证） | ✅ **[实现]**：`card.action.trigger` 事件 → `operator{open_id,user_id}` + `action{value,name}` + `context{open_message_id,open_chat_id}`；**动作仅管理员可执行**（与我方 `authorize_action` 同构） | `app/modules/feishu/feishu.py:385-406`、`:545-557` |

---

## 二、逐项明细

### 2.1 企微回调（**缺口 1/2 的技术答案**）

`app/adapters/external/wechat.py` 的原文要点（截取）：

```python
# :246-254
def VerifyURL(self, sMsgSignature, sTimeStamp, sNonce, sEchoStr):
    ret, signature = sha1.getSHA1(self.m_sToken, sTimeStamp, sNonce, sEchoStr)
    ...
    ret, sReplyEchoStr = pc.decrypt(sEchoStr, self.m_sReceiveId)
```
```xml
<!-- :81-111 的信封模板（原文，含其拼写 "msg_signaturet"） -->
<MsgSignature><![CDATA[%(msg_signaturet)s]]></MsgSignature>
```

**结论（可直接用于阶段 3 的企微接入）**：
1. **回调启用**需要三件套：**Token**（SHA1 签名）、**EncodingAESKey**（AES 解密）、**CorpID/ReceiveId**（解密校验）；
2. **URL 验证**：对 `timestamp`/`nonce`/`echostr` 做 SHA1 拼签 ⇒ 解出 `echostr` 明文即通过；
3. **消息体**：XML 信封 + `MsgSignature`（不是 JSON，也不是纯 header 签名）⇒ 与我方 `callback.py` 的
   "header 签名"模式**不同**，属"XML 信封 + AES"形态，接入时需新增解析与解密分支；
4. 这与 `01-channel-capabilities.md` §3.2 的判断一致：**我方现状"企微连回调也不启用"是保守但正确的**——
   启用它需要新建"XML + AES + SHA1"整条链路，而不是给现有 JSON 签名模式加一个渠道。

### 2.2 钉钉：**限流策略无从借鉴**（如实结论）

- `app/modules/dingtalk/dingtalk.py`：有 `build_request_url()`（加签）与 `send_msg()`（单次 POST ✅），
  **没有** `sleep`/`retry`/`for attempt in range(...)`/`429` 处理；
- `app/adapters/network/http.py` 的重试只覆盖：**代理 TLS1.2 回退**（`_can_retry_proxy_tls12` ✅）
  与**幂等方法**（`_REQUESTS_RETRY_IDEMPOTENT_METHODS = ("GET","HEAD","OPTIONS")` ✅）；
- ⇒ **PilotStd 不能从 MoviePilot 复制"钉钉限流策略"**：该项目的钉钉是"发出去就算完"的定位，
  没有面向 `errcode=88/限流` 的退避设计。**我方需自行定义**（登记为待办）。

**顺带的交叉验证（有价值）**：MoviePilot 的钉钉加签
`string_to_sign = f"{timestamp}\n{self._secret}"` + `HMAC-SHA256` + `base64`
**与我方 `verify_callback` 的 dingtalk 分支逐字同构** ⇒ 我方钉钉验签实现获得**独立第二来源**佐证。

### 2.3 飞书：能拿 `message_id`、但未做编辑（`patch`）

- **回调事件**（`card.action.trigger`）的真实字段：

| 字段 | 取值来源 | 我方对应 |
|---|---|---|
| `operator.open_id` / `operator.user_id` | `event.operator` | `envelope.actor_ref`（**不可信**，仅线索） |
| `action.value` / `action.name` | `event.action` | 我方 `action.value.{action,token}` 的解析口径 |
| `context.open_message_id` / `open_chat_id` | `event.context` | 我方目前未使用（无编辑能力） |

- **`open_message_id` 的存在**意味着：在企业级/长连接形态下，**飞书消息编辑的前提成立**
  （`im.v1.message.patch` 需要 `message_id`）——这**印证**了我方设计文档的判断
  （"消息编辑的前提在换成企业级形态后成立"），而**当前 webhook 机器人形态拿不到 message_id** ⇒ 不可编辑。
- **MoviePilot 未实现编辑**：全仓检索 `im.v1.message.patch` / `update_message` **无命中** ⇒
  即便具备 SDK 与 `message_id`，它也没有做"原地更新状态"这件事。⇒ 我方若要飞书编辑，
  需按官方 SDK 自行落地（**当前不做**，与 Q2 裁决一致：飞书属"后做"项）。
- **动作鉴权同构**：`_should_reject_admin_command(...)` ⇒ **仅管理员可执行动作**
  （`app/modules/feishu/feishu.py:549-557`），与我方 `authorize_action` 的角色收敛**同一设计取向**。

---

## 三、对 PilotStd 的可执行结论（不改代码，只给结论）

| 渠道 | 侦查后可下的结论 | 建议动作 |
|---|---|---|
| **企微** | 回调＝**XML 信封 + SHA1 签名 + AES 解密**（三件套：Token/EncodingAESKey/ReceiveId） | 阶段 3 若要企微交互 ⇒ **单独立批**（新链路，非"加一个渠道"）；现状"不启用回调"保持 |
| **钉钉** | 限流策略**无第三方可抄**；加签口径已被第二来源证实 | 限流策略自行定义（登记待办）；验签实现**维持不变**（已获佐证） |
| **飞书** | 企业级形态**可**编辑（回调带 `open_message_id`），但第三方亦未实现；动作**仅管理员** | 维持"后做"；需要时按 SDK 落地 `im.v1.message.patch` |

> **口径纪律**：以上均为**第三方实现证据（[实现]）**，不等于官方规范；实施前仍应对**目标渠道官方文档**
> 做一次确认（尤其企微的 AES 参数与飞书 patch 的字段），但已足以支撑"是否值得立批"的决策。
