# 自定义菜单最小可行设计（A-27）

> 状态：**调研/设计稿，未写代码**（2026-11-08）。只读代码与现有文档；不联网、不建迁移、不改配置。
> 关联：`docs/debt/03-open.md` A-27、`docs/DECISIONS.md` D-05/D-13/D-16/D-59、`docs/architecture/notification-system.md`（索引页）。

## 一、四渠道调研

| 渠道 | 是否已有菜单 | 已有能力（代码证据） | 缺失能力 | 官方文档要点（代码注释/现有取证） |
|---|---|---|---|---|
| **企业微信** | **否** | 自建应用凭据 `corpid/corpsecret/agentid` + `access_token` 缓存（`channels/wechat.py:40-41,109-120`）；回调 GET 验证 + POST 分发（`docker/api/notification_callback.py:67-115`）；XML 验签/解密（`wechat_crypto.py`）；菜单 click 的 `EventKey` 解析（`callback.py:280-317`）；D-59 明确“保留回调基础设施，复用于菜单点击” | `menu/create`/`menu/get`/`menu/delete` 客户端；菜单配置模型；同步触发；菜单 click 的“无 notification_log 目标”处理；`capabilities.supports_callback` 仍为 `False`（`wechat.py:240-242`） | 代码只取证了 `gettoken` 与 `message/send`（`wechat.py:40-41`）；**菜单 API 未在仓库取证**，实现前需按官方文档核对端点/字段。回调只对“企业自建应用”成立（`channel_spec_data.py:91-94` 注释） |
| **飞书** | **否** | 应用形态可发卡片并留存 `message_id`、可 PATCH 编辑（`channels/feishu.py:32-45`）；回调验签 + 卡片动作 `action.value` 解析（`callback.py:301-305`）；`supports_callback=True`（`feishu.py:402-404`） | 菜单创建 API；`application.bot.menu_v6`（或等价菜单事件）解析；菜单配置模型；`supports_edit` 仍为 `False` | 代码注释只覆盖 token / 发消息 / 编辑（`feishu.py:39-46`）；**菜单事件形态未取证**。A-27 备注“3+5 或 5+10，仅单聊” |
| **Telegram** | **否** | `callback_query` 解析（`callback.py:292-296`）；`editMessageText`（`telegram.py:204`）；长轮询/webhook 接收器（`telegram_receiver.py:35-52`）；`supports_callback/edit=True`（`telegram.py:200-201`） | `setMyCommands` / `setChatMenuButton`；命令消息（`/cmd`）处理分支；菜单配置模型 | 代码无 `setMyCommands` 或命令处理；A-27 备注“命令列表”（不是 3+5 的持久菜单） |
| **钉钉** | **否** | 企业级应用凭据 + 互动卡片（`channels/dingtalk.py:37-42`）；回调 `action`/`outTrackId` 解析（`callback.py:297-300`）；`supports_callback=True`（`dingtalk.py:320-321`） | 自定义菜单 API/能力证据；菜单配置模型；菜单 click 的账号归属 | A-27 备注“待补信息”；代码注释未出现菜单 API |

**已被覆盖、不需重做的子项**：

- 回调端点、验签、XML 解密、`EventKey` 解析已由 T-43/D-59 落地（`docker/api/notification_callback.py`、`callback.py`、`wechat_crypto.py`），菜单 click 只能**复用**，不另起一套。
- “只读动作/URL 按钮优先”已由 D-05、D-13 定调；菜单 v1 不做消息编辑、不做状态变更动作。
- 企微 `access_token` 缓存与自建应用发送已由 `wechat.py` 覆盖；菜单客户端复用它，不新增第二套 token 逻辑。
- Telegram 的 `callback_query` 与编辑已覆盖；未来若做命令菜单，只缺 `setMyCommands` 与命令处理，不需要重做回调。

## 二、设计稿

### 1. 目标与范围

**目标**：在 1 个渠道上提供最多 **3 个顶级菜单项**，管理员可配置、可手动同步；先解决“进入常用页面/查看状态”的导航需求。

**范围内**：

