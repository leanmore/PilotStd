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
