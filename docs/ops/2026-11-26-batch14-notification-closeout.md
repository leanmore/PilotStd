# 批次 14 + 通知模块（批次 9）收尾报告（2026-11-26）

> 覆盖：v0.207.1 部署验收（批次 14 自动化）→ v0.209.x 企微通知重构（借鉴 MoviePilot）→ 待最终真机截图确认。

## 1. 部署版本链路（全部已发版并可回溯）

| 版本 | tag | 关键内容 | 状态 |
|---|---|---|---|
| 0.207.1 | `v0.207.1` | 批次 9/10/11/12/13 + 发布流水线修复 | ✅ 已部署验收 |
| 0.208.0 | `v0.208.0` | D-2 省份粒度路由（DB50 → cqis 优先） | ✅ |
| 0.209.0 | `v0.209.0` | 企微纯文本（MP 风格）+ `web_base_url` 配置 API/UI | ✅ 已部署 |
| 0.209.1 | `v0.209.1` | 纯文本「点击查看」链接兜底（actions URL） | ✅ 已部署 |
| 0.209.2 | `v0.209.2` | 纯文本排版去重（标题/正文首行、链接重复） | ✅ 已发版，待部署验证 |

## 2. 批次 14 自动化验收（v0.207.1 实测，2026-11-26 18:35）

| 探测 | 结果 | 退出码 |
|---|---|---|
| `probe_v0207.py` | **11 / 11 通过** | 0 |
| `probe_all.py --allow-unconfigured-channels` | **45 通过 / 0 失败 / 17 无法验证** | **0（无阻断）** |
| `probe_batch1.py` | **10 通过 / 0 失败 / 14 无法验证** | 0 |

- 原 3 条阻断全部清零：`mass_delete_guard`（维护窗口强制标记后幂等 no-op，探针判据已同步修正）、
  `favorite_downloads.orphan`（0）、`feishu.credentials`（渠道未启用，按 `--allow-unconfigured-channels` 豁免）；
- 14 项「无法验证」为渲染/目录/真实外发类，按 `docs/ops/deploy-selfcheck.md` §10.2/10.3 人工核对（真机截图即其中一项）。

## 3. 通知模块（批次 9）重构：借鉴 MoviePilot

**取证**：clone `jxxghp/MoviePilot` @ `56af7d4`；其 `app/modules/wechat/wechat.py` 对自建应用**只发 `msgtype=text`**
（`title\n正文`、空行折叠、末尾 `点击查看：{link}`、2048 字节分段、端点带 `safe/enable_id_trans/enable_duplicate_check`），
站点域名统一 `APP_DOMAIN`。对比分析：`docs/plans/2026-11-26-mp-notification-borrow.md`。

**改造**：
1. 应用消息默认**纯文本**（`_format_app_text`）；`markdown`/`card` 变显式选项；Webhook 仍 markdown；
2. `web_base_url` 接线：`GET/PUT /api/notification/config` + 设置页输入框（三语）；生产已写入 `http://192.168.1.18:9028`；
3. 真机曝出的两个排版缺陷已修（0.209.2）：聚合 `body` 含标题行导致标题重复、正文已含链接导致链接重复。

**真机取证链**：
- `POST /api/notification/test-event` → `{"ok":true}`，`notification_log id=4666` `status=success`（平台 errcode=0）；
- 0.209.1 截图：纯文本渲染、无大字报、链接可点；
- 0.209.2 待部署后发最终验收消息（同时验证标题去重 + 「点击查看」链接）。

## 4. 遗留（外部/待用户）

| 项 | 说明 | 状态 |
|---|---|---|
| 0.209.2 部署 + 最终真机截图 | 通知模块结案的最后一步 | ⏳ 等部署 |
| 飞书渠道启用 | 凭证未配齐（`webhook_url`/`app_id`/`app_secret`/`receive_id`），当前未启用属预期 | 外部 |
| T-40 企微真发取证 | 已由 `id=4666` 真机截图替补；正式结案待用户确认排版 | ⏳ |
| A-46 隔离文件恢复 | 需用户确认是否找回 | 外部 |
| A-27 自定义菜单 | 等产品口径（企微/飞书/Telegram/钉钉菜单动作映射） | 外部 |
