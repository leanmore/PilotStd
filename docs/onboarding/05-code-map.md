# 05 · 代码地图：从 10 个入口读懂整个项目

> 不要从 `pilotstd/` 目录树开始逐个看。  
> 按下面的顺序，10 个入口就能覆盖 80% 的主链。

---

## 一、仓库地图

```text
PilotStd/
├── main.py                     # GUI / CLI 总入口
├── pilotstd/
│   ├── models.py               # ParsedStdInfo 等核心模型
│   ├── scan/                   # 扫描 + 标准号解析
│   ├── query/                  # 查询引擎 + 适配器
│   ├── download/               # 下载引擎 + 适配器
│   ├── organizer/              # 目录/文件名/移动
│   ├── manager/                # 门面 + Handler + 归编排
│   ├── pipeline/               # 状态路由
│   ├── core/                   # 配置/DB/索引/有效性/通知/工具
│   ├── announcement/           # 公告拉取/匹配
│   ├── monitor/                # Docker 监控入口
│   ├── tasks/                  # 收藏下载/日期提醒
│   ├── services/               # 收藏链处理器
│   ├── ui/                     # PyQt6 桌面端
│   └── cli/                    # 命令行
├── docker/                     # FastAPI + 调度器 + API
├── web/                        # Vue3 前端
├── tests/                      # 单元/集成/GUI/E2E
├── docs/                       # 文档（含本目录）
└── scripts/                    # 迁移/检查/生成脚本
```

---

## 二、10 个入口文件（按阅读顺序）

### 1. `pilotstd/models.py`

先看 `ParsedStdInfo`：

- 文件解析后的“标准身份”；
- 关键字段：`raw_filename`、`logical_code`、`number`、`year`、`part`、`std_name`、`source_path`、`effect_status`、`match_status`、`next_action`；
- `get_full_number()` / `is_valid_standard`。

**看什么**：为什么 `logical_code` 和 `number` 要分开存；为什么要有 `raw_number`。

---

### 2. `pilotstd/scan/parser/__init__.py` + `_exact_matcher.py`

看 `StandardParser.parse()`：

- 先 `_preprocess_input()` 清洗/展开短年份；
- 按通道依次尝试：DB / 团体 / BPVC / ITU / exact / typed / fuzzy / no_year；
- 失败打 `解析失败: path=... error=no_match`。

**看什么**：文件名如何变成标准号；哪些格式会失败。

---

### 3. `pilotstd/manager/facade/_auto.py`

看 `auto_run()` / `auto_run_stream()`：

```text
batch_scope("imp")
  scan_directory
  query
  download
  archive_standards
  organize_skipped_dirs
  organize_fallback
  auto_pipeline_summary
```

**看什么**：这是 CLI/Win 一键的完整主链；Web 不走这里。

---

### 4. `pilotstd/manager/facade/_scan.py`

看 `scan_directory()`：

- `FileScanner.scan([root])`；
- 解析每个 `FileInfo.filename`；
- 按四元组去重；
- 写 `parsed_results`；
- 发 `scan_complete`。

**看什么**：扫描只解析，不搬文件、不写 `file_index`。

---

### 5. `pilotstd/manager/facade/_query_subsystem.py` + `manager/classifier.py` + `pipeline/router.py`

看三件事：

1. `QueryEngine.query_standards()` 怎么查；
2. `QueryClassifier._write_back_results()` 怎么把 `QueryResult.status` 写回 `p.effect_status`；
3. `PipelineRouter.apply_actions()` 怎么分堆：archive/normalize/download/manual_download/pending/fallback。

**看什么**：查询结果如何变成“下一步动作”。

---

### 6. `pilotstd/manager/facade/_download.py` + `pilotstd/download/engine.py`

看：

- `DownloadHandler.download()` 如何从 `download_list` + `query_results` 构造任务；
- `DownloadEngine.download_batch()` 如何分批/重试；
- `_save_file()` 如何落盘（`.part` → `os.replace`）；
- `_post_process_download()` 如何回写 `source_path`。

**看什么**：下载只负责“拿到文件”，不负责“归档”。

---

### 7. `pilotstd/manager/facade/_organize.py` + `manager/organize/organizer.py` + `organizer/mover.py`

看：

- `archive_standards()`：归档入口、注册有效性、发通知；
- `OrganizerCore.organize()`：Word/非 Word 分流、去重、索引；
- `FileMover.normalize_filename()`：目录 + 文件名 + 过期作废；
- `_organize_word_item()`：Word 重解析（注意空 `scan.code_mapping`）。

**看什么**：真正的落盘/改名/写索引在这里。

---

### 8. `pilotstd/core/validity_checker.py` + `core/_validity_pipeline.py`

看：

- `register_new_standard()`：归档后写“未知”；
- `run_validity_check()`：采样到期标准；
- `check_standard()`：L1/L2/L3；
- `update_status()`：写状态，可能在 L2 + 开关下搬文件。

**看什么**：`standard_validity` 是跟踪表，不是归档第一权威。

---

### 9. `docker/api/` + `web/src/views/TaskView.vue`

Web 端五段式：

- `docker/api/scan.py`、`query.py`、`download.py`、`normalize.py`、`archive.py`；
- `pipeline_runs` 记录步骤；
- `TaskView.vue` 按顺序调 5 个 API。

**看什么**：生产当前 Web 下载结果不回灌归档，本地代码已修待部署；`normalize` 的 `new_filename` 归档不使用。

