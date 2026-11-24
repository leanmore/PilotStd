# Testing Baseline (E2E + Integration)

本文档记录 E2E 和集成测试的覆盖率基线，用于追踪测试质量演进趋势。
仅度量，不设门禁。每季度回顾一次，由团队共识决定是否调整目标。

## 最新基线

| 指标 | 值 | 日期 | Commit |
|------|-----|------|--------|
| E2E 用例数 | 8 | 2026-08-03 | 531668a |
| E2E 耗时 | 3.3s | 2026-08-03 | — |
| Integration 用例数 | 3 | 2026-08-03 | 678b246 |
| Integration 耗时 | 13.3s | 2026-08-03 | — |
| E2E + Integration 合计量 | 11 | 2026-08-03 | — |
| E2E + Integration 总耗时 | 16.0s | 2026-08-03 | — |
| 合计行覆盖率 | **12.4%** | 2026-08-03 | 678b246 |

> **2026-11-13 增量（P3-16 / P2-10 / P2-07）**：新增
> `tests/integration/test_monitor_catchup_e2e.py`（6 例，启动补扫真归档）、
> `tests/test_p2_10_silent_error_triage.py`（3 例）、`tests/test_check_docs_drift_counts.py`（4 例）
> 与 G-013 消息读取 `[WARN]` 用例（1 例）；`pytest` 全量 **6740 passed / 12 skipped**
> （见 `docs/governance/ISSUE_LEDGER.md` P2-10、P3-16）。

## 核心模块覆盖状态

| 模块 | E2E | Integration | 备注 |
|------|:--:|:--:|------|
| `wechat_ip/detector` | 82% | ❌ | 4 用例，responses mock |
| `wechat_ip/logic` | 0% | ❌ | 纯逻辑，已有单元测试(100%)，此处不计 |
| `wechat_ip/scheduler` | 0% | ❌ | 定时器+浏览器，E2E scope |
| `query/adapters/gongbiaoku` | ✅ | ❌ | 4 用例，respx mock |
| `announcement/ocr/_baidu` | ❌ | ✅ | 3 用例，pytest-httpserver |
| `announcement/ocr/_base` | ❌ | 部分 | OcrResult 模型被 Integrated test 间接覆盖 |
| `query/network` | ❌ | 部分 | safe_raw_get/post 被 Integration monkeypatch 拦截 |

## 未覆盖模块（设计意图）

| 模块 | 原因 |
|------|------|
| `announcement/ocr/_tencent` | HMAC-SHA256 签名，不适合 HTTP mock |
| `announcement/ocr/_aliyun` | 阿里云签名，不适合 HTTP mock |
| `announcement/ocr/OcrScheduler` | 双槽并行+冷却逻辑，需 E2E 集成测试 |
| `download/adapters/openstd_download` | **已实现**（5 步链路 + hcno 搜索页解析，见 `pilotstd/download/adapters/openstd_download.py:175-256`）；单元层已由 `tests/download/adapters/test_openstd_download.py`（43 passed）覆盖，另有 `tests/integration/test_favorite_download_chain_e2e.py` |
| `download/engine` | 多适配器编排，需 E2E 集成测试 |
| `ui/` 全部 | GUI 层，E2E scope |

## 历史趋势

| 日期 | 用例数 | 覆盖率 | 变更说明 |
|------|:--:|:--:|------|
| 2026-08-03 | 11 | 12.4% | 初始基线：detect_ip(4) + gongbiaoku(4) + Baidu OCR(3) |
| 2026-11-13 | +14 | — | P3-16 monitor 启动补扫 e2e(6) + P2-10 triage(3) + G-052 数字校验(4) + G-013 消息告警(1) |

## 使用说明

- 手动刷新基线：GitHub Actions → E2E Coverage Baseline → Run workflow
- 下载报告：Actions run → Artifacts → e2e-coverage-html
- 更新本文档：从 e2e-coverage.xml 读取 line-rate

## P4 总结 (2026-08-03)

### 交付成果

| 步骤 | 内容 | 状态 |
|:--:|------|:--:|
| 1 | openstd_download 5 步状态机 | **已实现**（P4 之后落地，详见 [download-pipeline.md](../reference/download-pipeline.md)） |
| 2 | BaiduOcrProvider 集成测试 (3 用例) | ✅ |
| 3 | E2E 覆盖率度量 (workflow + 基线) | ✅ |
| 4 | 性能回归基线 | ⏸️ 延后 P2 |
| 5 | CHANGELOG + integration-guide.md | ✅ |

### 测试矩阵

| 层级 | 目录 | 用例数 | 工具 | 耗时 |
|------|------|:--:|------|------|
| E2E (HTTP mock) | `tests/e2e/` | 8 | responses + respx | 3.3s |
| Integration (状态机) | `tests/integration/` | 3 | pytest-httpserver | 13.3s |
| **合计** | | **11** | | **16.0s** |

### 相关文档

