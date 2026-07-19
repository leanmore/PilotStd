# 可测性重构记录：UI 持久化与状态管理的纯逻辑提取范式

> 日期：2026-07-16
> 来源：P5-1 `_persistence.py` 重构实战验证
> 适用范围：UI 状态保存/恢复、配置文件读写、表单数据序列化等涉及"Qt 控件 ↔ 外部存储"的模块

---

## 1. 核心痛点

在传统的 UI Handler 中，状态保存与恢复逻辑通常与 Qt 控件强耦合：

```python
# 反模式：控件操作 + 数据转换 + 配置读写全部揉在一起
def save_window_geometry(self, window: QMainWindow) -> None:
    geo_b64 = window.saveGeometry().toBase64().data().decode()  # Qt 操作 + 编码
    self._config.set("appearance.window_geometry", geo_b64)      # 配置写入
    self._config.save()
```

导致的问题：

| 问题 | 后果 |
|------|------|
| 无法纯单元测试 | 必须启动 QApplication，测试极慢（秒级→分钟级）且易 Flaky |
| 边界条件难覆盖 | 配置丢失、类型错误、损坏的序列化数据等异常路径，在真实 UI 中极难触发 |
| 逻辑无法复用 | CLI/Web/Worker 等其他入口无法共享同一套序列化逻辑 |

---

## 2. 重构范式：序列化/反序列化薄层模式

将原本揉在一起的"控件操作 + 配置读写"拆分为对称的纯逻辑方法：

```
┌─────────────────────────────────────────────────────┐
│  Handler（薄包装层，允许 Qt 依赖）                      │
│  ┌──────────────┐      ┌──────────────────────────┐ │
│  │ 从控件读原始数据 │  →  │ Engine.serialize_xxx()    │ │
│  │ 写入控件       │  ←  │ Engine.deserialize_xxx()  │ │
│  └──────────────┘      └──────────────────────────┘ │
│         ↑                        ↓                   │
│    QWidget/etc            纯 dict/list/int/str/bytes  │
└─────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────┐
│  Engine（纯逻辑层，零 Qt 依赖）                         │
│  · 仅接收/返回 Python 原生类型                          │
│  · 禁止 `from PyQt6` 或 `import PyQt6`               │
│  · 所有方法为 @staticmethod                           │
└─────────────────────────────────────────────────────┘
```

**核心原则：**
- **Engine 零 Qt 依赖**：文件中禁止出现任何 PyQt6 import，只处理 dict、list、int、str、bytes
- **Handler 只做翻译**：从控件读原始数据 → 调用 Engine → 写入 config；反向亦然
- **Engine 不崩溃**：所有 deserialize 方法对非法输入返回合理默认值，不抛异常

---

## 3. 标准代码结构

### 3.1 Engine 层（`xxx_flow_engine.py`）

```python
class XxxFlowEngine:
    """持久化数据序列化/反序列化纯逻辑层（零 Qt 依赖）。"""

    @staticmethod
    def serialize_window_geometry(x: int, y: int, width: int, height: int) -> dict[str, int]:
        """将窗口坐标和尺寸序列化为 dict。"""
        return {"x": x, "y": y, "width": width, "height": height}

    @staticmethod
    def deserialize_window_geometry(data: Any, default: dict[str, int]) -> dict[str, int]:
        """反序列化窗口几何；数据无效时返回 default（绝不抛异常）。"""
        if not isinstance(data, dict):
            return default
        required = ("x", "y", "width", "height")
        if not all(k in data for k in required):
            return default
        try:
            return {k: int(data[k]) for k in required}
        except (ValueError, TypeError):
            return default
```

**关键设计决策：**

| 决策 | 理由 |
|------|------|
| 全部 `@staticmethod` | Engine 是无状态的纯函数集合，无需实例化上下文 |
| deserialize 永不为非法输入抛异常 | 配置文件可能被手动编辑、版本迁移损坏，崩溃不可接受 |
| 返回新对象而非修改输入 | `return list(data)` 而非修改 `data`，避免副作用 |
| Base64 等编解码在 Engine 中完成 | Handler 不应关心存储格式 |

### 3.2 Handler 层（薄包装）

```python
class PersistenceHandler:
    def __init__(self, config):
        self._config = config
        self._engine = PersistenceFlowEngine()  # 注入 Engine

    def save_window_geometry(self, window: QMainWindow) -> None:
        """保存窗口位置和大小。"""
        g = window.geometry()                                 # 1. 从控件提取
        data = self._engine.serialize_window_geometry(        # 2. Engine 序列化
            g.x(), g.y(), g.width(), g.height()
        )
        self._config.set("appearance.window_geometry", data)  # 3. 写入存储
        self._config.save()

    def restore_window_geometry(self, window: QMainWindow) -> None:
        """恢复窗口位置和大小。"""
        data = self._config.get("appearance.window_geometry", DEFAULT)  # 1. 读取存储
        result = self._engine.deserialize_window_geometry(data, DEFAULT) # 2. Engine 反序列化
        window.setGeometry(result["x"], result["y"],                    # 3. 写入控件
                          result["width"], result["height"])
```

