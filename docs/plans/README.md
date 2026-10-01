# 计划文档

> 本目录仅存放当前处于 **Active** 状态的计划文档。
> 已完成的计划请提炼 ADR 后归档至 `docs/archive/`。

---

## 当前计划

| 计划 | 主题 | 状态 |
|------|------|------|
| [notification-refactor-design.md](notification-refactor-design.md) | 事件通知模块重构设计（i18n / 模板 / 文案 / 覆盖度 / 聚合） | 实施中（第 1 批已落地；聚合器 `target_id` 修复待做） |
| [batch2-security-audit-design.md](batch2-security-audit-design.md) | 第 2 批方案设计：安全与审计闭环（3 个 P0 端点 + 统一接线规则 + 审计读取 API） | 实施中 |

---

## 生命周期

```
docs/plans/<plan>.md（Active）
    │
    ├── 实施完毕、合入 main
    │
    ├── 1. 提炼核心决策 → docs/adr/ADR-XXX.md
    └── 2. 移入归档 → docs/archive/<plan>.md
```

## 关联文档

- [ADR 目录](../adr/README.md) — 正式架构决策记录
- [历史决策摘要](../history/decisions-summary.md) — 已采纳决策索引
