# ui/controllers/query_mixin.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **509** |
| 类 | 1 个（`QueryMixin`） |
| 方法数 | 10 个 |
| 外部引用 | 1 处（`main_window.py:67`） |

---

## 方法清单

| # | 方法 | 行数 | 职责 | 分组 |
|---|------|------|------|------|
| 1 | `_on_query_result_ready` | 49 | 实时刷新表格行（字段回写+颜色） | 查询执行 |
| 2 | `_on_query_batch_ready` | 4 | 批量刷新包装器 | 查询执行 |
| 3 | `_on_query` | 63 | 查询主入口：Worker 创建+信号连接+按钮状态 | 查询执行 |
| 4 | `_show_query_summary` | **129** | 查询完成后的摘要统计+通知+对话框 | 结果展示 |
| 5 | `_show_pending_dialog` | **113** | 待确认清单表格对话框+CSV 保存 | 待确认管理 |
| 6 | `_on_pending_query` | 8 | 待确认查询入口（异常处理包装） | 待确认管理 |
| 7 | `_do_pending_query` | 82 | CSV 导入+解析+站点选择+执行查询 | 待确认管理 |
| 8 | `_write_pending_to_db` | 3 | 写入待确认表（委托 manager） | 待确认管理 |
| 9 | `_resolve_pending_in_db` | 3 | 标记已处理（委托 manager） | 待确认管理 |
| 10 | `_check_pending_lookup` | 14 | 启动时检查待确认清单 | 待确认管理 |

**分组统计**：
- 查询执行：3 个方法，116 行
- 结果展示：1 个方法，129 行
- 待确认管理：6 个方法，223 行

---

## 拆分建议

```
pilotstd/ui/controllers/query/
├── __init__.py        ← from .mixin import QueryMixin（向后兼容）
├── mixin.py           ← _on_query, _on_query_result_ready, _on_query_batch_ready (~120行)
├── summary.py         ← _show_query_summary (~130行)
└── pending.py         ← _show_pending_dialog + _on_pending_query + _do_pending_query +
                          _write_pending_to_db + _resolve_pending_in_db + _check_pending_lookup (~225行)
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~5 | `from .mixin import QueryMixin` |
| `mixin.py` | ~120 | 核心查询逻辑 |
| `summary.py` | ~130 | 查询结果摘要展示 |
| `pending.py` | ~225 | 待确认管理（对话框+CSV+DB） |

### 导入兼容性

```python
# main_window.py 保持不变
from .controllers.query_mixin import QueryMixin
# → 改为
from .controllers.query import QueryMixin  # __init__.py 重导出
```

`main_window.py:67` 需要修改 1 行：
```python
- from .controllers.query_mixin import QueryMixin
+ from .controllers.query import QueryMixin
```

---

## 依赖关系

- **被引用**：`main_window.py:67`（唯一外部引用）
- **内部依赖**：`PendingQueryDialog`, `QueryWorker`, `RowUpdate`, `i18n`, `models.ParsedStdInfo`, `platform.notify.NotifyService`
- **无循环依赖**：QueryMixin 仅被 MainWindow 混入使用

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| 中 | 509 行不算极端，但 `_show_query_summary`（129行）和 `_show_pending_dialog`（113行）两个方法过于庞大 |
| 收益 | 按职责拆分后，每个文件 <250 行，可独立理解和测试 |
| 风险 | 仅 1 处外部引用需修改，影响面极小 |
