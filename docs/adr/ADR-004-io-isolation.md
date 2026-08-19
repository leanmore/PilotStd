# ADR-004: I/O 隔离模式（P5-3 下载 / P5-4 清理）

> 日期：2026-07-16
> 状态：✅ Accepted
> 关联：[[ADR-002]] [[ADR-003]]

---

## 背景

`_download.py` 和 `_cleanup.py` Handler 中包含文件 I/O 和目录遍历逻辑，与 UI 控件操作耦合，导致：
- 无法在不创建真实文件系统的情况下测试
- 时间依赖（`datetime.now()`）使测试结果不稳定
- CSV 解析与下载决策逻辑混在一起

---

## 决策

### P5-3: I/O 隔离 1.0（DownloadFlowEngine）

- **零 I/O 约束**：Engine 不执行任何文件读写、网络请求、目录扫描
- **显式时间注入**：所有需要当前时间的逻辑通过参数传入 `reference_time`，而非内部调用 `datetime.now()`
- **引用透传**：Engine 接收内存中的数据对象，处理后返回新对象，不修改输入

### P5-4: I/O 隔离 2.0（CleanupFlowEngine）

- **目录树 dict 化**：Handler 将文件系统扫描结果转为 `dict` 传入 Engine
- **遍历与分析分离**：遍历（Handler 做，依赖文件系统）与分析（Engine 做，纯内存）完全解耦
- **排除模式可配置**：Engine 接收排除规则，不感知文件系统

---

## Engine 概要

| Engine | 文件 | 方法数 | 测试数 | 覆盖率 | 覆盖场景 |
|--------|------|--------|--------|--------|---------|
| DownloadFlowEngine | `download_flow_engine.py` | 4 | 39 | 100% | 零阈值、未来日期、损坏 CSV、路径注入 |
| CleanupFlowEngine | `cleanup_flow_engine.py` | 2 | 28 | 100% | dir_tree 空/None/非 dict、排除模式 |

---

## 范式文档

- I/O 隔离 1.0：[download-flow-engine-pattern.md](../guides/download-flow-engine-pattern.md)
- I/O 隔离 2.0：[cleanup-io-isolation-2.0.md](../guides/cleanup-io-isolation-2.0.md)

---

## 演进关系

I/O 隔离 2.0 是 1.0 的进化：
- 1.0 处理**数据级** I/O（文件内容）
- 2.0 处理**结构级** I/O（文件系统层级）
- 共同原则：Engine 不感知外部世界，所有外部依赖由 Handler 注入
