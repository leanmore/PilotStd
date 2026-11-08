# 08 · 当前边界与已知坑

> 这一份不是“待办清单”，而是**避免新人把现状当设计**。  
> 读完后你应该能判断：哪些现象是“设计如此”，哪些是“当前缺口”，哪些是“不能顺手修的历史包袱”。

---

## 一、快速表

| # | 现象 | 类型 | 影响 |
|---|---|---|---|
| 1 | Web 五段式下载件不进入归档 | 已修复（v0.171.0 部署） | 前端把下载成功项加入归档 items；后端重复策略待确认 |
| 2 | Docker monitor 只 scan + archive | 已修复（触发主链） | 去抖/锁 + auto_run；空目录清理保留 |
| 3 | Win watcher 只更新索引 | 设计边界 | 不会自动归档 |
| 4 | `standard_validity` 不是归档第一权威 | 设计边界 | 与 `file_index`/Query 可能不一致 |
| 5 | `standard_validity` 存在畸形键 | 历史数据缺陷 | 按表查询/搬移会漏 |
| 6 | Word 重解析使用空 scan.code_mapping | 实现缺陷 | TSG 等进入 `T 未知行业(T)` |
| 7 | 手动/一键下载任务不持久化 | 已修复（2026-11-07） | 任务落 `task_queue`；重启自动重试未完成，有次数上限 |
| 8 | 规范化只预览，归档忽略 `new_filename` | 已修复（2026-11-07） | 归档以预览名（`final_name`）为准；重名冲突走待确认 |
| 9 | 归档通知按“每次调用”发 | 已修复（2026-11-07） | 一次 auto_run 共用 batch_scope；零搬移仍发且正文完整 |
| 10 | DB 写存在 SELECT+INSERT 竞争 | 已修复（2026-11-07） | file_index 原子 UPSERT；validity 首次登记 INSERT OR IGNORE |
| 11 | monitor 懒加载 manager 无锁 | 实现缺陷 | 多实例/重复校验 |
| 12 | `validity_check_queue` 表不存在 | 已修复（v75） | 队列建表 + 60s 消费；见 #12 详述 |
| 13 | `/api/auto` 未传 `root_path` | 实现缺陷 | 该端点按当前签名不可用 |
| 14 | 下载只有 `openstd_download`；非 GB 无适配器，采标 GB 受版权限制 | 设计边界 + 能力缺口 | 非 GB/采标 GB 无法自动下载 |
| 15 | Web TaskView 没有“停止”按钮 | 已修复（Web B；Win A 不变） | `/task` 停止按钮；阶段间协作式停止 |
| 16 | 通知重试覆盖不均：钉钉企业卡片/飞书应用消息单次请求 | 已修复（2026-11-07） | 两条路径接入 `_with_retry`；429/5xx 退避重试 |
| 17 | 通知未读数与列表口径不一致 | 已修复（v0.171.0 + 管理员系统通知） | 普通用户按自身；管理员默认含系统通知；all=true 才是全部用户 |
| 18 | 通知日志按渠道各写一行，Web 铃铛直接展示导致同一事件重复 | 已修复（Web 展示层） | 铃铛按事件去重、角标按事件计数；日志页仍保留渠道明细 |
| 19 | 可信 IP 自动更新依赖浏览器，Docker 镜像未装 Playwright/Chromium | 已接入 CloakBrowser（待部署） | CloakBrowser 自带定制 Chromium；需要 license key 和首次二进制下载 |
| 20 | 时效性检查只落状态，不落查询明细 | 已修复（v76，待部署） | `validity_check_log` 保存证据/来源/失败原因/结果 JSON |
| 21 | 公告定时任务漏跑/晚发布公告可能漏抓 | 已修复（2026-11-07） | checkpoint 保留；定时多回看 7 天；超过 36 小时未成功抓取会在完成通知中告警 |

---

## 二、逐条说明

### 1. Web 五段式：下载件不进入归档（已修本地，待部署）

**证据**

- 原实现：`web/src/views/TaskView.vue` 的 `archiveItems` 只来自 scan.files + `normalizeResult`，`downloadResult` 只用于汇总；
- `docker/api/archive.py` 只接收请求体 `items[].source_path`，不读下载结果；
- 下载落 `get_library_root()`（Docker `/standards`）根目录，不写 `file_index`；
- `TaskView` 只对 `match_status==='exact'` 且非采标的结果发起下载，并用 `.slice(0, 10)` **最多 10 条**。