- [E2E 测试指南](e2e-guide.md) — mock 策略 + 用例矩阵
- [集成测试指南](integration-guide.md) — 架构决策 + monkeypatch 模式 + 故障排查
- [CHANGELOG](../../CHANGELOG.md) — v0.91.0 完整变更记录

## 性能回归基线 (Phase 1 A线 · 2026-08-03)

| 指标 | 值 | 备注 |
|------|-----|------|
| `parse_cookie_string` | <0.001ms (n=100) | 纯函数，无需持续监控 |
| `merge_ip_list` | <0.001ms (n=200) | 纯函数，无需持续监控 |
| `parse_app_urls` | <0.001ms (n=200) | 纯函数，无需持续监控 |
| `pdf_gen_100kb` | **1.0ms** median (n=10) | IO 密集锚点 |
| `pdf_gen_800kb` | **2.3ms** median (n=10) | IO 密集锚点 |

> `parse_cookie_string` / `merge_ip_list` / `parse_app_urls` 均为亚毫秒级纯函数，未来无需纳入性能回归监控。

### 刷新 SOP

1. 本地运行 `pytest tests/perf/ -v`
2. 检查 `.perf-baseline.json` 数字是否显著偏离上表
3. 若偏离 >20%，更新本表并附注原因

## E2E 覆盖率设计意图说明

### UI 层排除声明

`pilotstd/ui/*` 全部模块 E2E 覆盖率为 0%，这是**设计意图而非遗漏**：
- GUI 层由手动验收 + Playwright 独立套件守护
- pytest E2E 仅覆盖非 GUI 业务逻辑路径
- 新人请勿将 UI 0% 视为测试缺口

### 分层测试策略备注

| 模块 | E2E 覆盖 | 单元覆盖 | 说明 |
|------|:--:|:--:|------|
| `wechat_ip/logic` | 0% | **100%** | 纯逻辑层，单测已完全守护，E2E 不重复 |
| `wechat_ip/detector` | 82% | — | 主路径 + 降级已由 E2E 守护 |
| `announcement/ocr/_baidu` | 79% | — | Integration 已覆盖两步协议 + 降级 |
| `query/adapters/gongbiaoku` | 部分 | — | HTML 解析主路径已覆盖 |

### 测试数口径（四列，2026-11-15 定死）

| 时点 | collected | passed | subtests | skipped |
|---|---|---|---|---|
| 2026-11-13 `ed8ba431`（复核） | 6344 | 6333 | 401 | 11 |
| 2026-11-17 HEAD（A-47/健康检查/数据卫生） | 6428 | 6407 | 401 | 21 |

- `collected`：pytest 收集用例数（`--collect-only`）；`passed`：用例通过数，**不含** subtests；
  `subtests`：pytest-subtests 子用例通过数（独立一行输出）；`skipped`：跳过数。
- 旧记录 "6740 passed" = **passed + subtests**（6333 + 401 ≈ 6740），属口径混淆；此后一律按四列报数。
- 11-13 → 11-15 的差异：A-37 把网络 e2e 改为显式开启（该文件 13→2 passed、4→15 skipped）；
  A-33 删 10 例；本批新增 A-27.3 9 例、P1 5 例、file_index 保护 8 例、G-052/G-050 若干。

> **2026-11-21 增量（D-2 阶段 1 / A-27 / U-1 / G-02）**：新增测试文件 5 个 ——
> `tests/test_notification_policy_fallback.py`（6 例）、`tests/test_notification_link_level_render.py`（7 例）、
> `tests/test_notification_wechat_test_connection.py`（1 例）、`tests/test_validity_last_status.py`（4 例）、
> `tests/test_batch_result_metrics.py`（3 例），另有 `tests/test_notification_menu_chats.py`、`tests/test_notification_menu_config.py`、
> `tests/test_migrate_superseded_by_direction.py`、`tests/test_api_archive_stats.py` 同期扩充。
> 通知相关套件 `pytest -k "notification or renderer"` 实测 **1276 passed**。

> **2026-11-23 增量（方向 C 批次 3/5/6/7/8）**：新增 10 个 Python 测试文件 + 1 个前端测试文件 ——
> `test_check_g_050_continue_break.py`（4 例）、`test_upload_svg_xss.py`（13 例）、
> `test_db_migration_lock_loop.py`（3 例）、`test_pending_record_no_n_plus_one.py`（4 例）、
> `test_file_index_validate_scandir.py`（6 例）、`test_system_update_nonblocking.py`（4 例）、
> `test_check_g_056_doc_deadlinks.py`（7 例）、`test_resource_leaks.py`（5 例）、
> `test_db_conn_reclaim.py`（6 例）、`test_csp_no_unsafe_eval.py`（3 例）、
> 前端 `web/src/components/__new16_17.test.ts`（8 例）。
> 前端 vitest：**69 files / 680 tests**。
> 测试文件数变化幅度较大，按 CI 严格模式要求在此登记。
