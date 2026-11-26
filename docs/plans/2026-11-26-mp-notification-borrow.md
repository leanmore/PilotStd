# 企微通知重构：借鉴 MoviePilot 的实现（2026-11-26）

> 背景：生产企微通知排版崩坏、微信插件端报「暂不支持此消息类型」。按用户要求，
> 拉取 MoviePilot（`jxxghp/MoviePilot`，clone at `56af7d4`）定向逆向其通知实现，移植其格式方案。

## 1. MoviePilot 实现摘要（取证位置）

| 关注点 | MP 实现 | 取证 |
|---|---|---|
| 自建应用消息类型 | **只用 `msgtype=text`**（不发 markdown、不发 template_card） | `app/modules/wechat/wechat.py:208-252` `__send_message` |
| 文本排版 | `title\n正文`，**连续空行折叠为一个**；无 markdown 标记 | 同上 `formatted_text = text.replace("\n\n", "\n")` |
| 详情链接 | 正文末尾追加 **`点击查看：{link}`** 纯文本 | 同上 `content = f"{content}\n点击查看：{link}"` |
| 长度 | 按 **UTF-8 字节 2048** 分段，保留完整字符 | `__split_content`（第 158-206 行） |
| 端点字段 | `touser/msgtype/agentid/text{content}/safe=0/enable_id_trans=0/enable_duplicate_check=0` | 第 234-244 行 |
| 图文（有封面图时） | `msgtype=news`（`title/description/picurl/url`） | `__send_image_message`（第 254-292 行） |
| 站点域名 | 统一配置键 **`APP_DOMAIN`**（`get_runtime_setting("APP_DOMAIN")`），拼绝对链接 | `app/application/messaging/image.py:44`、`app/foundation/passkey.py:150` |
| 智能机器人模式 | markdown（`WECHAT_MODE=bot` 时） | `app/modules/wechat/__init__.py` `_is_bot_mode` |

## 2. 我们的实现差异（问题根因）

| 项 | 我们（改造前） | 结论 |
|---|---|---|
| 应用消息类型 | 先 `template_card`，失败降级 `markdown`，再 `text` | **卡片/markdown 在微信插件端不支持**；排版依赖客户端渲染差异 → 崩坏 |
| 文本排版 | markdown `##` 标题 + `**字段**` | 微信端看不到 markdown（显示「暂不支持此消息类型」） |
| 链接 | 卡片 `jump_list` / markdown `[查看详情](url)` | `web_base_url` 未配置时**完全无链接** |
| 域名配置 | `notification.web_base_url` 只在 config.json 默认值里，**无 API/UI 读写入口** | 用户配了也不知道是否生效；消息永远提示「未配置站内访问地址」 |

## 3. 改造方案（本轮落地）

1. **应用形态默认发 `msgtype=text`**（MP 对齐）：`title\n正文`（空行折叠）+ `点击查看：{url}`；
   端点补 `safe/enable_id_trans/enable_duplicate_check`；
2. `markdown` / `card` 保留为**显式选项**（`PILOTSTD_WECHAT_APP_FORMAT=markdown|card`），默认 `text`；
3. **`web_base_url` 接线**：`GET /api/notification/config` 下发、`PUT` 接受（校验 http(s) 且非回环，与发送侧
   `resolve_web_base` 同口径）、Web 设置页新增「站内访问地址」输入框（三语 i18n）；
4. 群机器人（Webhook）继续 markdown（该形态本来就只支持 markdown）。

## 4. 验收

- 单测：`tests/test_notification_wechat_card.py`（25 例：默认 text / markdown/card 选项 / 降级链 / 空行折叠与链接）、
  `tests/test_notification_api.py`（web_base_url 读写 4 例）；
- 真实发送：部署后经 `POST /api/notification/test-event` 发一条，用户真机截图确认排版干净、链接可点。
