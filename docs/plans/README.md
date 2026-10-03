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
| [notification-system-design/03-impl-design-D.md](notification-system-design/03-impl-design-D.md) | **实施设计总纲 + Docker 端阶段 D 详细设计**（8 阶段路线图与依赖；D 阶段：改动 6 处、验收 9 条、测试 14 个、G-010 净增 0 有效行的约束设计；4 项新待裁决） | 🔧 **待批准**（本轮只设计不实施） |
| [notification-system-design/04-refactor-P.md](notification-system-design/04-refactor-P.md) | **通知模块拆分（阶段 P）**（目录 29 文件/4530 有效行盘点；manager.py 498 行 45 成员；2 个拆分方案：A 两块纯函数化→~318 行/测试零改动、B 四块+Context→~220 行；零行为变更判据 6 条；G-048 防膨胀门禁） | 🔧 **待批准**（方案待决策者选） |
| [notification-system-design/05-refactor-decision.md](notification-system-design/05-refactor-decision.md) | **manager.py 拆分方案重新评估（目标优先）**（三条目标判据实测：加渠道 12→≤2、加事件 11→≤2、删事件 11→≤2；根因＝`events.py` 半 SSOT；软约束真实代价 25 行 + 6 处；结论：A/B 均未命中目标，新提方案 C） | 🔧 **待批准**（方案 C / 或退取 B） |
| [notification-system-design/06-spec-and-phasing.md](notification-system-design/06-spec-and-phasing.md) | **SSOT 重建方案（✅ 已定稿 2026-10-03）**（五处澄清 + 两处补充澄清：e2e `EVENTS` 实为 **476 行**、9 字段 100% 可覆盖/派生、`aggregation` 非常量 ⇒ spec **16 字段**；工作量 7 天=50h 小时级拆解 + 4 个历史锚点；五项裁决全部录入；三步：步 A 渠道 11→2、步 B 事件/删事件 11→2、步 C 薄门面） | ✅ **已定稿**，待进入步 A 实施设计 |
| [notification-system-design/07-impl-design-A.md](notification-system-design/07-impl-design-A.md) | **步 A 实施设计：渠道端到端收敛**（channel_spec 8+8 字段；后端 5 处 + 前端 13 处 + 新发现 2 处收敛点；`GET /api/notification/channels` + `spec_hash`；**实测发现 schema 缺 5 字段与 mask/secret 分裂**；G-045 就地扩展 A/B 两类错误；验收 9 条） | 🔧 **待批准**（5 项待裁决） |

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
