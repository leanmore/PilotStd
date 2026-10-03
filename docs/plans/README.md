# 计划文档

> 本目录仅存放当前处于 **Active** 状态的计划文档。
> 已完成的计划请提炼 ADR 后归档至 `docs/archive/`。

---

## 当前计划

| 计划 | 主题 | 状态 |
|------|------|------|
| [notification-redesign/00-README.md](notification-redesign/00-README.md) | **通知架构重设计**（三层事件分离 / 可交互消息 / Task 实体 / 回调闭环）——六阶段路径 + 15 项裁决 + 阶段 0/1 实施方案 | 架构已批准；阶段 0/1 方案待批 |
| [notification-refactor-design.md](notification-refactor-design.md) | 事件通知模块重构设计（i18n / 模板 / 文案 / 覆盖度 / 聚合） | 实施中（第 1、3、4 批已落地） |
| [batch2-security-audit-design.md](batch2-security-audit-design.md) | 第 2 批方案设计：安全与审计闭环（3 个 P0 端点 + 统一接线规则 + 审计读取 API） | 实施中（已落地，G-043 已接入 CI） |
| [batch5-terminology-design.md](batch5-terminology-design.md) | 第 5 批方案设计：术语表 + 禁用词门禁（G-044） | 📋 待裁决（F-1~F-6 六个决策点） |
| [moviepilot-investigation/01-moviepilot-notification-report.md](moviepilot-investigation/01-moviepilot-notification-report.md) | **MoviePilot 通知系统调查报告**（v2.15.6 源码实测，A–H 八组 28 问逐条作答） | 🔍 调查完成（零代码改动） |
| [moviepilot-investigation/02-pilotstd-gap-analysis.md](moviepilot-investigation/02-pilotstd-gap-analysis.md) | **PilotStd vs MoviePilot 差距分析**（三类判断 + 反向/保留清单 + 41 事件层次论断） | 🔍 分析完成（**不含改造方案**） |

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
