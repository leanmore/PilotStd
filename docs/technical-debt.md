# 技术债登记

> 版本：v1.1.0
> 更新日期：2026-08-25
> 详细登记见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md)
> 2026-08-25 全库审计：原待处理台账 12 条中 8 条（#1~#8）确认已解决并移入第一节（附 fix commit 证据），4 条（#9~#12）仍存在、描述已同步现状；第三/四节过时内容一并修正。同日 TD-9（#9，`bd34a226`）、TD-10（#10，P0 `07786678` + P1+P2 `acf2a7fd`）修复完成，剩余 2 条（#11~#12）待处理。

---

## 一、已清理

| 项目 | 说明 | 修复日期 |
|------|------|---------|
| DriveEnumerator 死代码 | `_file_tree.py` 内联副本删除，统一引用 `pilotstd/ui/drive_enumerator.py` 正本 | 2026-07-16 |
| LogHandler atexit 冲突 | `flush_logs()` + `app.aboutToQuit` 注册，Qt 析构前安全关闭 logging | 2026-07-16 |
| 跨 Handler 回调升级事件总线 | EventBus 单例 + 5 Handler 迁移（scan/query/download/archive/auto），13 个集成测试 | 2026-07-16 |
| 剩余 Handler 纯逻辑提取 | AutoFlowEngine（build_summary_stats）+ ScanFlowEngine（5 方法）+ AnnounceFlowEngine（3 方法），65 测试 | 2026-07-16 |
| _auto.py 全链路阶段验证 | test_auto_pipeline.py 补充 query/download/archive 阶段字段存在性断言 | 2026-07-16 |
| PriorityConfigManager 死代码（O-6） | `pilotstd/core/config/priority.py` 零生产引用（仅测试），删除模块 + 测试；`STANDARD_ROOT` 环境变量能力已由 `ConfigManager.__init__` 原生覆盖，不丢功能 | 2026-08-24 |
| TD-1 system.py F821 | 原 #1（登记 2026-07-24）：`docker/api/system.py:131` `Undefined name 'Any'`，缺 `from typing import Any`。`4bfb8078`（2026-07-25）补充导入；2026-08-25 审计实测 `ruff check docker/api/system.py` 通过 | 2026-07-25 |
| TD-2 Mixin 类型标注 | 原 #2（登记 2026-07-24）：`pilotstd/scan/parser/_exact.py` 等 13 文件 Mypy `[attr-defined]` 92 处。parser 已重构拆分为多模块（`_exact.py`→`_exact_matcher.py` 等，f6c6b4de/bddc6943）；2026-08-25 审计实测 `mypy pilotstd docker`：attr-defined = 0（剩余错误为 arg-type 等其他类型，见登记簿第四节） | 2026-08-25（审计确认） |
| TD-3 i18n key 一致性自动化检查 | 原 #3（登记 2026-07-29）：locale 键名未对齐时 vue-i18n 静默降级。`scripts/check_i18n_key_count.py` 已实现（顶层 key 对齐检测 + 50 警告 / 60 阻断阈值）并接入 CI（ci.yml `i18n key count & alignment check` step），配套 `tests/test_i18n_key_count.py`（11 用例）；当前 3 locale 文件顶层 key 各 15 个 | 2026-07-29 |
| TD-4 test_login_correct_password_returns_ok_and_cookie | 原 #4（登记 2026-08-15）：xdist cookie 竞态。`81652b6d` 添加 `@pytest.mark.xdist_group("auth")`（`tests/test_docker_auth.py:97`） | 2026-08-15 |
| TD-5 test_download_by_numbers_delegates | 原 #5（登记 2026-08-15）：mock 目标错误，mock 未生效触发真实查询超时。`c5e1c824` 修正为 `_core.scheduled_svc`（`tests/test_manager.py:369`） | 2026-08-15 |
| TD-6 test_do_request_timeout_retries | 原 #6（登记 2026-08-15）：mock 命中 token 获取流程致 call_count 漂移。`a720030a` 标记 `_session_mgr._initialized` 跳过 token 获取，断言 3 成立（`tests/test_query.py:743-754`） | 2026-08-15 |
| TD-7 test_01_overflow_concurrent | 原 #7（登记 2026-08-15）：bucket 并发 + config.json 文件锁竞态。`eddc02bf` 添加 `@pytest.mark.xdist_group("bucket_stress")`（`tests/test_query.py:970`） | 2026-08-15 |
| TD-8 test_04_large_batch_sub_buckets | 原 #8（登记 2026-08-15）：同上（bucket 并发 + config.json 锁）。`eddc02bf` 添加 `@pytest.mark.xdist_group("bucket_stress")`（`tests/test_query.py:1002`） | 2026-08-15 |
| TD-9 notification.py user_id 误用 | 原 #9（登记 2026-08-20，2026-08-25 审计升 🔴 高）：`_get_user_id` 把 token 的 user_id 传给按 username 查询的 `get_user_id()`（`WHERE username = ?`），多用户场景静默折叠为 user 1。`bd34a226`（2026-08-25）重写：形参 `username`→`user_id`，改用按主键 `get_user_by_id()` 校验，未知用户显式 401（删除兜底 1）；新增单元 401 分支 + 真实登录 + SQLite 集成测试（`tests/test_notification_api.py`，12 passed；联动 4 文件 28 passed） | 2026-08-25 |
| TD-10 test_api_snapshot.py 环境污染 | 原 #10（登记 2026-08-20）：模块级 `os.environ.setdefault` 注入独有 env 值（snapshot_*/admin_db_*）且永不恢复，污染后导入的 test_docker_auth 等模块（SUPERUSER 错值 → 登录 401，串行确定性失败 / xdist 下 flaky）。P0 `07786678`（2026-08-25）：test_api_snapshot/test_admin_db 改模块级 autouse env fixture（save/restore/pop 标准模式，同 test_api_favorites_auth.py:25-38）；P1+P2 `acf2a7fd`：4 个守卫式 `SUPERUSER` 注入清理（test_announce_detail 等）+ 10 个同值家族模块级 setdefault 收敛为 conftest 共享 fixture + 薄 wrapper。关门验证：全量串行 `tests/ --ignore=tests/gui/` 4084 passed / **0 failed**（基线 2 failed），14 skipped 不变 | 2026-08-25 |

