# 可测性重构记录：配置管理模块的纯逻辑提取范式

> 日期：2026-07-16
> 来源：P5-2 `_settings_io.py` 重构实战验证
> 适用范围：配置文件的加载/保存、表单数据的序列化/反序列化、用户偏好设置管理等涉及"Qt 控件 ↔ 配置存储"的模块
> 关联文档：[[persistence-engine-pattern]]（P5-1 持久化提取范式，本范式的前置基础）

---

## 1. 核心痛点

在传统的 UI Handler 中，配置读写逻辑通常与 Qt 控件强耦合。例如，直接在 `_save_*` 方法中读取 `QComboBox.currentText()`，或在 `_load_*` 方法中硬编码默认值并调用 `QCheckBox.setChecked()`，导致：

| 问题 | 后果 |
|------|------|
| 无法纯单元测试 | 必须启动 QApplication，测试极慢（秒级→分钟级）且易 Flaky |
| 脏数据难处理 | 用户手动修改配置文件或旧版本升级导致非法数据时，异常路径极难触发和验证 |
| 默认值散落 | 默认值硬编码在 Handler 各处，未来修改极易遗漏 |
| 方法组织混乱 | 原有 5 个 `_load_*` + 3 个 `_save_*` 方法不对称，按"功能域"划分而非"配置组" |

---

## 2. 重构范式：配置序列化/反序列化薄层模式

将原本揉在一起的"控件操作 + 配置读写 + 默认值管理"拆分为对称的纯逻辑方法。

```
┌──────────────────────────────────────────────────────────┐
│  Handler（薄包装层，允许 Qt 依赖）                          │
│                                                          │
│  _load_general()          _save_general()                │
│  _load_appearance()       _save_appearance()             │
│  _load_library()          _save_library()                │
│  _load_advanced()         _save_advanced()               │
│                                                          │
│  职责：Qt 控件 ↔ dict → Engine 调用 → config 读写          │
└──────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────┐
│  Engine（纯逻辑层，零 Qt 依赖）                             │
│                                                          │
│  DEFAULT_GENERAL      serialize_general()                │
│  DEFAULT_APPEARANCE   deserialize_general()              │
│  DEFAULT_LIBRARY      serialize_library()                │
│  DEFAULT_ADVANCED     deserialize_library()     ...      │
│                                                          │
│  职责：默认值管理 + 类型校验 + 缺失键回填 + 脏数据仲裁      │
└──────────────────────────────────────────────────────────┘
```

**核心原则：**
- **Engine 零 Qt 依赖**：禁止任何 PyQt6 import
- **默认值集中管理**：所有配置项的默认值统一定义在 Engine 类常量中，Handler 禁止硬编码
- **类型安全**：Engine 对每个键做 `type(val) is type(default_val)` 检查，类型不匹配时回退默认值
- **对称结构**：load 和 save 方法按配置组成对组织，`load_all_configs`/`save_all_configs` 作为编排入口

---

## 3. 标准代码结构

### 3.1 Engine 层（`settings_io_flow_engine.py`）

```python
class SettingsConfigIOEngine:
    """设置配置的纯逻辑序列化/反序列化。"""

    # 默认值常量（配置项唯一真相源）
    DEFAULT_GENERAL: dict[str, Any] = {
        "appearance.language": "zh_CN",
        "appearance.skip_welcome": False,
        "appearance.hyphen_style": True,
        "appearance.column_visibility": [True] * 9,
    }
    # ... DEFAULT_APPEARANCE, DEFAULT_LIBRARY, DEFAULT_ADVANCED

    @staticmethod
    def _fill_missing(data: Any, defaults: dict[str, Any]) -> dict[str, Any]:
        """用 defaults 填充 data 中缺失或类型错误的键。"""
        result = dict(defaults)
        if not isinstance(data, dict):
            return result
        for key in defaults:
            if key in data:
                val = data[key]
                default_val = defaults[key]
                if type(val) is type(default_val):  # 严格类型检查
                    result[key] = val
        return result

    @staticmethod
    def serialize_general(data: dict[str, Any]) -> dict[str, Any]:
        return SettingsConfigIOEngine._fill_missing(data, SettingsConfigIOEngine.DEFAULT_GENERAL)

    @staticmethod
    def deserialize_general(data: dict[str, Any] | None,
                            default: dict[str, Any] | None = None) -> dict[str, Any]:
        base = dict(SettingsConfigIOEngine.DEFAULT_GENERAL)
        if isinstance(default, dict):
            for k in base:
                if k in default:
                    base[k] = default[k]  # 运行时默认值覆盖静态默认值
        return SettingsConfigIOEngine._fill_missing(data, base)
```

**关键设计决策：**

| 决策 | 理由 |
|------|------|
| 使用完整 config key（如 `storage.root_dir`）作为 dict key | Handler 可直接迭代 `result.items()` 写入 config，无需二次映射 |
| deserialize 支持二级默认值（静态 + 运行时覆盖） | 像 `root_dir` 的默认值依赖 `QStandardPaths`，只能在运行时分发 |
| `type(val) is type(default_val)` 严格匹配 | `bool` 和 `int` 在 Python 中 `isinstance(True, int)` 为 True，用 `is` 区分 |
| 额外 key 自动过滤 | Engine 只认 DEFAULT 中声明的 key，Handler 传入的未知 key 被忽略 |

### 3.2 Handler 层（`_settings_io.py`）薄包装

