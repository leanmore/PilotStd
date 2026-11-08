# 通知渠道菜单 API 调研与实现状态

> 查阅日期：2026-11-08。官方文档可访问（企微/飞书/钉钉直连、Telegram 经本地代理）。
> 本页记录“持久菜单”能力；**Telegram 命令列表不算持久菜单**，单列。
> 实现：`pilotstd/core/notification/menu/`；管理 API：`docker/api/notification_menu.py`。

## 一、四渠道对比

| 渠道 | 实现状态 | 持久菜单 | 层级 | 读取/创建/删除端点 | 关键字段 | 权限/形态 | click 回调 |
|---|---|---|---|---|---|---|---|
| **企业微信** | **已实现（客户端 + 单测）** | **支持** | 3 个一级 + 每级最多 5 个二级 | `GET /cgi-bin/menu/get?access_token&agentid`；`POST /cgi-bin/menu/create?access_token&agentid`；`GET /cgi-bin/menu/delete?access_token&agentid` | `button[]`：`type`（`view`/`click`）、`name`、`url`/`key`、`sub_button[]` | 企业自建应用（`corpid`+`corpsecret`+`agentid`）；群机器人不支持 | 支持；`click` 事件通过回调 XML 的 `EventKey` 到达 |
| **飞书** | **已实现（群菜单，需 `chat_id`）** | **支持（群菜单）** | 3 个一级 + 每级最多 5 个二级 | `GET/POST/DELETE /open-apis/im/v1/chats/{chat_id}/menu_tree` | `menu_tree.chat_menu_top_levels[]`；每项 `chat_menu_item.action_type`（`NONE`/`REDIRECT_LINK`）、`name`、`redirect_link.web_url`；`children[]` | 自建/商店应用；`tenant_access_token`；需机器人能力且在群内；仅 `chat_mode=group` | 文档仅列 `NONE`/跳转，无 click 动作回调 |
| **钉钉** | **未实现（官方无持久菜单 API）** | **不支持（机器人）** | — | 机器人无持久菜单端点；`dd.showActionSheet` 是客户端 JSAPI；`服务号菜单更新` 属服务号，不是机器人 | — | 群机器人/互动卡片均无持久菜单 | — |
| **Telegram** | **已实现（命令列表，非持久菜单）** | **不支持（只有命令列表）** | 命令数可配（本实现限 3） | `getMyCommands` / `setMyCommands` / `deleteMyCommands`；`setChatMenuButton` 仅设置“菜单按钮” | `commands[]`：`command`、`description` | Bot API，bot token | 命令列表点击是用户发送 `/cmd` 消息，不是 callback |

### 官方链接

- 企微创建菜单：<https://developer.work.weixin.qq.com/document/path/90231>（获取/删除为相邻文档 90232/90233）
- 飞书添加群菜单：<https://open.feishu.cn/document/server-docs/group/chat-menu_tree/create>
- 钉钉显示操作菜单（客户端 JSAPI）：<https://open.dingtalk.com/document/isvapp/display-operation-menu>；服务号菜单：<https://open.dingtalk.com/document/orgapp/service-no-menu-update>
- Telegram `setMyCommands`：<https://core.telegram.org/bots/api#setmycommands>；`setChatMenuButton`：<https://core.telegram.org/bots/api#setchatmenubutton>

## 二、逐渠道结论

### 企业微信

- **结论：支持持久菜单，已实现 `WecomMenuClient`。**
- 一级 1~3 个、二级 1~5 个；`view` 跳 URL，`click` 推事件；`click` 事件由既有回调端点接收，`callback.py` 已解析 `EventKey`（T-43/D-59）。
- 错误码（按官方文档/实现映射）：`40001/40014/42001` token 失效，`45009` 限流，`48001` 未授权，`40054` 菜单超限。
- 限制：只有**企业自建应用**可创建菜单；群机器人 Webhook 形态明确返回“不支持”。