**技术细节**：见 [architecture.md](architecture.md) 事件总线重构决策记录。

---

## 二、待处理（原台账 #11~#12；#1~#10 已解决，见第一节）

| # | 项目 | 位置 | 错误类型 | 说明 | 登记日期 |
|---|------|------|---------|------|---------|
| 11 | G-010 警告基线 | 9 文件（400–500 有效代码行，详见 [登记簿](architecture/technical-debt-registry.md) 第六节） | G-010 警告（不阻断） | 警告档仅 stderr 提示、exit 0，不阻断 CI/合并；Boy Scout Rule：随改随拆（新增功能/修 Bug 时抽离大函数自然降行），不强制排期。2026-08-25 审计：仍 9 文件、阻断档（>500）0 文件；`manager.py` 447→479 行、`AppLayout.vue` 433→434 行，其余 7 文件不变 | 2026-08-23 |
| 12 | G-012 LANG 历史警告 | `pilotstd/core/notification/`、`docker/api/announce_detail.py`、`pilotstd/core/config/`、`scripts/audit_notification_chain*.py`、`scripts/check_g_010_code_size.py`、`pilotstd/services/favorite_chain_processor.py` 等 | G-012 LANG 警告（不阻断） | 不阻断提交（仅 hard error 阻断，LANG 为警告）；建议后续专项清理：将注释中的英文术语改写为中文或补充白名单（`check_g_012_comment_density.py` LANG_WHITELIST）；低优先级，Boy Scout Rule 随改随清。2026-08-25 审计：数量 44→**50** 条，涉及文件约 20 个（含 scripts/ 下新增脚本） | 2026-08-24 |

---

## 三、维持现状（E2E 兜底，不再拆解）

以下文件经审查为纯 Qt 控件构建，无可提取业务逻辑。**停止底层拆解**，仅通过 E2E 测试覆盖：

