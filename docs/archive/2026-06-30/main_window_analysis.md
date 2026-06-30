# ui/main_window.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **942** |
| 类 | 1 个（`MainWindow`，~830 行）+ 1 个模块函数（`run`） |
| 混入类 | 15 个（AnnounceMixin, ArchiveMixin, ...） |
| 方法数 | 38 个 |
| 外部引用 | 仅 1 处（`ui/__init__.py`） |

---

## 方法清单

### UI Setup（9 方法，~346 行，37%）

| 方法 | 行数 | 职责 |
|------|------|------|
| `_setup_menu` | 70 | 创建菜单栏（文件/视图/扫描/查询/下载/工具/帮助） |
| `_setup_toolbar` | 82 | 创建工具栏按钮 + 信号连接 |
| `_setup_central` | 102 | 中心区域（表格+日志栏+进度条） |
| `_setup_tray` | 15 | 系统托盘 |
| `_setup_status_bar` | 5 | 状态栏 |
| `_setup_log_handler` | 16 | 日志输出到 QTextEdit |
| `_setup_scanner` | 9 | 扫描器初始化 |
| `_setup_auto_save` | 9 | 自动保存定时器 |

### 事件/生命周期（13 方法，~140 行，15%）

| 方法 | 行数 | 职责 |
|------|------|------|
| `__init__` | 38 | 构造（注入 config + project，设置 UI） |
| `_stop_workers` | 19 | 停止所有 Worker 线程 |
| `_on_cancel` | 21 | 取消当前操作 |
| `_on_pause_toggle` | 15 | 暂停/继续 |
| `closeEvent/changeEvent/quit/restore/tray` | 44 | 窗口生命周期 |

### 动作处理器（14 方法，~290 行，31%）

| 方法 | 行数 | 职责 |
|------|------|------|
| `_on_check_update` | **112** | **最大方法**：检查 GitHub Release → 下载 → 写 bat → 重启 |
| `get_pipeline_stats` | 24 | 流水线统计 |
| `_switch_to_stage` | 20 | 阶段切换 |
| `_update_button_states` | 18 | 按钮启用/禁用 |
| `_init_manager` | 29 | 延迟初始化 StandardManager |
| `_on_settings/about/rule_query/rule_download/task` | 44 | 各动作响应 |

### 其他（2 方法 ~16 行）

| 方法 | 行数 | 职责 |
|------|------|------|
| `_mgr` (getter/setter) | 13 | Manager 属性访问 |
| `_get_selected_path` | 11 | 获取选中路径 |
| `_apply_announce_cache_mode` | 8 | 公告缓存模式 |

---

## 分组统计

| 分组 | 方法数 | 行数 | 占比 |
|------|--------|------|------|
| UI Setup | 9 | 346 | 37% |
| 事件/生命周期 | 13 | 140 | 15% |
| 动作处理器 | 14 | 290 | 31% |
| 其他 | 2 | 16 | 2% |
| 属性/混入声明 | — | 150 | 15% |

---

## 依赖关系

| 类型 | 详情 |
|------|------|
| 混入 | 15 个（已独立在 `controllers/` 和 `widgets/` 中） |
| 外部引用 | 仅 `ui/__init__.py` 1 处 |
| 信号 | `status_changed`, `progress_changed`, `auto_save_signal` 等 |

---

## 拆分建议

```
pilotstd/ui/main_window/
├── __init__.py         ← MainWindow 核心（__init__ + 生命周期 + 属性 + 混入集成）
├── _ui_setup.py        ← _setup_menu + _setup_toolbar + _setup_central + _setup_tray + _setup_status_bar + _setup_log_handler + _setup_scanner
└── _actions.py         ← _on_check_update + get_pipeline_stats + _switch_to_stage + _init_manager + _on_* 等
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~400 | 核心类 + 生命周期 |
| `_ui_setup.py` | ~350 | UI 构建方法 |
| `_actions.py` | ~290 | 动作处理器 |

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| **中** | 942 行。已有良好的 mixin 拆分，剩余主要是 UI 构建代码和动作处理器 |
| 收益 | `_on_check_update` 112 行，`_setup_` 方法 346 行，独立后易于维护 |
| 风险 | 仅 1 处外部引用，极低风险 |
