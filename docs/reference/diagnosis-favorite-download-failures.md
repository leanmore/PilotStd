# 诊断报告：收藏标准下载失败原因分类与可否重试

> **任务性质**：诊断（**零代码改动、零写库操作**）。所有结论基于实际代码阅读 + 生产实例只读查询 + 47,112 行生产日志。
> **诊断时间基准**：HEAD `a8b81adf`；被诊断实例 `http://192.168.1.18:9028`，容器版本 `17d68e58`。

---

## 0. 数据来源与方法（先看这条，它决定后面数字的可信度）

### 0.1 ⚠️ 仓库内的数据库是空的，真实数据在局域网 Docker 实例

| 位置 | 实测 |
|---|---|
| `D:\PilotStd\data\pilotstd.db`（`get_db_path()` 的返回值，来源 `pilotstd/core/config/paths.py:49-51`） | `user_favorites`=**0**、`favorite_downloads`=**0**、`announcement_record`=**0**、`file_index`=1 |
| `data\_v57f.db` / `data\_v57c_test.db` | 同样 0 条收藏 |
| `data\pilotstd.db.backup_20260708`（135MB，2026-07-08 生产快照） | **无** `user_favorites`/`favorite_downloads` 表（v44 迁移之前），`announcement_record`=227390 |

方法：把 db + wal + shm **复制到 `C:\Temp`** 后以 `file:...?mode=ro` **只读**查询（原库未打开写入）。

### 0.2 真实数据来源

全部来自 `docker-compose.yml:16` 的实例 `http://192.168.1.18:9028`，用 `config/docker_creds.json` 的账号登录取 session cookie，**只读 GET**：

1. `POST /api/login`（form）→ 200，role=admin
2. `GET /api/favorites`、`GET /api/favorites/export?format=json`、`GET /api/favorites?status=<各状态>`
3. `GET /api/users` → 全库**仅 1 个用户**（`id=1`）→ 故该用户 105 条 = `user_favorites` 全表
4. `GET /api/logs/rotated` + `GET /api/logs/rotated/{app.log,app.log.1..10}`（分页 1000/次）+ `GET /api/admin/logs/app` → 共 **47,112 行**生产日志（2026-09-10 ~ 2026-10-02）

### 0.3 没能用的更强手段（如实说明）

`POST /api/admin/db/query`（`docker/api/admin_db.py:180`）可直接在容器内跑任意 SELECT，**但成功路径必然 INSERT 一行 `audit_logs`**（`admin_db.py:251` `write_audit`），违反"禁止写库"约束 → **未调用**。

**因此**：分类计数是用 `GET /api/favorites` 返回的 JSON 经 Python `collections.Counter` 分组，**不是 SQL 聚合**；SQL 仅用于证明"仓库内 DB 为空"。

---

## 1. 从代码层面枚举：所有会导致收藏下载失败/中断的路径

链路入口：APScheduler cron `auto_archive_retry` 每天 **04:00**（`docker/app.py:157-161`、`docker/scheduler.py:287`）→ `process_chain()`（`pilotstd/services/favorite_chain_processor.py:320`）。

### 1.1 "根本没尝试"的闸门（非失败，但用户看起来"没下载"）

| # | 触发条件 | 代码位置 |
|---|---|---|
| G1 | `standard_type != 'NationalStd'` → 终态跳过 | `pilotstd/tasks/favorite_download.py:230-232`（`FavoriteSkip`） |
| G2 | 冷却期未过（`publish_date` 距今 < **28 天**） | `favorite_chain_processor.py:30,96-108`（`:104` SQL 条件） |
| G3 | `status` 不在 `('pending','failed')` 内 —— **`abandoned`/`done` 永不入选** | `favorite_chain_processor.py:101` |
| G4 | `retry_count >= MAX_RETRIES(7)` | `favorite_chain_processor.py:29,103` |
| G5 | 采标标准（`is_adopted`）→ 版权受限，终态跳过（**对照项**） | `pilotstd/download/engine.py:76-77`、`favorite_download.py:240-241,258-259` |

### 1.2 下载阶段真正抛错 / 置 `failed` 的路径

