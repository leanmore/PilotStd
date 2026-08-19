# ADR-002: Handler 层混合策略治理

> 日期：2026-07-16
> 状态：✅ Accepted
> 关联：[[ADR-003]] [[ADR-004]] [[ADR-005]] [[ADR-006]]

---

## 背景

Handler 组合模式消除 Mixin 后，`pilotstd/ui/core/handlers/` 目录仍存在 20 个 Handler 文件，~2000 行业务逻辑与 Qt 控件操作耦合：

- **不可测**：UI 覆盖率仅 65%，Handler 胶水层极低——方法直接操作 `QTableWidget`/`QComboBox`，无法纯单元测试
- **不可复用**：CLI/API 等非 Qt 入口无法共享 Handler 中的序列化、校验、分组逻辑
- **默认值散落**：30+ 配置项默认值硬编码在 Handler 各处，修改极易遗漏
- **大量内联逻辑**：CSV 解析、日期判定、目录扫描、状态映射等纯逻辑与 I/O 和 Qt 控件操作揉在一起

根本原因：设计时未考虑可测试性——30+ 构造参数通过依赖注入传 Handler，方法内直接操作 Qt 控件、内联创建 QThread/Worker。

---

## 决策：混合策略 D

经评估 5 种策略（全量 E2E、全量重构、按文件拆 Engine、按方法提取、混合策略），选择 **混合策略 D**：

| 层级 | 策略 | 覆盖范围 |
|------|------|---------|
| Top 3 高流量 Handler | 全量重构 | `_query`、`_archive`、`_actions` — 已有 FlowEngine |
| P5 高密度 Handler | 纯逻辑提取 | `_persistence`、`_settings_io`、`_download`、`_cleanup`、`_query_summary` |
| 剩余 12 个 Handler | E2E 兜底 | `_dialog`、`_table`、`_project`、`_theme` 等 — qtbot 验证行为不变 |

**选择理由**：
- Top 3 Handler 复杂度最高（查询管线、归档路由、动作编排），全量重构收益最大（已有 3 个 FlowEngine）
- P5 五个 Handler 含高密度纯逻辑（序列化、CSV 解析、目录分析、分组），提取后覆盖率从 65% → 85%+
- 剩余 Handler 多为 UI 编排层，E2E 测试性价比高于纯逻辑提取

---

## 重构模式

五个范式文档覆盖所有提取场景：

| 范式 | 文档 | 代表 Engine | 核心约束 |
|------|------|------------|---------|
| 序列化/反序列化 | persistence-engine-pattern.md | PersistenceFlowEngine | 零 Qt，成对 serialize/deserialize |
| 配置管理 | settings-io-engine-pattern.md | SettingsConfigIOEngine | 默认值集中管理，严格类型检查 |
| I/O 隔离 1.0 | download-flow-engine-pattern.md | DownloadFlowEngine | 零 I/O，显式时间注入 |
| I/O 隔离 2.0 | cleanup-io-isolation-2.0.md | CleanupFlowEngine | 目录树 dict 化，遍历与分析分离 |
| 数据分组 | query-summary-engine-pattern.md | QuerySummaryFlowEngine | 状态映射常量，安全字符串转换 |

**核心原则（所有 Engine 通用）**：
- Engine 零 Qt 依赖：禁止 `from PyQt6` / `import PyQt6`
- 默认值集中管理：类常量 `DEFAULT_*`，Handler 禁止硬编码
- I/O 隔离：文件读取/目录扫描由 Handler 完成，Engine 只接收内存数据
- Handler 薄包装层：每个方法不超过 5 行逻辑（读控件 → 调 Engine → 写存储）

---

## 测试分层

```
┌─────────────────────────────────────────────┐
│  E2E 测试（qtbot，真实 QApplication）          │
│  验证：Handler 薄包装层行为不变                │
│  耗时：~300s                                 │
├─────────────────────────────────────────────┤
│  Engine 单元测试（纯 pytest，零 Qt）           │
│  覆盖率 100%                                  │
│  验证：纯逻辑正确性 + 边界条件 + 异常容错       │
│  耗时：< 2s                                  │
└─────────────────────────────────────────────┘
```

---

## 门禁规则

| 检查项 | 阈值/条件 | 失败处理 |
|--------|----------|---------|
| E2E 测试（`-m e2e`） | 全部通过，允许重试 1 次 | 阻断合入 |
| 单元测试（不含 E2E） | 全部通过 | 阻断合入 |
| 覆盖率（已重构 Handler） | ≥ 85%（`--cov-fail-under=85`） | 阻断合入 |
| Ruff 检查 | 零错误 | 阻断合入 |
| Mypy 检查 | 零问题 | 阻断合入 |

---

## 参考

- [Composition over inheritance](https://en.wikipedia.org/wiki/Composition_over_inheritance)
- [Mixin 的反模式讨论](https://www.artima.com/articles/mixins-and-traits)
