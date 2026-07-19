# ADR-003: 纯逻辑提取范式（P5-1 序列化/反序列化）

> 日期：2026-07-16
> 状态：✅ 已落地
> 关联：[[ADR-002]] [[ADR-004]]

---

## 背景

`_persistence.py` Handler 中包含大量纯数据序列化/反序列化逻辑（Base64 编解码、JSON 序列化、类型转换），这些逻辑与 Qt 控件操作耦合，无法独立测试。

---

## 决策：Engine-Handler 分离模式

将纯逻辑提取为 `PersistenceFlowEngine`，Handler 保留薄包装层：

```
旧：Handler 方法内直接操作 Qt 控件 + 内联编解码逻辑
新：Handler（读控件 → 调 Engine → 写存储） + Engine（纯 Python 数据变换）
```

---

## 核心约束

- **零 Qt 依赖**：Engine 禁止 `from PyQt6` / `import PyQt6`
- **成对设计**：每个 `serialize` 方法有对应 `deserialize`，保证往返一致性
- **类型安全**：所有方法签名标注类型，Engine 内做类型校验
- **边界处理**：Base64 损坏、空输入、类型错误全部显式处理

---

## Engine 概要

| 属性 | 值 |
|------|-----|
| 文件 | `persistence_flow_engine.py` |
| 方法数 | 8 |
| 测试数 | 54 |
| 覆盖率 | 100% |
| 覆盖场景 | Base64 损坏、空输入、类型错误、往返一致性 |

---

## 范式文档

详见 [persistence-engine-pattern.md](../guides/persistence-engine-pattern.md)

---

## 推广

此范式后续应用于 P5-2（SettingsIO）、P5-5（QuerySummary）、P5-B1（Dialog）等 Engine，形成统一的 "Engine 零 Qt + Handler 薄包装" 模式。
