# Windows 覆盖率基线最终报告

**日期**: 2026-08-01 | **环境**: Windows 11 + Python 3.14 + PyQt6 6.11

---

## 基线

```
TOTAL   22582 stmts   9666 missed   57%
```

**基线已锁定** — 57%（`coverage_progress.json`: `baseline_locked: true`）

---

## 补测模块验证

| 模块 | stmts | 覆盖 | 测试 | 耗时 |
|------|-------|------|------|------|
| `pilotstd/announcement/_wps_utils.py` | 27 | 100% | 17 | 1.51s |
| `pilotstd/tasks/date_reminder.py` | 68 | 100% | 24 | 1.87s |
| `pilotstd/announcement/_raw_store.py` | 19 | 100% | 4 | 1.36s |
| `pilotstd/query/adapters/_njbz365_session.py` | 120 | 98% | 24 | 1.75s |
| **合计** | **234** | **99.5%** | **69** | **6.49s** |

快照: `coverage_snapshot_verified.json`

---

## 测试统计

| 指标 | 值 |
|------|-----|
| 测试清单总数 | 2984 |
| 有效执行数 | 2887 |
| 隔离文件数 | 97 (79 GUI + 18 并发) |
| 通过批次 | 6/8 (root_A-D, cli, web) |
| 非阻断失败 | 2/8 (network, deadlock) |

---

## 技术债

全部转为 Linux CI 专属任务，详见：
→ [tech_debt_linux_ci.md](../tech_debt_linux_ci.md)

| 优先级 | 类别 | 文件数 | 根因 | Linux 预期回收 |
|--------|------|--------|------|---------------|
| P0 | GUI 挂起 | 79 | Qt C++ 事件循环 | +3.0–4.0pp |
| P1 | 并发死锁 | 18 | threading.Lock | +0.5–1.0pp |
| P2 | 网络依赖 | 1 | e2e HTTP | 微小 |

---

## 归档

- 进度文件: `coverage_progress.json`
- 批次日志: `archive/windows_baseline_20260801/`
- 执行脚本: `archive/windows_baseline_20260801/run_batch_tests.py`
- 补测快照: `coverage_snapshot_verified.json`
- Linux 技术债: `tech_debt_linux_ci.md`
