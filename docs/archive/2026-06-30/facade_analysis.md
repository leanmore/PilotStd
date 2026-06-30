# manager/facade.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **1687** |
| 类 | 1 个（`StandardManager`） |
| 方法数 | **60 个** |
| 属性数 | ~15 个实例属性 |

---

## 方法分组统计

### 按业务域分组

#### 初始化与生命周期（4 方法，~150 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `__init__` | 130 | 依赖组装：CFG/DB/Scan/Query/Rotator/Download/Organize/FileIndex/Notification |
| `_init_notification` | 8 | 通知模块初始化 |
| `shutdown` | 5 | 资源释放 |
| `get_stage_queue/summary` | 13 | 流水线状态查询 |

#### Scan（4 方法，~160 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `scan_directory` | 51 | 同步扫描：文件遍历→解析→结果 |
| `scan_directory_stream` | 58 | 流式扫描：含跳过目录检测+进度回调 |
| `scan_and_index` | 31 | 扫描+写入 file_index 表 |
| `start_watching` / `stop_watching` | 25 | 文件系统监听 |

#### Query（12 方法，~310 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `_query_announcement_match` | 56 | 公告缓存精确查询 |
| `_build_result_from_cache` | 19 | 缓存→QueryResult 反序列化 |
| `query` | 66 | **核心查询方法**：多线程并发+实时结果+进度 |
| `_report_query_summary` | 103 | 查询结果分类统计+日志汇报 |
| `_classify_after_query` | 19 | 查询后分类 |
| `_parse_std_number` | 6 | 标准号解析 |
| `_resolve_replaces` | 9 | 替代关系文本处理 |
| `query_by_numbers` | 8 | 委托方法（无锁） |
| `query_local_cache` | 8 | 本地缓存查询 |
| `get_query_sites/cooldown/status/report` | 25 | 站点状态查询 |
| `get_quota_info` / `plan_batch` | 10 | 配额+批次规划 |

#### Download（3 方法，~120 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `download` | 58 | **核心下载**：队列取任务→下载→分类→回写 |
| `download_stream` | 54 | 流式下载：含进度回调 |
| `download_by_numbers` | 10 | 按标准号列表下载 |

#### Pending & Queue（9 方法，~45 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `record_pending/resolve/get/increment/exhausted/manual/requery` | 25 | 待确认项管理 |
| `enqueue_download_wait/get_due/remove` | 20 | 下载等待队列 |

#### Organize & Archive（11 方法，~320 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `organize` | 17 | 委托 organizer_service |
| `organize_stream` | 51 | 流式归档 |
| `organize_files` | 22 | 文件列表→解析→归档 |
| `expire_files` | 13 | 过期文件处理 |
| `normalize_files` | 37 | 文件规范化 |
| `normalize_files_stream` | 42 | 流式规范化 |
| `archive_standards` | 47 | **核心归档**：流水线+磁盘检测+Word镜像+兜底 |
| `_backfill_std_name` | 58 | 公告匹配补充标准名称 |
| `_make_archive_filename` | 16 | 归档文件名生成 |
| `handle_expired` / `merge_expire_from_source` | 18 | 过期处理（委托） |

#### Announce（4 方法，~75 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `check_announcements` | 4 | 委托 announce_service |
| `get_announcement_match` | 28 | 公告匹配结果查询 |
| `check_announcements_filtered` | 14 | 带过滤的公告检查 |
| `announce_stream` | 30 | 流式公告检查 |

#### Auto（2 方法，~150 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `auto_run` | 71 | 一键处理：扫描→查询→下载→归档 |
| `auto_run_stream` | 75 | 流式一键处理 |

#### File Index（4 方法，~50 行）

| 方法 | 行 | 职责 |
|------|-----|------|
| `upsert_file_index` | 22 | 文件索引写入 |
| `get_file_index/full_info` | 12 | 索引查询 |
| `parse_standard_number` | 4 | 文件名解析 |
| `restore_parsed_from_index` | 6 | 索引恢复为 ParsedStdInfo |

---

## 汇总

| 分组 | 方法数 | 总行数 | 占比 |
|------|--------|--------|------|
| 初始化/系统 | 4 | 150 | 9% |
| Scan | 4 | 160 | 10% |
| Query | 12 | 310 | **19%** |
| Download | 3 | 120 | 7% |
| Pending & Queue | 9 | 45 | 3% |
| Organize & Archive | 11 | 320 | **19%** |
| Announce | 4 | 75 | 5% |
| Auto | 2 | 150 | 9% |
| File Index | 4 | 50 | 3% |
| 委托/代理/静态 | 7 | ~50 | 3% |
| 空白/注释 | — | 217 | 13% |
| **总计** | **60** | **1687** | 100% |

---

## 拆分建议

```
pilotstd/manager/facade/
├── __init__.py         ← 组合所有子门面
├── _base.py            ← StandardManager 核心 + __init__ + lifecycle
├── _scan.py            ← scan_directory, scan_directory_stream, scan_and_index, start/stop_watching
├── _query.py           ← query, _report_query_summary, _query_announcement_match, _classify_after_query, ...
├── _download.py        ← download, download_stream, download_by_numbers
├── _organize.py        ← organize, organize_stream, archive_standards, normalize_files, ...
├── _auto.py            ← auto_run, auto_run_stream
└── _file_index.py      ← upsert_file_index, get_file_index, parse_standard_number, ...
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `_base.py` | ~200 | __init__ + shutdown + 委托属性（announce/pending/queue） |
| `_scan.py` | ~160 | 扫描相关方法 |
| `_query.py` | ~310 | 查询核心逻辑 |
| `_download.py` | ~120 | 下载核心逻辑 |
| `_organize.py` | ~320 | 归档/规范化/过期处理 |
| `_auto.py` | ~150 | 一键处理管线 |
| `_file_index.py` | ~50 | 文件索引操作 |
| `__init__.py` | ~20 | 组合类 |

### 导入兼容性

```python
# 外部零改动
from pilotstd.manager.facade import StandardManager
# → __init__.py 重导出组合类，完全兼容
```

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| **高** | 1687 行，60 个方法。Query 和 Organize 各占 ~320 行。 |
| 收益 | 拆分后每个子模块 <350 行，按业务域独立维护 |
| 风险 | 需确保 self 属性（cfg/db/parsed等）在各子模块间共享 |
