# PilotStd v4.2 项目状态

> 最后更新：2026-06-22
> 维护规则：每次任务完成后，由 Claude Code 更新本文件

## 一、当前版本信息

| 项目 | 值 |
|------|-----|
| 版本号 | 0.13.2 |
| 分支 | main |
| 目标 | v4.2 压测验收通过并修复阻塞项 |

## 二、已完成工作

### 代码修复（9项）
- [x] query_exact 修复
- [x] hbba 回退修复
- [x] 冷却配额修复
- [x] fallback/pending 过滤修复
- [x] csres 间隔修复
- [x] Docker 超时修复
- [x] HTML 标签修复
- [x] Web 公告缓存查询 API
- [x] API Key 管理（待简化）
- [x] WinUI 缓存集成

### 压测方案改造（v3.0，8/8项）
- [x] 版本一致性校验（第零步）
- [x] API Key 自动准备（已废弃，待简化）
- [x] CLI 1.7.1 cache_lookup
- [x] 执行顺序调整（Docker → WinUI）
- [x] WinUI 分两轮（甲轮回归 + 乙轮缓存）
- [x] Docker 新增 5 项测试（AUTH-05/06/07 + BIZ-12/13）
- [x] 汇总新增 3 项指标
- [x] atexit 吊销 Key（已废弃，待简化）

### 进度心跳恢复（v4.2）
- [x] query/engine.py：60s daemon 心跳线程，`[PROGRESS]` 结构化日志
- [x] tests/stress_web.py：同格式独立心跳，覆盖 AUTH+BIZ 5 项
- [x] tests/stress_driver.py：`[PROGRESS]` 汇总解析 + 180s 看门狗卡死检测

### 治理框架
- [x] 能力登记簿（docs/governance/capabilities_registry.md，41条，0 migrating）
- [x] 重构检查清单（docs/governance/refactoring_checklist.md）
- [x] 归档迁移协议（docs/governance/archive_migration_protocol.md）
- [x] extract_capabilities.sh（能力提取工具）
- [x] test_observability.py（AST 观测自检，34/34 PASS）
- [x] check_no_migrating.sh（迁移阻断守卫）
- [x] CONTRIBUTING.md 治理规范章节
- [x] PULL_REQUEST_TEMPLATE.md 能力迁移状态表
- [x] STATUS.md（本文件）

### v4.2 阻塞项修复（1/2 完成）
- [x] **njbz365 配额冷却修复** — 根因：`SiteRotator.record_success()` 累加 `request_count` 但未在达到 `max_requests` 时触发 `_enter_cooldown()`。冷却仅在 `get_available()` 中触发，但 `query_batch_parsed` 的 mini-bucket 循环不调用 `get_available()`，导致超额。修复：`record_success()` 新增冷却触发 + `_bucket_worker` 逐条冷却检查。验证：单元测试 4/4 PASS，冷却在第 5 次请求后正确触发。
- [ ] API 令牌简化（待实施）

## 三、当前阻塞项（P0）

### 3.1 ~~njbz365 配额冷却失效~~ ✅ 已修复
| 指标 | 修复前 | 修复后（预期） |
|------|--------|---------------|
| 实际消耗 | 294 次（超限 47%） | ≤ 200 + mini-bucket 余量（≤ 249） |
| 冷却触发 | 不触发 | 达到 max_requests 立即进入冷却 |

**根因**：`SiteRotator.record_success()` 累加 `request_count` 但不检查上限，冷却入口 `_enter_cooldown()` 仅在 `get_available()` 中调用，而 `query_batch_parsed` 的批量查询路径不经过 `get_available()`。

**修复**：`rotator.py:record_success()` 新增 `request_count >= max_requests` 检查 → 立即进入冷却；`engine.py:_bucket_worker` 逐条循环新增冷却检查。

### 3.2 API 令牌方案待简化
- 当前：依赖动态创建 API Key（已发现 500 错误：`'NoneType' object has no attribute 'cookies'`）
- 目标：改为静态令牌（参考 MoviePilot），移除动态创建/吊销逻辑
- 状态：方案已确认，待实施

## 四、待执行任务（P1）

| 任务 | 状态 | 依赖 |
|------|------|------|
| ~~njbz365 配额修复~~ | ✅ 已完成 | — |
| API 令牌简化 | 待执行 | 无 |
| 全量压测重跑（含 WinUI 乙轮） | 待执行 | API 令牌简化完成后 |
| v4.2 验收结论 | 待执行 | 全量压测完成后 |

## 五、最近决策记录

| 日期 | 决策 | 依据 |
|------|------|------|
| 2026-06-22 | njbz365 冷却修复：在 record_success 中触发 _enter_cooldown | 根因：批量查询路径不经过 get_available()，冷却入口缺失 |
| 2026-06-22 | 建立能力遗产治理框架（登记簿+迁移协议+工具脚本） | 对抗 AI 失忆和代码重构中能力静默丢失 |
| 2026-06-22 | API 令牌改用静态方案（参考 MoviePilot） | 动态创建 API Key 存在 500 错误，简化认证流程 |
| 2026-06-22 | 治理框架保留三层：登记簿 + 迁移协议 + extract_capabilities.sh | 团队精小，CI 门禁非当前瓶颈，轻量方案即可 |

## 六、关键命令速查

| 用途 | 命令 |
|------|------|
| 提取能力清单 | `bash scripts/extract_capabilities.sh <文件路径>` |
| 观测能力自检 | `python tests/test_observability.py --check-all` |
| 全量压测 | `python tests/stress_driver.py --source D:\标准 --output E:\标准 --config tests/test_config.json --yes` |