### 飞书

- **结论：支持群菜单（持久菜单），已实现 `FeishuMenuClient`。**
- 端点：`.../im/v1/chats/{chat_id}/menu_tree`；一级 3 个、每个一级最多 5 个二级。
- 关键错误码：`232070` 一级超限、`232071` 二级超限、`232073` 菜单修改中、`232078` 内容非法、`232025` 未启用机器人能力、`232014` 权限不足、`232055` 无菜单管理权限。
- 限制：菜单挂在**群**上，配置必须提供 `chat_id`；仅 `chat_mode=group`；当前只实现 `REDIRECT_LINK`（`view`），无 click 动作。

### 钉钉

- **结论：机器人无持久菜单 API，未实现菜单客户端（`DingtalkMenuClient` 显式返回 unsupported）。**
- `dd.showActionSheet` 是客户端 JSAPI（页面内弹操作菜单），不是服务端持久菜单；`服务号菜单更新` 属于服务号，不是本项目当前的通知机器人/互动卡片形态。
- 若老板要求钉钉也有“菜单”，需要先确认是否接受**卡片按钮/操作菜单**作为替代形态；本设计不把它当作持久菜单。

### Telegram

- **结论：官方无持久菜单，只有命令列表；已实现 `TelegramCommandClient`（命令列表，不是菜单）。**
- `setMyCommands` 注册 `/cmd` 列表；`setChatMenuButton` 只能设置底部菜单按钮的打开方式（commands/web_app 等），不能定义“3 个可点击菜单项”。
- 用户点击命令后发送 `/cmd` 文本消息，需要命令处理分支；本实现只做注册/读取/删除命令列表，不把它冒充持久菜单。

## 三、配置结构

```json
{
  "notification": {
    "menus": {
      "wechat": {
        "enabled": true,
        "items": [
          {"id": "task", "label_key": "notification.menu.task", "type": "view", "order": 1, "url": "/task"},
          {"id": "more", "label_key": "notification.menu.more", "type": "group", "order": 2,
           "children": [{"id": "logs", "label_key": "notification.menu.logs", "type": "view", "order": 1, "url": "/notification-logs"}]}
        ]
      },
      "feishu": {
        "enabled": true,
        "chat_id": "oc_xxx",
        "items": [{"id": "task", "label_key": "notification.menu.task", "type": "view", "order": 1, "url": "https://example.com/task"}]
      },
      "telegram": {
        "enabled": true,
        "items": [{"id": "task", "label_key": "notification.menu.task", "type": "command", "order": 1, "command": "/task"}]
      },
      "dingtalk": {"enabled": false, "items": []}
    }
  }
}
```

- 校验：顶级 ≤ 渠道上限、id 全局唯一、order 从 1 连续、type 在渠道闭集内、URL 拒绝 `javascript:`/`data:`；`group` 仅用于二级分组。
- 同步后在配置内写 `last_synced`（结构化菜单快照），用于幂等判断；不写密钥。
- 管理 API：`GET /api/notification/menu/status`、`POST /api/notification/menu/sync?channel=...`（admin）。

## 四、实现状态

| 渠道 | 客户端 | 单测 | 真实 API 验证 |
|---|---|---|---|
| 企业微信 | `WecomMenuClient`（get/create/delete） | `tests/test_notification_menu.py` | 待部署凭据 |
| 飞书 | `FeishuMenuClient`（群菜单 get/create/delete） | 同上 | 待 `chat_id` + 应用凭据 |
| Telegram | `TelegramCommandClient`（命令列表） | 同上 | 待 bot token；形态为命令列表 |
| 钉钉 | `DingtalkMenuClient`（显式 unsupported） | 同上 | 不适用（无持久菜单） |

> 真实渠道 API 验证需要老板提供企微/飞书/Telegram 凭据与一个测试群/chat_id；本地只做 fake transport 单测，未联网调用生产 API。
