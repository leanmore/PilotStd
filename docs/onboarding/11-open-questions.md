# 11 · 待决策问题记录（认知阶段）

> 用途：把“已查清事实、但需要用户/产品决策”的问题集中记录，避免在认知阶段误改代码。  
> 状态说明：`待决策` = 事实已查清，等用户拍板；`观察中` = 先不动；`已关闭` = 已决定/已修复。

---

## Q1. 路由 v2 的观察数据为什么一直是 0

**状态**：已决定 C；已加 `v2_skipped` 采样（cache_hit/preferred_site），真实 ≥1000 样本待验证环境

### 已查清的事实

1. v2 只由环境变量开启：
   - `router_v2.is_v2_enabled()` 仅当 `ROUTING_ENGINE_VERSION == "v2"` 返回 True；
   - 默认 v1。
2. 部署配置没有开启：
   - `docker-compose.yml` / `.env` 中没有 `ROUTING_ENGINE_VERSION`；
   - 线上 `app.log` 没有 `[v2 Router]` 行。
3. 本地埋点日志 `logs/router_v2_decisions.jsonl`：
   - 2133 条，全部 `routing_version=v1`；
   - v2 为 0；
   - 时间范围 2026-08-18 ~ 2026-11-06。
4. ADR-015 / 归档评估报告：
   - v2 灰度样本数 0；
   - 清理 v1 的安全阈值是 ≥1000 条 v2 样本；
   - 阶段三“灰度集成”进行中，阶段四“数据闭环回填”未完成。
5. 即使开启 v2，也有路径不产生 v2 记录：
   - `_query_one()` 先查缓存，缓存命中直接返回，绕过 v2 分支；
   - `preferred_site` 非空时不走 v2；
   - `record_decision()` 是异步 daemon 写盘，进程退出无 flush；
   - 写盘失败只记 `debug`，主链路不可见。

### 结论

不是“埋点模块坏了”，而是 **v2 从未真正运行过**；采样/回填闭环也没有执行。即使开启，缓存命中/指定站点也会漏采。

### 待决策选项

- **A. 冻结 v2**：承认它只是 ADR 实验，当前生产认知按 v1；不投入采样。
- **B. 受控采样**：在验证环境设置 `ROUTING_ENGINE_VERSION=v2`，关闭缓存/指定站点，跑 ≥1000 条，确认写入与回填，再评估 v1 清理。
- **C. 先修采样缺陷**：让缓存命中/指定站点也能记录“未进入 v2”的原因，再决定是否采样。

> 不建议在未采样的情况下直接切 v2 默认。

---

## Q2. `query.use_announcement_match=false` 的语义

**状态**：未决：先查清缓存机制；见 Q7

### 已查清的事实

- 该配置用于**查询阶段**，不是公告抓取阶段。
- `true`：`_query_via_cache()`，逐条先调 Web `/api/announce/lookup`，未命中再降级 `QueryEngine`；
- `false`（默认）：`_query_via_engine()`，直接 `QueryEngine`；
- 但 `QueryEngine` 内部 `CacheRepository.get()` 仍会：
  1. 查 `standard_info_cache`；
  2. 不命中回退 `announcement_match`；
  3. 再不命中才查实时适配器。
- 因此：**`false` ≠ 完全不使用公告缓存**；它只关闭“公告缓存优先模式”。
- 只有 `query.use_cache=false` 才会关闭缓存回退。
- `query.announcement_api_key` 为空时，`true` 也会全部 miss，退化为引擎查询。

### 公告抓取的真正开关

- 公告抓取：`tasks.auto_announce_enabled` + `tasks.auto_announce_cron`；
- `announcement.enabled` 只在 `pending_query_dialog` 中使用，不是全局抓取开关；
- 公告适配器是 3 个 SAMR 源（GB/HB/DB），与 21 个查询适配器、1 个下载适配器不是同一套。

### 待决策选项

- **A. 保持现状**：`false` = 不走公告优先，但缓存仍可回退 `announcement_match`；在文档中写清。
- **B. 改成完全隔离**：`false` = 连 `announcement_match` 也不读；需要改 `CacheRepository` 的调用参数/开关，并补测试。
- **C. 改名**：把配置改名为 `query.prefer_announcement_cache`，减少歧义（涉及配置兼容/迁移）。

