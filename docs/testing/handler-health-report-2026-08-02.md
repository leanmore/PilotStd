# 存活 Handler 健康度报告 (2026-08-02)

Phase 1+2 死代码清理后的 handlers/ 目录健康度快照。

## 目录概览

| 指标 | 清理前 | 清理后 |
|------|--------|--------|
| 总文件数 | 48 | 28 |
| Handler 类 | 21 | 13（含 SettingsConfigIO） |
| 死 Handler | 8 | 0 |
| FlowEngine | 20 | 14 |
| 死 FlowEngine | 6 | 0 |
| 总行数 | ~9,000 | 5,505 |

## 各 Handler 健康度

### FlowEngine（纯逻辑，零 Qt 依赖）

| 文件 | 行数 | 测试覆盖 | 测试文件 | 状态 |
|------|------|---------|---------|:--:|
| actions_flow_engine.py | 51 | 100% | test_actions_flow_engine.py | ✅ |
| announce_flow_engine.py | 132 | 100% | test_announce_flow_engine.py | ✅ |
| archive_flow_engine.py | 138 | 100% | test_archive_flow_engine.py | ✅ |
| auto_flow_engine.py | 71 | 100% | test_auto_flow_engine.py | ✅ |
| cleanup_flow_engine.py | 101 | 100% | test_cleanup_flow_engine.py | ✅ |
| download_flow_engine.py | 213 | 96% | test_download_flow_engine.py | ✅ |
| persistence_flow_engine.py | 92 | 100% | test_persistence_flow_engine.py | ✅ |
| project_flow_engine.py | 87 | 100% | test_project_flow_engine.py | ✅ |
| query_flow_engine.py | 227 | 100% | test_query_flow_engine.py | ✅ |
| query_summary_flow_engine.py | 130 | 100% | test_query_summary_flow_engine.py | ✅ |
| scan_flow_engine.py | 252 | 89% | test_scan_flow_engine.py | ⚠️ |
| settings_io_flow_engine.py | 241 | 100% | test_settings_io_flow_engine.py | ✅ |
| archive_worker_factory.py | 88 | **0%** | — | 🔴 缺测试 |
| query_worker_factory.py | 45 | **0%** | — | 🔴 缺测试 |
| protocols.py | 70 | **0%** | — | 🔵 Protocol 定义 |

### Handler 类（Qt 包装层，通过 GUI/E2E 测试覆盖）

| 文件 | 行数 | 单元覆盖 | 测试方式 | 状态 |
|------|------|---------|---------|:--:|
| _announce.py | 195 | 0% | E2E | ⚠️ |
| _archive.py | 353 | 0% | E2E | ⚠️ |
| _auto.py | 287 | 0% | E2E (test_auto_pipeline.py) | ⚠️ |
| _cleanup.py | 337 | 14% | E2E | ⚠️ |
| _download.py | 334 | 28% | E2E + test_download_handler_c1.py | ⚠️ |
| _persistence.py | 113 | 30% | E2E | ⚠️ |
| _project.py | 117 | 28% | E2E | ⚠️ |
| _query.py | 365 | 0% | E2E | ⚠️ |
| _query_summary.py | 343 | 0% | E2E | ⚠️ |
| _scan.py | 261 | 0% | E2E | ⚠️ |
| _settings.py | 427 | 9% | E2E (test_e2e_settings*.py) | ⚠️ |
| _settings_io.py | 398 | 8% | E2E | ⚠️ |

> Handler 类的 0-30% 覆盖率是设计意图，非缺陷。这些是 Qt 包装层，逻辑已提取到 FlowEngine，Handler 自身仅做控件读写和委托调用。正确性由 GUI E2E 测试保证。

## 扫描结果

| 工具 | 结果 |
|------|------|
| Ruff F401 (unused-import) | 0 违规 |
| Vulture (min-confidence=80) | protocols.py 4 项 Protocol 形参（假阳性） |
| 动态调用 (getattr/register) | task/queue.py 通用注册（活跃代码） |
| 未使用导入 | 0 |
| 可删除项 | **0** |

## 耦合问题

| 问题 | 严重度 | 说明 |
|------|:------:|------|
| Handler → Handler 直接调用 | 无 | 所有 Handler 通过 MainWindowCore 持有，不交叉依赖 |
| FlowEngine 循环依赖 | 无 | 所有 FlowEngine 为纯静态方法或无状态类 |
| protocols.py 孤立 | 低 | Protocol 定义，仅类型标注用途，未被运行时消费 |

## P2 补测建议

| 优先级 | 目标 | 建议用例数 | 理由 |
|:------:|------|:---------:|------|
| P2 | archive_worker_factory.py | 3-5 | 0% 覆盖，工厂逻辑独立可测 |
| P2 | query_worker_factory.py | 2-3 | 0% 覆盖，创建逻辑简单 |
| P3 | scan_flow_engine.py 89%→100% | 2-3 | 10 行未覆盖，低优先级 |
| P3 | download_flow_engine.py 96%→100% | 1-2 | 4 行未覆盖 |

## 技术债

| 项目 | 优先级 | 说明 |
|------|:------:|------|
| protocols.py 定义未消费 | P3 | Protocol 类仅用于类型标注，运行时无用。考虑迁入 `.pyi` stub 文件或保留作为文档 |
| Handler 类覆盖率低 | — | 设计意图，非债。Qt 包装层无法做有意义的单元测试 |
| _settings.py 427 行 | P2 | 接近 G-010 单文件上限，后续功能增长可能超标 |

## 总结

- **代码库健康度**：✅ 清洁
- **新发现死代码**：0（Phase 1+2 已清零）
- **需深入排查**：0
- **可立即清理**：0
- **补测缺口**：2 个 worker_factory（P2，约 133 行缺测试）