---

### 10. `pilotstd/ui/workers/auto.py` + `ui/core/handlers/_archive.py`

Win 端：

- `AutoWorker` → `auto_run_stream`（一键闭环）；
- 手动分步：`ScanWorker` / `QueryWorker` / `DownloadWorker` / `NormalizeWorker` / `ArchiveWorker`；
- `ArchiveUIHandler.on_save_to_folder()` 真正归档。

**看什么**：Win 一键和 Web 五段式的差异；Win 手动下载后需再点归档。

---

## 三、请求/动作 → 代码入口速查

| 你想找 | 入口 |
|---|---|
| 文件名解析 | `scan/parser/StandardParser.parse` |
| 目录扫描 | `manager/facade/_scan.py::scan_directory` |
| 查询 | `manager/facade/_query_subsystem.py::query` |
| 状态写回/分堆 | `manager/classifier.py::classify`、`pipeline/router.py::apply_actions` |
| 下载 | `manager/facade/_download.py::download`、`download/engine.py` |
| 归档 | `manager/facade/_organize.py::archive_standards` |
| 目录/文件名 | `organizer/mover.py::normalize_filename`、`organizer/industry_lookup.py::get_folder_name` |
| 有效性 | `core/validity_checker.py`、`core/_validity_pipeline.py` |
| 通知 | `core/notification/manager.py::send_event` |
| Docker 监控 | `monitor/scheduler.py::_on_file` |
| Win watcher | `scan/watcher.py::FileWatcher` |
| Web 任务页 | `web/src/views/TaskView.vue` |
| Win 一键 | `ui/workers/auto.py::AutoWorker` |

---

## 四、测试地图

| 层 | 目录/文件 | 看什么 |
|---|---|---|
| 解析 | `tests/test_scanner.py`、`tests/unit/.../parser*` | 标准号格式覆盖 |
| 归档 | `tests/unit/manager/organize/test_organizer.py` | Word/非 Word/索引 |
| 监控 | `tests/integration/test_monitor_archive_e2e.py` | `_on_file` 真归档 |
| 查询 | `tests/unit/.../query*`、`tests/test_query_*` | 路由/缓存/配额 |
| 下载 | `tests/download/adapters/test_openstd_download.py` | 下载契约 |
| 通知 | `tests/test_aggregate_buffer.py`、`tests/test_notification_*` | 聚合/渠道 |
| Web API | `tests/test_docker_api.py` | 接口契约 |
| 前端 | `web/src/**/*.test.ts` | 组件/流程 |
| E2E | `web/e2e/` | 浏览器流程 |

### 怎么选测试

- 改解析：先跑 `tests/test_scanner.py` + 解析相关；
- 改归档：跑 `tests/unit/manager/organize/test_organizer.py`；
- 改监控：跑 `tests/integration/test_monitor_archive_e2e.py`；
- 改通知：跑 `tests/test_aggregate_buffer.py` + `tests/test_notification_*`；
- 改 Web：跑后端 `tests/test_docker_api.py` + 前端四件套。

---

## 五、如何从一条日志定位代码

### 例 1：`解析失败: path=... error=no_match`

1. `grep -R "解析失败" pilotstd/scan/parser/`；
2. 定位 `StandardParser.parse` 的失败分支；
3. 看对应通道正则/清洗规则。

### 例 2：`[MONITOR] 归档完成: N 条`

1. `pilotstd/monitor/scheduler.py::_on_file`；
2. 看 `scan_directory` + `archive_standards`；
3. 对照 `tests/integration/test_monitor_archive_e2e.py`。

### 例 3：`SQL执行失败: INSERT INTO standard_validity`

1. `grep -R "INSERT INTO standard_validity" pilotstd/`；
2. `validity_checker.register_new_standard`；
3. 看是否并发重复插入（UNIQUE）。

### 例 4：`Telegram HTTP 429`

1. `pilotstd/core/notification/channels/telegram.py`；
2. 看重试/限流；
3. 对照 `notification_log` 的 `failed` 行。

---

## 六、改功能应该改哪里

| 需求 | 修改点 | 必跑测试 |
|---|---|---|
| 支持一种新文件名格式 | `scan/parser/` | 解析相关 |
| 新增查询站点 | `query/adapters/` + `registry.py` | 适配器/查询 |
| 改“废止→过期作废”规则 | `organizer/mover.py`、`core/status.py` | 归档/状态 |
| 改 Word 归档 | `manager/organize/organizer.py` | `test_organizer.py` |
| 改有效性检查 | `core/validity_checker.py` | `test_validity_*` |
| 改通知聚合 | `core/notification/aggregate_buffer.py` | `test_aggregate_buffer.py` |
| 改 Web 流程 | `web/src/views/TaskView.vue` + `docker/api/` | 前端四件套 + API |
| 改 Win 一键 | `ui/workers/auto.py` + `_auto.py` | UI 相关 |
| 改监控 | `monitor/scheduler.py` | `test_monitor_*` |

---

## 七、自检

1. 只看 `pilotstd/` 目录，能说出主链的 7 个站吗？
2. `auto_run` 和 `TaskView` 的代码入口分别在哪？
3. 解析失败先看哪个函数？
4. 归档目标路径由哪两个函数决定？
5. 改 Word 归档要跑哪个测试文件？
6. 看到 `UNIQUE constraint failed` 先看哪两张表？

参考答案见 [`10-assessment.md`](10-assessment.md)。