| 文件 | 行数 | 内容特征 | 策略 |
|------|------|---------|------|
| `pilotstd/ui/core/handlers/_settings.py` | 426 | QTabWidget/QGroupBox/QFormLayout 构建 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_theme_ops.py` | 142 | QIcon/QTranslator/QStyleSheet 管理 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_tree_ops.py` | 263 | QTreeWidget+QMenu+QThread 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_export_ops.py` | 143 | QFileDialog+QTextEdit+QTableWidget 编排 | E2E 兜底 |
| `pilotstd/ui/main_window/parts/_file_dialog_ops.py` | 51 | QFileDialog 封装，零业务逻辑 | E2E 兜底 |

**策略**：关注增量——未来若沉淀复杂业务逻辑（如动态对比度计算、复杂联动校验），再考虑局部提取。

**2026-08-25 审计**：原 `_theme.py`/`_file_tree.py`/`_export.py`/`_file_dialog.py` 已随 Handler 重构删除（`d1c12253` 创建 `main_window/parts/*_ops.py` 等价物，`cfb166fe` 清理旧文件），`_settings.py` 361→426 行；策略不变。

---

## 三-B、i18n key 一致性检查（#3 详情）

> 状态：✅ 已实施（2026-07-29）——`scripts/check_i18n_key_count.py` 落地并接入 CI（ci.yml `i18n key count & alignment check` step，WARN 50 / FAIL 60）。本节保留为方案说明与历史记录。

- **触发阈值**：单个 locale 文件的顶层 key 数量 ≥ 60（当前 3 文件顶层 key 各 15 个、叶子 key 各 88 个，脚本 WARN_THRESHOLD=50 / FAIL_THRESHOLD=60）
- **推荐工具**（按优先级）：
  1. `i18n-check` — 专为 vue-i18n 设计，CLI 对比各 locale 文件键名并支持 CI 集成
  2. `vue-i18n-extract` — 可从源码自动提取缺失 key 并生成报告
  3. 自研脚本 — 遍历 JSON key 树做 diff，适合不想引入新依赖的场景
- **当前卡点**：自动化检查已落地（对齐检测 + 数量阈值），PR 模板中的 `☑️ 已确认新增 i18n key 在所有 locale 文件中存在` 人工项保留为兜底
- **实施时注意事项**：
  - 需排除 `home.pending` vs `nav.pending` 这种同名不同层级的 key（它们合法共存，不应报错）
  - 建议按完整路径（如 `nav.download_import`）做 diff，而非仅比较叶子 key 名
  - zh-TW.json 当前与 zh-CN.json 结构一致，可作为对齐参照

---

## 四、已跳过测试（历史 13 条，现存 6 条）

详见 [architecture/technical-debt-registry.md](architecture/technical-debt-registry.md) 第一节。

| # | 测试 | 原因 | 分类 |
|---|------|------|------|
| 1 | `test_gb_exact_match` | 外部 API 返回空 | E2E 网络依赖 |
| 2 | `test_hg_exact_match` | hbba 无响应 | E2E 网络依赖 |
| 3 | `test_cold_start_pending` | ahbz 未登录（测试已删除，见登记簿） | E2E 认证依赖 |
| 4 | `test_sh_exact_match` | hbba 无响应 | E2E 网络依赖 |
| 5 | `test_split_pdf_pages` | 无可用 OCR provider | 环境依赖 |
| 6 | (sparse file) | 系统不支持 | 平台依赖 |
| 7~13 | 7 个 Handler E2E | 测试文件已删除（`cfb166fe`，tests/gui/） | 已删除（由单元测试覆盖） |

**2026-08-25 审计**：#1~#6 skip 标记仍在（行号随文件重构漂移：#1 现于 `test_e2e_adapters.py:42`、#6 现于 `test_scanner.py:502`）；#3 测试已不存在；#7~#13 对应 `tests/gui/test_e2e_*.py` 文件已于 `cfb166fe`（Handler/Mixin dual-track 清理）删除，功能由对应单元测试覆盖。

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
