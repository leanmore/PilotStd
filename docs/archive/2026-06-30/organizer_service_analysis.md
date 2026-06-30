# manager/organizer_service.py 结构分析

> 分析日期：2026-06-30

---

## 当前结构

| 属性 | 值 |
|------|-----|
| 总行数 | **524** |
| 类 | 1 个（`OrganizerService`） |
| 方法数 | 9 个 |
| 外部引用 | 3 处（facade.py, service_factory.py, __init__.py） |

---

## 方法清单

| # | 方法 | 行数 | 职责 | 分组 |
|---|------|------|------|------|
| 1 | `__init__` | 24 | 构造，注入 5 个依赖 | — |
| 2 | `organize` | **157** | 主归类流程：PDF移动+Word镜像+内容去重+索引写入 | 核心归类 |
| 3 | `_dedup_standard` | 21 | 同标准号旧路径清理 | 核心归类 |
| 4 | `organize_skipped_dirs` | 93 | 跳过目录整体镜像（不解析不分类） | 镜像/兜底 |
| 5 | `organize_fallback` | 80 | 归档收尾：源目录残留文件兜底镜像 | 镜像/兜底 |
| 6 | `_is_word_or_template` | 4 | 扩展名判断（静态） | 工具 |
| 7 | `_resolve_industry_in_path` | 18 | 行业代号→完整目录名（静态） | 工具 |
| 8 | `handle_expired` | 11 | 废止标准移入过期目录（委托子处理器） | 过期处理 |
| 9 | `merge_expire_from_source` | 39 | 源目录过期文件夹合并到标准库 | 过期处理 |

**分组统计**：
- 核心归类：2 个方法，178 行
- 镜像/兜底：2 个方法，173 行
- 过期处理：2 个方法，50 行
- 工具方法：2 个方法，22 行（静态，被 facade.py 直接引用）

---

## 依赖关系

### 外部引用

| 文件 | 导入方式 | 用途 |
|------|---------|------|
| `facade.py:44` | `from .organizer_service import OrganizerService` | 类导入 |
| `service_factory.py:42` | `organizer_svc = OrganizerService(...)` | 实例化 |
| `manager/__init__.py:7` | `from .organizer_service import OrganizerService` | 重导出 |

### facade.py 静态方法引用

```python
# facade.py:1139 — 静态方法引用
return OrganizerService._is_word_or_template(src_path)

# facade.py:1159 — 静态方法引用
return OrganizerService._resolve_industry_in_path(rel_path)
```

**注意**：两个静态方法被 facade.py 直接调用，拆分后需保持 `OrganizerService` 上的引用可用。

---

## 拆分建议

```
pilotstd/manager/organize/
├── __init__.py       ← from .organizer import OrganizerService（重导出）
├── organizer.py      ← OrganizerService 主类 + organize + _dedup_standard (~200行)
├── mirror.py         ← organize_skipped_dirs + organize_fallback (~175行)
├── expire.py         ← handle_expired + merge_expire_from_source (~50行)
└── _utils.py         ← _is_word_or_template + _resolve_industry_in_path (~22行)
```

| 模块 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | ~8 | 重导出 `OrganizerService` |
| `organizer.py` | ~200 | 核心类 + constructor + `organize()` + `_dedup_standard` |
| `mirror.py` | ~175 | `organize_skipped_dirs` + `organize_fallback` |
| `expire.py` | ~50 | `handle_expired` + `merge_expire_from_source` |
| `_utils.py` | ~22 | `_is_word_or_template` + `_resolve_industry_in_path` |

### 类结构（组合模式）

```python
# __init__.py
from ._utils import _is_word_or_template, _resolve_industry_in_path
from .expire import OrganizerExpireMixin
from .mirror import OrganizerMirrorMixin
from .organizer import OrganizerCore

class OrganizerService(OrganizerCore, OrganizerMirrorMixin, OrganizerExpireMixin):
    _is_word_or_template = staticmethod(_is_word_or_template)
    _resolve_industry_in_path = staticmethod(_resolve_industry_in_path)
```

### 导入兼容性

```python
# 外部无需修改
from pilotstd.manager.organizer_service import OrganizerService
# → __init__.py 重导出，保持不变
```

---

## 拆分优先级

| 优先级 | 理由 |
|--------|------|
| 中 | 524 行不算极端，但 `organize()` 方法 157 行过于庞大，内部嵌套 3 层（for + if-else + try/except） |
| 收益 | 镜像和过期逻辑独立，职责清晰 |
| 风险 | 外部引用 3 处，0 处需修改（`__init__.py` 重导出） |
