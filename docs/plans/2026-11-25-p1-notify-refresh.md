# P1-6 复核：企微 vs Telegram 通知效果对比（当前代码状态重测）

| 项目 | 值 |
|------|-----|
| 任务包 | P1-6「企微 vs TG 通知信息量对齐」**复核**（重测 + 剩余缺口） |
| 日期 | 2026-11-25 |
| 性质 | **只读复核**；未改代码/配置/其它文档，未 commit/push；临时脚本全部在 `C:\Temp\` |
| 复核基线（本地） | HEAD=`bbc60b61`，含 3 个修复提交：`73be260f`（卡片级别/链接/计数 + auto_backup）、`c7be4541`（降级分段/markdown 标题/安全告警应用形态）、`35e3f12e`（5 事件补对象） |
| 复核基线（生产） | 只读 `GET http://192.168.1.18:9028/api/health` → `version=0e92e5d2…`、`schema_version=76`、`status=ok` ⇒ **生产仍停在修复前提交**（`0e92e5d2` 是 3 个修复提交的祖先；`git diff 0e92e5d2..HEAD -- pilotstd/core/notification` 有 7 文件 / +182/-41 行） |
| 探针 | `C:\Temp\p2_probe.py`（44 事件 × 2 场景（web_base_url 配/不配）× 8 种渲染输出）、`p2_analyze.py`、`p2_card_edge.py`（边界/截断）、`p2_card_limits.py`（真实多明细载荷）、`p2_prod_menu.py`（生产只读 GET） |
| 样本规模 | **88 组事件渲染 = 704 条渲染输出**：0 渲染异常、0 i18n 缺键泄漏；另 3 组超长压测（100 条明细/标准）、6 组真实多明细载荷、5 组旧 payload 兼容 |
| 上一轮报告 | `docs/plans/2026-11-24-p1-notification-parity.md`（466 行，基线 `0e92e5d2`） |
| 结论一句话 | **模板层三类缺口（级别/链接/列表）在渲染器代码层已全部闭合**（27/27、7/7、7/7；对象 5/5；`auto_backup` TG 不再崩）。**但渠道实际呈现层未闭合**：企微 `template_card` 报文不满足官方必填/条数契约（44/44 缺 `card_image`/`image_text_area`；6/44 在常规载荷下 `vertical_content_list` 已超官方上限 4），大概率被平台拒收并**全量降级为 `msgtype=text`**，而降级文本是 markdown 源码（`##`/`**`/`[x](url)` 原样显示）；同时 TG 的「详情」链接行未做 MarkdownV2 转义（`web_base_url` 一旦配置，7 个事件会 400 **整条丢失**）。**P1-6 不可闭合。** |

> **本轮取证方式（不靠记忆）**：① 用**当前 HEAD 的真实构建器 + 真实渲染器**实跑全部 44 事件（探针脚本见 §7）；② 读修复提交 diff 与新增测试；③ 官方文档核对企微 `template_card` / TG MarkdownV2 的字段契约（外部文档，链接见 §4）；④ 生产只读 `GET /api/health`、`GET /api/notification/menu/status`（未做任何生产写操作）。

---

## 0. 结论摘要（先看这里）

1. **上一轮 3 类字段缺口已闭合**（代码层）：级别 **27/27**、详情链接 **7/7**（卡片 `jump_list` 首项 + `card_action`）、ListBlock 计数/完整列表 **7/7**（上一轮 5 个 + B-4 新增的 `archive_failed`/`normalize_failed` 共 7 个）；5 个「缺对象」事件 **5/5** 已补；`auto_backup` 的 TG `TypeError` 已消失。**704 条渲染输出中 0 异常、0 i18n 键名泄漏。**
2. **但「企微卡片」这条路径本身不符合官方字段契约，且这是上一轮明确留白的未取证项**：`news_notice` 要求 `card_image`/`image_text_area` 至少一项、`card_action` 必填、`vertical_content_list` 条数 ≤4、条目 `title` 必填；当前渲染器 **44/44 无图字段**、条目 `title` 恒为空串、`web_base_url` 未配置时 **44/44 无 `card_action`**、常规载荷下 **6/44 条数超 4**（真实多明细载荷实测 6–11 条）。按企微错误码口径（数组元素超限同 40058），**卡片大概率被拒收 → `channels/wechat.py:76-84` 降级为文本**；由于降级文本也能投递成功，**生产 `notification_log` 只会看到 success，日志层无法分辨"卡片成功"还是"降级文本成功"**。
3. **新发现的反向缺陷（TG 整条丢失，与 P0-1 同类）**：`renderer_base.py:206-211` 在**转义之后**把 `detail_link_line()`（裸 URL）拼到 MarkdownV2 正文；URL 含 `.`/`-` 等 reserved 字符未转义 ⇒ Telegram 返回 400 `can't parse entities`，**7 个带 link 的事件整条收不到**。仅在 `notification.web_base_url` 已配置时触发（默认空 ⇒ link 被清空 ⇒ 当前默认部署不触发），但这正是 P0-3「卡片链接」修复生效的前提。
4. **若卡片果真全量降级**，则用户实际看到的是 `msgtype=text` 的 **markdown 源码**：`## 标题`、`**字段**：值`、`[查看详情](url)` 原样呈现、链接不可点；企微应用消息本身支持 `msgtype=markdown`（≤2048 字节），降级路径选错了消息类型（`channels/wechat.py:177-188`）。
5. **上一轮 P2 横切三项未随本批修复**：聚合后 `event_type` 被改成类别名、聚合摘要首行退化为级别前缀、日志接口 `level` 恒 info（`aggregate_buffer.py:449,490-514`、`docker/api/notification_logs.py:133-139`）。
6. **生产未部署本批修复**（见页首），因此上一轮的生产实证缺口（如 `notification_log id=2034` 的 TG TypeError）在部署前**依旧存在**；本报告"已闭合"均为**代码层结论**，生产验收必须等部署 + 一次真机发送。