**已修（本地代码，未部署）**

- 下载结果中 `status=success` 且有 `saved_path` 的项，解析标准号后并入 `archiveItems`；
- 按 `source_path` 去重，避免与扫描件重复；
- 回归：`web/src/views/TaskView.test.ts` 新增用例，3 passed；全量 `pnpm test` 352 passed。

**影响**

- 本次“一键处理”下载的文件留在 `/standards` 根目录；
- 不在分类目录、不在 `file_index`、不在 `standard_validity`；
- 只有用户之后再次手动扫描 `/standards` 并归档，才会被处理。

**不要误判**

- 这不是“Win 一键的问题”；Win 一键走 `auto_run_stream`，是闭环的（见 [`01-positioning.md`](01-positioning.md)）。

**如果要修**

- 把 `saved_path` 转成 `ParsedStdInfo` 并加入归档入参；
- 处理同一标准的扫描件/下载件重复、覆盖、路径校验；
- 需要前端 + API + 测试一起改。

---

### 2. Docker monitor：只 scan + archive（已修，改为触发主链）

**修复（2026-11-07）**

- `_on_file` 不再自己 `scan_directory + archive_standards`；
- 改为按父目录去抖/加锁，调用现有主链 `mgr.auto_run(source_root)`；
- 主链负责 scan/query/download/archive/兜底；
- manager 懒加载仍有 `_mgr_lock` 双检；
- 归档后调用 `_cleanup_empty_dirs(watch_path, source_root)`；
- 同一目录 10 秒内只触发一次，避免多文件事件重复跑主链；
- 回归：`test_monitor_archive_e2e.py` + `test_monitor_cleanup.py` → 7 passed。

**历史证据（修复前）**

- `pilotstd/monitor/scheduler.py::_on_file`：`scan_directory(dirname(path))` → `archive_standards`；
- 没有 query/download/fallback/clean；
- 每个文件事件都扫描整个目录，重复处理明显。

**影响**

- 监控投放的文件可能：
  - 没有 `effect_status`（不查有效性）；
  - 不补下载；
  - 无标准号文件/跳过目录留在 Inbox；
  - 空目录不清理；
  - 每文件一条归档通知。

**不要误判**

- 不是“设计成轻量监控”；历史 commit 明确“归档从未实现”，后来才补归档（见 [`03-architecture.md`](03-architecture.md)）。
- Win 桌面不走这个 `_on_file`。

---

### 3. Win watcher：只更新索引

**证据**

- `pilotstd/ui/main_window/parts/_actions_ops.py`：`watchdog.enabled` 才 `mgr.start_watching()`；
- `pilotstd/scan/watcher.py::FileWatchHandler._handle_new_or_modified()`：哈希 → 解析 → `file_index.upsert()`；
- 不归档、不查询、不下载；
- `watchdog.enabled` 默认 false。

**影响**

- 开启后只是“索引更新”，不是“自动整理”；
- 不要把 Win watcher 与 Docker monitor 混为一谈。

---

### 4. `standard_validity` 不是归档第一权威

**证据**

- `effect_status` 来自 `QueryClassifier._write_back_results()`（`QueryResult.status`）；
- `archive_standards()` 只 `register_new_standard()` 写“未知”，不读 `standard_validity`；
- 归档目录由 `FileMover` 根据 `p.effect_status` 决定。

**影响**

- Query 说废止 → 归档进“过期作废”；
- `standard_validity` 可能仍是“未知”；
- `/api/stats` 看 `file_index`，`/api/export/standards` 看 `standard_validity`，两边可能不一致。

**如果要改**

- 先决定优先级（L2 实时 > 表历史 > L1 猜测）；
- 必须先修畸形键；
- 归档要同步写表或先查表，处理并发/唯一键。

---

### 5. `standard_validity` 的历史畸形键

**证据**

- 批次前备份：803 条中 709 条 `standard_number` 形如 `' 1234-2020'`（前导空格、缺代号）；
- 706 条可由 `file_index` 的 `(number, year)` 唯一还原；
- 历史来源与 `c4b7d861`（前端归档漏传 `logical_code` 导致 `未知行业()`）相关；迁移脚本只修 `file_index`，未修 `standard_validity`。

**影响**

