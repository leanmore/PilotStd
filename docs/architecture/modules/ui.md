# 模块文档：UI 主窗口（MainWindow）

| 属性 | 值 |
|------|-----|
| 模块路径 | `pilotstd/ui/main_window/` |
| G-031 映射 | `pilotstd/ui/main_window/` |
| 核心类 | `MainWindow(QMainWindow)` |
| 子模块数 | 14 个 parts + 14 个 Handler |
| 总行数 | ~1,700（main_window + parts） |
| 状态 | 活跃 |

## 模块职责

PilotStd 桌面端的主窗口界面，提供三段式布局（文件树 / 工作表 / 操作日志），作为所有用户操作的视觉入口和结果展示层。通过 Handler 组合模式（非 Mixin 继承）将业务逻辑委托给 `MainWindowCore` 及 14 个 Handler。

## 架构

```
MainWindow (QMainWindow)
├── 布局
│   ├── 左侧: 文件导航树 (200px)
│   ├── 中间: 工作表格 (stretch)
│   └── 右侧: 操作日志 (240px)
├── MainWindowCore (组合容器)
│   ├── ScanUIHandler        — 扫描触发与进度
│   ├── QueryUIHandler       — 查询结果展示
│   ├── DownloadUIHandler    — 下载队列管理
│   ├── ArchiveUIHandler     — 归档操作
│   ├── AutoHandler          — 自动流水线
│   ├── AnnounceUIHandler    — 公告界面
│   ├── SettingsHandler      — 设置面板
│   ├── ExportHandler        — 导出
│   ├── CleanupHandler       — 清理
│   ├── DialogHandler        — 对话框
│   ├── FileDialogHandler    — 文件选择
│   ├── ThemeHandler         — 主题/语言/图标
│   └── UISetupHandler       — UI 组装
└── parts/ (方法注入)
    ├── _actions_ops.py      — 菜单动作
    ├── _delegate_ops.py     — 业务委托
    ├── _table_ops.py        — 表格操作
    ├── _file_tree_ops.py    — 文件树操作
    ├── _query_ops.py        — 查询操作
    ├── _theme_ops.py        — 主题操作
    └── ... (共 14 个)
```

## Handler 组合模式

> 旧版 28 个 Mixin 已在 2026-07-11 全部重构为 Handler 组合模式。参见 [STATUS.md](../../../STATUS.md)。

- `MainWindow.__init__()` 中构造 `MainWindowCore` 容器
- 每个 Handler 通过 callback 回调 MainWindow 的 UI 方法
- Handler 之间不直接通信，通过 `MainWindowCore` 共享状态
- `parts/` 目录下的方法片段通过 `from .parts._xxx import method` 注入为 MainWindow 实例方法

## 工作流

```
扫描 → 查询 → 下载 → 规范化 → 归档
  │       │       │        │        │
  v       v       v        v        v
ScanUI  QueryUI DownloadUI NormalizeUI ArchiveUI
Handler Handler  Handler    (worker)   Handler
```

## 依赖关系

- `pilotstd/manager/` — `StandardManager` 门面（`self._mgr`），所有业务操作的入口
- `pilotstd/ui/core/_core.py` — `MainWindowCore` 依赖容器
- `pilotstd/ui/core/_core_adapters.py` — 协议适配器（`ITableOps` 等），懒加载 `pilotstd.ui.workers` 的类型（如 `RowUpdate`）
- `pilotstd/core/config/` — 配置管理
- `pilotstd/core/project.py` — 项目管理

## 相关文档

- [管理模块](manager.md) — `StandardManager` 门面架构
- [ADR-001](../../adr/ADR-001-modal-dialog-auto-clicker.md) — 模态对话框自动处理