---

## 1. 复核基线与方法

### 1.1 代码基线

| 项 | 值 |
|---|---|
| 本地 HEAD | `bbc60b61`（分支 `feat/debt-cleanup-round2`；复核起点无未提交改动） |
| 本任务相关修复 | `73be260f`（P0-1/P0-2/P0-3/P1-1）、`c7be4541`（P1-2/P1-3/P1-4）、`35e3f12e`（P1-5 五个对象） |
| 生产 | `0e92e5d2`（**修复前**）；`git diff 0e92e5d2..HEAD -- pilotstd/core/notification` = 7 文件 +182/-41 |
| 相关测试 | `tests/test_notification_wechat_card.py`（含 6 个 P0/P1-1 新用例）、`tests/test_notification_renderer.py::TestAutoBackupTelegramRender`（222-240）、`tests/unit/core/test_renderer_plain_text.py`（B2）、`tests/test_notification_security_channel_form.py`（B3）；本轮实跑 **76+7+5 例全绿** |

### 1.2 探针口径（与上一轮不同的两点）

1. **两个配置场景**：`notification.web_base_url` **已配置**（`http://pilotstd.example.lan:9028`，代表"站内入口可用"）与 **未配置**（默认空，代表"出厂/当前生产未取证取值"）。上一轮只跑了前者，漏掉了"链接被设计性清空"这一分支对其它渠道的影响面判断。
2. **逐事件 fact 提取**：对 8 种输出（TG 文本/按钮、企微 Webhook markdown、企微模板卡片 JSON、卡片降级文本、飞书卡、钉钉卡、桌面）分别检查是否含：级别前缀（次数）、`message.link`、ListBlock「共 N 条」、`detail_url`、动作、i18n 键泄漏、非 str Block 值、分段数/字节数、卡片条目数/单条长度。

### 1.3 判据（沿用上一轮）

- 字段缺口 = 「上一轮 §2.3/§3 定义的 `LV`（级别）/`L`（详情链接）/`LC`（列表计数）/`DU`（完整列表链接）在**该渠道输出中不出现**」；
- 跨渠道差异 = TG 有而企微没有（或反之）的**信息项**；纯排版（`•` vs `-`、转义反斜杠）不计；
- 卡片按**生产在用形态**（应用消息 `template_card`）评估（生产渠道配置沿用上一轮只读取证：`webhook_url=""` + `corpid/agentid/corpsecret` 齐 ⇒ 应用形态）。

---

## 2. 44 事件复核总表

> 图例：`LV`=级别前缀；`L`=详情链接；`LC`=列表「共 N 条」；`DU`=ListBlock 完整列表链接。
> **「L 已闭(base配)」**=仅当 `notification.web_base_url` 已配置时闭合；未配置时 `_links.absolutize_message_link` 按设计把 link 清空（`_links.py:141-148`），**所有渠道都不显示**，不算跨渠道差异。
> 「卡片条目 N条」= 默认样例 payload 下 `template_card.vertical_content_list` 的条数；**官方上限 4**，`⚠️` 表示已超限（详见 §4-D1）。