- 按 `standard_number` 精确匹配会漏；
- 不要默认“表里都是规范键”。

**如果要修**

- 先 dry-run 统计：唯一可还原/歧义/无匹配；
- 备份后再更新；
- 处理与正确键的重复合并；
- 详细方案见 [`12-data-repair-plan.md`](12-data-repair-plan.md)（仅方案，未执行）。

---

### 6. Word 重解析：空 scan.code_mapping → `T 未知行业(T)`

**证据**

- `pilotstd/manager/organize/organizer.py:41`：
  `StandardParser(self._cfg.get("scan.code_mapping", {}))`；
- `_organize_word_item()` 用这个解析器重解析 `.doc/.docx`；
- `_exact_match_group()` 对 `TSG 3001-2009` 匹配成 `T/SG`；
- `get_folder_name("T/SG")` → base `T` → `T 未知行业(T)`；
- 只有 Word 分支重解析，PDF 走扫描器解析器，通常进 `TSG` 目录。

**影响**

- TSG 等 Word 文件目录错误；
- `file_index.logical_code` 写 `T/SG`；
- `standard_validity` 写 `T/SG ...`，与 `TSG ...` 形成第三套身份。

**如果要修**

- 用 `build_code_mapping()` 构造 `_std_parser`，或直接用主流程 `p` 的 `logical_code/number/year`；
- 保留“无标准号 Word → 镜像”行为；
- 现有 `TestOrganizeWordItem` 用例需要同步调整。

---

### 7. 手动/一键下载任务不持久化

**证据**

- `DownloadTask` 是内存 dataclass（`pilotstd/download/models.py`）；
- `DownloadEngine.download_batch()` 返回后任务结束；
- `task_queue` 有 `DOWNLOAD` 类型但没有真实 handler；
- 只有 `favorite_downloads` 是持久化状态机。

**影响**

- 重启/崩溃丢失未完成下载；
- 不会自动重试（收藏链除外）；
- `.part` 只会被清理，不续传。

**已做（2026-11-07，下载任务 + Web 管道）**

- 下载任务落 `task_queue`（task_type=download），状态/重试次数/错误可查；
- 服务启动后自动重试未完成下载，超过 `max_retries` 保持 failed；
- Web 五段式另有阶段级续跑（见下）；
- 下载引擎本身仍不做 HTTP 断点续传。

- Web 五段式增加“服务重启 → interrupted → 阶段级继续”：
  - 后端启动把 running/stopping 标为 interrupted；
  - `/task` 显示“继续任务”，从最后一次完整阶段继续；
  - 不自动续跑半阶段。
- 这不等于下载任务持久化：`DownloadTask` 仍是内存对象，见上面原证据。

**如果要修下载任务**

- 新增下载任务表或复用 `task_queue` + 注册 handler；
- 定义 `pending/running/failed/retry/abandoned`；
- 幂等，避免重启后重复下载/归档。

---

### 8. 规范化：预览，不是文件操作

**证据**

- `normalize_files_stream()` 只计算 `normalized/folder`，不 `safe_move`、不写 `file_index`；
- Web `postArchive()` 不使用 `new_filename`；`docker/api/archive.py` 也没有该字段；
- Win `NormalizeWorker` 只更新表格，`on_save_to_folder()` 才归档；
- CLI `normalize` 明确“不移动”。

**影响**

- 用户可能以为“规范化”已经改名；
- 预览与最终归档可能漂移（入口字段不同）。

**如果要改**

- 把规范化降级为可选预览，而不是主链强制步骤；
- 或让归档显式使用预览结果（需要处理冲突/一致性）。

---

### 18. 通知铃铛按渠道重复展示（已修）

**原因**

- `notification_log` 是**每渠道一行**（Web/企微/钉钉/飞书/Telegram），便于排查投递；
- 铃铛 `GET /api/notification/logs` 不做去重，直接按行展示；
- 同一事件启用两个渠道时，铃铛出现两条，角标也按渠道计数。

**修复（2026-11-07，Web 展示层）**

- 铃铛按 `event_type + standard_number + sent_at + title + body` 去重；
- 角标按去重后事件计数；
- 点击一条时，把同事件的其他渠道副本一起标记已读；
- 日志页仍保留每渠道明细，不影响诊断。

### 19. 可信 IP 自动更新缺浏览器（部分修复）

**原因**