- 1 个渠道（建议企业微信）；
- 最多 3 个顶级项，v1 只做 `view`（打开 Web 页面）；
- 配置存储 + 手动同步 + 幂等更新 + 管理员审计；
- 失败可见（状态接口/日志），不静默。

**范围外**：

- 二级菜单（企微 5 个/飞书 5~10 个）——v2；
- `click` 回调动作、状态变更（retry/snooze/mark_done）——v2 且仅只读动作；
- 按用户/角色动态菜单、多租户；
- 自动在每次保存配置时推送菜单；
- 其他三个渠道。

### 2. 渠道选择（第一版做 1 个）

**建议：企业微信（WeCom）第一版。**

理由：

1. 唯一能在 v1 以**真正的持久菜单**（3 个顶级项）落地，和 A-27 的“企微 a（3+5）”形态一致；
2. 自建应用凭据、`access_token` 缓存、回调端点/验签/解密/`EventKey` 解析都已存在，新增面主要是 `menu/create|get|delete` 一个客户端；
3. `view` 类型菜单点击直接打开 Web 页面，**不需要** `notification_log` 记录，能绕开当前回调服务的 token 限制；
4. D-59 已明确把回调基础设施留给“菜单点击”，企微是这条路线最顺的渠道。

**与 D-16 的关系**：D-16 说“先做已取证渠道（TG/钉钉），企微/飞书能力补齐推迟”，针对的是阶段 3 的**消息编辑/回调能力**；本设计 v1 只做**出站菜单创建 + view 导航**，不依赖未取证的编辑/回调，故不构成对 D-16 的推翻。若老板要求严格按 D-16 排序，备选是 Telegram 命令列表（见问题 1）。

**备选**：Telegram 命令列表（`setMyCommands`）实现最小，但它是“输入 `/` 时出现的扁平命令列表”，不是 3 项持久菜单，且需要新增命令处理；作为 fallback。

### 3. 菜单模型（最多 3 项，存 config vs DB）

**建议存 `config.json`，不建 DB 表/迁移。**

建议结构（示意，最终字段名以实现为准）：

```json
{
  "notification": {
    "menus": {
      "wechat": {
        "enabled": true,
        "items": [
          {"id": "task", "label_key": "notification.menu.task", "type": "view", "url": "/task", "order": 1},
          {"id": "logs", "label_key": "notification.menu.logs", "type": "view", "url": "/notification-logs", "order": 2},
          {"id": "settings", "label_key": "notification.menu.settings", "type": "view", "url": "/settings", "order": 3}
        ]
      }
    }
  }
}
```

约束：

- `items` 最多 3 项；`id` 唯一；`order` 1..3 连续；
- `type` v1 闭集 `{view}`；v2 再增 `{click}`，且 click 仅允许只读动作；
- `label_key` 必须是 i18n 键（禁止菜单文案硬编码中文，避免 G-047/G-040）；
- `url` 只接受站内相对路径或 `http(s)` 绝对地址；禁止 `javascript:`/`data:`；相对路径以 `notification.web_base_url` 拼绝对地址；
- 不存任何密钥；渠道凭据仍走既有 `user_credentials`。

**为什么不是 DB**：

- 菜单是**渠道级**配置，不是用户级；没有多用户维度；
- `config.json` 已有 `web_base_url`、渠道开关等，天然同源；
- 建表要新迁移（P-106 约束、schema 校验、回填），收益低；
- 未来若做“按用户/角色动态菜单”，再评估 DB（或 `notification_policy` 扩展），v1 不预留空表。

### 4. 触发创建（自动 vs 手动）

**建议 v1 手动同步，不自动。**

- 新增管理员端点（示意）：`POST /api/notification/menu/sync`，`GET /api/notification/menu/status`；
- 同步流程：读配置 → `menu/get` 取线上菜单 → 与期望值做**结构化 diff** → 有差异才 `menu/create`（或先 `menu/delete` 再建，按官方 API 语义）→ 回写“最后同步时间/结果/差异摘要”；
- 幂等：相同配置重复同步不调用写接口；
- 关闭 `enabled` 时不自动删线上菜单，需管理员显式“删除/停用”动作（避免配置误删把用户菜单清空）；
- 审计：`write_audit` 记录操作者、渠道、结果；不记录完整 URL 查询串/密钥；
- 自动（保存配置即推送）放 v2：先观察手动同步的成功率、限流与错误码，避免保存动作被网络失败拖住。

