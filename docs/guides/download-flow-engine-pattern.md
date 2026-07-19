# 可测性重构记录：核心业务流的纯逻辑提取与 I/O 隔离范式

> 日期：2026-07-16
> 来源：P5-3 `_download.py` 重构实战验证
> 适用范围：文件解析、数据过滤/去重、路径校验等涉及"外部 I/O + 核心业务规则"的模块
> 关联文档：[[persistence-engine-pattern]]（P5-1 基础范式）、[[settings-io-engine-pattern]]（P5-2 配置管理范式）

---

## 1. 核心痛点

在传统的 UI Handler 中，业务处理逻辑通常与外部 I/O 和 Qt 控件强耦合：

```python
# 反模式：I/O + 业务规则 + UI 全部揉在一起
def on_import_download(self) -> None:
    path = QFileDialog.getOpenFileName(...)       # UI
    with open(path, "r") as f:                     # I/O
        lines = [line.strip() for line in f]       # 业务解析
    for line in lines:
        if is_recently_published(...):             # 业务规则（依赖 datetime.now()）
            self._mgr.enqueue_download_wait(p)     # 副作用
    # ...
```

| 问题 | 后果 |
|------|------|
| 无法纯单元测试 | 必须依赖真实文件系统，测试极慢（秒级→分钟级）且易 Flaky |
| 业务规则隐式依赖 | `is_recently_published` 内部调用 `datetime.now()`，无法用固定日期测试边界 |
| 边界条件难覆盖 | 无效 CSV 格式、缺失列、空列表、路径遍历攻击等异常路径极难触发 |
| 常量散落 | 阈值、日期格式等硬编码在 Handler 各处，修改极易遗漏 |

---

## 2. 重构范式：I/O 隔离 + 纯逻辑提取

```
┌──────────────────────────────────────────────────────────────┐
│  Handler（薄包装层，允许 Qt + I/O）                            │
│                                                              │
│  职责（只能做这三件事）：                                       │
│  1. 真实 I/O 操作（open、QFileDialog、网络请求）               │
│  2. 调用 Engine 纯逻辑方法                                     │
│  3. Qt 控件交互（表格更新、弹窗、信号连接）                     │
│                                                              │
│  示例：                                                       │
│  with open(path) as f:           ← I/O                       │
│      content = f.read()                                      │
│  items = self._engine.parse_csv(content)  ← Engine           │
│  self._work_table.setRowCount(...)       ← Qt                │
└──────────────────────────────────────────────────────────────┘
                              ↕
┌──────────────────────────────────────────────────────────────┐
│  Engine（纯逻辑层，零 Qt + 零 I/O）                            │
│                                                              │
│  职责：                                                       │
│  · 数据格式转换（CSV 解析、编码/解码）                          │
│  · 业务规则执行（日期判定、去重、路径校验）                      │
│  · 常量集中管理（阈值、格式、校验规则）                          │
│                                                              │
│  绝对禁止：                                                    │
│  · from PyQt6 / import PyQt6                                 │
│  · open(), os.listdir(), Path.read_text()                    │
│  · requests, urllib, socket                                  │
│  · datetime.now()（应接收显式 reference_date 参数）            │
└──────────────────────────────────────────────────────────────┘
```

**核心原则（I/O 隔离）：**
- **Engine 零 I/O**：所有方法只做纯内存操作，文件读取由 Handler 完成并传入内容
- **显式时间注入**：涉及日期的逻辑使用参数化 `reference_date`，不隐式调用 `datetime.now()`
- **容错不崩溃**：所有方法对非法输入返回合理默认值（空列表、False），不抛异常
- **引用透传**：Engine 返回列表中的对象与输入同一引用，方便 Handler 后续操作

---

## 3. 标准代码结构

### 3.1 Engine 层（`download_flow_engine.py`）