| # | 原因 | 触发条件 | 代码位置 |
|---|---|---|---|
| D1 | 会话层 100% 请求失败（历史 bug） | monkeypatch 委派错误 → 每个请求 `AttributeError` | `pilotstd/download/session.py:24-41`（docstring `:30` 记录"2026-09-20 生产日志 427 条，收藏下载 0 成功"） |
| D2 | 没有匹配的下载适配器 | `task.source_site` 无对应 adapter 且 `can_handle` 全 False | `engine.py:78-80`、`:120-124`（映射表 `:334-336`） |
| D3 | 标准未被 openstd 收录 / 标准号写法不匹配 → 拿不到 hcno | 搜索页无同号行 | `download/adapters/openstd_download.py:130-158`（`:152-157`）、`:177-184` |
| D4 | hcno 搜索页请求异常 / HTTP≠200 | 网络或站点异常 | `openstd_download.py:143-149` |
| D5 | 网络类异常（超时/连接失败）退避重试 3 次后仍失败 | `_FETCH_MAX_ATTEMPTS=3`、退避 `(2,4)`s | `engine.py:26-28,83-100`；另一路径 `:131-140`（`RETRYING`） |
| D6 | 适配器业务失败（不重试） | 适配器返回空且置了 `task.error_message` | `engine.py:96-97` |
| D7 | 验证码图片获取失败 | GET `/gc` 抛异常 | `openstd_download.py:326-329` |
| D8 | 验证码识别失败（每轮 2 次） | ddddocr 返回非 4 位且无 callback | `openstd_download.py:355-367` |
| D9 | 验证码提交失败 | 2 次 `verifyCode` 均非 `success` | `openstd_download.py:369-394`（`:21-25,88` 记录该事故） |
| D10 | `viewGb` 异常 / HTTP≠200 / 200+0 字节 / 非 PDF | 会话未授权、暂无全文、端点迁移 | `openstd_download.py:262-266`、`:268-276`、`:279-283`、`:301-308`（整轮重试 `_VIEW_ROUNDS=2`） |
| D11 | 引擎取字节后不落盘为空 | `fetch_bytes` 返回空 | `favorite_download.py:249-262` |
| D12 | 数据库写入异常（如 `UNIQUE` 竞态） | `Database.execute()` 捕获 sqlite 异常后抛 `DatabaseError`；**真实触发点可以是构造 `StandardManager()` 时**，此时下载还没开始 | `pilotstd/core/db/database.py:225-231`；实测触发点 `pilotstd/query/daily_quota.py:45,63-74`（`_ensure_today_rows`）经 `manager/facade/_base.py:175` 被调用 |
| D13 | 记录不存在 / 标准号为空 | 查不到 `announcement_record.id` 或 `standard_number` 空 | `favorite_download.py:326-332` |
| D14 | 拿不到"已收录"证据（查询链路失败） | `_load_cached_query_result`/`_query_std_gov` 均返回 None | `favorite_download.py:234-239`、`:50-78` |
| D15 | 线程级异常 | `run_paced_batches` 吞掉 worker 异常并落 `None`，该条**既不计失败也不进汇总** | `engine.py:290-297` + `favorite_chain_processor.py:139` |

### 1.3 "下载成功但归档/入库失败"（与 D 类表现不同）

| # | 原因 | 触发条件 | 代码位置 |
|---|---|---|---|
| A1 | inbox 落盘失败 | 磁盘满/权限/路径异常 | `favorite_download.py:263`，兜底 `:395-402` |
| A2 | 标准号无法解析（归档器入口） | `parse_standard_number()` 返回 None | `favorite_download.py:298-300` |
| A3 | 归档器调用抛异常 | `mgr.archive_standards()` 异常 | `favorite_download.py:304-308` |
| A4 | **归档超时**：60 秒内 `file_index` 未登记该标准 | 轮询 30×2s 未命中 | `favorite_download.py:367-391`（`:381-391` 写 failed + `归档超时：文件未被归档器登记进索引`） |
| A5 | 归档器内部失败（目标已存在/去重/移动失败） | `organizer/mover.py` 各分支 | `favorite_download.py:305`（被 A3 捕获） |

