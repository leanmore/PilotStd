# Testing Playbook

GUI 层测试实战经验沉淀。每次补测批次完成后更新。

---

## Playbook v0.3 更新 (2026-08-02)

### NEW: Handler 模式测试范式
- 适用：非 QWidget 继承类，Qt 对象作为方法参数传入
- 构造：真实实例化 Handler，仅 mock 外部依赖（config/mgr/callback）
- Qt 容器：使用真实 QTableWidget/QModelIndex 等作为数据载体，qtbot.addWidget() 管理生命周期
- 禁止：mock Qt 数据容器本身（QTableWidgetItem、QModelIndex 等）
- 源码核验必做：Handler 属性归属（如 file_index 在 mgr 上）、方法签名参数数量、返回值类型必须逐行对照源码，AI 草案默认假设不可信

### NEW: Windows pytest-cov 路径规范
-  `--cov=pilotstd/ui/core/handlers/_table_helper`
-  `--cov=pilotstd.ui.core.handlers._table_helper`
- 原因：Windows 下反斜杠被 shell 转义，正斜杠不被 pytest-cov 识别为模块路径

### NEW: UI 层跳过标准
满足任一条件即标记 E2E scope，不写单元测试：
1. QMenu/QFileDialog 多 action 分支（≥5 个）
2. 纯命令式 UI 构建代码（addAction/setText 等），无业务逻辑
3. clipboard/拖拽等全局单例交互，且核心逻辑未提取为纯函数

### REVISED: 覆盖率增量验证节奏
- 每批次 ≤10 个测试，执行时间 ≤1s
- 立即 commit + push，不累积多批次
- 覆盖率命令必须在提交前实际运行并确认数字变化

### TECH-DEBT: 双 Toolbar 创建路径
- _UISetupToolbarMixin.setup_toolbar 与 _ui_setup_ops.py:122 存在独立 QToolBar 创建
- 状态：待确认是否为历史冗余或功能分离
- 优先级：P2，不阻塞补测

---

## Playbook v0.2 (2026-08-02)

P0-B 批次（4 方法 × 9 测试）经验沉淀。

### Handler 纯逻辑方法测试模式
- 真实实例化 Handler → mock config/mgr/callback 三个外部依赖
- 使用 ParsedStdInfo + RowUpdate 构造真实数据对象
- QTableWidget 作为数据容器，不 mock

### 覆盖率命令修正
- 发现 `--cov=path/to/module` 在 Windows 上报 0%
- 修正为 `--cov=python.module.path` 格式

---

## Playbook v0.1 (2026-08-02)

P0-A 批次（QueryWorker + AutoWorker 共 4 方法）经验沉淀。

### Worker 测试模式
- 真实实例化 Worker（线程不启动）
- mock 外部依赖（adapter/mgr/config），不 mock 内部信号
- set_pause_event 通过 threading.Event 验证状态转换

### Qt 信号测试
- 使用 qtbot.waitSignal 而非手动 sleep
- 验证信号参数类型和值，不只看信号是否发射
