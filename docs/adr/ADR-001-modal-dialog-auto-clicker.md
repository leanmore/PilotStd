# ADR-001: ModalDialogAutoClicker — 事件驱动模态对话框自动处理

| 属性 | 值 |
|------|-----|
| 状态 | ✅ Accepted |
| 日期 | 2026-07-14 |
| 决策者 | 项目治理顾问 |
| 实现提交 | `e07d80af` |
| Related to | [ADR-010-mixin-refactor](ADR-010-mixin-refactor.md)（原 ADR-001 编号由本文件承接，mixin 版重编号为 ADR-010；两者为独立决策，无取代关系） |

> **Note**: 本 ADR 与 ADR-010（原 ADR-001）共享编号历史，但两者为独立决策，无取代关系。

## 背景

PilotStd 的 GUI 测试套件（`tests/gui/`）在 CI 中运行时，PyQt6 模态对话框（`QMessageBox`、`QDialog`）会阻塞测试执行。测试线程在 `QDialog.exec()` 处挂起，等待人工点击关闭，导致 CI 超时失败（45 分钟 `timeout-minutes`）。

已有的 `_suppress_dialogs` 机制通过在业务代码中检查标志位来跳过弹窗，但存在以下局限：

1. 并非所有对话框都检查该标志（如 `_question_dlg` 直接 `exec()`）
2. 每个新的对话框都需要手动添加检查逻辑
3. `_on_cancel` 会将 `_suppress_dialogs` 重置为 `False`，导致后续操作弹出对话框

测试文件中对 `_suppress_dialogs = True` 的依赖意味着：

- 测试代码需了解业务代码的内部对话框逻辑
- 业务代码需要为测试场景保留 `_suppress_dialogs` 检查
- 修改对话框逻辑时需同步修改所有相关测试

## 决策

**采用事件驱动的 `ModalDialogAutoClicker`，在 Qt 事件层拦截并自动关闭模态对话框。**

### 实现原理

```
QApplication.eventFilter()
  ├── QEvent.Type.Show / WindowActivate
  │   └── 检测 obj 是否为模态 QDialog / QMessageBox
  │       └── QTimer.singleShot(10ms) → 延迟点击确认按钮
  └── 其他事件 → 透传
```

### 点击优先级

```
QMessageBox: Ok → Yes → Close → Cancel → 首个可用按钮
QDialog:     QDialogButtonBox(Ok→Yes→Close→Cancel) → 首个 QPushButton
```

### 关键设计决策

1. **事件驱动而非轮询**：监听 Qt 原生 `Show`/`WindowActivate` 事件，不使用 `QTimer` 轮询，零 CPU 开销
2. **延迟点击**：`QTimer.singleShot(10ms)` 确保对话框完全初始化后再点击，避免竞态
3. **autouse fixture**：`@pytest.fixture(autouse=True)` 使所有 GUI 测试自动受益，无需逐个测试修改
4. **干净清理**：`cleanup()` 在测试结束后移除事件过滤器，不影响后续测试
5. **非侵入**：不修改任何业务代码，不碰 `_suppress_dialogs`、`_on_cancel` 等逻辑

## 后果

### 正面

- **CI 稳定性**：所有 GUI 测试不再因对话框挂起而超时
- **零业务代码修改**：对话框逻辑保持原样，`_suppress_dialogs` 机制继续服务于生产环境的自动模式
- **测试简化**：测试代码无需手动处理对话框，恢复原始测试逻辑（如 `test_cancel_stops_query_worker` 回退为简洁版本）
- **覆盖全面**：新对话框自动获得点击处理，无需逐个添加
- **可观察**：若对话框出现在非预期时间，测试仍会因后续断言失败而暴露问题（而非静默通过）

### 负面

- **隐蔽性**：对话框被自动关闭，测试不会因"出现了不该出现的对话框"而失败（可通过断言对话框文本间接验证）
- **事件过滤器开销**：全局事件过滤器对每个 Qt 事件进行类型检查，但在测试套件规模下可忽略

## 备选方案

| 方案 | 描述 | 为何不采纳 |
|------|------|-----------|
| A. 轮询定时器 | `QTimer` 每 100ms 检测弹窗并点击 | CPU 空转，需手动调整间隔，竞态风险 |
| B. 完善 `_suppress_dialogs` | 在所有对话框中添加标志检查 | 侵入业务代码，每新增对话框都需添加 |
| C. 逐测试手动处理 | 每个测试中显式 `click_modal_button()` | 重复代码，新测试容易遗漏 |
| D. Mock 对话框类 | Monkey-patch `QMessageBox.exec` 返回预设值 | 不测试真实对话框行为，过度隔离 |

方案 D 在特定场景（如需要验证对话框文本内容）中可作为补充手段，但不替代本方案。

## 相关链接

- 实现文件：`tests/gui/conftest.py` — `ModalDialogAutoClicker` 类 + `auto_handle_modal_dialogs` fixture
- 受影响的测试：`tests/gui/test_manual_workflow.py`、`tests/gui/test_query.py` 等所有 GUI 测试
- 门禁：`.github/workflows/ci.yml` — `test-gui` job