- `pilotstd/wechat_ip/browser.py` 优先 CloakBrowser，回退 Playwright；
- `docker/requirements-docker.txt` 没有 `playwright`，Dockerfile 也没安装 Chromium；
- 因此 Docker 内 `WechatIPUpdater` 启动必失败；
- 原 `run_check` 只捕获 `BrowserError`，ImportError 等异常只进后台线程日志，用户看不到。

**已修（2026-11-07）**

- `run_check` 捕获所有异常，写回 `error` 并发失败通知；
- 状态页不再用空 URL 校验 Cookie，避免误报“Cookie 失效”；
- 定时读取 Cookie 不再回退到公开默认密钥。

**A1 方案（2026-11-07 已接入）**

- Docker 依赖加入 `cloakbrowser==0.7.1`；它自带定制 Chromium，不再需要原版 Chromium；
- Dockerfile 安装 `playwright install-deps chromium` 与中文字体；
- `CLOAKBROWSER_LICENSE_KEY` 通过 compose/.env 注入；
- 定制 Chromium 缓存放 `/app/data/cloakbrowser`（随 `./data` 卷持久化）；
- 容器启动时用 `python -m cloakbrowser install` 预装内核，`binary_info()` 判断是否可执行；
- `WechatIPUpdater` 使用 `launch_persistent_context` 保持企业微信登录态；
- 首次启动下载约 200MB 定制 Chromium，离线/无 key 时会失败并通知。

### 9. 通知聚合的现状

**证据**

- `archive_standards()` 每次调用都 `ensure_batch_key("arch")`，不同调用不同批次键；
- 归档即使 `moved=0` 也发 `archive_complete`；
- 企微卡片无 `card_action` 时可能 42045，降级文本；
- Telegram 429 常见。

**影响**

- 大批量时可能每文件一条通知；
- 聚合器对 `scan_complete`/`standard_first_registered` 有效，对归档不一定；
- 通知日志里大量 `failed`/`429`。

**已改（2026-11-07）**

- `moved=0` 仍发 `archive_complete`；正文包含 count/skip/fail/dirs，不再只有标题；
- `archive_standards` payload 增加 total/skipped_exists/failed；
- `notification_log.body` 对归档事件不再为空。
- **刻意不抑制零计数**：用户要求零搬移也要可追踪；
- 一次 `auto_run` 在 `batch_scope("imp")` 内完成 scan/query/download/archive，归档复用同一批次键；
- 批量通知收敛为一条管道汇总 + 必要的归档正文，不再按文件逐条发。

**如果要改**

- 监控/批处理共用一个批次键；
- 渠道层做全局限流/重试；
- 企微无卡片动作时直接文本。

---

### 10. DB 写竞争（已修复）

**修复（2026-11-07）**

- `FileIndexRepository.upsert()` 改为单条 `INSERT ... ON CONFLICT(file_path) DO UPDATE`，不再 SELECT+INSERT；
- `register_new_standard()` 改为单条 `INSERT OR IGNORE ... WHERE NOT EXISTS`，用 `rowcount` 判断是否首次登记；
- 并发扫描/归档/首次登记不会再撞唯一键；
- 回归：`tests/test_file_index_full.py` 75 passed；`test_validity_checker*.py` 87 passed。

**原证据**

- `register_new_standard()`：SELECT → INSERT；
- `FileIndexRepository.upsert()`：SELECT → INSERT/UPDATE；
- 并发归档会 `UNIQUE constraint failed`。

**影响**

- 日志大量 `SQL执行失败`；
- 个别文件已搬走但统计 `failed`。

**如果要修**

- `INSERT OR IGNORE` / `ON CONFLICT DO UPDATE`；
- 用 `rowcount` 判断是否首次；
- 保留错误日志。

---

### 11. monitor 懒加载 manager 无锁

**证据**

- `pilotstd/monitor/scheduler.py::_on_file`：
  `if self._mgr is None: self._mgr = StandardManager()`；
- 多个 Timer 线程同时进入；
- 可能出现多个 `StandardManager` 实例、多次 `file_index` 启动校验。

**影响**

- 资源浪费；
- 配置/DB 连接/校验线程重复；
- 日志里多次 `已加载 Fernet Key` / `file_index 启动校验`。

**如果要修**

- `start()` 时注入/构造唯一 manager；
- 加锁 + double-check；
- 或由 `docker/manager.py` 单例注入。

---