**用户可见表现的差别**：D 类在 `favorite_downloads` 里是 `failed`/`abandoned`，文件**从未落盘**（`local_path` 空）；A 类会先写 `downloading → archiving`，文件**已经躺在 inbox**，但索引没登记，最终 failed —— 即"**下载成功、归档失败**"。**A4 是历史数据里唯一实际发生的归档失败。**

**另外两个"看起来失败其实成功"的显示缺陷**（代码事实，实测可见）：
- **成功分支不清 `error_message`**：`favorite_download.py:371-375`（done 路径）与 `:276-280`（复用路径）都只写 `status`/`local_path` → 已完成项仍挂着旧错误文本。
- **`/api/favorites` 返回的是 `user_favorites.local_path`**（v44 解耦后恒为 NULL），而不是 `favorite_downloads.local_path`：`docker/api/favorites.py:275-284`（`_DOWNLOAD_FIELDS` `:252-257` 里没有 `fd.local_path`）→ 已完成项在列表里**看不到归档路径**。

---

## 2. 实际发生次数（真实数据）

### 2.1 总量（`GET /api/favorites`，105 条）

- 全部 `user_id=1`、全部 `standard_type='NationalStd'`
- `user_favorites.status`：`pending` **105/105**
- `favorite_downloads.status`：**`abandoned` 99**，**`done` 6**
- 105 条**全部**有队列行（`download_status` 为 null 的 0 条）

### 2.2 失败原因分类（按次数降序；排除项单列）

| 排名 | 原因 | 次数 | `download_status` | `last_attempt` |
|---|---|---|---|---|
| **1** | **会话缺陷** `'super' object has no attribute 'request'` | **61** | abandoned | 全部 2026-09-20 |
| **2** | **旧版"取下载链接"实现失败** `无法获取下载链接: <标准号>` | **28** | abandoned | 08-28:2, 08-29:6, 08-31:6, 09-01:10, 09-02:4 |
| **3** | **归档超时** `归档超时：文件未被扫描器处理`（**实际已成功**） | **6** | **done** | 全部 2026-09-28 |
| **4** | **数据库竞态** `数据库操作失败`（favorite_id=38 / GB/T 4842-2026） | **1** | abandoned | 2026-09-20 |
| — | （对照，**排除**）`采标标准，版权受限，自动跳过` | 9 | abandoned | 09-20:6, 09-26:3 |

**61 + 28 + 6 + 1 + 9 = 105** ✅（与全表吻合）

### 2.3 日志侧交叉验证（47,112 行，2026-09-10 ~ 10-02）

| 观测 | 数据 | 与代码/数据的印证 |
|---|---|---|
| `'super' object has no attribute 'request'` | **427 行**；09-14~09-20 **每天恰好 61 行**；去重 `favorite_id` **62 个** | 与 `session.py:30` 记录的"427 条"完全吻合 |
| `[链] 下载放弃（重试 7 次）` | **68 行，全部在 2026-09-20** | = 62 条会话受害者 + 6 条采标；与 `MAX_RETRIES=7`（`favorite_chain_processor.py:29`）对上 |
| `收藏归档超时` | **12 行**（09-26 六条、09-27 六条） | 同期 `viewGb 第1轮取到全文` 6 条（09-26 20:23、09-28 04:00）→ 证实"**字节下载成功、索引未登记**" |
| `[链] 处理完成`（每日） | 09-11~09-13 `0`；**09-14~09-20 每天 `68`**；09-21~09-23 `0`；09-24 `1`；09-25 `1`；09-26 `6` 与 `9`；09-27 `6`；09-28 `6`；**09-29~10-02 全部 `0`** | 09-14~09-20 是会话缺陷期；09-21 修复后无新受害者 |
| `verifyCode 结果` | `error` **16 行**（09-24:2、09-25:2、09-26:12）、`success` **11 行** | 09-24/25 的 2 次 error 让 `favorite_id=106`（GB 18047-2026）连挂两天；09-26 又让 favorite_id 1~5 与 106 共 6 条失败 |
| `数据库操作失败` | **7 行**（每天 04:00:00 的第一条），traceback 明确 | 见下 |
| `无法获取下载标识(hcno)` / viewGb 类失败 / OSError | **0 行** | 现网日志无此类 |