> 当前默认行为是 A；如果产品语义要求 B，需要单独立项。

---

## Q3. 非 GB / 采标 GB 的下载能力

**状态**：已决定：A（接受边界，后续有渠道再补）

- 非 GB：没有下载适配器，是当前设计边界；
- 采标 GB：openstd 的“采”标记 + 版权限制，按设计跳过；
- 如果业务要求可下载，需要新增合法来源/授权适配器，不能靠重试修；
- 详见 [`08-known-boundaries.md`](08-known-boundaries.md) #14。

---

## Q4. `validity.checked_count` 与检查历史不一致

**状态**：待查：Web 页面显示与通知消息不一致

- 线上 `/api/validity/config`：`checked_count=0`、`round_completed=false`；
- 但 `/api/validity/history` 有 15 个检查日期，例如 2026-11-05 checked=49 / changed=7、2026-11-04 checked=240 / changed=39；
- 可能原因：手动 `/api/validity/run` 传 `update_counters=false`；定时任务才传 true；或计数器按“轮次”而非“历史”统计；或配置保存/重建时被重置；
- 用户补充：Web 页面显示的数字/状态，与通知渠道消息不一致；两者可能相关，也可能独立，合并跟踪（另见 Q8）；
- 需要先查清“计数器语义”，不能直接把 0 当成“没检查”。

---

## Q5. 通知重试覆盖不一致

**状态**：已决定：A（补重试）；待执行

- 渠道基座 `_with_retry` 已覆盖：
  - 企微应用/文本路径；
  - 钉钉 Webhook 文本；
  - 飞书 Webhook 卡片；
  - Telegram。
- 但以下路径目前**没有**走 `_with_retry`：
  - 钉钉企业级互动卡片：`DingTalkChannel.send()` → `_send_card()`，内部直接 `requests.post`；
  - 飞书应用消息：`FeishuChannel.send()` → `_send_app()` → `_post_app_message()`，单次请求。
- 影响：这两种形态遇到 429/5xx/网络抖动时不会重试，和基座注释“四家统一重试”不一致。
- 需要决定：补齐重试，还是明确写成“仅 Webhook/文本路径保证重试”。

---

## Q6. `QueryResult.hcno` 的历史注释仍把 pid 当 hcno

**状态**：已处理：注释已修正；保留手工显式 hcno；未改下载行为

- `pilotstd/query/models.py:25-26` 注释写“新平台 hcno = std_gov 查询结果的 pid，直接用于下载”；
- 这是历史错误假设，与当前下载实现相反：
  - `openstd_download._resolve_target()` **不读取** `task.query_result.hcno`；
  - 唯一合法来源是 `task.extra["hcno"]`（手工/GUI）或 openstd 搜索页按行匹配；
  - `TestHcnoResolution::test_query_result_pid_is_not_used_as_hcno` 已钉住行为（49 passed）。
- 风险：后来维护者若信了注释，可能重新引入 pid 兜底，导致“验证码失败”假象。
- 建议：只改注释，说明“`QueryResult.hcno` 是按站点的详情 ID，不是 openstd hcno”；不改行为。等批准后做。

---

## Q7. 查询缓存是不是“热缓存”？怎样保证最新？

**状态**：已修本地代码（stale 跳过 + put 置 fresh）；待部署/观察

### 已查清的事实

- 查询缓存不是进程内热缓存，而是 **SQLite 持久表**：
  - `standard_info_cache`：网络查询结果；
  - `announcement_match`：公告匹配结果，作为第二回退。
- `CacheRepository.get()` 只按 `(standard_number, source_site)` 读表，**不检查**：
  - `cached_at`；
  - `data_state`；
  - `source_version`；
  - `_active_ttl` / `_inactive_ttl`（这两个参数已定义但未在 `get()` 使用）。
- `CacheManager` 是另一套“版本 + LRU”管理器，能把缓存标记 stale，但 `CacheRepository` **没有调用它**。
- 因此当前“缓存最新”没有硬保证：只有显式 `refresh()`、`query.use_cache=false` 或 `force_refresh` 才能绕过/清除。

### 只读统计（prebatch.bak + live）