**Handler 方法的正确职责（只能做这三件事）：**
1. 从 Qt 控件读取原始数据（或写入 Qt 控件）
2. 调用 Engine 的序列化/反序列化方法
3. 读写配置存储（config.get / config.set）

---

## 4. 测试策略

### 4.1 Engine 单元测试（纯 Python，毫秒级）

```python
# 不启动 QApplication，不导入 PyQt6
class TestDeserializeWindowGeometry:
    DEFAULT = {"x": 0, "y": 0, "width": 800, "height": 600}

    def test_normal(self, engine):
        data = {"x": 10, "y": 20, "width": 1024, "height": 768}
        result = engine.deserialize_window_geometry(data, self.DEFAULT)
        assert result == {"x": 10, "y": 20, "width": 1024, "height": 768}

    def test_none_returns_default(self, engine):
        assert engine.deserialize_window_geometry(None, self.DEFAULT) == self.DEFAULT

    def test_corrupted_base64_returns_empty_bytes(self, engine):
        """损坏的 Base64 → 返回 b""，不抛异常。"""
        assert engine.deserialize_header_state("!!!invalid!!!") == b""

    def test_type_mismatch_returns_default(self, engine):
        """传入 list 而非 dict → 返回默认值。"""
        assert engine.deserialize_window_geometry([1, 2, 3], self.DEFAULT) == self.DEFAULT
```

**必测场景清单：**

| 场景 | 序列化 | 反序列化 |
|------|--------|---------|
| 正常输入 | ✓ | ✓ |
| 空值（None, "", [], {}） | ✓ | ✓ |
| 零值（0, 0.0） | ✓ | ✓ |
| 负数 | ✓ | — |
| 类型错误（str→dict, list→int） | — | ✓ |
| 损坏数据（Base64 非法字符、错误填充、截断） | — | ✓ |
| 缺失字段（dict 缺 key） | — | ✓ |
| 往返一致性 | serialize → deserialize 结果与原始输入一致 | |

### 4.2 Handler E2E 测试（qtbot，验证薄包装层行为不变）

```python
@pytest.mark.e2e
def test_window_geometry_roundtrip(window, qtbot):
    handler = window._core.persistence
    handler.save_window_geometry(window)
    handler.restore_window_geometry(window)  # 不崩溃即可
```

**E2E 测试只验证一件事**：Handler 调用链不崩溃，数据能成功往返。

---

## 5. 已知踩坑记录

### 5.1 并行 fallback 代码路径

MainWindow 的 `_persistence_ops.py` 中存在独立的 fallback 路径（`_core` 未初始化时直接操作 config）。修改 Engine 的序列化格式时，fallback 路径必须同步更新，否则会因格式不兼容崩溃。

**教训**：重构前 `grep` 所有直接读写同一 config key 的代码路径，确保全部同步。

### 5.2 反序列化默认值不要覆盖控件默认值

`deserialize_column_widths` 在配置无数据时返回 `[default] * col_count`，但 Handler 不应无条件应用此结果——如果配置中根本没有列宽数据，应跳过恢复，保留控件自身的默认列宽。

```python
# 正确做法：配置无数据时不干预
def restore_column_widths(self, work_table):
    widths = self._config.get("appearance.column_widths")
    if widths is None:
        return  # 不干预，保留控件默认值
    result = self._engine.deserialize_column_widths(widths, col_count, DEFAULT)
    ...
```

### 5.3 序列化格式变更会影响跨版本兼容性

将 `window_geometry` 从 `QByteArray.toBase64()` 改为 `{x, y, width, height}` 字典后，旧版本保存的配置将无法被新版本读取。如果这是有意为之，需在发布说明中注明。

---

## 6. 后续复用清单

当 AI 遇到以下 Handler 文件时，应主动提议按此范式重构：

| 文件 | 可提取内容 |
|------|-----------|
| `_settings_io.py` | 设置导入/导出的 JSON ↔ dict 转换逻辑 |
| `_table.py` | 表格列配置、排序状态的序列化 |
| `_theme.py` | 主题颜色/字体的配置序列化 |
| `_file_tree.py` | 文件树展开状态的序列化 |
| `_project.py` | 项目文件路径列表的序列化 |

**触发词**：当任务描述中出现"提取纯逻辑"、"拆分 Qt 依赖"、"提高可测性"、"Engine 模式"等关键词时，AI 必须引用本文档作为范式参考。

---

## 7. 检查清单（重构前自检）

- [ ] 已 grep 所有直接读写同一 config key 的代码路径
- [ ] Engine 文件零 `from PyQt6` / `import PyQt6`
- [ ] 所有 Engine 方法为 `@staticmethod`
- [ ] 所有 deserialize 方法对非法输入返回默认值（不抛异常）
- [ ] Handler 方法不超过 5 行逻辑（只做控件提取 → Engine 调用 → 存储读写）
- [ ] 已写纯 Python 单元测试覆盖正常/边界/异常三种场景
- [ ] E2E 测试全绿（验证薄包装层行为不变）
- [ ] 覆盖率 ≥ 95%