| # | 事件 | 修复前缺口（2026-11-24） | 当前状态（本轮实测） |
|---|------|--------------------------|----------------------|
| 1 | `standard_status_changed` | 卡片缺级别+详情链接 | LV 已闭；L 已闭(base配)｜卡片条目 2条 |
| 2 | `standard_first_registered` | 卡片缺列表计数/完整列表链接/详情链接 | L 已闭(base配)；LC 已闭；DU 已闭｜卡片条目 ⚠️6条 |
| 3 | `validity_batch_report` | 卡片缺级别 | LV 已闭｜卡片条目 ⚠️6条 |
| 4 | `validity_round_summary` | 卡片缺列表计数 | LC 已闭｜卡片条目 4条 |
| 5 | `validity_standard_failed` | 卡片缺级别+详情链接 | LV 已闭；L 已闭(base配)｜卡片条目 2条 |
| 6 | `validity_system_failed` | 卡片缺级别；弱对象 | LV 已闭；弱对象仍在（§4-D8）｜卡片条目 2条 |
| 7 | `date_reminder` | — | 无渠道字段缺口｜卡片条目 1条 |
| 8 | `scan_complete` | 卡片缺级别 | LV 已闭｜卡片条目 3条（真实多失败载荷 7 条） |
| 9 | `scan_empty` | 缺对象（未写扫描路径） | 对象已补（路径）｜卡片条目 2条 |
| 10 | `auto_scan_failed` | 卡片缺级别 | LV 已闭｜卡片条目 2条 |
| 11 | `batch_query_summary` | 卡片缺列表计数 | LC 已闭｜卡片条目 4条 |
| 12 | `query_failed` | 卡片缺级别 | LV 已闭｜卡片条目 1条 |
| 13 | `query_empty` | 卡片缺级别；缺对象（无标准号） | LV 已闭；对象已补（标准号清单，列前 10）｜卡片条目 2条 |
| 14 | `batch_download_complete` | 卡片缺级别 | LV 已闭｜卡片条目 2条（5 条失败明细时 6 条） |
| 15 | `download_failed` | 卡片缺级别+详情链接 | LV 已闭；L 已闭(base配)｜卡片条目 3条 |
| 16 | `normalize_complete` | 卡片缺列表计数 | LC 已闭｜卡片条目 3条 |
| 17 | `normalize_failed` | 卡片缺级别；缺对象 | LV 已闭；LC 已闭；对象已补（明细 1 条，口径瑕疵见 §4-D8）｜卡片条目 3条 |
| 18 | `archive_complete` | — | 无渠道字段缺口｜卡片条目 ⚠️5条 |
| 19 | `archive_failed` | 卡片缺级别；缺对象 | LV 已闭；LC 已闭；对象已补（失败明细）｜卡片条目 4条 |
| 20 | `archive_abandoned` | 卡片缺级别 | LV 已闭｜卡片条目 2条 |
| 21 | `expire_standard_moved` | — | 无渠道字段缺口｜卡片条目 1条 |
| 22 | `replacement_not_found` | 卡片缺级别 | LV 已闭｜卡片条目 1条 |
| 23 | `announcement_fetch_complete` | — | 无渠道字段缺口｜卡片条目 ⚠️5条 |
| 24 | `announcement_check_complete` | 卡片缺级别 | LV 已闭｜卡片条目 2条 |
| 25 | `announcement_fetch_failed` | 卡片缺级别 | LV 已闭｜卡片条目 1条 |
| 26 | `announce_fetch_summary` | 卡片缺级别 | LV 已闭｜卡片条目 3条 |
| 27 | `auto_backup` | TG 渲染 float 抛错→整条丢失 | TG 已不崩（`12\.5` 正常转义输出）｜卡片条目 2条 |
| 28 | `image_update_available` | — | 无渠道字段缺口｜卡片条目 2条 |
| 29 | `trust_ip_update` | 卡片缺级别 | LV 已闭｜卡片条目 4条 |
| 30 | `worker_error` | 卡片缺级别 | LV 已闭｜卡片条目 3条 |
| 31 | `task_execution_failed` | 卡片缺级别 | LV 已闭｜卡片条目 3条 |
| 32 | `quota_exhausted` | 卡片缺级别 | LV 已闭｜卡片条目 1条 |
| 33 | `notification_delivery_failed` | 卡片缺级别 | LV 已闭｜卡片条目 2条 |
| 34 | `desktop_toast` | N/A（平台层，不适用） | N/A｜卡片条目 1条 |
| 35 | `favorite_created` | 卡片缺详情链接 | L 已闭(base配)｜卡片条目 4条 |
| 36 | `task_progress` | Webhook 形态缺标题 | 标题已补（markdown 首行 `## 任务进行中`）｜卡片条目 1条 |
| 37 | `download_started` | 卡片缺详情链接；缺结果 | L 已闭(base配)；**缺结果（未修）**｜卡片条目 1条 |
| 38 | `download_complete` | 卡片缺详情链接 | L 已闭(base配)｜卡片条目 3条 |
| 39 | `favorite_abandoned_summary` | 卡片缺级别+列表计数 | LV 已闭；LC 已闭｜卡片条目 ⚠️8条 |
| 40 | `notification_credential_changed` | 卡片缺级别 | LV 已闭｜卡片条目 4条 |
| 41 | `security_password_changed` | 卡片缺级别；弱结果 | LV 已闭；**弱结果仍在**（§4-D8）｜卡片条目 3条 |
| 42 | `security_token_refreshed` | 卡片缺级别；弱对象 | LV 已闭；弱对象仍在（§4-D8）｜卡片条目 3条 |
| 43 | `security_login_failed` | 卡片缺级别 | LV 已闭｜卡片条目 4条 |
| 44 | `auto_pipeline_summary` | 缺对象（无批次/范围） | 对象已补（任务号+路径）｜卡片条目 ⚠️6条 |

**统计**：事件 44；级别事件 **27**（全部 LV 已闭，且**恰好出现一次**：卡片 `main_title.desc` 1 次、TG/markdown/飞书/钉钉/桌面各 1 次、卡片降级文本 1 次）；带 link 事件 **7**（base 配置时全部闭合）；ListBlock 事件 **7**（LC/DU 全闭）；「缺对象」事件 **5**（全闭）；`desktop_toast` N/A。**上一轮 34/44 的字段缺口并集 → 0/44（字段层）。** 但**卡片形态**风险覆盖 44/44（§4-D1）。

---

## 3. 上一轮缺陷逐条判定 + 已闭合证据

### 3.1 逐条判定

| 上一轮编号 | 缺陷 | 判定 | 依据 |
|---|---|---|---|
| P0-1 | `auto_backup` float `size_mb` → TG `TypeError`，整条丢失 | **已修** | `_builders_system.py:128-135` 统一 `str()`；TG 输出 `文件大小: 12\.5`；回归 `tests/test_notification_renderer.py::TestAutoBackupTelegramRender`（222-240）绿 |
| P0-2 | 企微模板卡片不渲染级别（27 事件） | **已修（代码层）** | `renderer_wecom_card.py:81-88` 把 `level_prefix()` 写进 `main_title.desc`；27/27 均含且**恰好一次**；6 个新测试（`tests/test_notification_wechat_card.py:270-340`）绿 |
| P0-3 | 企微模板卡片不渲染 `message.link`（7 事件） | **已修（条件性）** | `renderer_wecom_card.py:60-76` link 作 `jump_list` 首项 + `card_action` 指向它；**仅当 `web_base_url` 已配置**（未配置时 link 被 `_links.py:141-148` 清空） |
| P1-1 | 卡片 ListBlock 丢「共 N 条」/`detail_url` | **已修** | `renderer_wecom_card.py:106-118`；7/7 事件卡片含计数与完整列表链接；测试 `:324-340` 绿 |
| P1-2 | 卡片拒收降级文本 `text[:2000]` 字符硬截断 | **已修** | `channels/wechat.py:177-188` 改 `split_for_channel(text,"wecom")` 字节分段逐段发送；6314 字节 → 5 段、每段 ≤2048、带「续 N/M」；测试 `:208-268` 绿 |
| P1-3 | 企微 Webhook 形态 body-only 消息丢标题 | **已修** | `renderer.py:150-162` 覆写 `_render_plain_text` 补 `## 标题`；`task_progress` 首行 `## 任务进行中`；测试 `tests/unit/core/test_renderer_plain_text.py` 绿 |
| P1-4 | 安全告警直连投递只认 webhook 形态 | **已修** | `security_notifier.py:92-106` 应用形态优先；`tests/test_notification_security_channel_form.py` 5 例绿 |
| P1-5 | 5 个事件缺对象 | **已修**（附 1 处口径瑕疵） | `_builders_task_results.py:100-117/143-168/173-200/204-226/357-396`；输出见 3.2 片段；旧 payload 仍兼容（不崩、不追加）；`normalize_failed` 计数口径见 §4-D8 |
| P2-1/P2-2/P2-3 | 聚合 event_type / 摘要首行 / 日志 level | **仍缺**（未在本批修复范围） | 见 §4-D7 |
| P2-4 | `supports_callback` 自述冲突 | **仍缺** | `channels/wechat.py:238-250`（False）vs `interaction.py:52-57`（True） |

