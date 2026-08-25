# 技术债登记簿

> 更新日期：2026-08-25
> 维护规则：每次接受的技术决策或跳过的测试在此登记
> 2026-08-25 审计：修正 Mypy attr-defined 数量（244→0）、G-010 行数漂移、已跳过测试表行号/删除项，与 docs/technical-debt.md 保持同步

---

## 一、已跳过的测试 (13 条登记，现存 6 条)

| # | 测试 | 文件 | 行号 | 原因 | 分类 | 处理方式 |
|---|------|------|------|------|------|---------|
| 1 | `test_gb_exact_match` | `test_e2e_adapters.py` | :42（TestE2EStdGov，原 :28） | 外部 API (std_gov) 返回空 match_status | E2E 网络依赖 | 2026-06-30 添加 `@unittest.skip`（现 :40-41 为 skipIf(_CI) + skip） |
| 2 | `test_hg_exact_match` | `test_e2e_adapters.py` | :118（TestE2EHbba，原 :103） | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest`（:97 skipIf(_CI)） |
| 3 | `test_cold_start_pending` | `test_e2e_adapters.py` | 已不存在（原 :239） | ahbz 未登录状态 | E2E 认证依赖 | 2026-08-25 审计：测试已删除；TestE2EAhbz（:234）重构为 test_gb_exact_match/test_sh_exact_match/test_iso_exact_match，skipIf(_CI) 网络防护保留 |
| 4 | `test_sh_exact_match` | `test_e2e_adapters.py` | :104（TestE2EHbba，原 :300） | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest`（:97 skipIf(_CI)） |
| 5 | `test_split_pdf_pages` | `test_ocr_fallback.py` | :38（fixture skip）/ :56（def，原 :39） | 无可用 OCR provider | 环境依赖 | `pytest.skip` 在 setup/fixture 中（非函数内） |
| 6 | (sparse file) | `test_scanner.py` | :502（原 :472） | 系统不支持此场景文件 | 平台依赖 | 原有 `self.skipTest` |
| 7 | `test_e2e_dialog` | `tests/gui/test_e2e_dialog.py` | 已删除 | DialogHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除（Handler/Mixin dual-track 清理），由单元测试间接覆盖 |
| 8 | `test_e2e_file_tree` | `tests/gui/test_e2e_file_tree.py` | 已删除 | FileTreeHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除，文件树操作由 test_file_tree.py 覆盖 |
| 9 | `test_e2e_settings` | `tests/gui/test_e2e_settings.py` | 已删除 | SettingsHandler 由 SettingsDialog 独立创建 | 架构重构 | 登记簿历史条目，无对应现存文件（cfb166fe 删除集合外，原需完整 QStackedWidget 控件树） |
| 10 | `test_e2e_table` | `tests/gui/test_e2e_table.py` | 已删除 | TableHandler 不在 MainWindowCore 中 | 架构重构 | `cfb166fe` 删除，表格操作由 test_table.py 覆盖 |
| 11 | `test_e2e_settings_io` | `tests/gui/test_e2e_settings_io.py` | 已删除 | SettingsConfigIO 是 SettingsHandler 内部组件 | 架构重构 | 登记簿历史条目，无对应现存文件（cfb166fe 删除集合外，原需完整 SettingsDialog 控件树） |
| 12 | `test_e2e_theme` | `tests/gui/test_e2e_theme.py` | 已删除 | ThemeHandler 纯 Qt 控件操作 | 架构重构 | `cfb166fe` 删除，应用主题由 MainWindow 初始化路径覆盖 |
| 13 | `test_e2e_table_helper` | `tests/gui/test_e2e_table_helper.py` | 已删除 | TableHelperHandler 不在 MainWindowCore 中 | 架构重构 | 登记簿历史条目，无对应现存文件（cfb166fe 删除集合外），表格操作由 test_table.py 覆盖 |

**处理策略**：#1~#6（外部 API/环境依赖）E2E 测试保留在本地开发时手动运行，CI 环境自动跳过。#7~#13（架构重构）对应测试文件均已不存在：其中 #7/#8/#10/#12（test_e2e_dialog/file_tree/table/theme）由 `cfb166fe`（Handler/Mixin dual-track 清理，删 8 个死 Handler/Mixin 文件 + `tests/gui/test_e2e_*.py` 6 个测试）删除；#9/#11/#13（settings/settings_io/table_helper）不在删除集合中，为登记簿历史条目，无对应现存文件。功能均由对应单元测试间接覆盖。

---

## 二、已接受的设计决策

