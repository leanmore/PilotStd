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
| `download/adapters/openstd_download` | 5 步状态机，待 P4 步骤1 |
| `download/engine` | 多适配器编排，需 E2E 集成测试 |
| `ui/` 全部 | GUI 层，E2E scope |

## 历史趋势

| 日期 | 用例数 | 覆盖率 | 变更说明 |
|------|:--:|:--:|------|
| 2026-08-03 | 11 | 12.4% | 初始基线：detect_ip(4) + gongbiaoku(4) + Baidu OCR(3) |

## 使用说明

- 手动刷新基线：GitHub Actions → E2E Coverage Baseline → Run workflow
- 下载报告：Actions run → Artifacts → e2e-coverage-html
- 更新本文档：从 e2e-coverage.xml 读取 line-rate

## P4 总结 (2026-08-03)

### 交付成果

| 步骤 | 内容 | 状态 |
|:--:|------|:--:|
| 1 | openstd_download 5 步状态机方案 | 方案锁定（待实现） |
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