### 3.2 证据片段（本轮探针实跑输出，仅截取关键行）

**P0-1 `auto_backup`（TG 不再崩）**

```
*自动备份成功*

备份路径: D:/b\.db

文件大小: 12\.5
```

**P0-2 级别（`standard_status_changed`，error）**：卡片 JSON

```json
"main_title": {"title": "[废止] 标准已废止", "desc": "❌ 错误"}
```

降级文本首行 `❌ 错误`；27 个 warning/error 事件在两个场景 × 7 种输出中级别均出现 **1 次**（无二次前缀）。

**P0-3 链接（`download_complete`，`web_base_url` 已配置）**：卡片 JSON

```json
"jump_list": [
 {"type": 1, "url": "http://pilotstd.example.lan:9028/standards/GB/T 12345-2020", "title": "详情"},
 {"type": 1, "url": "http://pilotstd.example.lan:9028/notification-logs", "title": "查看详情"}
],
"card_action": {"type": 1, "url": "http://pilotstd.example.lan:9028/standards/GB/T 12345-2020"}
```

未配置 `web_base_url` 场景：`message.link=None`，卡片无 `jump_list`/`card_action`，TG/markdown 也**没有详情行**（设计口径：不给坏链）。

**P1-1 列表（`standard_first_registered`）**：卡片 `vertical_content_list` 条目

```
"**登记标准清单**（共 2 条）"
"- GB/T 12345-2020 | 食品安全国家标准 示例"
"- GB/T 67890-2021 | 另一标准"
"查看完整列表：https://example.lan/standards/list"
```

**P1-2 降级分段**：`MarkdownRenderer` 输出 6314 字节 ⇒ `split_for_channel(..., "wecom")` = 5 段，字节 `[12, 2045, 2045, 2045, 221]`，第 2 段起带 `（续 2/5）…（续 5/5）`。

**P1-3 `task_progress`（Webhook markdown 首行）**

```
## 任务进行中

任务 自动扫描：已处理 30/100（30%），已运行 5 分钟；当前步骤：下载阶段
```

**P1-5 五个对象事件（markdown，base 已配置；卡片同内容）**

```
scan_empty        : 未发现新文件 / 路径：D:\收件箱
query_empty       : 共 3 条标准，均未查询到结果 / 标准号：GB/T 12345-2020, GB/T 67890-2021, GB/T 11111-2019
archive_failed    : 2 条标准归档失败：目标目录不可写 / 失败明细（…）（共 2 条）+ 2 行
normalize_failed  : 2 条标准规范化失败：系统异常已记录日志 / 失败明细（…）（共 1 条）+ 1 行
auto_pipeline_sum  : 任务：imp-abcd1234 / 路径：D:\收件箱 / 扫描 12、查询到 8、下载成功 6、归档完成 5
```

旧 payload（无新键）实跑：5 事件均**不崩、不追加对象块**（向后兼容），符合提交说明。

**横切闭合**：704 条渲染输出中，`notification.*` 键名泄漏 **0**、`<RENDER ERROR>` **0**、非 str Block 值 **0**；`tests/unit/test_i18n_completeness.py`（三语缺键守卫）本轮实跑 **5 passed**。

---

## 4. 仍存在的差异（按严重度排序）

> 排序：渠道级「整条丢失/整类降级」 > 结构契约不合法 > 用户可见格式退化 > 已登记的横切/模板口径。
> 「复现」全部基于 §7 的探针脚本，不发网络。

### D1（P0，新取证）企微模板卡片报文不满足官方字段契约 → 大概率全量降级文本