### 12. `validity_check_queue` 表不存在（已修，v75）

**原证据**

- `pilotstd/manager/validity_service.py` 是唯一引用：
  `INSERT OR IGNORE INTO validity_check_queue ...`；
- 代码库中没有建表迁移/DDL；
- 异常被逐条吞掉，接口返回 `ok=True, enqueued=0`（假成功）；
- 即使补表，也没有消费者。

**修复（v75）**

- 迁移 `_migrate_v75_validity_queue.py` 建表 + 索引；
- `ValidityService.process_pending()` 消费 pending：
  - `file_index` 路径 → 标准号；
  - 调 `ValidityChecker.check_standard()`；
  - 写回 success/failed/error；
- 调度器每 60 秒 drain，启动时补跑；
- 前端文案改为“已加入队列，后台检查中”。

**仍需验证**

- 部署 v0.172+ 后跑一次选中文件检查；
- 观察 `validity_check_queue` 的 pending/success/failed 数量。

---

### 13. `/api/auto` 未传 `root_path`

**证据**

- `docker/api/auto.py` 调 `mgr.auto_run()`；
- `auto_run(root_path, ...)` 要求 `root_path`；
- Web 实际走 `TaskView` 五段式，不走该端点。

**影响**

- 该端点按当前签名不可用；
- 不要把它当成 Web 一键的真实入口。

---

### 14. 下载只有 `openstd_download`：非 GB 无适配器，采标 GB 受版权限制

**证据**

- `pilotstd/download/adapters/` 只有 `openstd_download.py` 一个实现；
- `DownloadEngine._find_adapter()` 对 GB 类强制兜到 `openstd_download`，非 GB 走 `can_handle` 后通常返回“无下载适配器”；
- `openstd_download.can_handle()` 只认 `source_site == "openstd_download"`；
- 全库有 21 个**查询**适配器，但下载侧仍只有 1 个。

**影响**

- 21 个查询站点都可以“答出”某条标准，但只有 GB 类能真正下载；
- 非 GB（HG/SH/NB/ISO/ASME 等）即使查询到全文入口，也不会自动下载；
- **GB 类里的“采标”标准**（采用 ISO/IEC 等）会被 openstd 的“采”标记拦截，按版权限制跳过；
- “查询有结果”不等于“能下载”，排查时要分开看。

**预期 vs 缺口**

- **预期**：非 GB 没有下载适配器；采标 GB 受版权限制不提供全文，这是已知设计边界；
- **缺口**：如果业务希望这些标准也能自动获取，需要新增合法来源/授权适配器，不能靠重试或改 openstd 适配器解决。

**不要误判**

- 这不是“下载失败”，是“没有对应下载适配器”；
- 不要因为 `source_site` 是 `cssn`/`hbba` 就认为下载会失败——GB 类会按标准性质兜到 openstd。

**如果要扩展**

- 新增下载适配器，并在 `_find_adapter()` 里按标准性质/站点映射；
- 需要单站点实测 hcno/端点/验证码/版权闸，不能只按查询站点名猜。

---

### 15. Web TaskView 没有“停止”按钮（已修，Web B）

**修复（2026-11-07）**

- `/task` 增加停止按钮；
- 后端 `pipeline_runs` 状态：`running → stopping → stopped`；
- 前端在 scan/query/download/normalize/archive 每个阶段边界检查停止标记；
- 当前阶段跑完后停止，不硬杀线程；
- Win 端仍为 A：只停 UI 等待，不杀 worker。

**原证据**

- `web/src/views/TaskView.vue` 只有“开始”按钮（`:loading="running"`）；
- `onBeforeUnmount(() => { stopPolling() })` 只清前端轮询；
- 没有调用后端取消接口；
- 后端 `pipeline_runs` 仍继续跑；
- `resolveActiveRun()` 只在 `running/pending` 时恢复；`completed/failed` 会清掉 `task_active_run`，重进页面看不到结果；
- 轮询连续失败 3 次就 `stopPolling()`，不会自动重连。

**影响**

- 用户离开页面/刷新后，后端任务可能继续；
- `runPipeline()` 没有 `if (running) return` 的显式重入保护，重复触发是否被 Button loading 拦住取决于组件行为；
- 只能等任务结束，不能主动停；
- 任务在离开期间完成/失败，回来时结果可能已不可见；
- 网络抖动一次持续 6 秒，前端就停止同步。

