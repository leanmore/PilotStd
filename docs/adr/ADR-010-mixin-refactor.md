# ADR-010：Mixin 重构 16→1

- **日期**：2026-08-04
- **状态**：🗄 Deprecated（内容已由 Handler 组合系列 ADR 承接，见 Related ADRs）
- **Superseded by**：[ADR-001-modal-dialog-auto-clicker](ADR-001-modal-dialog-auto-clicker.md)（测试基础设施；原 ADR-001 编号释放后本文件重编号为 ADR-010）

## Related ADRs

本文件属于 **Handler 组合重构运动**（2026-07-11 至 2026-08-04）的一部分，该运动分两阶段：

| 阶段 | 时间 | 载体 |
| :--- | :--- | :--- |
| Handler 组合模式（消除 Mixin 多重继承） | 2026-07-11 | docs/architecture.md「Handler 组合模式」章节 |
| Handler 治理策略（混合策略 D + 纯逻辑提取） | 2026-07-16 | [ADR-002](ADR-002-handler-governance.md) / [ADR-003](ADR-003-persistence-pattern.md) / [ADR-004](ADR-004-io-isolation.md) / [ADR-005](ADR-005-event-bus.md) / [ADR-006](ADR-006-ui-hold-strategy.md) |
| 收藏与归档解耦 | 2026-07-20 | [ADR-007](ADR-007-favorite-archive-decouple.md) |
| GUI 测试 _wait_worker 消除 | 2026-08-02 | [ADR-008](ADR-008-wait-worker-elimination.md) |
| Mixin 16→1 收尾（本文件） | 2026-08-04 | 本文档 |

**说明**：本文件原编号为 ADR-001，与 ADR-001-modal-dialog-auto-clicker 冲突（README 索引以 modal-dialog 版为准）。2026-08-19 文档整理中重编号为 ADR-010 以消除冲突，历史决策内容与守护机制（test_architecture_mixin_guard.py）保持不变。

## 上下文

随着项目演进，早期大量使用的 Mixin 模式导致类继承层次过深、MRO 冲突频发、
单元测试困难（需 mock 整个宿主类），且职责边界日益模糊。
为提升代码可维护性和可测试性，对生产代码中的 Mixin 进行全面重构。

## 决策

将 16 个 Mixin 中的 15 个转换为以下模式之一：

| 模式 | 适用场景 | 示例 |
|------|---------|------|
| 纯函数化 | 方法不访问 self 状态 | 通知 Builder ×4 |
| 独立类 + 组合注入 | 多方法共享单一依赖 | FileIndexQuery, OrganizerMirror |
| `__getattr__` 动态代理 | 纯属性委托样板 | BaseProperties (149→0行) |
| 工厂函数 | 一次性初始化编排 | CoreInitQuery |
| 合并组合类 | 存在交叉调用的多个 Mixin | QueryExec+QueryReport |
| `_DispatchContext` dataclass | 多组件依赖注入 | BatchDispatcher |

**唯一保留**：`_WindowLifecycleMixin` — Qt QMainWindow 要求 `closeEvent`/`changeEvent`
通过 MRO 分发，这是框架硬约束而非设计选择。

## 已消除的 15 个 Mixin

| # | Mixin | 行数 | 方式 |
|---|-------|------|------|
| 1 | 通知 Builder ×4 | ~500 | 纯函数化 |
| 2 | `ForeignHandlerMixin` | 125 | 纯函数化 |
| 3 | `OrganizerExpireMixin` | 51 | 纯函数化 |
| 4 | `_FileIndexQueryMixin` | 185 | 独立类 + 组合 |
| 5 | `OrganizerMirrorMixin` | 186 | 独立类 + 组合 |
| 6 | `_QueryExecMixin` | 246 | 合并组合类 |
| 7 | `_QueryReportMixin` | 113 | 合并组合类 |
| 8 | `_BasePropertiesMixin` | 149 | `__getattr__` 压缩 |
| 9 | `_CoreInitQueryMixin` | 50 | 工厂函数 |
| 10 | `_Njbz365SessionMixin` | 215 | 独立类 + 组合 |
| 11 | `ExactMatchMixin` | 271 | 独立类 + 组合 |
| 12 | `_BatchDispatchMixin` | 341 | 独立类 + 组合 |

## 终态

```
grep -rn "class.*Mixin" pilotstd/
pilotstd/ui/main_window/_window_lifecycle.py:17:  class _WindowLifecycleMixin:
```

Mixin 白名单已从 16 个收敛至 1 个。

## 策略固化

未来新增跨切面逻辑，优先使用 **Composition + _DispatchContext** 模式。
仅在 Qt QObject 多重继承场景下可考虑 Mixin，且需经过架构评审。

## 守护机制

`tests/test_architecture_mixin_guard.py` 自动扫描 `pilotstd/` 目录，
除 `_WindowLifecycleMixin` 外禁止任何新增 Mixin 类定义。
CI 预提交钩子会在违规时阻断。
