# ADR-008: GUI 测试 _wait_worker 消除与 wait_for_worker_and_ui 沉淀

> 日期：2026-08-02
> 状态：✅ Accepted
> 关联：C1-C4 重构系列

---

## 背景

PilotStd GUI 测试套件中存在多处独立复制的 `_wait_worker` 辅助函数，用于等待 QThread Worker 完成。这些副本存在三个结构性问题：

1. **信号竞态**：Mock 环境下 Worker 在 0.0s 内完成，`finished_signal` 在 `qtbot.waitSignal()` 注册监听器前发射，导致 30s 超时
2. **UI 异步间隙**：Worker 线程结束后，handler 回调（如 `_on_normalize` → `_add_table_row`）在 Qt 事件循环中异步执行，`_wait_worker` 未等待 UI 更新
3. **代码重复**：5 个测试文件各自定义近 40 行的 `_wait_worker`，总计 ~190 行重复代码

---

## 决策

**分阶段消除 `_wait_worker`，沉淀 `wait_for_worker_and_ui` 原子 helper + 可复用 predicate 库。**

### 架构

```
tests/gui/helpers/
  __init__.py          wait_for_worker_and_ui(qtbot, window, attr, ui_predicate)
  predicates.py        worker_done, table_has_rows, status_contains, ...
```

`wait_for_worker_and_ui` 执行两层原子等待：

| 层 | 机制 | 职责 |
|:--:|------|------|
| L1 | `qtbot.waitUntil(not worker.isRunning())` | 等待 Worker 线程结束 |
| L2 | `qtbot.waitUntil(ui_predicate)` | 等待 UI 状态收敛 |

### 信号竞态修复

弃用 `qtbot.waitSignal(finished_signal)`，改用 `qtbot.waitUntil(not w.isRunning())` 轮询线程状态。即使 Worker 在函数调用前已结束，`isRunning()` 立即返回 `False`，不会超时。

### Predicate 库

语义化 lambda 减少内联重复：

| Predicate | 替换 | 适用场景 |
|-----------|------|----------|
| `worker_done()` | `lambda: True` | 仅需确认线程结束 |
| `table_has_rows(window)` | `lambda: window.work_table.rowCount() > 0` | 扫描/查询后验证数据 |
| `status_contains(window, "完成")` | `lambda: "完成" in window.status_label.text()` | 操作完成状态验证 |
| `file_exists(path)` | `lambda: Path(path).exists()` | 归档/下载文件验证 |

---

## 迁移阶段

| 阶段 | 文件 | 迁移数 | 关键动作 |
|:--:|------|:------:|----------|
| C1 | helpers/__init__.py + test_helpers.py | 新建 | 创建原子 helper + 6 场景单元测试 |
| C2 | test_organize.py + normalize.py | 1 | 首个迁移验证 + 临时诊断日志 |
| C3 | test_full_pipeline.py / test_organize.py / test_download.py / test_manual_workflow.py | 28 | 批量迁移 + 删除所有本地定义 |
| C4 | predicates.py + stress_winui.py | 1 | 提取语义 predicate + deprecated 删除 |

**总计**：30 调用点迁移，~190 行重复代码消除，全项目 `_wait_worker` 零残留。

---

## 影响

- **CI 稳定性**：消除全部信号竞态导致的间歇性超时
- **可维护性**：新测试只需 1 行 `wait_for_worker_and_ui` + 语义 predicate
- **可扩展性**：新增 Worker 类型的 predicate 只需在 `predicates.py` 加一个函数

---

## 防回潮措施

CI 添加 lint gate：
```bash
grep -rn '_wait_worker' tests/ --include='*.py' && echo "ERROR: _wait_worker is deprecated" && exit 1
```