**数据库竞态的 traceback（原文）**：
```
sqlite3.IntegrityError: UNIQUE constraint failed: daily_quota.site_name, daily_quota.query_date
  File "/app/pilotstd/tasks/favorite_download.py", line 256, in download_to_inbox
    mgr = StandardManager()
  File "/app/pilotstd/manager/facade/_base.py", line 175, in _init_query_subsystem
    self._core.quota_tracker = DailyQuotaTracker(self._core.db, limits=daily_limits)
  File "/app/pilotstd/query/daily_quota.py", line 71, in _ensure_today_rows
```
→ 是 `StandardManager()` **构造期**被并发补行撞 `UNIQUE`，**下载尚未开始**。

### 2.4 28 条"无法获取下载链接"的标准号（完整）

```
GB/T 47914-2026, 47921-2026, 47881-2026, 47880-2026, 47877-2026, 47874-2026, 47832-2026,
GB/T 16923-2026, 8028-2026, 6396-2026, 2520-2026, 711-2026, GB/Z 184.2-2026,
GB/T 45779-2025, 47995-2026, 47991-2026, 23691-2026, 47992-2026, 36037-2026, 30825-2026,
29713-2026, 20671.11-2026, 20671.4-2026, 19019-2026, 14983-2026, 14180-2026, 10546-2026, 2653-2026
```

### 2.5 6 条 `done` 的完整失败史（同一条标准经历了 D9 → A4 → 成功）

标准号：`GB/T 2970-2026`、`GB/T 5613-2026`、`GB/T 7607-2026`、`GB/T 13237-2026`、`GB/T 7597-2026`、`GB 18047-2026`

时间线：09-24/25 验证码失败 → 09-26 04:00 验证码失败 6/6 → 09-26 20:23 六条 `viewGb 第1轮取到全文` 成功但 60s 内未登记 → `收藏归档超时` 6 条 → 09-27 04:00 再超时 6 条 → **09-28 04:00 全部成功**（日志：`归档完成: /standards/GB 国家标准/GBT 5613-2026 铸钢牌号表示方法.pdf` + `[链] 下载成功: record_id=1852896`）。

**其 `download_error` 仍是 `归档超时：文件未被扫描器处理`** —— 成功不清错（见 1.3）。

### 2.6 遗留字段（`user_favorites.error_message`，v44 之前的旧字段）

`'sqlite3.Row' object has no attribute 'get'` × 3（GB/T 7607/5613/2970-2026，旧代码 `row.get(...)`）、`无法获取下载链接` × 2（GB/T 7597/13237-2026）—— **全部是已 `done` 的记录**。

### 2.7 无法精确统计的部分（如实说明）

- 表里**没有 `failure_code` 结构化字段**（见 `_migrate_v44.py:26-40` 建表语句），`error_message` 是**自由文本** → 分类是靠**前缀分组**，可能存在近义文本被分到不同类的误差；
- `retry_count` **未在 `/api/favorites` 返回**，故"重试 7 次"是用日志反推的。

---

## 3. 每一类"重试是否有效"