| # | 决策 | 日期 | 原因 | 影响范围 | 替代方案 |
|---|------|------|------|---------|---------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | SMTP 配置复杂 + 安全风险 (密码存储) | `notification/manager.py` 渠道注册 | 未来可通过 OAuth2 接入 |
| 2 | 静态 API 令牌不支持过期 | 2026-06-25 | 简单优先，压测/脚本使用 | `docker/auth.py` API Key 管理 | 可扩展为支持 TTL |
| 3 | 分批渐进式 G-010 治理 | 2026-06-24 | 一次性改造风险高 | 全项目 | 激进重构已否决 |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | 保持公开接口不变 | `engine/`, `notification/` | 组合模式需大量接口改动 |
| 5 | 纯 UI 编排文件不再拆解 Engine | 2026-07-16 | _settings/_theme/_file_tree/_export/_file_dialog 5 个 Handler 均为纯 Qt 控件构建，无可提取纯逻辑 | `pilotstd/ui/core/handlers/` 5 文件 | 仅 E2E 兜底，未来若沉淀复杂业务逻辑再局部提取 |
| 6 | JWT_SECRET 固定默认值 | 2026-06-30 | 服务重启后 token 不失效 | `docker/auth.py` | 环境变量覆盖有最高优先级 |
| 7 | 内存会话存储 (无持久化) | 2026-06-30 | 简单够用，重启后需重新登录是预期行为 | `docker/session_store.py` | Redis 可在规模化后引入 |
| 8 | `QueryUIHandler.__init_tr` 命名不规范 | 2026-07-12 | Mixin→Handler 重构中，`__init__` 逻辑命名为 `__init_tr` 而非 `__init__`，导致构造参数错配漏检 | `_query.py` | 已修复：补充 `__init__` 委托给 `__init_tr`，消除实例化失败风险 |

---

## 三、已知问题

| # | 问题 | 严重程度 | 发现日期 | 状态 | 说明 |
|---|------|---------|---------|------|------|
| 1 | E2E 测试依赖外部 API | 低 | 历史遗留 | 已接受 | 6 个测试跳过，CI 不影响 |
| 2 | Mypy mixin attr-defined 错误 | 低 | 历史遗留 | ✅ 已解决 (2026-08-25) | 原 244 条（mixin 类引用其他 mixin 属性）。parser 重构 + 类型标注后，2026-08-25 审计实测 `mypy pilotstd docker`：attr-defined = 0 |
| 3 | `_batch.py` 溢出回收逻辑仍部分内联 | 低 | 2026-06-30 | 部分缓解 | 溢出处理已委托 `_overflow`。`query_batch_parsed` 已废弃。**关联：纯逻辑提取已完成** — AutoFlowEngine (7 测试) + ScanFlowEngine (31 测试) + AnnounceFlowEngine (20 测试)，共 3 Engine / 58 纯单元测试，已标记完成 (2026-07-16) |
| 4 | 数据库迁移链顺序依赖 (v7 需 file_index 表存在) | 低 | 2026-06-30 | 已缓解 | 已添加 try/except 守卫 |
| 5 | `test_migration_runs_pending` 依赖 `CURRENT_SCHEMA_VERSION` patch 路径 | 低 | 2026-06-30 | 已修复 | 修正为 `database.CURRENT_SCHEMA_VERSION` |
| 6 | WebSocket 广播无用户级路由 (广播到所有连接) | 中 | 2026-06-25 | 已接受 | 当前设计为全局广播，未来可按 user_id 路由 |
| 7 | 会话存储重启即丢失 | 中 | 2026-06-30 | 已接受 | 重启后需重新登录是预期行为，可后续引入 Redis |
| 8 | 构建缓存策略 — Docker Registry Cache + GHA cache 双通道，依赖哈希自动失效 | 低 | 2026-06-29 | ✅ 已实施 (2026-07-01) | `.github/workflows/ci.yml` — `build-and-push` job，`cache-from` + `cache-to` 双通道 |
| 9 | Toast 弹窗已删除 — Web 通知走企业微信/飞书等外部渠道 | 2026-07-09 | 已关闭 | Toast 组件及配置已全部移除 | Toast 组件及相关配置于 2026-07-09 全部移除 |
| 10 | 静态令牌永不过期 — API Key 不设自动轮换 | 中 | 2026-06-29 | 已接受 | 当前安全模型足够。决策（2026-07-16）：保持现状，不做更改。理由：当前无外部 API 调用场景，令牌泄露风险极低。未来触发条件：出现外部 API 集成需求时重新评估 |
| 11 | 测试覆盖 | 低 | 2026-06-29 | 已接受 | 942 PASS |
| 12 | 前后端配置键名不一致 (scan/query/validity) → 数据静默丢失 | 高 | 2026-07-05 | ✅ 已修复 (2026-07-05) | `skip_file_keywords`→`exclude_patterns`、`query.interval`→`query_interval`、`validity.update_interval`→`total_weeks` |
| 13 | 后端 GET 硬编码事件列表 vs 前端完整列表 → 订阅状态加载丢失 | 高 | 2026-07-05 | ✅ 已修复 (2026-07-05) | `ALL_EVENT_KEYS` 从 events.py 派生，GET/PUT 统一 |
| 14 | 设置模块 4 处独立维护事件/字段列表 → 增删不同步 | 中 | 2026-07-05 | ✅ 已修复 (2026-07-06) | events.py SSOT + settings_schema.py + E2E 一致性测试 |
| 15 | Telegram 通知 404 刷屏 (token 未 strip + 无错误分类) | 中 | 2026-07-05 | ✅ 已修复 (2026-07-05) | strip + HTTPError 分类 + 120s 去重 |
| 16 | PyInstaller --noconsole sys.stderr=None 兜底 | 高 | 2026-07-09 | 已回退 | _SafeStream 于 2026-07-09 禁用，改用原生 stderr |
| 17 | PyPDF2 已废弃，CI 产生 DeprecationWarning | 低 | 2026-07-05 | ✅ 已修复 (2026-07-05) | 全量迁移至 pypdf |
| 18 | python-multipart 缺失导致 PyInstaller 打包后文件上传崩溃 | 高 | 2026-07-06 | ✅ 已修复 (2026-07-06) | 加入共享 requirements.txt |

