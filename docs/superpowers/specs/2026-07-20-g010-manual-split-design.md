# G-010 补充拆分 — 12个文件手动安全拆分

## 背景

751feb64 提交通过自动化工具拆分了 9 个超 400 行文件。但另有 12 个文件（11 个预存违规 + file_index.py）自动化提取导致大量 import 断裂，需手动逐个安全拆分。

同时 G-012 门禁报模板 DB 未执行迁移——根因是 `pilotstd/core/db/__init__.py` 未导入 `migrations` 模块，导致 `@migration` 装饰器未触发，`MIGRATIONS` 字典为空。

## 目标

- G-012 修复：1 行改动，确保迁移链正常执行
- 12 个文件拆分：每个文件 ≤ 300 逻辑行
- 零 import 断裂：外部调用方无需修改
- 所有现有测试通过

## G-012 修复

**文件**：`pilotstd/core/db/__init__.py`
**改动**：添加 `from . import migrations  # noqa: F401`
**原理**：`@migration` 装饰器依靠模块导入触发注册。当前 `__init__.py` 只导出 `Database` 和 `_constants`，未导入 `migrations`，导致 `MIGRATIONS` 字典为空，Database 构造时 `_run_migrations()` 无迁移可执行。

## 文件拆分方案

### 执行顺序（由外向内，无状态到有状态）

| 序号 | 原文件 | 拆分目标 | 风险等级 |
|------|--------|---------|---------|
| 1 | `_table_ops.py` (404行) | `_table_io.py` (~180行) + 保留(~230行) | 低 |
| 2 | `file_index.py` (400行) | `_file_index_query.py` (~200行) + 保留(~200行) | 低 |
| 3 | `_ui_setup.py` (425行) | `_ui_toolbar.py` (~160行) + `_ui_layout.py` (~160行) + 保留(~120行) | 中 |
| 4 | `__init__.py` main_window (452行) | `_window_lifecycle.py` (~200行) + 保留(~250行) | 中 |
| 5 | `_core.py` (506行) | `_core_adapters.py` (~160行) + `_core_init_query.py` (~170行) + 保留(~200行) | 高 |
| 6 | `njbz365.py` (432行) | `_njbz365_session.py` (~230行) + 保留(~210行) | 中 |
| 7 | `_batch.py` (463行) | `_batch_dispatch.py` (~250行) + 保留(~220行) | 中 |
| 8 | `announce_service.py` (440行) | `_announce_fetch.py` (~250行) + 保留(~200行) | 中 |
| 9 | `_query.py` (509行) | `_query_exec.py` (~190行) + `_query_report.py` (~170行) + 保留(~170行) | 高 |
| 10 | `_base.py` (470行) | `_base_properties.py` (~240行) + 保留(~240行) | 中 |
| 11 | `validity_checker.py` (446行) | `_validity_pipeline.py` (~200行) + 保留(~250行) | 中 |
| 12 | `_message_builders.py` (492行) | `_builders_validity.py` (~200行) + `_builders_batch.py` (~190行) + `_builders_system.py` (~190行) + 保留(~20行) | 低 |

### 各文件拆分详情

#### 1. _table_ops.py → _table_io.py
- **提取**：`_on_save_result`, `_save_txt`, `_save_csv`, `_row_get`, `_get_visible_cols`, `_table_to_list`
- **保留**：表格操作/右键菜单/复制/列可见性控制
- **策略**：纯函数提取，无类依赖

#### 2. file_index.py → _file_index_query.py
- **提取**：`get`, `get_all`, `find_by_standard`, `find_by_hash`, `find_moved_files`, `get_full_info`, `count`, `get_status_stats`
- **保留**：`__init__`, 校验, upsert/remove/clear 等写操作
- **注意**：拆分后两文件头部加 `# THREADING: single-threaded` 注释

#### 3. _ui_setup.py → _ui_toolbar.py + _ui_layout.py
- `_ui_toolbar.py`：`setup_menu`, `_make_toolbar_btn`, `setup_toolbar`
- `_ui_layout.py`：`setup_file_tree`, `setup_work_table`, `setup_log_panel`, `setup_central`, `setup_status_bar`
- 保留：`__init__`, `setup_tray`, `on_tray_activated`, `setup_log_handler`, `setup_scanner`, `setup_auto_save`, `on_shutdown_aggregator`, `set_toolbar_enabled`, `get_library_root`
- **注意**：确认 toolbar 是 `self.toolbar` 实例属性而非局部变量

