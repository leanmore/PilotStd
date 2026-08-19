# ADR-006: 纯 UI 编排文件维持策略

> 日期：2026-07-16
> 状态：✅ Accepted
> 关联：[[ADR-002]]

---

## 背景

在 Handler 层治理过程中，对 20 个 Handler 文件逐一审查后，确认以下 5 个文件为 **纯 Qt 控件构建 + UI 编排**，不含可提取的业务逻辑。

---

## 决策：停止底层拆解

以下 Handler **不再创建 `*_flow_engine.py`**，仅通过现有 E2E 测试兜底行为底线：

| 文件 | 行数 | 方法数 | 内容特征 | 策略 |
|------|------|--------|---------|------|
| `_settings.py` | 361 | 23 | QTabWidget/QGroupBox/QFormLayout 构建 | E2E 兜底 |
| `_theme.py` | 90 | ~10 | QIcon/QTranslator/QStyleSheet 管理 | E2E 兜底 |
| `_file_tree.py` | ~200 | ~12 | QTreeWidget+QMenu+QThread 编排 | E2E 兜底（DriveEnumerator 已登记债务） |
| `_export.py` | ~60 | ~5 | QFileDialog+QTextEdit+QTableWidget 编排 | E2E 兜底 |
| `_file_dialog.py` | ~40 | ~3 | QFileDialog 封装，零业务逻辑 | E2E 兜底 |

---

## 核心原则

- **停止底层拆解**：不再为上述文件创建 Engine
- **守住行为底线**：P4 阶段已有 E2E 测试覆盖核心交互路径
- **关注增量**：未来若沉淀复杂业务逻辑（如动态对比度计算、复杂联动校验），再考虑局部提取

---

## 判断标准

是否提取 Engine 的判断流程：

```
1. 文件中是否有纯数据变换逻辑（编解码、校验、分组）？
   ├── 是 → 提取 Engine
   └── 否 → 进入 2

2. 文件中是否有 I/O 逻辑（文件读写、网络请求）与业务规则耦合？
   ├── 是 → 提取 Engine（I/O 隔离模式）
   └── 否 → 进入 3

3. 文件是否仅包含 Qt 控件构建 + 信号连接 + 布局编排？
   ├── 是 → 维持现状 + E2E 兜底
   └── 否 → 重新审查
```