### 5. 交互形式

**v1：3 个 `view` 菜单项**，点击打开现有 Web 页面（任务、通知日志、设置）。不需要回调、不需要 `notification_log` 目标，所有能看到 Web 的用户都能用。

**v2（另批）：`click` 菜单项**，复用 `POST /api/notification/callback/wechat`：

- 企微菜单 click 事件把键放在 `EventKey`（`callback.py:280-317` 已有解析）；
- **已知缺口**：`callback_service._resolve_target` 目前要求 token 形如 `log_id:user_id` 且必须命中 `notification_log`（`callback_service.py:55-69`）；菜单 click 没有对应通知记录，不能伪造 log id。v2 需增加“菜单 click”分支：用 `FromUserName` 走既有的 `_resolve_target_by_actor` 定位本地用户 → 验签 → 角色授权 → 只读动作；不伪造 token、不复用通知记录；
- v2 动作仅 `view_detail`/`open_logs` 等只读动作；`retry`/`snooze`/`mark_done` 不做（D-05 默认只读）。

### 6. 工作量拆分

| # | 工作 | 预估 | 交付 |
|---|---|---|---|
| 1 | 配置模型/默认值/校验 + i18n 键（3 个菜单文案） | 0.5 天 | 1 commit |
| 2 | 企微菜单客户端：`menu/get`/`menu/create`/`menu/delete`，复用 `_access_token`，错误码/限流映射 | 1 天 | 1 commit |
| 3 | 管理员同步/状态 API + 审计 + 幂等 diff | 0.5 天 | 1 commit |
| 4 | 前端通知设置页“菜单配置 + 同步”最小 UI（可选，若 v1 只允许改 config 可后置） | 0.5 天 | 1 commit |
| 5 | 测试：payload/3 项上限/URL 校验/幂等/无凭据/错误码；文档与能力索引 | 0.5 天 | 随批 |
| 6 | v2：菜单 click 分支（`EventKey` + 无 log 目标的用户定位） | 1 天 | 另批 |

v1 合计约 **2.5~3 天 / 3~4 commit**，无 DB 迁移。

### 7. 风险与边界

| 风险 | 说明 | 缓解 |
|---|---|---|
| 官方 API 未在仓库取证 | 菜单端点/字段只在外部文档；当前禁网，不能现场核对 | 实现前先取证并记录到 `docs/reference/`；先用假 HTTP 单测，不拿生产试 |
| 企微 `supports_callback=False` 的旧声明 | `wechat.py:240-242` 与 T-43 后的回调实现不一致 | v1 的 `view` 菜单不依赖它；v2 做 click 前先修正能力声明与测试 |
| 仅自建应用可用 | 群机器人 Webhook 没有菜单 API，也收不到回调 | 同步前校验 `corpid/corpsecret/agentid`；状态接口明确提示“webhook 形态不支持” |
| 菜单是全局的 | 一个应用一套菜单，不能按用户/角色 | v1 接受；多用户动态菜单另立需求 |
| URL 安全 | 管理员可配任意 URL | 只允许站内相对路径/`http(s)`；拒绝 `javascript:`/`data:`；渲染前做长度/字符校验 |
| 幂等/限流 | 重复同步被平台限流或产生抖动 | 结构化 diff 后再写；记录 `errcode`；手动触发，失败可重试 |
| 回滚 | 线上菜单可能与配置不一致 | 状态接口显示“最后同步/差异”；停用需显式删除；不自动清空 |

### 8. 待老板拍板的 3 个问题

1. **第一版渠道**：企业微信（推荐，真 3 项菜单、凭据/回调基础已具备）还是 Telegram（更轻，但只是扁平命令列表、需命令处理）？
2. **v1 交互**：只做 `view` 导航（推荐，零回调改造）还是必须包含 `click` 只读动作（需先解决“菜单 click 没有 notification_log 目标”的 token/用户定位方案）？
3. **存储与触发**：`config.json` + 手动同步（推荐，无迁移）还是 DB + 保存即自动同步（需要新表/迁移与多用户模型）？
