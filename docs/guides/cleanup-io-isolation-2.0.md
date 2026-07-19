# 文件系统 I/O 隔离 2.0：从扁平数据到树形结构的范式进化

> 日期：2026-07-16
> 来源：P5-4 `_cleanup.py` 重构实战验证
> 前置文档：[[download-flow-engine-pattern]]（P5-3，I/O 隔离 1.0 基础范式）
> 关联文档：[[persistence-engine-pattern]]（P5-1）、[[settings-io-engine-pattern]]（P5-2）

---

## 1. 升级概述

本次针对 `_cleanup.py` 的"文件系统 I/O 隔离"实践，标志着架构从 **1.0 版本**（以 `_download.py` 为代表）向 **2.0 版本** 的本质跨越。

| 版本 | 代表模块 | 核心突破 |
|------|---------|---------|
| 1.0 | P5-3 `_download.py` | 文件读写解耦：`open()` → `content: str` → Engine |
| 2.0 | P5-4 `_cleanup.py` | 目录树解耦：`os.scandir()` → `dir_tree: dict` → Engine |

如果说 1.0 解决了基础的文件读写解耦，那么 2.0 成功验证了"纯逻辑提取范式"在**处理复杂层级数据时的泛化能力**。这不仅是代码层面的重构，更是测试策略与架构思维的全面升级。

---

## 2. 核心维度升级详解

### 2.1 隔离对象：从单一文件到复杂树形结构

**1.0 阶段**：
```
文件 → open() → 字符串内容 → Engine.parse() → list[dict]
```
输入输出模型：字符串 → 字典列表的线性转换。

**2.0 阶段**：
```
目录树 → os.scandir() → dir_tree: dict[str, list[str]] → Engine.analyze() → (empty, expire)
```
输入输出模型：嵌套字典树 → 分类结果。

**关键策略**：避免将 `os.scandir` 的 `DirEntry` 对象直接传入 Engine。由 Handler 将物理目录树构建为纯内存字典树：

```python
# Handler：文件系统遍历（I/O 密集型）
dir_tree: dict[str, list[str]] = {}
for entry in os.scandir(path):
    if entry.is_dir():
        children = list(os.scandir(entry.path))
        dir_tree[entry.path] = [c.name for c in children]  # 只取名称字符串

# Engine：纯内存分析（逻辑密集型）
empty_dirs, expire_only = engine.scan_empty_dirs(dir_tree)
```

**价值**：证明了系统具备处理复杂嵌套数据结构的隔离能力，彻底屏蔽了文件系统的物理形态。

### 2.2 测试纯度：从依赖临时目录到纯内存构造

**1.0 阶段**：虽然实现了文件内容读取的隔离，但在验证文件系统逻辑时仍依赖 `tmp_path` 创建真实临时文件。

**2.0 阶段**：真正的零 I/O 测试。

```python
# 1.0 测试（仍有 I/O 依赖）
def test_parse_csv(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("col1,col2\n...")
    with open(csv_file) as f:
        result = engine.parse_csv(f.read())

# 2.0 测试（纯内存构造）
def test_scan_empty_dirs(engine):
    dir_tree = {
        "/root/empty_A": [],
        "/root/empty_B": [],
        "/root/non_empty": ["file.txt", "subdir"],
        "/root/expire_only": ["过期作废"],
    }
    empty, expire = engine.scan_empty_dirs(dir_tree)
    assert sorted(empty) == ["/root/empty_A", "/root/empty_B"]
```

**价值**：测试响应速度达到微秒级，彻底消除了文件系统状态对单元测试的干扰。

### 2.3 架构解耦：从读写分离到遍历与分析分离

| 维度 | 1.0（P5-3） | 2.0（P5-4） |
|------|-----------|-----------|
| 分离模式 | 读文件 vs 解析内容 | 物理遍历 vs 业务分析 |
| Handler 职责 | `open()` + `read()` | `os.scandir()` 递归遍历 |
| Engine 职责 | `csv.reader(content)` | 空目录判定 + 过期检测 |
| 传参形式 | 字符串内容 | 字典树（`dict[str, list[str]]`） |
| 可独立优化 | 文件读取策略 | 遍历策略（深度/广度、并发） |

**价值**：
- 业务逻辑可独立于操作系统进行演进和测试
- I/O 优化策略（如并行遍历）可独立于业务逻辑调整
- Engine 的 `scan_empty_dirs` 可复用于 CLI/API 等非 Qt 入口

---

## 3. 技术决策记录

### 3.1 `is_dir` 信息的取舍

`os.DirEntry.is_dir()` 是文件系统特有的信息，Engine 无法从 `list[str]` 中获取。

**决策**：在 `scan_empty_dirs` 的 `expire_only` 判定中，放弃精确的 `is_dir()` 检查，改为字符串匹配。如果排除无关项后仅剩一个子项且名称等于 `expire_folder_name`，即视为 expire_only。

**理由**：文件命名为"过期作废"且是目录中唯一子项的概率极高，`is_dir()` 检查是防御性的而非逻辑必要的。这种简化不改变实际行为，但使 Engine 完全零 I/O。

### 3.2 排序职责的归属

原始代码使用 `sorted(os.scandir(path), key=lambda e: e.name)` 对顶级目录排序。

**决策**：排序不进入 Engine。排序是展示层关注点（影响对话框中的目录顺序），不影响"是否为空的"逻辑判定。

**理由**：`scan_empty_dirs` 的返回列表顺序不影响正确性。如需排序，由 Handler 或 UI 层处理。

### 3.3 `build_unrecognized_tree` 的 UI 增强

原始代码将未识别文件平铺展示。重构后 Engine 按后缀分组，Handler 在 QTreeWidget 中增加分组父节点。

**决策**：在保持 `(QTreeWidget, list[QTreeWidgetItem])` 返回签名不变的前提下，增加后缀分组层级。

**理由**：`collect_selected_files` 只遍历文件级 `QTreeWidgetItem`（子节点），分组父节点自然被跳过，无需修改下游代码。

---

## 4. 后续复用指南

当 AI 遇到以下场景时，应优先采用 2.0 范式：

| 场景 | Handler 构建 | Engine 接收 |
|------|-------------|------------|
| 目录扫描/清理 | `os.scandir` → `dict[str, list[str]]` | 空目录/过期判定 |
| 文件索引构建 | `os.walk` → 嵌套 dict | 索引查询/过滤 |
| 配置树解析 | JSON/YAML → 嵌套 dict | 配置校验/合并 |
| 文件分类/整理 | `os.listdir` → `list[str]` | 按规则分组/重命名 |

**触发词**：目录树分析、文件遍历隔离、dir_tree 字典、纯内存构造测试、I/O 隔离 2.0
