# 术语表

> 按“业务概念 → 数据字段 → 模块/文件”组织。  
> 新人遇到不认识的词，先查这里，再查代码。

---

## 一、业务概念

| 术语 | 解释 |
|---|---|
| **标准号** | 标准身份，如 `GB/T 1234-2020`；由代号、顺序号、年份、部分号组成。 |
| **标准代号 / `logical_code`** | 如 `GB`、`GB/T`、`HG/T`、`TSG`、`DB50/T`。 |
| **顺序号 / `number`** | 标准号中的数字部分，如 `1234`。 |
| **年份 / `year`** | 标准发布/版本年份。 |
| **部分号 / `part`** | 多部分标准的 `.1`、`.2`，如 `GB/T 1234.1-2020`。 |
| **修改单** | 标准的第 N 号修改单，独立文件；用 `file_kind` 标识。 |
| **现行** | 当前有效。 |
| **废止 / 已废止** | 失效；两者是别名，`normalize_status()` 归一。 |
| **被代替** | 有替代标准。 |
| **作废** | 作废状态。 |
| **即将实施** | 已发布、未到实施日。 |
| **过期** | 过期状态（与“过期作废”目录名不同）。 |
| **待确认** | 查询/匹配不确定，需人工。 |
| **未知** | 尚未判定。 |
| **过期作废** | 物理目录名，默认 `storage.expire_folder`；不是状态值。 |
| **规范化** | 计算规范文件名/目录的预览，不移动文件。 |
| **归档** | 真正生成目标路径并移动文件，写索引。 |
| **收容/兜底** | 无标准号/跳过目录的镜像归档。 |
| **采标** | 采用 ISO/IEC 等国际标准的国内标准；版权受限，openstd 通常不提供全文下载。 |
| **`pid`** | `std_gov` 查询结果里的站点标识；**不是** openstd 的 `hcno`，不能直接用于下载。 |
| **`hcno`（openstd）** | openstd 搜索页 `showInfo('<hcno>')` 里的下载标识；必须按标准号逐行匹配，不能用 `pid` 代替。 |
| **`QueryResult.hcno`** | 查询适配器的按站点详情 ID（`hbba`/`njbz365` 等会用）；**不是** openstd 下载 hcno 的同义词。 |
| **查询适配器** | 负责从站点查“标准状态/名称/替代关系”的适配器，当前 21 个。 |
| **下载适配器** | 负责取全文的适配器，当前只有 `openstd_download`（GB 类）。 |
| **公告抓取适配器** | 负责抓 SAMR 公告的适配器，当前 3 个：GB/HB/DB；**不是查询/下载适配器**。 |

---

## 二、数据字段/对象

| 术语 | 解释 | 代码 |
|---|---|---|
| **`ParsedStdInfo`** | 解析后的标准信息对象 | `pilotstd/models.py` |
| **`QueryResult`** | 一次查询结果对象 | `pilotstd/query/models.py` |
| **`DownloadTask`** | 下载任务对象（内存） | `pilotstd/download/models.py` |
| **`effect_status`** | Query 得到的当前状态，写回 `ParsedStdInfo` | `manager/classifier.py` |
| **`match_status`** | 匹配状态：`exact/newer/older/code_only/mismatch` | `manager/classifier.py` |
| **`next_action`** | 路由后的下一步：`archive/normalize/download/pending` | `pipeline/router.py` |
| **`file_index`** | 文件路径索引表 | `core/file_index.py` |
| **`standards`** | 内容身份四要素表 | `core/db/_migrate_v16_v49.py` |
| **`standard_validity`** | 历史有效性/待复检表 | `core/validity_checker.py` |
| **`standard_info_cache`** | 查询结果缓存 | `query/cache.py` |
| **`announcement_match`** | 公告匹配缓存 | `core/file_index.py` 常量 |
| **`query.use_announcement_match`** | 是否走“公告缓存优先模式”；false 仍可能经 `CacheRepository` 回退读 `announcement_match` | `manager/facade/_query_subsystem.py`、`query/cache.py` |
| **`announcement_record`** | 公告原始记录 | `announcement/` |
| **`pending_lookup`** | 待确认清单 | `manager/pending_service.py` |
| **`download_queue`** | 等待公开期队列，不是执行队列 | `manager/pending_service.py` |
| **`notification_log`** | 通知发送日志 | `core/notification/` |
| **`pipeline_runs`** | Web 五段式管道状态 | `task/pipeline_store.py` |
| **`task_queue`** | 通用任务表（UI 展示） | `task/queue.py` |
| **`favorite_downloads`** | 收藏下载状态机 | `tasks/favorite_download.py` |

---

## 三、模块/文件