| 类别 | 次数 | 判定 | 依据（代码 / 数据） |
|---|---|---|---|
| 会话缺陷 `'super'…request` | 61(+1) | **重试有效**（但需人工重新入队） | 根因修复 `21a34b36`(2026-09-21) 现为 `session.py:24-41`；该提交是部署版本 `17d68e58`(2026-10-01) 的**祖先**（`git merge-base --is-ancestor` exit 0）。修复后该串出现 **0 次**（09-21~10-02）。**不会自动重试**：`favorite_chain_processor.py:101` 只选 `pending/failed` |
| 旧版取链接失败 `无法获取下载链接` | 28 | **重试有效**（失败模式已不存在） | 该实现 `_get_download_url`（读 `standard_info_cache.result_json.download_url`，无行即 None）在 `70db4a9e` 引入、`a5a8f641`(2026-09-13) 整体替换为适配器字节抓取（当前 HEAD `git grep "无法获取下载链接"` **零命中**）。同为 `abandoned`，不自动重试 |
| 数据库竞态 `数据库操作失败` | 1 | **重试有效** | 修复 `3e23bbdf`(2026-09-21) 把补行改成 `INSERT OR IGNORE`（`daily_quota.py:71-74`），部署版本已含；09-21 后该错误 **0 次** |
| 归档超时 | 6 | **无需重试（已成功）** | 6 条 `download_status='done'`，09-28 04:00 已归档；修复 `cc8cc447`(2026-09-26) 让链路自己调 `archive_standards`（现 `favorite_download.py:286-309`） |
| 验证码失败（日志 9 次） | 0（终态） | **重试有效** | 根因是 `/bzgk/gb` 对 POST 的 301 降级（`openstd_download.py:21-25`），已由 `532d994f`(2026-09-26) 迁 `/bzgk/std` 修复；09-28 起 `verifyCode success` 11 次、`error` 0 次 |
| **采标版权受限（对照）** | 9 | **重试无效**（设计即终态） | `engine.py:31,76-77`、`favorite_download.py:25-33,240-241`、`favorite_chain_processor.py:255-259`（**一次即 abandoned**，不消耗重试窗口） |
| 磁盘 / 权限 / 依赖缺失 | **0** | 不适用 | 47k 行日志无 OSError / No space / Permission denied；`ddddocr` 实测正常工作（`识别: JDDR`、`RYQV`） |
| 无 hcno / 适配器不匹配 / 限流 / 超时退避 | **0** | 不适用 | 现网日志零命中；09-14~09-20 期间网络错误被会话缺陷掩盖 |

### 判断"重试有效"的最重要实测证据

修复落地后的 **2026-09-28 04:00** 运行：`[链] 处理完成: {'download': 6}` 且 **6/6 成功**（`viewGb 第1轮取到全文` + `归档完成` + `[链] 下载成功`）；而 09-29~10-02 每天 `{'download': 0}`（没有可处理记录）。

**即"能下的时候确实下下来了"** —— 这是"重试有效"最直接的证据。

---

## 4. 可操作建议

### 4.1 项目里有没有"重试"入口？

**没有**面向收藏下载的重试 API / UI / CLI。

| 事实 | 位置 |
|---|---|
| 唯一 retry 端点 `POST /api/tasks/{task_id}/retry` **只对 `task_queue` 生效**，与收藏链无关 | `docker/api/tasks.py:123-139`；UI 入口 `web/src/components/TaskManager.vue:90,175` |
| `pilotstd/cli/` 内 grep `retry|favorite|process_chain` **零命中** | — |
| 调度设置页只能改 cron / 开关，**不能立即触发一次运行** | `web/src/views/settings/SettingsTabSchedule.vue:149-156`、`pilotstd/core/config/defaults.py:112-113`（默认 `0 4 * * *` 启用） |

**状态机含义**（`favorite_chain_processor.py:32-40`）：`pending`/`failed` 会被 04:00 自动捡起；**`abandoned` 是终态** —— 除非人工改状态，**永远不会再试**。

### 4.2 批量处理 99 条 `abandoned` 的两条路（**均未执行任何写操作**）

**路 A（无需 DB 权限，逐条，走现有 API/UI）**：取消收藏 → 重新收藏
- `DELETE /api/favorites/{record_id}`（`docker/api/favorites.py:203-234`；`pending/abandoned` 分支直接 `DELETE`）
- `POST /api/favorites {record_id}`（`favorites.py:92-188`；`:151-166` 重新插入一条 `status='pending'` 的 `favorite_downloads` 行）
- 队列行会被级联删除：`favorite_downloads` 外键 `ON DELETE CASCADE`（`pilotstd/core/db/_migrate_v44.py:37`）+ `PRAGMA foreign_keys=ON`（`pilotstd/core/db/database.py:201`）
- UI 入口：公告详情页星标（`web/src/views/AnnounceDetail.vue:224` → `web/src/composables/useFavorite.ts`）
- ⚠️ **级联行为是代码推断**，未实测（实测会产生写操作）