```python
class DownloadFlowEngine:
    DEFAULT_THRESHOLD_DAYS = 28  # 业务常量集中管理

    @staticmethod
    def filter_too_new_standards(
        standards: list[Any],
        threshold_days: int = DEFAULT_THRESHOLD_DAYS,
        reference_date: date | None = None,  # 显式时间注入
    ) -> list[Any]:
        """纯日期判定：哪些标准发布不满 threshold_days 天。"""
        if reference_date is None:
            reference_date = date.today()
        too_new = []
        for p in standards:
            pub_str = getattr(p, "found_publish_date", "")
            if not pub_str:
                continue
            try:
                pub_date = datetime.strptime(pub_str, "%Y-%m-%d").date()
                if reference_date - pub_date < timedelta(days=threshold_days):
                    too_new.append(p)  # 同引用，方便 Handler 后处理
            except (ValueError, TypeError):
                continue
        return too_new

    @staticmethod
    def parse_download_csv(csv_content: str) -> list[dict[str, str]]:
        """纯内存 CSV 解析 — 不碰文件系统。"""
        if not csv_content or not csv_content.strip():
            return []
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)
            return [r for r in rows if any(v.strip() for v in r.values())]
        except Exception:
            return []  # 容错不崩溃

    @staticmethod
    def validate_download_paths(paths: list[str], root_dir: str) -> dict[str, bool]:
        """字符串级路径安全检查 — 不检查文件系统。"""
        result = {}
        for p in paths:
            if not isinstance(p, str) or not p.strip():
                result[str(p)] = False
            elif "\x00" in p or ".." in p.replace("\\", "/").split("/"):
                result[p] = False
            elif len(p) > 4096:
                result[p] = False
            else:
                result[p] = True
        return result
```

### 3.2 Handler 层（薄包装）

```python
def on_import_download(self) -> None:
    path, _ = QFileDialog.getOpenFileName(...)      # Qt
    if not path:
        return

    # 1. I/O：读文件
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        QMessageBox.warning(...)                     # Qt
        return

    # 2. Engine：解析 + 去重
    if path.lower().endswith(".csv"):
        records = self._engine.parse_download_csv(content)
        first_key = list(records[0].keys())[0]
        lines = [r.get(first_key, "").strip() for r in records]
    else:
        lines = [line.strip() for line in content.splitlines() if line.strip()]

    items = [{"number": line} for line in lines]
    items = self._engine.deduplicate_downloads(items, "number")

    # 3. 下行调用
    self._mgr.download_by_numbers([item["number"] for item in items])
```

---

## 4. 与 P5-1 / P5-2 的范式对比

| 维度 | P5-1 Persistence | P5-2 SettingsIO | P5-3 DownloadFlow |
|------|-----------------|-----------------|-------------------|
| 核心约束 | 零 Qt | 零 Qt + 默认值集中 | **零 Qt + 零 I/O** |
| 数据粒度 | 单项（x,y,w,h） | 分组字典（30 项→4 组） | 异构（列表+字符串+路径） |
| 时间处理 | 无 | 无 | **显式 reference_date 注入** |
| 引用语义 | 返回新对象 | 返回新 dict | **返回输入同引用** |
| 额外依赖 | base64 | 无（纯 dict 操作） | csv, io, datetime |
| 容错策略 | Base64 损坏→b"" | 类型错→默认值 | 异常→空列表/False |

---

## 5. 已知踩坑记录

### 5.1 `datetime.now()` 是隐式 I/O

`datetime.now()` 读取系统时钟，导致测试结果随时间变化。解决方案：所有日期判定方法接收显式 `reference_date` 参数，Handler 传入 `date.today()`。

### 5.2 对象引用语义

ParsedStdInfo 无自定义 `__eq__`，默认 `==` 退化为 `is` 比较。Engine 返回的列表必须包含输入列表中的同一对象引用，否则 Handler 中的 `p in too_new` 会失效。

### 5.3 CSV 解析的容错层次

`csv.DictReader` 对大多数格式错误不抛异常（只是解析结果异常），真正的异常来自 `io.StringIO()` 对非 str 输入。测试需同时覆盖两种路径。

### 5.4 路径校验的作用域

Engine 的路径校验只做字符串级别检查（空字节、`..` 遍历、超长），不查文件系统。文件存在性、磁盘空间等检查是 Handler 或下载 Worker 的职责。

---

## 6. 后续复用清单

| 文件 | 可提取内容 |
|------|-----------|
| `_cleanup.py` | 过期判断、文件匹配规则、清理策略 |
| `_announce.py` | 公告过滤、日期比较、内容解析 |
| `_scan.py` | 文件名解析、扩展名过滤、路径规范化 |
| `_export.py` | 格式转换、字段映射、数据聚合 |

**触发词**：I/O 隔离、纯内存操作、显式时间注入、零 I/O 依赖、reference_date 参数化