```python
def _load_general(self) -> None:
    """加载通用设置：语言、启动行为、列可见性。"""
    h = self._h
    if not all([h._lang_combo, h._skip_welcome_cb, h._dash_cb]):
        return

    # 1. 从 config 读取原始值 → 构建 dict
    raw = {
        "appearance.language": self._config.get(
            "appearance.language", self._engine.DEFAULT_GENERAL["appearance.language"]
        ),
        "appearance.skip_welcome": self._config.get(
            "appearance.skip_welcome", self._engine.DEFAULT_GENERAL["appearance.skip_welcome"]
        ),
    }
    # 2. Engine 反序列化（脏数据仲裁 + 缺失回填）
    result = self._engine.deserialize_general(raw)

    # 3. 写入 Qt 控件
    h._lang_combo.setCurrentText(lang_map.get(result["appearance.language"], ...))
    h._skip_welcome_cb.setChecked(result["appearance.skip_welcome"])

def _save_general(self) -> None:
    """保存通用设置。"""
    h = self._h
    # 1. 从控件读值 → 构建 dict
    data = {}
    if h._lang_combo:
        data["appearance.language"] = LANG_CODES[h._lang_combo.currentIndex()]
    if h._skip_welcome_cb:
        data["appearance.skip_welcome"] = h._skip_welcome_cb.isChecked()

    # 2. Engine 序列化（补全缺失键 + 类型校验）
    result = self._engine.serialize_general(data)

    # 3. 逐键写入 config
    for key, value in result.items():
        self._config.set(key, value)
```

---

## 4. 测试策略

### 4.1 Engine 单元测试（纯 Python）

必测场景清单：

| 场景 | serialize | deserialize |
|------|-----------|-------------|
| 完整数据 | ✓ | ✓ |
| 空 dict / None | ✓ | ✓ |
| 部分键（缺 key 自动回填） | ✓ | ✓ |
| 额外 key（自动过滤） | ✓ | — |
| 类型错误（int→str, list→str 等） | — | ✓ |
| 运行时默认值覆盖 | — | ✓ |
| 往返一致性（serialize → deserialize） | — | 四组全测 |
| DEFAULT 常量完整性 | 验证所有必需 key 存在 | — |

### 4.2 Handler E2E 测试

当前 `test_e2e_settings_io.py` 标记为 skip（需要完整 SettingsDialog 控件树）。本范式不改变外部接口，不影响现有测试。

---

## 5. 与 P5-1 范式的差异

| 维度 | P5-1 PersistenceEngine | P5-2 SettingsConfigIOEngine |
|------|----------------------|---------------------------|
| 数据粒度 | 单项数据（窗口几何、分栏尺寸） | 分组字典（30 个配置项分 4 组） |
| 默认值策略 | 每个方法独立传入 default 参数 | 类常量集中管理 + 运行时覆盖 |
| 类型安全 | 简单的 isinstance 检查 | `type(val) is type(default_val)` 严格匹配 |
| 方法数量 | 4 对（8 方法） | 4 对（8 方法 + 1 内部辅助） |
| 编排层 | 无（Handler 直接暴露 8 方法） | `load_all_configs`/`save_all_configs` 编排 4 对 |

---

## 6. 已知踩坑记录

### 6.1 OCR 密钥的安全占位符

OCR 密钥在加载时不写入文本框（只显示"已保存"/提示 placeholder），保存后清空文本框。这是安全设计，不是数据丢失。Engine 的 DEFAULT 中 OCR 值均为空字符串，反序列化逻辑不感知此行为。

### 6.2 脏数据仲裁在 Handler 中

`announcement.enabled` 和 `query.use_announcement_match` 互斥的仲裁逻辑（两者不能同时为 True）保留在 Handler 中，因为需要操作 Qt 控件的 `blockSignals` 和 `setEnabled` 状态。

### 6.3 运行时默认值

`storage.root_dir` 的默认值依赖 `QStandardPaths.writableLocation()`，无法静态定义。解决方案是 Engine 的 `DEFAULT_LIBRARY` 中设为空字符串，Handler 通过 `deserialize_library(raw, {"storage.root_dir": computed_path})` 在运行时注入。

### 6.4 空列表 vs None

`column_visibility` 的空列表 `[]` 是合法值（用户可能隐藏所有列）。Engine 不做"空列表→默认值"的回退，该逻辑保留在 Handler 中：
```python
visible = result["appearance.column_visibility"]
if not visible:
    visible = self._engine.DEFAULT_GENERAL["appearance.column_visibility"]
```

---

## 7. 后续复用清单

当 AI 遇到以下 Handler 文件时，应主动提议按此范式重构：

| 文件 | 可提取内容 |
|------|-----------|
| `_download.py` | 下载路径、并发数、重试策略的配置序列化 |
| `_table.py` | 表格列配置、排序状态的序列化 |
| `_auto.py` | 自动化规则的配置序列化 |
| `_announce.py` | 公告来源、检查间隔的配置序列化 |

**触发词**：配置加载/保存、用户偏好、设置序列化、默认值集中管理、SettingsConfigIOEngine 模式

---

## 8. 检查清单（重构前自检）

- [ ] Engine 文件零 `from PyQt6` / `import PyQt6`
- [ ] 所有默认值定义为 Engine 类常量（`DEFAULT_*`）
- [ ] Handler 中无硬编码默认值，统一通过 `self._engine.DEFAULT_*` 引用
- [ ] 所有 Engine 方法为 `@staticmethod`
- [ ] deserialize 方法支持运行时默认值覆盖（`default` 参数）
- [ ] `_fill_missing` 做严格类型检查（`type(val) is type(default_val)`）
- [ ] 额外 key 自动过滤，不在 DEFAULT 中的 key 不输出
- [ ] load/save 方法成对组织，`load_all_configs`/`save_all_configs` 作为编排入口
- [ ] 已写纯 Python 单元测试，覆盖率 ≥ 95%
- [ ] 全量 GUI 测试通过