**路 B（需人工授权 DB 写权限，一条 SQL）**：`POST /api/admin/db/query`（`docker/api/admin_db.py:180`）
```sql
UPDATE favorite_downloads
   SET status='pending', retry_count=0, last_attempt=NULL, error_message=NULL
 WHERE status='abandoned' AND user_id=1 AND standard_type='NationalStd'
   AND (error_message IS NULL OR error_message NOT LIKE '采标%');
```
⚠️ 该端点成功后会 INSERT 一行 `audit_logs`（`admin_db.py:251`），属写库，**需明确授权**。

### 4.3 建议处理顺序

1. **先重排 62 条会话受害者**（根因已修 + 部署版本已含 + 427 条日志证据链最完整）；
2. **再重排 28 条"无法获取下载链接"**（整段实现已被替换，同属"重试有效"）；
3. **跳过 9 条采标**（`GB/T 7584.1/2/6-2026`、`GB/T 18663.6-2026`、`GB/T 47161-2026`、`GB 20097-2025`、`GB/T 8335-2026`、`GB/T 8336-2026`、`GB/Z 184.1-2026`）—— 版权受限，人工线下取件；
4. **无需处理那 6 条 `done`**；但建议单独排工单修两个显示缺陷（成功不清 `error_message`：`favorite_download.py:276-280,371-375`；`/api/favorites` 取了 `user_favorites.local_path`：`docker/api/favorites.py:275-284`）；
5. **重排后看次日 04:00 的 `[链] 处理完成` 与失败明细**：
   - 若出现 `无法获取下载标识(hcno)`（`openstd_download.py:179-182`）＝ 该标准 openstd **未收录**（**永久**）；
   - 若出现 `采标标准，版权受限`（`engine.py:31`）＝ 转为版权受限（**永久**）；
   - 其余失败再进下一轮。

### 4.4 防护建议（只报告，不改）

**`abandoned` 无任何复活入口，是本次"很多收藏一直没下载"的关键放大器**：上游 bug 只持续约 7 天，但 **62 条记录被永久冻结**。

建议给收藏页加"**失败原因 + 一键重排**"入口（需另立工单）。

---

## 5. 需要用户补充 / 授权

1. **是否授权写操作**（路 A 的 DELETE+POST，或路 B 的 UPDATE）—— 否则 99 条 `abandoned` 只能人工逐条处理，且**没有任何自动路径**；
2. **确认 `192.168.1.18:9028` 是否就是"看到很多没下载"的那个实例** —— 本次实测该实例只有 1 个用户、105 条收藏；若还有别的实例/账号（如生产容器），请给地址+账号，按同一只读方法复测；
3. **`/standards` 与 `/inbox` 的可访问方式**（若怀疑磁盘/权限类失败）—— 目前 47k 行日志**零** OSError/磁盘/权限证据，无需优先排查；但无法从外部证实 `GB/T 47914-2026` 等 28 条在 openstd 侧是否已收录全文，**这只能靠"重排后看结果"确认**。

---

## 6. 一句话总结

| 问题 | 答案 |
|---|---|
| 为什么"很多收藏没下载"？ | 105 条里有 **99 条处于 `abandoned` 终态**；其中 **61 条**是 2026-09-14~09-20 的会话层 bug 造成（**该 bug 已修复**），**28 条**是更早的"取下载链接"旧实现失败（**该实现已被替换**），**1 条**是数据库竞态（**已修复**） |
| 除版权受限外还有哪些原因？ | 会话缺陷（61）、旧版取链接（28）、归档超时但实际已成功（6）、数据库竞态（1）—— 共 4 类；磁盘/权限/无 hcno/限流在现网日志中**各 0 次** |
| 能重试吗？ | 前 3 类**重试有效**；那 6 条**无需重试（本就成功）**；9 条采标**重试无效** |
| 为什么没自动恢复？ | `abandoned` 是**终态**，调度只捡 `pending`/`failed`（`favorite_chain_processor.py:101`）→ 需人工重新入队 |
| 代价是什么？ | **61 条**参考（会话）+ **28 条**（旧实现）**重试有效**；**9 条**永久，需线下；**6 条**本就成功 |
