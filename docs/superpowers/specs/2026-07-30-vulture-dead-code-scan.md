> ⚠️ **ARCHIVED (2026-08-19): 不再维护。** 08-02 已执行死代码清理，纯历史快照
>
---

# Vulture 死代码扫描报告 — handlers 目录

**扫描日期**：2026-07-30  
**扫描工具**：vulture 2.16  
**扫描范围**：`pilotstd/ui/core/handlers/`（排除 `*_flow_engine.py`）  
**复核人**：AI（逐条 grep 验证）

---

## 1. 扫描参数

| 参数 | 值 |
|------|-----|
| 主阈值 | 80%（正式判定） |
| 补充阈值 | 60%（Phase 1 靶点发现） |
| 排除规则 | `*_flow_engine.py` |
| 扫描文件数 | 24 个 .py 文件 |

---

## 2. 80% 置信度结果

### 原始发现：4 条

| # | 文件 | 行号 | 发现 | 置信度 |
|---|------|------|------|--------|
| 1 | protocols.py | 42 | unused variable 'task_name' | 100% |
| 2 | protocols.py | 52 | unused variable 'task_id' | 100% |
| 3 | protocols.py | 53 | unused variable 'task_id' | 100% |
| 4 | protocols.py | 54 | unused variable 'task_id' | 100% |

### 误报剔除：4 条（100%）

| # | 剔除理由 |
|---|---------|
| 1 | `protocols.py:42` — `IDialogOps.stage_prereq_dialog` 是 `typing.Protocol` 接口 stub，参数 `task_name` 是 API 契约文档的一部分，stub 体（`...`）中必然"未使用"。存活。 |
| 2-4 | `protocols.py:52-54` — `ITaskOps` Protocol 接口的 `update_task_status`、`task_completed`、`get_task_status` 方法，参数 `task_id` 同样是接口签名文档。存活。 |

### 真实死代码：0 条

**80% 阈值结论：handlers 目录（排除 flow_engine）零真实死代码。**

---

## 3. 60% 置信度 _actions.py 逐条验证（12 项）

### 3.1 关键发现：`ActionsHandler` 为已实例化但零调用的死类

`ActionsHandler` 在 `pilotstd/ui/core/_core.py:315` 被实例化为 `self.actions`，但 **`self.actions.` 在整个 `pilotstd/` 代码库中零调用**（含 `getattr` 动态访问检查）。mixin 方法（`_actions_ops.py`）有**独立重复实现**，未委托给 Handler。

### 3.2 逐条 grep 验证结果

| # | 行号 | 方法/属性 | Grep 结果 | 判定 | 判定依据 |
|---|------|----------|----------|------|---------|
| 1 | 49 | `_progress` | `_actions.py` 内仅 L49 赋值；`pilotstd/` 内无 `self.actions._progress` 读取 | **死代码** | 仅存储 `progress_callback`，从未读取或调用 |
| 2 | 63 | `init_manager` | `pilotstd/ui/` 内无 `.init_manager(` 调用；mixin `_init_manager`（`_actions_ops.py:43`）有独立实现 | **死代码** | 零外部调用，mixin 不委托 |
| 3 | 83 | `set_toolbar_enabled` | `self.actions.` 零调用；mixin `_set_toolbar_enabled`（`_actions_ops.py:69`）有独立实现 | **死代码** | 零外部调用 |
| 4 | 90 | `apply_announce_cache_mode` | `self.actions.` 零调用；mixin `_apply_announce_cache_mode`（`_actions_ops.py:81`）有独立实现 | **死代码** | `_settings_io.py:56` 和 `_settings.py:386` 通过 `hasattr(mw, "_apply_announce_cache_mode")` 调用的是 mixin 版本，非 handler |
| 5 | 99 | `switch_to_stage` | `self.actions.` 零调用；mixin `_switch_to_stage`（`_actions_ops.py:91`）有独立实现 | **死代码** | 零外部调用 |
| 6 | 126 | `on_cancel` | `self.actions.` 零调用；mixin `_on_cancel`（`_actions_ops.py:123`）有独立实现；Qt 信号槽 `.connect(self._on_cancel)` 绑定的是 mixin 版本 | **死代码** | Qt 信号槽绑定到 mixin，非 handler |
| 7 | 140 | `on_pause_toggle` | 同上模式；mixin `_on_pause_toggle`（`_actions_ops.py:144`）有独立实现 | **死代码** | Qt 信号槽绑定到 mixin |
| 8 | 166 | `on_rule_download` | `self.actions.` 零调用；mixin `_on_rule_download`（`_actions_ops.py:173`）有独立实现 | **死代码** | 零外部调用 |
| 9 | 169 | `on_task_center` | `self.actions.` 零调用；mixin `_on_task_center`（`_actions_ops.py:181`）有独立实现 | **死代码** | Qt 菜单绑定到 mixin |
| 10 | 178 | `on_settings` | `self.actions.` 零调用；mixin `_on_settings`（`_actions_ops.py:194`）有独立实现 | **死代码** | Qt 菜单绑定到 mixin |
| 11 | 251 | `on_check_update` | `self.actions.` 零调用；mixin `_on_check_update`（`_actions_ops.py:272`）有独立实现 | **死代码** | Qt 菜单绑定到 mixin |
| 12 | 291 | `on_about` | `self.actions.` 零调用；mixin `_on_about`（`_actions_ops.py:303`）有独立实现 | **死代码** | Qt 菜单绑定到 mixin |

