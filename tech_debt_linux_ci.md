# Linux CI 技术债专项

> 来源：Windows 覆盖率基线锁定（57%）— 2026-08-01
> 归属：本文件为 Windows 覆盖率任务的正式交付物，同时作为 Linux CI 专项的唯一输入文档

## P0: GUI 系统性挂起（79 文件）

### 根因
Windows 下 `pytest-timeout` 的 `timeout_method=thread` 无法中断 PyQt6 C++ 事件循环。
Linux 下可用 `timeout_method=signal` (SIGALRM) 强制中断。

### 文件清单（tests/gui/）
```
test_actions_flow_engine.py    test_announce_flow_engine.py
test_archive_flow_engine.py    test_archive_worker.py
test_auto_flow_engine.py       test_auto_pipeline.py
test_cleanup_flow_engine.py    test_context_menu.py
test_context_menu_signals.py   test_coverage_actions.py
test_coverage_dialogs.py       test_coverage_export.py
test_coverage_filetree.py      test_coverage_final.py
test_coverage_final2.py        test_coverage_guards.py
test_coverage_mainwindow.py    test_coverage_misc.py
test_coverage_queries.py       test_coverage_table.py
test_coverage_theme.py         test_coverage_workers.py
test_dialog_flow_engine.py     test_dialogs.py
test_download.py               test_download_flow_engine.py
test_download_handler_c1.py    test_e2e_announce.py
test_e2e_auto.py               test_e2e_cleanup.py
test_e2e_download.py           test_e2e_export.py
test_e2e_file_tree.py          test_e2e_organize.py
test_e2e_project.py            test_e2e_query.py
test_e2e_query_summary.py      test_e2e_scan.py
test_e2e_settings.py           test_e2e_table.py
test_event_bus_integration.py  test_file_tree_flow_engine.py
test_i18n_keys.py              test_init_all_handlers.py
test_main_window_table.py      test_notify_flow_engine.py
test_organize_flow_engine.py   test_persistence_flow_engine.py
test_project_flow_engine.py    test_query_flow_engine.py
test_query_summary_flow_engine.py test_query_worker_factory.py
test_rule_edit_dialog.py       test_scan_flow_engine.py
test_settings_io_flow_engine.py test_table_flow_engine.py
test_table_helper_flow_engine.py test_task_center_dialog.py
test_themes.py                 test_toolbar_flow_engine.py
test_toolbar_signal_bindings.py test_tray_signals.py
test_ui_core.py                test_watcher_flow_engine.py
test_welcome_dialog.py         test_workers.py
(79 files total)
```

### Linux CI 执行命令模板
```bash
xvfb-run -a -s "-screen 0 1920x1080x24" \
  pytest tests/gui/ \
    --cov=pilotstd --cov-append \
    --timeout=15 --timeout_method=signal \
    -v --tb=long -p no:warnings
```

### 预期回收
- 79 文件 × 估算 50-80% 覆盖 = **3.0–4.0pp**

---

## P1: 并发死锁（18 root 文件）

### 根因
`threading.Lock()` 在测试间共享，前序测试的后台线程持有锁未释放。

### 文件清单（tests/）
```
test_announce_engine.py        test_ci_scan_fix.py
test_core.py                   test_file_index_full.py
test_final_complete.py         test_group1_announcement_manager.py
test_manager_unit.py           test_migrations_full.py
test_mock_pipeline.py          test_monitor.py
test_monitor_scheduler.py      test_network.py
test_notification_e2e.py       test_observability.py
test_query.py                  test_system_api.py
test_task_scheduler.py         test_ui_core.py
```

### 重构检查项
- [ ] 将 `threading.Lock` 改为 `threading.RLock`（可重入）
- [ ] 在 `MonitorStats._flush()` 等关键路径添加 `lock.acquire(timeout=5)`
- [ ] 确保所有 `start()` 的线程在 `teardown` 中 `join(timeout=5)`

### 预期回收
- **0.5–1.0pp**

---

## P2: 网络依赖（1 文件）

### 文件
`tests/test_e2e_adapters.py`

### 修复方案
用 `responses` 库 mock 外部 API 调用，或标记 `@pytest.mark.integration` 在单元测试中跳过。

---

## 预期总回收
| 来源 | 文件数 | 预期增量 |
|------|--------|---------|
| P0 GUI | 79 | +3.0–4.0pp |
| P1 并发 | 18 | +0.5–1.0pp |
| P2 网络 | 1 | 微小 |
| **合计** | **98** | **+3.5–5.0pp → 目标 61–62%** |

## 当前状态
- Windows 基线: 57%（已锁定）
- 补测模块: 4/4 验证（99.5% avg）
- 有效测试: 2887/2984
