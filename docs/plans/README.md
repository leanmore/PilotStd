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
| [moviepilot-investigation/03-user-needs-and-aggregation-recheck.md](moviepilot-investigation/03-user-needs-and-aggregation-recheck.md) | **用户视角通知需求推导 + MoviePilot 聚合复查**（37 个用户时刻／重复 5·多余 3·粒度错配 7·缺失 1；01 报告 7 条结论修正） | 🔍 调查完成（**不含改造方案**） |
| [dual-end-investigation/01-architecture-recon.md](dual-end-investigation/01-architecture-recon.md) | **PilotStd 双端架构实测**（`pilotstd/` 与 `docker/` 依赖关系、Windows 端信号呈现机制、41 事件分端归属：Docker 25／两端 15／Windows 1） | 🔍 侦察完成（**不含方案**） |
| [dual-end-investigation/02-cli-and-signal-path.md](dual-end-investigation/02-cli-and-signal-path.md) | **双端报告澄清**（CLI 定位推断 + Windows 任务中心判定 + 共享事件信号链路 + 共享重统计；含对 01 报告的 2 处修正声明） | 🔍 澄清完成（**不含方案、不裁决定位**） |
| [notification-system-design/00-framework.md](notification-system-design/00-framework.md) | **通知系统方案框架**（回答 6 个决策问题：Docker 通知清单 / 旧设计重审 / Windows 端方向 / 技术发现处置 / MoviePilot 学与不学 / 实施路径 + 11 项待裁决） | 📐 **待批准**（方向审批用，不含实施细节） |
| [notification-system-design/01-channel-capabilities.md](notification-system-design/01-channel-capabilities.md) | **四渠道双向形态能力调查**（钉钉/企微/飞书/Telegram × 7 维度；证据等级标注 + 8 项缺口清单；结论：当前 4 渠道均为低端形态） | 🔍 调查完成（**不含方案**） |
| [notification-system-design/02-framework-update.md](notification-system-design/02-framework-update.md) | **框架更新 + 分档通知策略初版**（6 项裁决录入 + 2 处更正 + 阶段 3 重定义 + 四档策略（阈值基于实测耗时）+ 5 项新待裁决） | 📐 **待批准**（方向审批用） |

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