#### 4. __init__.py → _window_lifecycle.py
- **提取**：`_restore_from_tray`, `_quit_app`, `changeEvent`, `closeEvent`, `run_auto`, `_stop_workers`, `_on_auto_save`, `_on_atexit_save`, `_collect_state`
- 保留：`__init__`, `_init_core`, UI 回调
- **注意**：生命周期方法加防御性检查 `if not hasattr(self, '_core'): return`；确保 `_init_core()` 和 UI 回调注册顺序不变

#### 5. _core.py → _core_adapters.py + _core_init_query.py
- `_core_adapters.py`：`_TableOpsAdapter`, `_DialogOpsAdapter`, `_TaskOpsAdapter`, `_QueryWorkerFactoryAdapter`
  - 顶部添加类型注解注释标明每个适配器期望的宿主接口契约
- `_core_init_query.py`：`_init_query`, `_init_query_ui`(94行), `_init_query_connections`, `_init_query_state`
  - 检查 `_init_query_ui` 是否可进一步分为 UI 创建 + 信号绑定
- 保留：`__init__` + 其余 `_init_*` 方法

#### 6. njbz365.py → _njbz365_session.py
- **提取**：`_ensure_session`, `_refresh_csrf`, `_retry_request`, `_compute_sign`, `_build_base_params`, `_do_request`
- 保留：业务方法 `_search`, `_search_candidates`, `_fetch_replaces`, `_post_process_result`, `fetch_replaces_detail`

#### 7. _batch.py → _batch_dispatch.py
- **提取**：`_init_batch_state`, `_bucket_items`, `_setup_dispatch_context`, `_bucket_worker`, `_dispatch_queries`, `_collect_csres_results`, `_finalize_batch` + 辅助函数
- 保留：`BatchHandler.__init__`, `query_standards`, `query_batch_parsed`

#### 8. announce_service.py → _announce_fetch.py
- **提取**：`_get_ocr_provider`, `_get_or_create_engine`, `_write_checkpoint`, `_record_fetch_failure`, `check_announcements`, `check_announcements_filtered`, `trigger_fetch`, `_run_fetch_task`, `check_with_notification`, `_after_fetch`
- 保留：核心调度/锁/统计/查询方法 + 导入委托

#### 9. _query.py → _query_exec.py + _query_report.py
- `_query_exec.py`：`_query_announcement_match`, `_build_result_from_cache`, `_query_via_cache`, `_query_via_engine`, `_finalize_query`, `query`, `query_stream`
- `_query_report.py`：`_report_category_breakdown`, `_report_download_queue`, `_report_query_summary`, `_parse_std_number`, `_classify_after_query`, `_resolve_replaces`
- 保留：`__init__` + 委派/状态方法

#### 10. _base.py → _base_properties.py
- **提取**：所有 `@property` 快捷访问器（~40个 2行方法）
- 保留：`__init__` + `_init_*` 初始化 + `_bind_methods` + `shutdown`

#### 11. validity_checker.py → _validity_pipeline.py
- **提取**：`_sample_due_standards`, `_process_validity_batch`, `_finalize_validity_round`, `run_validity_check`
- 保留：`ValidityChecker` 类

#### 12. _message_builders.py → 3个 builder mixin
- `_builders_validity.py`：7 个有效性检查 builder 方法
- `_builders_batch.py`：6 个批次/查询/下载 builder 方法
- `_builders_system.py`：7 个系统/备份/错误 builder 方法
- 保留：`class MessageBuildersMixin(_ValidityBuilders, _BatchBuilders, _SystemBuilders): pass`

## 验收清单

- [ ] G-012 通过（`python scripts/check_g_012_sql_schema.py` 零不一致）
- [ ] G-010 通过（`python scripts/check_g_010_code_size.py` 零违规）
- [ ] `pytest -x` 全量通过
- [ ] IDE Pylance/Mypy 零 Unresolved import 或 AttributeError 误报
- [ ] GUI 冒烟测试：工具栏可用、表格右键菜单正常、查询功能完整、托盘恢复/关闭正常
- [ ] `__all__` 导出一致性（若原文件有定义）
- [ ] Docstring 不丢失
- [ ] 每步拆分后单独 git commit