---

## 四、Mypy 豁免项

| 豁免类型 | 数量 | 原因 |
|---------|------|------|
| `attr-defined` (mixin) | 0（原 244，2026-08-25 审计已清零） | mixin 类引用在其他 mixin 中定义的属性，mypy 无法跨文件推断；parser 重构 + 类型标注后不再产生 |
| `import-untyped` | — | psutil 等第三方库无类型标注 |
| UI 目录 `ignore_errors=true` | — | PyQt6 mixin 架构与 mypy strict 模式冲突 |

策略：mypy 错误不阻断 pre-commit（使用 `--no-verify`），CI 中仍运行 mypy 但标记为 non-blocking。

---

## 五、处理流程图

```
发现技术债
  ├── 严重 (安全/数据丢失) → P0 立即修复
  ├── 中等 (可修复，需设计) → P1 下个迭代
  ├── 低 (可接受) → 登记本文件，不排期
  └── 环境依赖 → 测试跳过 + 本文件登记

接受设计决策
  ├── 记录决策原因 + 影响范围 + 替代方案
  └── 定期回顾 (每季度)

---

## 四、已跳过的环境依赖 (1)

| # | 项目 | 影响范围 | 原因 | 处理方式 |
|---|------|---------|------|---------|
| 14 | `pytest-asyncio` | `tests/test_health.py` 5 个异步测试 | 新增 /api/health 端点单元测试使用 `@pytest.mark.asyncio`，需额外安装 `pytest-asyncio` 包 | 2026-07-20 手动 `pip install pytest-asyncio` 后本地通过；CI runner 尚未验证是否已自带此包，若 CI 失败需在 `requirements*.txt` 中补充依赖 |

---

## 六、G-010 警告基线（Backlog，9 文件）

> 状态：backlog（不阻断 CI——警告档仅 stderr 提示，exit 0）
> 处置：Boy Scout Rule——后续新增功能/修复缺陷时顺手抽离大函数，自然降低有效代码行数；不强制排期拆分
> 规则：警告档 = 有效代码行 >400 且 ≤500（`scripts/check_g_010_code_size.py` 两档制）；阻断档（>500）当前 0 文件
> 2026-08-25 审计：行数微漂移——`pilotstd/core/notification/manager.py` 447→479、`web/src/components/AppLayout.vue` 433→434，其余不变

| # | 文件 | 类型 | 有效代码行 | 总行 |
|---|------|------|-----------|------|
| 1 | `scripts/check_g_012_sql_schema.py` | .py | 499 | 634 |
| 2 | `docker/auth.py` | .py | 490 | 610 |
| 3 | `web/src/views/AnnounceDetail.vue` | .vue | 476 | 537 |
| 4 | `docker/api/announce_detail.py` | .py | 454 | 577 |
| 5 | `pilotstd/core/notification/manager.py` | .py | 479 | 509 |
| 6 | `scripts/check_g_012_comment_density.py` | .py | 440 | 586 |
| 7 | `pilotstd/core/db/_migrate_v16_v49.py` | .py | 438 | 530 |
| 8 | `web/src/components/AppLayout.vue` | .vue | 434 | 537 |
| 9 | `web/src/components/NotificationConfig.vue` | .vue | 426 | 469 |
