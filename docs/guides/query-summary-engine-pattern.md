# 可测性重构记录：数据分组与状态映射的纯逻辑提取范式

> 日期：2026-07-16
> 来源：P5-5 `_query_summary.py` 重构实战验证
> 适用范围：数据分组/分类、状态码映射、安全字符串转换、统计摘要构建
> 关联文档：[[persistence-engine-pattern]]（P5-1）、[[settings-io-engine-pattern]]（P5-2）

---

## 1. 核心痛点

查询汇总等模块中，分桶逻辑、状态描述映射、字符串安全转换等纯逻辑与 QDialog/QTableWidget 构建耦合：

- `build_buckets` 中 `next_action → 桶名` 的映射散落在方法内
- `_get_pending_reason` 依赖 i18n 翻译函数，无法纯单元测试
- `safe_str` 作为 Handler 静态方法，被 CSV 导出和 UI 渲染混用
- 统计消息的计数逻辑内联在 toast 通知中

---

## 2. 重构范式

将分桶、状态映射、字符串转换、统计构建提取为 Engine 纯静态方法：

```
QuerySummaryFlowEngine
├── 类常量：STATUS_LABEL_MAP, ACTION_TO_BUCKET, BUCKET_NAMES
├── build_buckets(standards) → dict[str, list]
├── get_pending_reason(status) → str
├── safe_str(value) → str
└── build_summary_message(buckets, total) → str
```

**核心原则：**
- 状态映射集中为类常量，不再依赖 i18n 翻译函数
- `safe_str` 处理 bool 值特殊情况：`True/False → ""`
- `build_summary_message` 返回可读统计字符串，Handler 直接使用

---

## 3. 标准代码结构

### 3.1 Engine 层

```python
class QuerySummaryFlowEngine:
    STATUS_LABEL_MAP = {
        "chain_exhausted": "所有适配器已尝试",
        "match_not_exact": "匹配不精确",
        "name_conflict": "名称冲突",
    }

    ACTION_TO_BUCKET = {
        "archive": "organize",
        "download": "download",
        "pending": "pending",
    }

    @staticmethod
    def build_buckets(standards):
        buckets = {k: [] for k in QuerySummaryFlowEngine.BUCKET_NAMES}
        for p in (standards or []):
            key = QuerySummaryFlowEngine.ACTION_TO_BUCKET.get(
                getattr(p, "next_action", "") or ""
            )
            if key:
                buckets[key].append(p)
        return buckets

    @staticmethod
    def safe_str(value):
        if isinstance(value, bool):
            return ""
        return str(value) if value else ""
```

### 3.2 Handler 层

```python
def build_buckets(self):
    return self._engine.build_buckets(self._parsed_results)

def _get_pending_reason(self, item):
    status = getattr(item, "stage_status", "") or ""
    reason = self._engine.get_pending_reason(status)
    if reason:
        return reason
    return self._engine.get_pending_reason(
        getattr(item, "match_status", "") or ""
    )
```

---

## 4. 测试要点

- 构造最小 `ParsedStdInfo` 兼容对象（仅需 `next_action`/`stage_status` 属性）
- 覆盖所有 7 个桶名 + 未知 action 跳过
- 覆盖所有 6 个状态码 → 中文描述映射
- `safe_str` 重点测 `bool` 值 → `""` 的边界
- 超大列表（10000+）验证性能

---

## 5. 后续复用

当 Handler 中出现以下模式时，参照此范式提取：
- 状态码 → 描述的静态映射表
- 对象按属性分桶/分组的逻辑
- 通用安全字符串转换函数
- 从分组结果构建统计摘要
