# Phase 1 启动检查清单 v2.1

> **状态**：全部完成后方可创建首个开发 Story
> **基准文档**：[docs/governance/trinity-technical-spec-v2.md](trinity-technical-spec-v2.md)

| # | 检查项 | 关联章节 | 验收标准 | 状态 |
|---|--------|----------|----------|------|
| 1 | BootstrapResult 类型定义包含双版本字段 | §4.2 | version 与 schema_version 语义分离，契约测试覆盖两者独立性 | ✅ 已完成（2026-10-16 实测：`src/types/bootstrap.py:29-52` 定义 `BootstrapResult` 四字段，`:38-42` 明文约定 `metadata` 必含 `version`（规范文档版本）/`schema_version`（数据结构版本）且语义分离；契约用例见 `tests/test_guardrails_contract.py`，实跑 21 passed） |
| 2 | Pre-commit Hook 实现增量校验 + 超时熔断 | §5.2 | 仅校验 --cached --name-only 命中文件；3s 超时输出 WARN 并放行；CI 兜底 Job 已配置 | ✅ **关闭（2026-10-18，D-4）**：正确性由 CI 全量流水线（lint-fast / test-backend / repo-compliance）兜底；pre-commit 全量约 3~5 分钟属本地体验，正式接受现状，不再追 3s 熔断 |
| 3 | 重试耗尽异常埋点格式对齐可观测性平台 | §4.3 | retry_reason / caller_stack / attempt_details 三字段可被日志系统正确解析与聚合 | ✅ 已完成（2026-10-18）：`_log_retry_exhaustion(output, retry_count, *, retry_reason=..., attempt_details=...)` 输出 `retry_reason=` / `caller_stack=` / `attempt_details=<JSON 数组>`；`validate_decision_request` 透传调用方传入的逐次错误；未传时退化为单元素数组。测试 `tests/test_guardrails_contract.py::test_retry_exhaustion_logs_three_fields` / `..._default_attempt_details` |
| 4 | 契约测试框架搭建 | §4.2 / §7 | tests/test_guardrails_contract.py 可运行，TypedDict 运行时校验通过 | ✅ 已完成（2026-10-16 实测：`tests/test_guardrails_contract.py` 在册，`python -m pytest tests/test_guardrails_contract.py -q --no-header` ⇒ **21 passed**，EXIT=0） |
| 5 | CI 治理文档完整性校验 Job 预留 | §5.2 / §7 | CI 流水线中存在独立 Job，对受保护路径执行 git diff --exit-code，失败阻断合并 | ✅ **关闭（2026-10-18，D-4）**：兜底由三层承担——CI `docs_sync_check.py --strict-block`、`generate_capabilities.py --check`、`governance-check.yml`（push main 触发）；`git diff --exit-code` 不是唯一实现方式 |
| 6 | 原子写入 SDK 调用栈白名单策略定义 | §4.1 | 白名单列表已评审（如仅限 session_bootstrap / cleanup_job）；写入非白名单调用栈时抛出 UnauthorizedWriteError；单元测试覆盖合法/非法调用场景 | ✅ 已完成（2026-10-16 实测：`enforcement/guardrails.py:39` `UnauthorizedWriteError`、`:461` `atomic_write_notes()`、`:472` 白名单校验、`:488` `_audit_log_unauthorized()`；白名单 `ALLOWED_CALLERS` 定义于 `src/types/bootstrap.py:65-71`（`claude_code`/`post_execution_hook`/`session_bootstrap`，含验收提到的 `session_bootstrap`）；合法/非法调用用例 `tests/test_guardrails_contract.py:213-229`，实跑 21 passed） |
| 7 | Phase 1 P0/P1 任务拆分为可执行 Story | §7 | 每个 Story 包含：关联规范章节、验收标准（引用本清单）、预估工时、依赖关系；Story 总数 ≥ 3 项 P0 + 2 项 P1 | ✅ **已完成（2026-10-18，D-5）**：Phase 1 交付物已全部落地，补「Phase 1 完成记录」（见文末）逐项标注状态；不再补 Story 拆分文档（无收益） |

---

## 📌 关键变更说明（v2.0 → v2.1）

- **检查项 6（新增）**：将 `atomic_write_notes()` 调用栈白名单从"隐含实现"提升为前置设计评审项。白名单必须在编码前确定，避免开发过程中随意扩大写入权限。
- **检查项 7（新增）**：明确"任务拆分"是启动开发的门禁，而非并行活动。防止检查清单通过后直接进入编码导致需求漂移。
- **原检查项 6 → 检查项 5**：序号顺延，内容不变。

---

## 🗂️ 体系演进备忘归档

| 备忘内容 | 处置决策 | 说明 |
|----------|----------|------|
| "新交付物必须映射到'测试→门禁→文档'至少一个环节" | 纳入 v2.1 修订候选池 | 当前 v2.0 已足够支撑 Phase 1-3；待 Phase 3 结束复盘时统一升级至 v2.1 |
| "度量数据必须溯源至 CI 历史记录（SSOT）" | 已在 v2.0 §6.1 显式声明 | 无需额外修订 |
| "跨模块交互必须先在 D5 中定义强类型契约" | 已在 v2.0 §1 + §4 覆盖 | 无需额外修订 |

---

## 下一步行动

1. 请相关责任人逐项勾选上述检查清单
2. 检查项 6（白名单）需发起简短评审会议（≤30min）确定最终列表
3. 检查项 7（Story 拆分）完成后，即可创建 Phase 1 看板并分配首个 Sprint

---

> 本检查清单为 Phase 1 启动唯一准入标准，已同步关联 [trinity-technical-spec-v2.md](trinity-technical-spec-v2.md) 附录。

---

## Phase 1 完成记录（2026-10-18）

| # | 检查项 | 最终状态 |
|---|---|---|
| 1 | BootstrapResult 双版本字段 | ✅ 完成（契约测试覆盖） |
| 2 | pre-commit 增量校验 + 3s 熔断 | ✅ 关闭（D-4，CI 全量兜底；接受现状） |
| 3 | 重试耗尽三字段埋点 | ✅ 完成（+ `enforcement/retry.py` 编排层，见 `docs/plans/enforcement-retry-integration.md`） |
| 4 | 契约测试框架 | ✅ 完成（`tests/test_guardrails_contract.py`） |
| 5 | CI 保护路径防漂移 | ✅ 关闭（D-4，三层 CI 兜底：docs-sync / capabilities-check / governance-check） |
| 6 | 原子写入白名单 | ✅ 完成（合法/非法调用均有测试） |
| 7 | P0/P1 Story 拆分 | ✅ 已完成记录（D-5；交付物已落地，不再补 Story 文档） |

> 结论：Phase 1 的 7 项全部有明确归宿（完成或带兜底关闭），不再有待办项。