| 项 | 内容 |
|---|---|
| 现象 | 当前 `WeChatCardRenderer.render_card()` 产物按官方字段表**多处不合法**：① `news_notice` 要求 `card_image` 与 `image_text_area` **必填其一**，当前**恒不输出**（44/44）；② `card_action` 对 `news_notice` **必填**，`web_base_url` 未配置时**恒不输出**（44/44；此时既无 `jump_list` 也无动作）；③ `vertical_content_list` **条数 ≤4**，当前「每个渲染行 = 一条」，常规载荷 **6/44 已超限**（`archive_complete`/`announcement_fetch_complete` 5 条，`validity_batch_report`/`standard_first_registered`/`auto_pipeline_summary` 6 条，`favorite_abandoned_summary` 8 条）；真实多明细载荷（`batch_download_complete` 5 失败、`scan_complete` 5 失败、`validity_batch_report` 5 变更、`favorite_abandoned_summary` 5 示例）实测 **6–11 条**；④ 条目 `title` 官方**必填**，当前恒为 `""`（全部条目）。 |
| 后果 | 企微对非法参数（含数组元素超限）返回 **40058**；卡片被拒收后走 `channels/wechat.py:76-84` 的**文本降级**。因降级也能成功投递，`notification_log` 仍记 `success` ⇒ **日志无法区分「卡片成功」与「降级成功」**。若成立，则 P0-2/P0-3/P1-1 的卡片修复在生产上**不可达**——上一轮"企微卡片信息量差"实际表现为"企微只收到文本降级"。 |
| 证据（代码） | `renderer_wecom_card.py:44-58`（每行一条、`textwrap` 宽 140）、`:81-93`（卡片 dict：无 `card_image`/`image_text_area`；`card_action` 仅当 `jump_list` 存在）、`:44-58`（每个渲染行生成 `{"title": "", "desc": …}`，条目 `title` 恒为空串）。模块 docstring `:18-22` 自述"该字段是否必填官方正文未取到 ⇒ 缺失时省略"——**该留白本轮已取到官方字段表**。 |
| 证据（官方文档） | 企微《模板卡片类型》：`card_image` 与 `image_text_area` "news_notice类型的卡片，card_image和image_text_area两者必填一个字段，不可都不填"；`card_action` "news_notice模版卡片中该字段为必填项"；`vertical_content_list` "列表长度不超过4"。[链接1](https://developer.work.weixin.qq.com/document/path/101032) 《结构体说明》同口径：`card_image` 必填其一、`jump_list` 最多 3 条、`vertical_content_list` 最多 4 条。[链接2](https://developer.work.weixin.qq.com/document/path/101839) 另：错误码 40058 "参数值的长度超出了限制…参数字段若是数组类型，若元素个数超出限制，也同样报错40058"（[go-workwx errcodes](https://pkg.go.dev/github.com/jamsman94/go-workwx@v1.10.0/errcodes)、[官方社区答复](https://developer.work.weixin.qq.com/community/question/detail?content_id=16571056316962875684)）。 |
| 影响面 | 卡片形态 **44/44**；其中条数超限至少 **6/44**（常规载荷），多明细事件更多。 |
| 复现 | `python C:\Temp\p2_probe.py` → `p2_render.json` 的 `wecom_card`；`python C:\Temp\p2_card_edge.py`（`official_contract` 段）、`p2_card_limits.py`（真实载荷条数）。 |
| 修复方向（需用户裁定三选一） | A. **应用消息改发 `msgtype=markdown`**（官方支持、≤2048 字节，与 Webhook 同渲染器/同分段）——最小改动、信息量与 TG 对齐，最推荐；B. 补齐 `news_notice` 必填项（固定 `card_image` URL + `card_action` + 合并到 ≤4 条 + 非空 `title`）——仍有 4 条上限丢行；C. 换 `text_notice` 卡型（无图片必填）——需重排 `sub_title_text`/`horizontal_content_list`，本仓无语料实证。 |
| 备注 | 本项**无法在"不发网络"约束内证实实际 errcode**；建议部署前用维护窗口发 1 条测试消息，抓 `errcode` 后定案。 |

### D2（P0，新发现）TG「详情」链接行未做 MarkdownV2 转义 → 7 个事件整条丢失

| 项 | 内容 |
|---|---|
| 现象 | `BlockRenderer.render()` 在**逐块转义完成之后**追加 `level_prefix` 与 `detail_link_line(message)`；TG 没有覆盖该追加逻辑，`detail_link_line` 返回裸 URL（`https://…/standards/GB/T 12345-2020`），其中 `.`/`-`/`_` 等 MarkdownV2 保留字符**未加反斜杠**。对照：ListBlock 的 `detail_url` 走了 `self._escape()`（`renderer_telegram.py:113-114`），同一份 URL 在块内被转义、在详情行未转义——**同一渲染器内自相矛盾**。 |
| 后果 | 设置 `parse_mode=MarkdownV2` 时 Telegram 对未转义保留字符返回 HTTP 400（`can't parse entities`），`channels/telegram.py:61-87` 直接判定该段失败 ⇒ **整条通知丢弃**（与 P0-1 同级的反向整条丢失）。影响 **7 个带 link 事件**：`standard_status_changed`、`standard_first_registered`、`validity_standard_failed`、`download_failed`、`favorite_created`、`download_started`、`download_complete`。**触发条件**：`notification.web_base_url` 已配置（默认空 ⇒ link 被清空 ⇒ 当前默认部署不触发）；但该配置恰是 P0-3 生效的前提，一旦按 P0-3 建议配置，TG 立刻开始整条失败。 |
| 证据（代码） | `renderer_base.py:157-162`（`detail_link_line` 返回裸 URL）、`:174-212`（`render()` 末尾 `text = f"{text}\n\n{link_line}"`，无渠道转义钩子）；`renderer_telegram.py:82-128`（块级 `_escape`）、`:130-137`（只对 body-only 的 title/body 转义）。 |
| 证据（实测输出） | `p2_card_edge.py` → `tg_detail_line.text`：`*t*\n\nx\n\n详情：https://std.example.com/standards/GB/T 12345-2020`（`.` 未转义）；`p2_probe.py` 的 7 个 link 事件 `tg_unlinked_url=True`。 |
| 证据（官方规则） | Telegram Bot API《MarkdownV2 style》规定 18 个保留字符（下划线、星号、方括号、圆括号、波浪号、反引号、大于号、井号、加号、减号、等号、竖线、花括号、点、感叹号）在正文中必须用前导 `\` 转义。[链接](https://core.telegram.org/bots/api#markdownv2-style) |
| 影响面 | 7 个事件（base 已配置时整条丢失）。 |
| 复现 | `python C:\Temp\p2_card_edge.py`（`tg_detail_line`）；或 `TelegramRenderer().render(NotificationMessage(title="t", blocks=[TextBlock(text="x")], link="https://a.b/c.d"))` → 输出含 `详情：https://a.b/c.d`。 |
| 修复方向 | 给 `BlockRenderer` 增加可覆盖的 `_render_link_line()`/`_render_detail(link)` 钩子，Telegram 覆盖为 `详情：{self._escape(url)}`；或 TG 覆盖 `render()` 对追加段统一转义。顺带把 `level_prefix` 也纳入同一钩子（当前无 reserved 字符，但更稳）。新增 2–3 例（断言 URL 中 `.`/`-`/`_` 均带前导 `\`）。 |

### D3（P1，新发现）卡片拒收后的降级文本用 markdown 源码发 `msgtype=text`

| 项 | 内容 |
|---|---|
| 现象 | `_send_app_text()` 取 `MarkdownRenderer().render()`（含 `## 标题`、`**字段**：值`、`- 条目`、`[查看详情](url)`），但以 `{"msgtype": "text"}` 发送；企微**文本消息不解析 markdown**，用户看到的是源码，`[查看详情](url)` 也不是可点链接。 |
| 后果 | 若 D1 成立（卡片被拒），**这就是企微生产实际观感**：每条形如 `## 下载归档完成` / `**标准号**：GB/T …` / `[查看详情](http://…)`；信息量不丢但格式/可点性退化，与 TG 的富文本呈现差距最大。 |
| 文件:行 | `channels/wechat.py:177-188`（`_send_app_text`）；渲染来源 `renderer.py:124-141`（链接行）、`:150-162`（标题）、`:175-194`（列表）。 |
| 证据 | 探针 `fallback_text`：`has_md_heading=True`、`has_md_bold=True`、`has_md_link=True`。企微应用消息**支持 `markdown` msgtype（≤2048 字节）**（[官方社区](https://developer.work.weixin.qq.com/community/question/detail?content_id=16774697775667930008)、[长度限制答复](https://developer.work.weixin.qq.com/community/question/detail?content_id=16349055040439120427)）。 |
| 影响面 | 全部被拒收的卡片（D1 成立时 44/44；即使 D1 只有"多行/无动作"子集被拒，也有 6–44 个）。 |
| 修复方向 | 降级改发 `{"msgtype":"markdown","markdown":{"content": segment}}`（按 2048 字节分段不变）；若必须用 text，则新增纯文本渲染器（去掉 `##`/`**`/markdown 链接语法）。 |

### D4（P1，残留）企微卡片 desc 里出现字面 markdown（`**…**`、`- `、`|`）

| 项 | 内容 |
|---|---|
| 现象 | 卡片正文逐行进 `vertical_content_list[].desc`，而 desc 是**纯文本**；ListBlock 首行仍是 `**{title}**（共 N 条）`、条目行仍是「`- ` 前缀 + 竖线分隔的字段串」 ⇒ 企微客户端显示字面 `**`/`-`。P1-1 修复时明确注意到"desc 不解析 markdown"（完整列表链接特意不写成 `[文案](url)`），但标题加粗与条目前缀未一并处理。 |
| 文件:行 | `renderer_wecom_card.py:106-118`（`_render_list` 的 `**{block.title}**` 与 `- ` 前缀）。 |
| 证据 | `p2_probe.py`：7 个 ListBlock 事件卡片 desc 含 `**`（`card_literal_asterisks=True`），例：`"**失败明细（标准号 / 标准名 / 错误类型 / 说明）**（共 2 条）"`。 |
| 影响面 | 7 个 ListBlock 事件（D1 成立时随卡片一起不可见，但即使卡片恢复也会显示）。 |
| 修复方向 | 卡片 `_render_list` 不输出 `**`/`- `，改 `• ` 与纯文本标题；新增 2 例断言 card desc 不含 `**`。 |

### D5（P2，残留/新发现）卡片 body-only 正文 140 字符硬截断

| 项 | 内容 |
|---|---|
| 现象 | `render_card()` 在"无 blocks 且 body 非空"时执行 `items.append({"title":"","desc": str(message.body)[:140]})`——**硬截断且不 `textwrap`**；块行路径则是 `textwrap.wrap` 不丢内容。同一渲染器两条路径口径不一致。 |
| 文件:行 | `renderer_wecom_card.py:57-58`；对照 `:50-56`。 |
| 证据 | `p2_card_edge.py`：300 字符 body-only → 卡片 desc **140 字符**（尾部丢失），TG 同消息 **309 字符**全文。 |
| 影响面 | 目前 44 事件中 body-only 的仅 `task_progress`（正文模板短，实测 1 条 40 余字符，不触发）；但渠道测试消息/未来 body-only 事件会触发。 |
| 修复方向 | 同块行逻辑：先 `textwrap.wrap(..., width=…)` 再逐条输出；或直接复用 `split_for_channel` 的字节口径。 |

### D6（P2，新发现）卡片单条 desc 宽 140 字 > 官方"建议不超过 112 个字"

| 项 | 内容 |
|---|---|
| 现象 | `textwrap.wrap(..., width=140)`；官方 `vertical_content_list.desc` 说明为"二级普通文本，**建议不超过 112 个字**"（建议值，非硬限）。中文 140 字约 420 字节，接近/超出建议。 |
| 文件:行 | `renderer_wecom_card.py:54`。 |
| 证据 | `p2_card_edge.py`：300 字单行 → desc 宽度 `[140,140,20]`。 |
| 修复方向 | 宽度改 112（或按字节 336），与官方建议对齐；1 例断言。 |

### D7（P2，上一轮已登记，本批未修）横切三项

| 项 | 现象 | 文件:行 | 证据 |
|---|---|---|---|
| 聚合后 `event_type` 变类别名 | `_send_merged(event_type, …)` 的 `event_type` 来自 `aggregate_keys.events_in_group()`；日常桶键 `2␟daily␟u0` ⇒ 落库 `event_type="daily"` | `aggregate_buffer.py:449`、`aggregate_keys.py:111-127` | 上一轮生产实证（`daily` 92、`batch_summary` 1499…）；本轮代码未变 |
| 聚合摘要首行退化为级别前缀 | `_build_summary` 多条时取 `render(msg).split("\n")[0]`，未跳过 `level_prefix` 行 | `aggregate_buffer.py:490-514` | 上一轮生产实证 `id=4619` body=`📦 聚合通知（2 条）\n• ⚠️ 警告\n• ⚠️ 警告`；本轮代码未变 |
| 日志接口 `level` 恒 info | `_business_level(event_type)` 拿业务事件名与类别名比较 | `docker/api/notification_logs.py:133-139` | 静态代码复核（本轮代码未变）；与渠道无关但同属"严重度信息丢失" |

### D8（P2，残留）模板口径瑕疵（渠道无关）

| # | 项 | 现象 | 文件:行 |
|---|---|---|---|
| 1 | `normalize_failed` 计数/明细口径不一致 | 正文用 `total=len(parsed_list)` ⇒ "2 条标准规范化失败"，但 `failed_items` 只带"当前正在处理的那条" ⇒ 明细块"（共 1 条）"；用户看到"2 条失败"却只有 1 条明细 | `_organize.py:485-490`、`_builders_task_results.py:204-226` |
| 2 | `download_started` 缺「结果」 | 仍只有"标准号：…"，无排队/预期信息（结果由 complete/failed 承载） | `_builders_batch_download.py:89-110`（上一轮判定，本轮输出复核一致） |
| 3 | `validity_system_failed` 弱对象 | 仍只有"有效性检查系统级失败 / 错误：系统异常已记录日志"，无站点/阶段上下文 | `_builders_validity.py:240-257` |
| 4 | `security_password_changed` 弱结果 | `sessions_revoked=True` 时不显示"已撤销会话数"（输出仅账号+来源 IP+提示） | `_builders_system_security.py:91-95` |
| 5 | `security_token_refreshed` 弱对象 | 对象=API 静态令牌（上一轮判定"系统级可接受"） | `_builders_system_security.py:107-132` |
| 6 | 能力自述冲突 | `supports_callback`：wechat 渠道 False vs `interaction` 注册表 True | `channels/wechat.py:238-250` vs `interaction.py:51-57` |
| 7 | 文档数量漂移 | 覆盖度矩阵仍写"41 事件"（实际 44） | `docs/governance/notification_coverage.md:31` |

### D9（P3，死路径，新观察）`open_logs` 动作永不触发

`_links.attach_web_actions()` 仅在 `message.failed_items` 非空时追加 `open_logs`（`_links.py:103-106`），但**全库没有任何通知构建器设置 `NotificationMessage.failed_items`**（grep `failed_items=` 无命中；失败明细都放进 `ListBlock`）⇒ `open_logs` 永不产生。副作用（正面）：`jump_list` 最多 2 条（`详情`+`查看详情`），未触及官方 ≤3 上限。修复方向：要么给构建器补 `failed_items`，要么删除该死分支并明确"只保留 `view_detail`"。

---

## 5. 结论：P1-6 是否可闭合

### 5.1 判定：**不可闭合**

- **可闭合的部分（已完成）**：上一轮列出的 P0-1、P0-2、P0-3、P1-1、P1-2、P1-3、P1-4、P1-5 **在渲染器/构建器代码层全部成立**（27/27、7/7、7/7、5/5、TG 不崩、704 输出 0 异常/0 缺键）。
- **阻塞闭合的部分**：① **D1**——企微卡片报文不满足官方必填/条数契约，卡片路径大概率整体不可用，卡片的字段修复在生产上**可能从未生效**（上一轮 §7.2-1 的留白项，本轮已取证为缺陷）；② **D2**——TG 在 `web_base_url` 配置后会因未转义链接行**整条丢失 7 类事件**；③ **D3**——降级文本是 markdown 源码，是"降级为文本"这一实际路径上的用户可见退化。
- **判定口径**：P1-6 的验收判据是"**用户实际收到的企微信息量不少于 TG**"，而不是"渲染器 JSON 里字段齐全"。当前生产（`0e92e5d2`）连渲染器修复都没有；本地 HEAD 在"卡片被平台接受"这一前提未证实前，也不能宣称闭合。

### 5.2 剩余工作量估计

| 项 | 涉及文件 | 预计代码量 | 新增/改用例 | 备注 |
|---|---|---|---|---|
| D1 卡片形态（三选一，需用户裁定） | `renderer_wecom_card.py` +（方案 A）`channels/wechat.py` | 60–150 行 | 6–8 例 | **决策点**：A 改 `msgtype=markdown`（最小、推荐）/ B 补齐 `news_notice` / C 换 `text_notice` |
| D2 TG 链接行转义 | `renderer_base.py` + `renderer_telegram.py` | 10–20 行 | 2–3 例 | 加可覆盖钩子，勿在基座里直接转义（其它渠道不需要） |
| D3 降级消息类型 | `channels/wechat.py` | 15–25 行 | 2–3 例 | 改 `msgtype=markdown` 或纯文本渲染 |
| D4 卡片字面 markdown | `renderer_wecom_card.py` | ~5 行 | 2 例 | `_render_list` 去 `**`/`- ` |
| D5 body-only 截断 | `renderer_wecom_card.py` | ~5 行 | 1–2 例 | 复用 `textwrap` |
| D6 desc 宽度 112 | `renderer_wecom_card.py` | 1 行 | 1 例 | |
| D7 聚合/日志横切（上一轮 P2） | `aggregate_buffer.py`、`docker/api/notification_logs.py` | 15–25 行 | 2–3 例 | 可另立 P2 批次 |
| D8 模板口径残留 | `_organize.py`、`_builders_task_results.py`、`channels/wechat.py` | ~10 行 | 2–3 例 | 含弱项修补（产品可裁定不做） |
| D9 `open_logs` 死路径 | `_links.py` 或构建器 | ~5 行 | 1 例 | 低优先 |
| **合计** | **5–6 个文件** | **约 120–250 行（含测试）** | **约 20–25 例** | 另需 **1 次维护窗口真机验收**：企微应用消息 + TG 各发 1 条（抓 `errcode` / 确认 TG 400 消失），并要求生产部署到含修复的提交 |

### 5.3 建议落地顺序（关键路径）

1. **先裁定 D1 的卡型方案**（A/B/C）——它决定后续 D4/D5/D6 是否还需要做（若选 A `msgtype=markdown`，D4/D5/D6 全部消失，D3 同时被解决）。
2. **D2**（TG 转义）与 D1 无依赖，可并行；改动小、风险低，建议**下一批即修**。
3. 部署 + 真机验收：验证 ① TG 收到 `auto_backup` 成功行（生产 `notification_log` 新行 success）；② 带 link 事件 TG 不再 400；③ 企微侧同一条消息的实际形态（卡片 or markdown/text）与信息量。
4. 最后处理 D7/D8/D9（不影响 P1-6 主判据）。

---

## 6. 与上一轮结论的对照（本轮修正）

| 上一轮结论 | 本轮结果 |
|---|---|
| 企微卡片 34/44 事件至少丢一个核心字段（级别 27/链接 7/列表 5） | **字段层修正为 0/44**（27/27、7/7、7/7 全部出现）；但**卡片形态整体可用性**存疑（D1），若卡片被拒收则这些字段随卡一起不可见 → 实际交付物是降级文本 |
| TG 已对齐（仅 `auto_backup` 反向缺陷） | **不成立**：TG 另有 D2（链接行未转义，base 配置时 7 事件整条丢失） |
| 企微卡片平台条数/长度上限未取证（§7.2-1） | **已取证**：`vertical_content_list` ≤4、`jump_list` ≤3、`card_image`/`image_text_area` 必填其一、`card_action` 必填；当前实现不满足（D1） |
| P1-2（降级文本 2000 字符截断）已修即闭合 | 分段已修，但**消息类型选错**（`text` 不渲染 markdown）⇒ 用户可见格式仍退化（D3） |
| 生产与本地的通知子系统源码一致（`0e92e5d2`） | **已不成立**：生产仍 `0e92e5d2`，本地 HEAD 领先 7 文件 +182/-41（修复未部署） |
| 5 个「缺对象」事件为 P1 级模板缺口 | 已修；`normalize_failed` 仍有计数/明细口径不一致（D8-1） |

---

## 7. 复现方式与未取证项

### 7.1 复现命令（全部只读；产物在仓库外 `C:\Temp\`）

```powershell
cd D:\PilotStd
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe C:\Temp\p2_probe.py        # 44 事件 × 2 场景 × 8 输出 → p2_render.{json,md}
.\.venv\Scripts\python.exe C:\Temp\p2_analyze.py      # 缺口/分片/泄漏汇总
.\.venv\Scripts\python.exe C:\Temp\p2_table.py        # §2 表行生成
.\.venv\Scripts\python.exe C:\Temp\p2_card_edge.py    # 卡片边界/截断/TG 详情行
.\.venv\Scripts\python.exe C:\Temp\p2_card_limits.py  # 真实多明细载荷的 vertical_content_list 条数
.\.venv\Scripts\python.exe C:\Temp\p2_prod_menu.py    # 生产只读 GET（health 另用 /api/health）
# 回归（只读，不写仓内文件）
.\.venv\Scripts\python.exe -m pytest tests\test_notification_wechat_card.py tests\test_notification_link_level_render.py tests\test_notification_renderer.py tests\test_notification_security_channel_form.py tests\test_security_notifier_degradation.py tests\unit\test_i18n_completeness.py -q -p no:cacheprovider
```

### 7.2 未取证项（明确留白，不作结论）

| # | 项 | 原因 |
|---|---|---|
| 1 | 企微对当前卡片报文的**实际 errcode**（40058？是否真拒收） | 本任务禁止发网络/发测试消息；需维护窗口发 1 条抓响应。D1 结论的"实际拒收"目前是**文档契约 + 错误码口径推断**，不是实测 |
| 2 | `notification.web_base_url` 的生产取值 | 只读 `GET /api/notification/config` 只返回 `enabled/quiet_hours/channels/rules`（不含该键）；`GET /api/notification/menu/status` 也无绝对 URL 可反推；`/api/health` 只给版本。⇒ D2 的触发条件在生产是否成立仍未知 |
| 3 | 生产渠道侧最终收到的原文/截图 | `notification_log` 只存构建器/聚合摘要的 `title`/`body`，不存各渠道渲染后文本；企微卡片是否成功无法从日志区分 |
| 4 | 生产部署状态对 P1-6 的影响 | 生产 `version=0e92e5d2`（修复前）；本轮所有"已闭合"仅代表本地 HEAD |
| 5 | 企微 `text_notice` 卡型字段 | 本仓无语料，未评估其是否更适合（D1 方案 C 的可行性需另做取证） |

---

*本报告只写本文件；未修改任何代码/配置/其他文档，未 commit/push。所有渲染结论均来自当前 HEAD 的真实构建器 + 真实渲染器实跑（`C:\Temp\p2_*.py`），所有外部文档结论带链接。*