| 术语 | 解释 | 路径 |
|---|---|---|
| **`StandardManager`** | 业务门面，三端共享 | `pilotstd/manager/facade/` |
| **`ManagerCore`** | 依赖容器 | `pilotstd/manager/facade/_core.py` |
| **`AutoPipeline`** | 一键编排 | `pilotstd/manager/facade/_auto.py` |
| **`ScanHandler`** | 扫描入口 | `pilotstd/manager/facade/_scan.py` |
| **`QuerySubsystem`** | 查询执行 | `pilotstd/manager/facade/_query_subsystem.py` |
| **`DownloadHandler`** | 下载入口 | `pilotstd/manager/facade/_download.py` |
| **`OrganizeHandler`** | 归档入口 | `pilotstd/manager/facade/_organize.py` |
| **`OrganizerCore`** | 归档核心（Word/非 Word） | `pilotstd/manager/organize/organizer.py` |
| **`FileMover`** | 目录/文件名/移动 | `pilotstd/organizer/mover.py` |
| **`DirBuilder`** | 目录结构 | `pilotstd/organizer/dir_builder.py` |
| **`StandardParser`** | 文件名解析 | `pilotstd/scan/parser/` |
| **`QueryEngine`** | 查询引擎 | `pilotstd/query/engine/` |
| **v2 路由** | ADR-015 的三级漏斗路由实验，环境变量 `ROUTING_ENGINE_VERSION=v2` 才启用，默认 v1 | `pilotstd/query/routing/router_v2.py` |
| **`QueryClassifier`** | 结果写回/分堆 | `pilotstd/manager/classifier.py` |
| **`PipelineRouter`** | 状态路由 | `pilotstd/pipeline/router.py` |
| **`DownloadEngine`** | 下载引擎 | `pilotstd/download/engine.py` |
| **`ValidityChecker`** | 时效检查 | `pilotstd/core/validity_checker.py` |
| **`NotificationManager`** | 通知门面 | `pilotstd/core/notification/manager.py` |
| **`NotificationAggregator`** | 通知聚合器 | `pilotstd/core/notification/aggregate_buffer.py` |
| **`FileWatcher`** | Win 可选 watcher（只索引） | `pilotstd/scan/watcher.py` |
| **`FileMonitorScheduler`** | Docker 监控（scan+archive） | `pilotstd/monitor/scheduler.py` |

---

## 四、入口/环境

| 术语 | 解释 |
|---|---|
| **Web 端** | Vue3 + FastAPI + Docker；TaskView 五段式。 |
| **Win 端** | PyQt6 桌面；一键 `auto_run_stream`；手动分步。 |
| **CLI** | `python main.py --cli ...`。 |
| **Docker monitor** | `_on_file`，只 scan+archive。 |
| **Inbox** | 监控/投放目录，默认 `/inbox`。 |
| **标准库根** | `STANDARD_ROOT` / `storage.root_dir`，Docker 默认 `/standards`。 |
| **开发环境** | 本地最新 + 本地/Mock。 |
| **验证环境** | 本地新代码 + 局域网 Docker 真实 API。 |
| **复现环境** | 旧 commit + 同一 Docker API。 |
| **生产环境** | 已发布；红线：禁止直接改代码/UPDATE/重启测试。 |

---

## 五、常见缩写

| 缩写 | 含义 |
|---|---|
| **GB** | 国家标准 |
| **GB/T** | 推荐性国家标准 |
| **DB** | 地方标准 |
| **HG/T** | 化工行业推荐性标准 |
| **SH/T** | 石油化工行业推荐性标准 |
| **TSG** | 特种设备安全技术规范 |
| **NB/T** | 能源行业推荐性标准 |
| **JB/T** | 机械行业推荐性标准 |
| **WAL** | SQLite Write-Ahead Logging |
| **ADR** | Architecture Decision Record |
| **CI** | Continuous Integration |
| **E2E** | End-to-End 测试 |
| **OCR** | 光学字符识别（下载验证码/扫描件） |

---

## 六、容易混淆的三组词

### 1. `effect_status` vs `standard_validity`

- `effect_status`：本次查询得到的“现在”；
- `standard_validity`：历史跟踪/待复检。

### 2. 归档 vs 规范化

- 规范化：预览新文件名，不移动；
- 归档：真正移动/改名/写索引。

### 3. Docker monitor vs Win watcher

- Docker `_on_file`：scan + archive；
- Win `FileWatcher`：只更新 `file_index`。

---

## 七、自检

1. 标准号、`logical_code`、`number`、`year` 的关系？
2. `file_index` 与 `standards` 的区别？
3. `download_queue` 是执行队列吗？
4. 归档和规范化的区别？
5. Docker monitor 与 Win watcher 的区别？

参考答案见 [`10-assessment.md`](10-assessment.md)。
