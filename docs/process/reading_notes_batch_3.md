# 精读笔记 — 第 3 批（ADR 决策记录）

- **Created**: 2026-08-19T21:50:00+08:00
- **Updated**: 2026-08-19T21:50:00+08:00
- **批次状态**: 待确认（等待人类 Gate 确认）
- **精读深度判定留痕**: 依据审计描述「ADR = 决策记录/活跃」+ 用户指令"重点关注编号连续性、状态标记、交叉引用一致性"→ 判定 **逐字精读全部 10 个文件**（README + 9 个 ADR）

---

## 1. 文件清单与状态总览

| 文件 | 状态标记 | 日期 | 主题 |
| :--- | :--- | :--- | :--- |
| README.md | — | — | 索引（编号 001-009） |
| ADR-001-mixin-refactor-16-to-1.md | 已关闭 | 2026-08-04 | Mixin 16→1 重构 |
| ADR-001-modal-dialog-auto-clicker.md | 已接受 | 2026-07-14 | 模态对话框自动点击器 |
| ADR-002-handler-governance.md | ✅ 已落地 | 2026-07-16 | Handler 混合策略治理 |
| ADR-003-persistence-pattern.md | ✅ 已落地 | 2026-07-16 | 纯逻辑提取范式 |
| ADR-004-io-isolation.md | ✅ 已落地 | 2026-07-16 | I/O 隔离模式 |
| ADR-005-event-bus.md | ✅ 已落地 | 2026-07-16 | EventBus 重构 |
| ADR-006-ui-hold-strategy.md | ✅ 已落地 | 2026-07-16 | 纯 UI 编排维持策略 |
| ADR-007-favorite-archive-decouple.md | ♻ 已修订(v44) | 2026-Q1→Q3 | 收藏归档解耦 |
| ADR-008-wait-worker-elimination.md | ✅ 已落地 | 2026-08-02 | _wait_worker 消除 |

## 2. 编号连续性核查（核心）

| 编号 | 状态 | 说明 |
| :--- | :--- | :--- |
| 001 | 🔴 **冲突** | 两个文件同名 001；README 索引只收录 modal-dialog 版，mixin-refactor 版游离 |
| 002-007 | ✅ 连续 | 均有文件且索引收录 |
| 008 | ⚠️ **空档** | 索引有编号无文件（"首页公告三栏分类"）；无详情说明 |
| 009 | ⚠️ **空档** | 索引有编号无文件（"CronTrigger 调度"）；详情写在 README L34-37 而非独立文件 |

**证据**：`docs/adr/` 目录实际 9 个 .md（README + 8 个 ADR 文件，其中 001 两个）；索引登记 9 个编号（001-009）。文件数 8 与编号数 9 不匹配（008/009 无文件，001 双文件）。

## 3. 状态标记核查

- 现有状态词汇：✅ / ♻ 已修订(v44) / 已接受 / 已关闭 —— **无统一规范**（✅ 与"已接受/已关闭"混用）
- 建议（阶段 C 提出）：统一状态词汇表：`✅ 已落地` / `♻ 已修订` / `📝 已提议` / `⛔ 已废弃` / `🗄 已关闭`

## 4. 交叉引用一致性核查

| 引用方 | 被引用 | 结果 |
| :--- | :--- | :--- |
| architecture.md L236 "6 个 ADR" | docs/adr/ 实际 8 个 ADR 文件 | 🔴 过时（Q2-4 已决策更新为 8） |
| architecture.md L127-135 决策表 | ADR-003/004/005 | ✅ 一致 |
| architecture.md L67/L139/L145 | ADR-002/006/005 | ✅ 一致 |
| ADR-003 L49 → guides/persistence-engine-pattern.md | 存在 | ✅ |
| ADR-004 L45-46 → guides/download-flow-engine-pattern.md、cleanup-io-isolation-2.0.md | 存在 | ✅ |
| ADR-008 防回潮（grep _wait_worker 阻断） | check_all.sh "G-XXX _wait_worker 防回潮" | ✅ 一致 |
| ADR-007 收藏状态机 | architecture.md L191-218 | ✅ 一致 |
| ADR-001-mixin 终态 grep 结果 | 实际仅 `_WindowLifecycleMixin` | ✅ 可验证 |

## 5. 关键认知

1. **Handler 组合（07-11）与 Mixin 16→1（08-04）是同一重构运动的两阶段**：architecture.md 记录 Handler 组合模式，ADR-001-mixin 记录 Mixin 清除收尾。两者应互相引用（当前无交叉引用）→ 待补。
2. **ADR 层级定位**：ADR-002/003/004/005/006 是 Handler 重构的五个决策，与 architecture.md 的"Handler 层治理策略"章节构成 L2 决策层（ADR=详情、architecture.md=速查）。
3. **ADR-001-modal-dialog 是测试基础设施决策**（非生产架构），建议在地图中归类"测试治理"子类。

## 6. 操作需求草案（供阶段 B 汇总）

| 动作 | 目标 | 优先级 | 证据 |
| :--- | :--- | :--- | :--- |
| 重编号 | ADR-001-mixin-refactor-16-to-1（人工决定新编号） | P0 | 编号冲突 |
| 补文件或降级 | ADR-008/009：补独立文件或改为索引内联说明 | P1 | 索引登记但无文件 |
| 状态规范 | 统一 ADR 状态词汇（✅/♻/📝/⛔/🗄） | P2 | 现有混用 |
| 交叉引用 | architecture.md 与 ADR-001-mixin 互引（Handler 组合↔Mixin 清除） | P3 | 同一重构两阶段 |
| 修正 | architecture.md L236 "6 个 ADR"→8 | P2 | Q2-4 已决策 |