### 3.3 连带死代码（vulture 未报告，但因父方法死代码而不可达）

`_actions.py` 中以下方法被上述 12 项中的方法内部调用，但入口方法本身已死，故连带不可达：

| 行号 | 方法 | 被谁内部调用 |
|------|------|-------------|
| 117 | `update_button_states` | 无外部调用 |
| 154 | `on_rule_query` | `on_rule_download`（L167）→ 死代码 |
| 189 | `try_check_update_throttle` | `on_check_update`（L260）→ 死代码 |
| 201 | `confirm_update_available` | `on_check_update`（L271）→ 死代码 |
| 223 | `download_update_file` | `on_check_update`（L281）→ 死代码 |
| 237 | `_prompt_restart` | `download_update_file`（L232）→ 死代码 |

### 3.4 测试覆盖确认

- `tests/gui/test_coverage_actions.py` — 测试的是 **mixin 方法**（`window._init_manager()` / `window._switch_to_stage()` 等），非 `ActionsHandler` 方法
- `tests/test_ui_handlers_init.py` — 仅验证 `ActionsHandler` 可导入且是 type，不测试任何方法
- `tests/test_ui_core.py:354` — `@patch("pilotstd.ui.core._core.ActionsHandler")` mock 了类本身，不测试其实例方法

**`ActionsHandler` 任何方法的测试覆盖：0 行。**

---

## 4. 存活未覆盖代码清单（Phase 1 靶点）

### 4.1 核心矛盾

`_actions.py`（243 行）处于灰色地带——不是"存活未覆盖"，而是**"已实例化但从未调用"**。这在分类上更接近死代码，但其架构意图（回调注入、纯逻辑提取）明确，更可能是**未完成的重构**。

### 4.2 推荐处理路径

| 路径 | 描述 | Phase 1 工作量 |
|------|------|---------------|
| **A：完成委托（推荐）** | 将 mixin 方法改为薄层，委托给 `self.actions.xxx()`，为 Handler 写纯逻辑测试 | 改 ~80 行 mixin + 写 ~150 行测试 |
| B：删除 Handler | 删除 `_actions.py` + `actions_flow_engine.py` + `_core.py` 实例化代码 | 删 ~300 行，零测试 |
| C：维持现状 | 不做任何改动 | 零工作量，但死代码留在仓库 |

路径 A 的收益：
- 消除 mixin/handler 重复实现（~80 行重复逻辑）
- Handler 方法接受回调注入，可纯内存测试，无需 QApplication
- 符合项目"纯逻辑提取"范式（`project_persistence_engine_pattern`、`project_download_flow_engine_pattern`）

### 4.3 _actions.py 目标覆盖率（路径 A）

```
当前覆盖率：0%（Handler 方法零测试）
存活代码行数：~170 行（排除 import/注释/空白/类定义）
目标 = min(0 + 170 × 0.7, 70%) = 70%
```

### 4.4 非 _actions.py 的 60% 发现（Phase 1 次要靶点）

以下 5 项来自其他 handler 文件，在 60% 阈值下被标记。**建议 Phase 1 只聚焦 `_actions.py`，以下各项作为 Phase 1.1 可选任务**：

| 文件 | 行号 | 方法 | 置信度 | 初判 |
|------|------|------|--------|------|
| `protocols.py` | 31 | `get_table_as_list` | 60% | Protocol stub，存活 |
| `protocols.py` | 34 | `get_selected_seq` | 60% | Protocol stub，存活 |
| `protocols.py` | 44 | `info_dlg` | 60% | Protocol stub，存活 |
| `protocols.py` | 45 | `warning_dlg` | 60% | Protocol stub，存活 |
| `protocols.py` | 52-54 | `update_task_status`/`task_completed`/`get_task_status` | 60% | Protocol stub，存活 |
| `protocols.py` | 61 | `create_pending_query_dialog` | 60% | Protocol stub，存活 |
| `query_worker_factory.py` | 16 | `QueryWorkerFactory` | 60% | 待验证，疑似存活 |

---

## 5. 复核方法说明

- 对 12 项逐一执行 `grep -rn` 全代码库搜索
- 额外检查 `getattr` 动态访问、`.ui` 文件信号槽声明、lambda/partial 包装模式
- 交叉验证 mixin 方法（`_actions_ops.py`）与 handler 方法（`_actions.py`）是否为委托关系
- 确认 `self.actions.` 在 `pilotstd/` 全代码库零调用

---

## 6. 决策点

请选择路径（A / B / C）以确定 Phase 1 的执行方向：

- **A**：完成委托重构 + 为 Handler 写测试（推荐，对齐项目范式）
- **B**：删除 ActionsHandler 死代码
- **C**：维持现状，跳过 _actions.py，Phase 1 聚焦其他文件
