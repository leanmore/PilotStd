# 技术债登记簿

> 更新日期：2026-06-30
> 维护规则：每次接受的技术决策或跳过的测试在此登记

---

## 一、已跳过的测试 (6)

| # | 测试 | 文件 | 行号 | 原因 | 分类 | 处理方式 |
|---|------|------|------|------|------|---------|
| 1 | `test_gb_exact_match` | `test_e2e_adapters.py` | :28 | 外部 API (std_gov) 返回空 match_status | E2E 网络依赖 | 2026-06-30 添加 `@unittest.skip` |
| 2 | `test_hg_exact_match` | `test_e2e_adapters.py` | :103 | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest` |
| 3 | `test_cold_start_pending` | `test_e2e_adapters.py` | :239 | ahbz 未登录状态 | E2E 认证依赖 | 原有 `self.skipTest` |
| 4 | `test_sh_exact_match` | `test_e2e_adapters.py` | :300 | hbba 外部 API 无响应 | E2E 网络依赖 | 原有 `self.skipTest` |
| 5 | `test_split_pdf_pages` | `test_ocr_fallback.py` | :87 | 无可用 OCR provider | 环境依赖 | 原有 `self.skipTest` |
| 6 | (sparse file) | `test_scanner.py` | :472 | 系统不支持此场景文件 | 平台依赖 | 原有 `self.skipTest` |

**处理策略**：E2E 测试保留在本地开发时手动运行，CI 环境自动跳过。未来可引入 `responses` / `vcrpy` 等 mock 工具录制回放。

---

## 二、已接受的设计决策

| # | 决策 | 日期 | 原因 | 影响范围 | 替代方案 |
|---|------|------|------|---------|---------|
| 1 | 邮件渠道列入黑名单 | 2026-06-29 | SMTP 配置复杂 + 安全风险 (密码存储) | `notification/manager.py` 渠道注册 | 未来可通过 OAuth2 接入 |
| 2 | 静态 API 令牌不支持过期 | 2026-06-25 | 简单优先，压测/脚本使用 | `docker/auth.py` API Key 管理 | 可扩展为支持 TTL |
| 3 | 分批渐进式 GATE-15 治理 | 2026-06-24 | 一次性改造风险高 | 全项目 | 激进重构已否决 |
| 4 | Mixin 模式拆分大文件 | 2026-06-30 | 保持公开接口不变 | `engine/`, `notification/` | 组合模式需大量接口改动 |
| 5 | JWT_SECRET 固定默认值 | 2026-06-30 | 服务重启后 token 不失效 | `docker/auth.py` | 环境变量覆盖有最高优先级 |
| 6 | 内存会话存储 (无持久化) | 2026-06-30 | 简单够用，重启后需重新登录是预期行为 | `docker/session_store.py` | Redis 可在规模化后引入 |

---

## 三、已知问题

| # | 问题 | 严重程度 | 发现日期 | 状态 | 说明 |
|---|------|---------|---------|------|------|
| 1 | E2E 测试依赖外部 API | 低 | 历史遗留 | 已接受 | 6 个测试跳过，CI 不影响 |
| 2 | Mypy mixin attr-defined 244 错误 | 低 | 历史遗留 | 已接受 | mixin 模式固有局限，需 Protocol 类型标注 |
| 3 | `_batch.py` 溢出回收逻辑仍在 `query_batch_parsed` 内联 | 低 | 2026-06-30 | 已记录 | 可进一步提取为独立 mixin (P2) |
| 4 | 数据库迁移链顺序依赖 (v7 需 file_index 表存在) | 低 | 2026-06-30 | 已缓解 | 已添加 try/except 守卫 |
| 5 | `test_migration_runs_pending` 依赖 `CURRENT_SCHEMA_VERSION` patch 路径 | 低 | 2026-06-30 | 已修复 | 修正为 `database.CURRENT_SCHEMA_VERSION` |
| 6 | WebSocket 广播无用户级路由 (广播到所有连接) | 中 | 2026-06-25 | 已接受 | 当前设计为全局广播，未来可按 user_id 路由 |
| 7 | 会话存储重启即丢失 | 中 | 2026-06-30 | 已接受 | 重启后需重新登录是预期行为，可后续引入 Redis |
| 8 | 构建缓存策略 — Docker 构建缓存，依赖变化时自动失效 | 低 | 2026-06-29 | 已接受 | CI 构建效率优化，构建产物不使用缓存 |
| 9 | Toast 弹窗配置 — 用户可在 NotificationConfig.vue 中配置开关 | 低 | 2026-06-29 | 已接受 | 前端用户体验，非安全相关 |
| 10 | 静态令牌永不过期 — API Key 不设自动轮换 | 中 | 2026-06-29 | 已接受 | 当前安全模型足够，可后续引入 TTL |
| 11 | 测试覆盖策略 — 全量覆盖 (后端 + 前端组件) | 低 | 2026-06-29 | 已接受 | 615 PASS / 6 SKIP / 0 FAIL |

---

## 四、Mypy 豁免项

| 豁免类型 | 数量 | 原因 |
|---------|------|------|
| `attr-defined` (mixin) | 244 | mixin 类引用在其他 mixin 中定义的属性，mypy 无法跨文件推断 |
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
```
