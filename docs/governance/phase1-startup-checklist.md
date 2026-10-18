# Phase 1 启动检查清单 v2.1

> **状态**：全部完成后方可创建首个开发 Story
> **基准文档**：[docs/governance/trinity-technical-spec-v2.md](trinity-technical-spec-v2.md)

| # | 检查项 | 关联章节 | 验收标准 | 状态 |
|---|--------|----------|----------|------|
| 1 | BootstrapResult 类型定义包含双版本字段 | §4.2 | version 与 schema_version 语义分离，契约测试覆盖两者独立性 | ✅ 已完成（2026-10-16 实测：`src/types/bootstrap.py:29-52` 定义 `BootstrapResult` 四字段，`:38-42` 明文约定 `metadata` 必含 `version`（规范文档版本）/`schema_version`（数据结构版本）且语义分离；契约用例见 `tests/test_guardrails_contract.py`，实跑 21 passed） |
| 2 | Pre-commit Hook 实现增量校验 + 超时熔断 | §5.2 | 仅校验 --cached --name-only 命中文件；3s 超时输出 WARN 并放行；CI 兜底 Job 已配置 | ⬜ 待办（实测依据 2026-10-16：`scripts/check_all.sh:390`/`:435` 已有 `git diff --cached --name-only` 增量校验；但 `git grep -n "timeout" -- scripts/check_all.sh` **零命中** ⇒ 无 3s 超时熔断；`.husky/pre-commit` 只转发 `check_all.sh --fast --guards --local`，无内联熔断逻辑） |
| 3 | 重试耗尽异常埋点格式对齐可观测性平台 | §4.3 | retry_reason / caller_stack / attempt_details 三字段可被日志系统正确解析与聚合 | ✅ 已完成（2026-10-18）：`_log_retry_exhaustion(output, retry_count, *, retry_reason=..., attempt_details=...)` 输出 `retry_reason=` / `caller_stack=` / `attempt_details=<JSON 数组>`；`validate_decision_request` 透传调用方传入的逐次错误；未传时退化为单元素数组。测试 `tests/test_guardrails_contract.py::test_retry_exhaustion_logs_three_fields` / `..._default_attempt_details` |
| 4 | 契约测试框架搭建 | §4.2 / §7 | tests/test_guardrails_contract.py 可运行，TypedDict 运行时校验通过 | ✅ 已完成（2026-10-16 实测：`tests/test_guardrails_contract.py` 在册，`python -m pytest tests/test_guardrails_contract.py -q --no-header` ⇒ **21 passed**，EXIT=0） |
| 5 | CI 治理文档完整性校验 Job 预留 | §5.2 / §7 | CI 流水线中存在独立 Job，对受保护路径执行 git diff --exit-code，失败阻断合并 | ⬜ 待办（实测依据 2026-10-16：`git grep -n "diff --exit-code" -- .github/workflows scripts .husky` **零命中**；受保护路径常量 `PROTECTED_GOVERNANCE_PATHS`（`src/types/bootstrap.py:56-62`）全库仅 3 处引用——定义、契约测试导入、`len >= 5` 断言，**无任何 CI 作业消费该清单**） |
| 6 | 原子写入 SDK 调用栈白名单策略定义 | §4.1 | 白名单列表已评审（如仅限 session_bootstrap / cleanup_job）；写入非白名单调用栈时抛出 UnauthorizedWriteError；单元测试覆盖合法/非法调用场景 | ✅ 已完成（2026-10-16 实测：`enforcement/guardrails.py:39` `UnauthorizedWriteError`、`:461` `atomic_write_notes()`、`:472` 白名单校验、`:488` `_audit_log_unauthorized()`；白名单 `ALLOWED_CALLERS` 定义于 `src/types/bootstrap.py:65-71`（`claude_code`/`post_execution_hook`/`session_bootstrap`，含验收提到的 `session_bootstrap`）；合法/非法调用用例 `tests/test_guardrails_contract.py:213-229`，实跑 21 passed） |
| 7 | Phase 1 P0/P1 任务拆分为可执行 Story | §7 | 每个 Story 包含：关联规范章节、验收标准（引用本清单）、预估工时、依赖关系；Story 总数 ≥ 3 项 P0 + 2 项 P1 | ⬜ 待办（实测依据 2026-10-16：`git grep -ln "P0 Story\|Story 总数" -- docs` **仅命中本清单自身**；全库无 Phase 1 Story 拆分产物/看板文件） |

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
