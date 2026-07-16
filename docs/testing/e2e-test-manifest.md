# E2E 测试用例索引

> 最后更新：2026-07-16
> 基于实际代码状态验证，数据来源：`pytest tests/gui/ -m e2e --collect-only -q`

---

## 测试总览

| 指标 | 数值 |
|------|------|
| E2E 测试文件 | 20 |
| E2E 测试用例 | 28 |
| 覆盖 Handler | 18 |

---

## 测试文件明细

### 自动管线

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_auto_pipeline.py](../tests/gui/test_auto_pipeline.py) | AutoUIHandler | 2 | 全流程（有文件/空目录） |
| [test_e2e_auto.py](../tests/gui/test_e2e_auto.py) | AutoUIHandler | 1 | 自动管线注册 |

### 公告

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_announce.py](../tests/gui/test_e2e_announce.py) | AnnounceUIHandler | 2 | 公告检查守卫（启用/禁用） |

### 查询

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_query.py](../tests/gui/test_e2e_query.py) | QueryUIHandler | 0 | 无 `@pytest.mark.e2e` 标记 |
| [test_e2e_query_summary.py](../tests/gui/test_e2e_query_summary.py) | QuerySummaryHandler | 2 | 查询结果分桶 |

### 扫描

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_scan.py](../tests/gui/test_e2e_scan.py) | ScanUIHandler | 2 | 扫描填充表格（目录/单文件） |

### 下载

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_download.py](../tests/gui/test_e2e_download.py) | DownloadUIHandler | 2 | 下载过滤（空/守卫） |

### 清理

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_cleanup.py](../tests/gui/test_e2e_cleanup.py) | CleanupHandler | 2 | 空目录扫描（完全空/仅过期） |

### 对话框

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_dialog.py](../tests/gui/test_e2e_dialog.py) | DialogUIHandler | 1 | 对话框处理器不在 core 中 |
| [test_e2e_file_dialog.py](../tests/gui/test_e2e_file_dialog.py) | FileDialog | 1 | 文件选择对话框 |

### 文件树

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_file_tree.py](../tests/gui/test_e2e_file_tree.py) | FileTreeHandler | 1 | 文件树处理器不在 core 中 |

### 持久化

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_persistence.py](../tests/gui/test_e2e_persistence.py) | PersistenceHandler | 2 | 窗口几何/分割器尺寸持久化 |

### 项目管理

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_project.py](../tests/gui/test_e2e_project.py) | ProjectHandler | 1 | 项目状态恢复 |

### 设置

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_settings.py](../tests/gui/test_e2e_settings.py) | SettingsHandler | 1 | 设置处理器需要对话框 |
| [test_e2e_settings_io.py](../tests/gui/test_e2e_settings_io.py) | SettingsIOHandler | 1 | 设置 I/O 需要设置处理器 |

### 表格

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_table.py](../tests/gui/test_e2e_table.py) | TableHandler | 1 | 表格处理器不在 core 中 |
| [test_e2e_table_helper.py](../tests/gui/test_e2e_table_helper.py) | TableHelper | 1 | 表格辅助处理器不在 core 中 |

### 主题

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_theme.py](../tests/gui/test_e2e_theme.py) | ThemeHandler | 1 | 主题处理器需要视觉验证 |

### 导出

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_e2e_export.py](../tests/gui/test_e2e_export.py) | ExportHandler | 1 | 导出树收集 |

### 事件总线

| 文件 | 覆盖 Handler | 测试数 | 说明 |
|------|-------------|--------|------|
| [test_event_bus_integration.py](../tests/gui/test_event_bus_integration.py) | EventBus | 3 | 自动管线事件/扫描事件/迁移回归 |

---

## 维护说明

- 新增 Handler 后，必须在 `tests/gui/` 下新增对应的 `test_e2e_*.py` 文件
- 测试函数需标记 `@pytest.mark.e2e` 方可被 CI 的 `-m e2e` 筛选
- 所有 E2E 测试仅运行于 Windows CI（`test-e2e` job），需要 `PyQt6` + `pytest-qt`
