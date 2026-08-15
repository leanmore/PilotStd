# 技术债登记

> 版本：v1.0.0
> 更新日期：2026-07-16
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)

---

## 一、已清理（P7 完成）

| 项目 | 说明 | 修复日期 |
|------|------|---------|
| DriveEnumerator 死代码 | `_file_tree.py` 内联副本删除，统一引用 `pilotstd/ui/drive_enumerator.py` 正本 | 2026-07-16 |
| LogHandler atexit 冲突 | `flush_logs()` + `app.aboutToQuit` 注册，Qt 析构前安全关闭 logging | 2026-07-16 |
| 跨 Handler 回调升级事件总线 | EventBus 单例 + 5 Handler 迁移（scan/query/download/archive/auto），13 个集成测试 | 2026-07-16 |
| 剩余 Handler 纯逻辑提取 | AutoFlowEngine（build_summary_stats）+ ScanFlowEngine（5 方法）+ AnnounceFlowEngine（3 方法），65 测试 | 2026-07-16 |
| _auto.py 全链路阶段验证 | test_auto_pipeline.py 补充 query/download/archive 阶段字段存在性断言 | 2026-07-16 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、待处理（已登记，未排期）

| # | 项目 | 位置 | 错误类型 | 说明 | 登记日期 |
|---|------|------|---------|------|---------|
| 1 | system.py F821 | `docker/api/system.py:131` | Ruff F821 | `Undefined name 'Any'`，缺少 `from typing import Any` | 2026-07-24 |
| 2 | Mixin 类型标注 | `pilotstd/scan/parser/_exact.py` 等 13 文件 | Mypy `[attr-defined]` | Mixin 模式导致 92 处属性解析失败，需逐文件标注或重构为显式组合 | 2026-07-24 |
| 3 | i18n key 一致性自动化检查 | `web/src/locales/*.json`（当前 3 文件 / zh-CN 约 45 key） | 人工遗漏 | 各 locale 文件键名未对齐时 vue-i18n 静默降级为显示原始 key，需自动化检查防回归 | 2026-07-29 |
| 4 | test_login_correct_password_returns_ok_and_cookie | `tests/test_docker_auth.py:97` | 测试 flaky（xdist cookie 竞态） | `-n auto` 下 setUpClass 共享 TestClient，cookie 被并发清除；🔴 高，修复：`@pytest.mark.xdist_group("auth")` 串行化 | 2026-08-15 |
| 5 | test_download_by_numbers_delegates | `tests/test_manager.py:350` | 测试 mock 目标错误 | mock 的是 `mgr._scheduled_svc`，实际调用走 `mgr._core.scheduled_svc`，mock 未生效触发真实查询超时；🔴 高，修复：修正 patch 路径 | 2026-08-15 |
| 6 | test_do_request_timeout_retries | `tests/test_query.py:735` | 测试断言过时 | 已用 mock 但 mock 整个 `_session.post`，同时命中 token 获取流程，`call_count=4`≠断言 `3`（串行也失败，非 flaky）；🔴 高，修复：修正 mock 粒度或调整断言 | 2026-08-15 |
| 7 | test_01_overflow_concurrent | `tests/test_query.py:969` | 测试并发竞态 | `-n auto` 下 session 级 `shared_db` 临时 SQLite + `ConfigManager` 的 config.json 文件锁竞态；🟡 中，修复：`xdist_group` 串行化 | 2026-08-15 |
| 8 | test_04_large_batch_sub_buckets | `tests/test_query.py:998` | 测试并发竞态 | 同上（bucket 并发 + config.json 锁）；🟡 中，修复：`xdist_group` 串行化 | 2026-08-15 |

---

## 三、维持现状（E2E 兜底，不再拆解）

以下 Handler 经审查为纯 Qt 控件构建，无可提取业务逻辑。**停止底层拆解**，仅通过 E2E 测试覆盖：

| 文件 | 行数 | 内容特征 | 策略 |
|------|------|---------|------|
| `_settings.py` | 361 | QTabWidget/QGroupBox/QFormLayout 构建 | E2E 兜底 |
| `_theme.py` | 90 | QIcon/QTranslator/QStyleSheet 管理 | E2E 兜底 |
| `_file_tree.py` | ~200 | QTreeWidget+QMenu+QThread 编排 | E2E 兜底 |
| `_export.py` | ~60 | QFileDialog+QTextEdit+QTableWidget 编排 | E2E 兜底 |
| `_file_dialog.py` | ~40 | QFileDialog 封装，零业务逻辑 | E2E 兜底 |

**策略**：关注增量——未来若沉淀复杂业务逻辑（如动态对比度计算、复杂联动校验），再考虑局部提取。

---

## 三-B、i18n key 一致性检查（#3 详情）

- **触发阈值**：单个 locale 文件的顶层 key 数量 ≥ 60（当前 zh-CN.json ≈ 45 key，en.json ≈ 45 key，zh-TW.json ≈ 45 key）
- **推荐工具**（按优先级）：
  1. `i18n-check` — 专为 vue-i18n 设计，CLI 对比各 locale 文件键名并支持 CI 集成
  2. `vue-i18n-extract` — 可从源码自动提取缺失 key 并生成报告
  3. 自研脚本 — 遍历 JSON key 树做 diff，适合不想引入新依赖的场景
- **当前手动卡点**：PR 模板中已增加 `☑️ 已确认新增 i18n key 在所有 locale 文件中存在` 检查项，技术债解决前由 Reviewer 人工确认
- **实施时注意事项**：
  - 需排除 `home.pending` vs `nav.pending` 这种同名不同层级的 key（它们合法共存，不应报错）
  - 建议按完整路径（如 `nav.download_import`）做 diff，而非仅比较叶子 key 名
  - zh-TW.json 当前与 zh-CN.json 结构一致，可作为对齐参照

---

## 四、已跳过测试（13）

详见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md) 第一节。

| # | 测试 | 原因 | 分类 |
|---|------|------|------|
| 1 | `test_gb_exact_match` | 外部 API 返回空 | E2E 网络依赖 |
| 2 | `test_hg_exact_match` | hbba 无响应 | E2E 网络依赖 |
| 3 | `test_cold_start_pending` | ahbz 未登录 | E2E 认证依赖 |
| 4 | `test_sh_exact_match` | hbba 无响应 | E2E 网络依赖 |
| 5 | `test_split_pdf_pages` | 无可用 OCR provider | 环境依赖 |
| 6 | (sparse file) | 系统不支持 | 平台依赖 |
| 7~13 | 7 个 Handler E2E | Handler 不在 MainWindowCore（架构重构） | 架构重构 |

---

## 五、已接受的设计决策（5）

详见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md) 第二节。

| # | 决策 | 日期 | 影响范围 |
|---|------|------|---------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | `notification/manager.py` |
| 2 | 静态 API 令牌不支持过期/无 TTL | 低 | 令牌永不过期，泄露后风险无限期存在。决策：保持现状。理由：当前无外部 API 调用场景，实现 TTL 需增加刷新/轮换逻辑，投入产出比不高。未来若有外部集成需求可重新评估 | 2026-06-25 / 2026-07-16 确认 | `docker/auth.py` |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 全项目 |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | `engine/`, `notification/` |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | `ui/core/handlers/` 5 文件 |