**不要误判**

- 这不是“前端卡住”；前端只是不再轮询；
- Win 端有协作式中断（`check_stop` → `WorkerAborted`），Web 目前没有对应能力。

**如果要修**

- 需要后端提供取消端点 + `pipeline_runs` 状态机加 `cancelled`；
- 前端加停止按钮、取消后恢复状态；
- 要处理“已发出的归档/下载请求无法回滚”的边界。

---

### 16. 通知重试覆盖不均：钉钉企业卡片/飞书应用消息单次请求（已修）

**修复（2026-11-07）**

- 钉钉企业卡片拆出 `_post_card_once`，`_send_card` 接 `_with_retry`；
- 飞书应用消息拆出 `_post_app_message_once`，`_post_app_message` 接 `_with_retry`；
- 429/5xx/网络类异常退避重试；非重试错误不放大；
- 钉钉“创建成功但投递失败”重试可能重复建卡，属“不丢消息”的取舍，已注释说明。

**原证据**

- `channels/base.py::_with_retry` 是统一重试基座（3 次、2/4s、retry-after 优先）；
- 企微应用/文本、钉钉 Webhook、飞书 Webhook、Telegram 都接入了；
- 但：
  - `DingTalkChannel.send()` 企业形态直接 `_send_card()`，内部是 `requests.post`，没有 `_with_retry`；
  - `FeishuChannel.send()` 应用形态直接 `_send_app()` → `_post_app_message()`，也是单次请求。
- 这两条路径遇到 429/5xx/网络抖动不会重试。

**影响**

- “四家统一重试”只对 Webhook/文本路径成立；
- 企业应用/卡片形态的失败率会高于预期；
- 排查时不能只看“渠道基座有重试”就认为所有形态都覆盖。

**如果要修**

- 把 `_send_card` / `_post_app_message` 改成返回 `(ok, retryable)` 的 attempt 函数，再套 `_with_retry`；
- 补企业形态的 429/5xx 测试；
- 注意卡片创建是“创建 + 投递”两步，重试要避免重复建卡。

---

### 17. 通知未读数与列表口径不一致

**证据（2026-11-07 实测）**

| 接口 | 结果 |
|---|---|
| `/api/notification/logs`（当前用户） | total **578** |
| `/api/notification/logs?is_read=false`（当前用户） | total **7** |
| `/api/notification/unread-count` | **1441** |

代码原因：

- `get_logs()` 带 `user_id` 过滤；
- `get_unread_count()` 不带 `user_id`，直接 `COUNT(*) WHERE is_read=0`；
- `mark_logs_read(ids=[])` 更新 `notification_log` 全表，不按用户。

**已修（本地代码，未部署）**

- `get_unread_count(user_id)` / `mark_logs_read(..., user_id)` 已按用户过滤；
- API 的 `/api/notification/unread-count` 与 `/api/notification/read` 都传当前用户；
- 单条已读先校验归属，不能借 id 标记别人的日志；
- 回归：`tests/test_notification_unread_isolation.py` + `test_notification_manager.py` + `test_notification_logs_user_isolation.py` + `test_notification_api.py` → **57 passed**。

**影响**

- 未读 badge 可能大于列表总数；
- “全部已读”会清掉其他用户的未读；
- Web 页面显示与通知消息统计容易互相矛盾。

**如果要修**

- `get_unread_count(user_id)` 按用户过滤；
- `mark_logs_read` 按用户/按权限更新；
- 统一列表、未读数、全部已读的 WHERE 口径；
- 补多用户测试。

---

## 三、新人处理原则

1. **先判断类型**：设计边界 / 当前缺口 / 历史数据缺陷；
2. **不要顺手修**：这些问题大多跨前端/API/DB/测试，需方案批准；
3. **先看证据**：日志、代码、测试、备份数据；
4. **修复前先写失败测试**；
5. **修完更新本文件**：把已修复项移除/标注。

---

## 四、自检

1. Web 下载件为什么留在 `/standards` 根？
2. Docker monitor 和 Win watcher 分别做什么？
3. `standard_validity` 为什么不是归档第一权威？
4. TSG Word 为什么进 `T 未知行业(T)`？
5. 手动下载任务重启后会怎样？
6. 规范化会不会移动文件？
7. 哪些问题不能“顺手修”，为什么？

参考答案见 [`10-assessment.md`](10-assessment.md)。