| 指标 | 结果 |
|---|---|
| `standard_info_cache` 行数 | 517 |
| `cached_at` > 7 天 | 496 |
| `cached_at` > 30 天 | 417 |
| `cached_at` 中位数 | 约 103.8 天 |
| `data_state` | stale 515 / valid 2 |
| `source_version` | 517 条全为空串 |
| live `/api/cache/stats` | `standard_info_cache` 517 条，全部 stale |
| `announcement_match` 行数 | 92 |
| 两表标准号交集 | 67 |
| 仅 `standard_info_cache` | 369 |
| 仅 `announcement_match` | 25 |
| 重合度（按标准号） | 67/517 = 13.0%；67/92 = 72.8% |

> 注意：这是**表覆盖重合度**，不是实际查询命中率；当前没有 per-site cache hit 指标，不能把 13% 当“命中率”。
>
> 结论：查询缓存不是“热缓存”，而是长期未校验的 SQLite 持久缓存；417 条超过 30 天，且 `data_state` 已 stale 仍可能被 `CacheRepository.get()` 返回。

### 需要决定

- A. 查询缓存加 TTL/`data_state` 校验，过期自动回源；
- B. 查询缓存接入 `CacheManager` 的版本校验；
- C. 保持现状，只靠显式刷新；
- D. 先做只读统计：多少缓存超过 7/30 天、多少 stale。

> 用户已明确“重点保证缓存最新”，建议至少做 A/B 之一；先记录，待认知补齐后出方案。

---

## Q8. Web 页面显示与通知消息不一致

**状态**：待查

- 用户反馈：Web 页面显示的数字/状态，与通知渠道收到的消息不一致；
- 可能差异源：
  - Web 看 `file_index` / `standard_validity`，通知看事件 payload；
  - 通知按批次/用户聚合，Web 按当前库统计；
  - 通知发送时间与页面刷新时间不同；
  - 归档通知按“每次调用”计数，Web 按最终文件数。
- 下一步：用同一批次、同一时间点，对照页面数字、`notification_log` payload、`file_index`/`validity` 三处；先查清再定是否 bug。

### 已发现的硬矛盾（2026-11-07 实测）

| 接口 | 结果 |
|---|---|
| `/api/notification/logs`（当前用户） | total **578** |
| `/api/notification/logs?is_read=false`（当前用户） | total **7** |
| `/api/notification/unread-count` | **1441** |

未读数大于列表总数，且大于当前用户未读条数，属于明显不一致。

代码原因：

- `get_logs()` 有 `user_id` 过滤；
- `get_unread_count()` 没有 `user_id` 过滤，直接 `COUNT(*) WHERE is_read=0`；
- `mark_logs_read()` 也不按用户过滤，传入空 ids 时更新全表。
- 结果是“列表按用户、未读数按全库”，多用户/历史数据下 badge 会大于列表。

### 另一条证据：11/7 批次通知没有出现在 `notification_log`

- 线上 `/api/notification/logs` total **578**，最新一条 `sent_at` 为 **2026-11-03**；
- 其中 `archive_complete` 仅 **22 条**（11 个 correlation_id × 2 渠道），没有 2026-11-07 批量归档的记录；
- 但 `app.log` 在 2026-11-07 08:10–08:15 记录 **1196 条**通知（598 次归档 × 2 渠道）；
- 结论：**渠道可能发了，但 `notification_log` 没留下对应批次记录**，或日志被清理/恢复过；这使“页面 vs 通知”无法按同一批次对账。
- 需要区分：日志清理保留期、DB 恢复、通知写库失败、批次被聚合后只写一条。

### 另一条证据：归档通知的“内容”没有完整落库

- `archive_complete` builder 把“已归档 N 个文件”放在 `TextBlock`，不是 `body`；
- `notification_log` 只存 `title` / `body`，不存 blocks；
- 实测 `archive_complete` 的 `body` 为空、`task_context` 为空，只剩 `correlation_id`；
- 因此 Web 日志页看不到“归档了多少”，而通知渠道消息里有 count block；页面统计与通知内容天然对不上。

---

## 维护规则

- 任何“待决策”项在用户拍板后改为“已关闭”，并写明决定/日期/影响；
- 不把待决策项直接写成代码 TODO；
- 不在未批准前修改行为。
