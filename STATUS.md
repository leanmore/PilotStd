# PilotStd 项目状态

> 最后更新：2026-07-01
> 维护规则：每次任务完成后，由 Claude Code 更新本文件
> 当前阶段：修复/重构阶段已完成，治理常态化运行中

## 一、当前版本信息

| 项目 | 值 |
|------|-----|
| 版本号 | 0.52.6 (代码) / v0.53.0 (最新 tag) |
| 分支 | main |
| 未推送提交 | 1 (6bbb957 — GATE-15 清零) |
| 目标 | GATE-15 违规归零 + 测试 100% 通过 (0 FAIL) |

## 二、最近治理动作

### 2026-07-01 — 通知系统智能聚合 + 自动暂停（两端同步实现）

**背景**：通知弹窗在批量操作时存在刷屏问题，用户缺乏控制手段。

**实现内容**：
- **智能聚合**：缓冲窗口 300ms，按消息主题合并（如"任务完成"×3 → "3项任务已完成"），回退按级别聚合。
- **自动暂停**：30秒内出现 3 次 Warning 或 Error 级别通知 → 自动暂停全部弹窗 5 分钟。
- **用户控制**：设置页提供"启用自动暂停"开关（默认开启）+ 暂停状态横幅 + "立即恢复"按钮。
- **关闭开关**：回退到原有 3 秒去重逻辑（无聚合/暂停）。

**涉及文件**：
- 新建：`web/src/composables/useNotificationAggregator.ts`（128行）
- 新建：`pilotstd/core/notification_aggregator.py`（160行）
- 修改：`web/src/composables/useNotification.ts`、`web/src/components/NotificationConfig.vue`
- 修改：`pilotstd/platform/notify.py`、`pilotstd/ui/pages/settings_page.py`

**门禁状态**：GATE-15 合规，所有修改文件 ≤500 行；Ruff PASS；未修改后端代码。

**平台覆盖**：Web 端 + WinUI 端（系统托盘气泡 + 铃铛，QMessageBox 未改造）。

## 三、测试状态

| 指标 | 值 |
|------|-----|
| 总用例 | 621 |
| 通过 | 615 (99.0%) |
| 跳过 | 6 (环境依赖) |
| 失败 | **0** |

**6 个 SKIP 明细**：E2E 外部 API 依赖 4 项、OCR provider 缺失 1 项、系统文件场景不支持 1 项。

## 三、代码规模治理

| 维度 | 治理前 | 治理后 |
|------|--------|--------|
| 文件 >500 行 | 13+ | **0** |
| 函数 >80 行 | 46+ | **0** |
| 包化目录 | 0 | 11 |
| 拆分函数 | 0 | 31 |

### 包化目录 (11)

| # | 目录 | 子文件数 | 最大单文件 |
|---|------|---------|-----------|
| 1 | `core/config/` | 6 | 139 |
| 2 | `core/db/` | 4 | 488 |
| 3 | `manager/facade/` | 8 | 435 |
| 4 | `query/engine/` | 9 | 424 |
| 5 | `scan/parser/` | 5 | 247 |
| 6 | `announcement/ocr/` | 5 | 381 |
| 7 | `ui/main_window/` | 3 | 344 |
| 8 | `ui/workers/` | 10 | 116 |
| 9 | `ui/controllers/query/` | 4 | 256 |
| 10 | `manager/organize/` | 5 | 185 |
| 11 | `cli/commands/` | 12 | 139 |

### 拆分函数 (31)

| 批次 | 数量 | 难度 | 完成日期 |
|------|------|------|---------|
| 前期低难度 | 10 | 低 | 6月24-27日 |
| 前期中难度 | 9 | 中 | 6月27-28日 |
| 本次对话 (第一批) | 5 | 低 | 6月29日 |
| 本次对话 (第二批) | 5 | 中 | 6月30日 |
| 本次对话 (第三批) | 3 | 大函数 | 6月30日 |
| **合计** | **32** | — | — |

## 四、安全加固

| 项目 | 状态 | 日期 |
|------|------|------|
| 服务端会话存储 | ✅ 已完成 | 6月30日 |
| JWT_SECRET 固定默认值 | ✅ 已完成 | 6月30日 |
| token 主动登出失效 | ✅ 已完成 | 6月30日 |
| 通知系统 P1 补全 (is_read + WS + 通知中心) | ✅ 已完成 | 6月30日 |

## 五、当前阻塞项 (P0)

无。全部阻塞项已修复。

## 六、待执行任务 (P1)

无。当前所有 P1 任务已完成。

## 七、最近决策记录

| 日期 | 决策 | 依据 |
|------|------|------|
| 2026-06-30 | GATE-15 清零 — 31 个函数拆分 + 11 个文件包化，文件 ≤500 行 & 函数 ≤80 行 全部达标 | 代码可维护性系统化提升 |
| 2026-06-30 | 服务端会话存储 — JWT_SECRET 固定默认值 + 内存会话存储 + 主动登出失效 | 安全审计第三批遗留项 |
| 2026-06-30 | 通知系统 P1 补全 — is_read 列 + WebSocket 推送 + 通知中心 API | 通知系统全链路接入 |
| 2026-06-30 | 混合继承 — 大文件拆分采用 mixin 模式 (MiniBucketMixin + CsresMixin + ReportMixin + MessageBuildersMixin) | 保持公开接口不变 |

## 八、关键命令速查

| 用途 | 命令 |
|------|------|
| 全量测试 | `python -m pytest tests/ -q` |
| 仅非 E2E | `python -m pytest tests/ -q -k "not e2e"` |
| Ruff 检查 | `ruff check pilotstd docker` |
| GATE-15 行数检查 | `find pilotstd docker -name '*.py' -exec wc -l {} + \| sort -rn \| head -20` |

## 九、关键文件索引

| 文档 | 路径 |
|------|------|
| 治理汇总 | `docs/architecture/governance-summary.md` |
| 技术债登记 | `docs/architecture/technical-debt-registry.md` |
| GATE-15 规则 | `docs/development/gate-15-enforcement.md` |
| 会话存储设计 | `docs/development/session-store-design.md` |
| 重构经验 | `docs/guides/refactoring-lessons.md` |
| CHANGELOG | `CHANGELOG.md` |
