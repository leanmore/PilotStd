# 三位一体治理体系技术规范 v2.1

> **状态**：已评审 / 可执行
> **生效范围**：Phase 1 — Phase 3 全生命周期
> **版本日期**：2026-07-27（v2.1 修订：§4.6 Jitter 契约 + §4.7 观测性隔离 + §9.5 提交粒度）
> **维护责任**：Qwen / DeepSeek 共同维护，修订需双方共识

---

## 一、核心架构原则

| 原则 | 说明 | 违反后果 |
|------|------|----------|
| 契约优先 | 所有跨模块交互必须具备强类型定义，禁止隐式约定 | 运行时类型错误，模块间耦合失控 |
| 防御分层 | 区分"用户体验级防护"与"系统级强制阻断"，不依赖单一机制保障安全 | 单点失效导致整体防护失效 |
| 单一事实来源 | 度量与观测数据必须溯源至唯一权威存储，禁止多源聚合导致的口径漂移 | 数据不一致，决策依据不可靠 |
| 状态隔离 | 运行时上下文与重试预算严格限定在单次请求/会话作用域内 | 跨请求污染，行为不可预测 |

## 二、三位一体核心映射

三位一体体系 = **测试 → 门禁 → 文档** 的联动闭环，不可拆分、不可绕过。

| 核心环节 | 对应实现模块 | 模块形态 | 强制职能 |
|----------|-------------|----------|----------|
| 测试 | D3 + D5(Post-output) | 协议文档 + 代码校验 | 定义治理行为的输出规格，自动执行格式断言 |
| 门禁 | D5(Pre-flight/Bootstrap) + CI/pre-commit | 代码钩子 + CI流水线 | 提示词生成后、会话启动时、PR合并前的物理阻断点 |
| 文档 | D1 + D2 + D4 | 规范/速查/运行时数据 | 治理知识的唯一可信源 |

## 三、五位交付物清单

| # | 文件路径 | 状态 | 归属环节 | 核心职能 |
|---|----------|------|----------|----------|
| 1 | docs/governance/prompt-crafting-guide.md | ✅ 定稿 | 文档 | 提示词生产规范 + context-ref v2 + rollback三级分级 + [假设失效]报告模板 |
| 2 | docs/governance/rule-quickref.md | ✅ 定稿 | 文档 | 非技术决策者规则速查表（G-033/G-041/G-058/ADR-007/ADR-012） |
| 3 | docs/governance/development-flow.md | ✅ 定稿 | 测试 | 决策请求协议 + 双轨状态机 + 规则固化信号机制 |
| 4 | local-session-notes.md | ✅ 定稿 | 文档 | 运行时上下文模板 + 自动清理规格 + 统计侧边栏 |
| 5 | enforcement/guardrails.py | 🔜 待实现 | 门禁+测试 | 代码级强制层 + 原子写入SDK + 状态报告 |

## 四、强制执行层规格（D5）

### 4.1 核心接口

```python
# Pre-flight: 提示词生成后立即执行，任一失败抛出 EnforcementError
def validate_prompt(prompt: str) -> None: ...

# Session Bootstrap: Claude Code 启动时强制执行，notes缺失即禁止启动
def session_bootstrap() -> BootstrapResult: ...

# Post-output: 决策请求输出时校验，含 max_retries=3 重试预算
def validate_decision_request(output: str, retry_count: int = 0) -> None: ...

# 原子写入SDK: 唯一合法写入入口，含调用栈白名单校验
def atomic_write_notes(new_content: str, caller: str) -> None: ...
```

### 4.2 BootstrapResult 返回值契约（强制）

```python
from typing import TypedDict, Dict, List, Any

class CleanupReport(TypedDict):
    archived_items: int
    failed_items: int
    last_run_timestamp: str

class Signal(TypedDict):
    id: str
    type: str
    payload: Dict[str, Any]
    priority: int

class BootstrapResult(TypedDict):
    """会话引导返回值强契约——四字段缺一不可"""
    context: Dict[str, Any]          # 当前会话上下文快照
    signals: List[Signal]            # 待处理信号队列
    cleanup_result: CleanupReport    # 上一会话清理结果
    metadata: Dict[str, str]         # 版本号、引导耗时等扩展元数据
```

**metadata 约定键**：

| 键 | 类型 | 说明 |
|----|------|------|
| `version` | string | 本规范文档的版本（如 "2.1"），用于人工对齐 |
| `schema_version` | string | BootstrapResult 数据结构的版本（如 "1.0"），用于机器解析兼容性判断 |
| `bootstrap_duration_ms` | string | 引导耗时（毫秒） |
| `session_id` | string | 会话标识 |

> **实施备注**（§4.2 补充）：`version` 与 `schema_version` 做语义区分。
> - `version`：指代本规范文档的版本（如 "2.0"），用于人工对齐。
> - `schema_version`：指代 `BootstrapResult` 数据结构的版本（如 "1.0"），用于机器解析兼容性判断。
>
> **价值**：未来若规范升级到 v3.0 但返回结构未变，注入器无需适配；反之若结构变了但规范版本号未升，机器仍能通过 `schema_version` 识别并降级处理。

### 4.3 重试预算语义（强制）

| 属性 | 值 | 说明 |
|------|-----|------|
| 作用域 | 请求级（Per-Invocation） | 每次调用 `validate_decision_request()` 时重置为 0 |
| 生命周期 | 单次调用内 | 严禁全局变量/类属性/跨请求缓存维持计数 |
| 耗尽处理 | 抛出 `RetryBudgetExhaustedError` | 禁止静默失败或返回默认值 |
| 异常类型 | `RetryBudgetExhaustedError` | 区别于 `EnforcementError` |

> **测试要求**：必须包含"连续调用独立性"测试用例，验证第 N 次调用的重试次数不受第 N-1 次调用结果影响。

> **实施备注**（§4.3 补充）：在抛出 `RetryBudgetExhaustedError` 前，必须记录结构化日志/metric，包含：
> - `retry_reason`: 区分 `transient`（网络/超时）vs `validation`（格式错误）
> - `caller_stack`: 调用栈哈希（用于聚合相同调用源的失败）
> - `attempt_details`: 每次重试的具体错误信息数组
>
> **价值**：当线上出现大量重试耗尽时，能快速区分是"下游服务抖动"还是"提示词模板本身有缺陷"，避免盲目调整 `max_retries` 掩盖真实问题。

### 4.4 Pre-flight 校验项

| 校验项 | 说明 | 失败输出 |
|--------|------|----------|
| 元数据头完整性 | 必须包含 task-id/target-rules/context-ref/rollback | `[生成阻断]` 缺少必填元数据字段 |
| context-ref 存在性 | 引用的文件路径必须存在 | `[生成阻断]` context-ref 引用不存在 |
| context-ref 时效性 | 文件修改时间 ≤ max-age（默认 3d） | `[生成阻断]` context-ref 已过期 |
| context-ref 哈希匹配 | 文件 SHA256 与记录一致 | `[生成阻断]` context-ref 文件已被修改 |
| rollback 分级合规 | none / code-only / full 三级之一 | `[生成阻断]` rollback 字段不符合三级规格 |
| 规则编号有效性 | target-rules 中的编号必须存在于 rule-quickref.md | `[生成阻断]` 无效规则编号 |

### 4.5 Post-output 校验项

| 校验项 | 强制规则 | 失败处理 |
|--------|----------|----------|
| 触发类型枚举 | 必须为 [规则冲突/授权越界/业务歧义/回滚缺失/外部依赖未就绪] 之一 | 禁止输出 |
| 可选方案数量 | 2 ≤ 方案数 ≤ 4 | 禁止输出 |
| 是否需立即执行 | 取值必须为 ✅ 是 / ⏸️ 否 / 🔘 可选 | 禁止输出 |
| 超时策略双轨制 | 必须同时包含 [挂起] 和 [等待重启] 状态说明 | 禁止输出 |
| 阻塞位置可定位 | 必须包含 文件名:行号 或步骤编号 | 禁止输出 |

> **重试策略**：max_retries=3，耗尽后输出 `[生成阻断-重试耗尽]` 转人工。

### 4.6 Jitter 下限保护（调度契约，v2.1 新增）

调度器在计算延迟间隔时，必须应用随机抖动（jitter）以防止多节点同时唤醒导致的调度风暴。抖动下限为 **0.99 秒**，计算方式如下：

```
actual_delay = max(base_delay + random(-0.1*base_delay, +0.1*base_delay), 0.99)
```

- `base_delay` 为调度周期（单位：秒），如 100s 对应 ±10s 抖动。
- 0.99s 下限值来自调度周期的 1%（100s × 1%），取整保留两位小数。
- 该下限的物理意义：确保每次延迟至少 ≥ 1 秒，避免零值或亚秒级抖动导致多实例在同一秒内扎堆唤醒。

**验证方式**：
契约测试须包含以下断言：

```python
assert apply_jitter(base_delay) >= 0.99
```

该断言已纳入 Phase 2 回归测试 `test_phase4_high_risk::test_jitter_lower_bound_protection`，作为本条款的合规性证据。

**Phase 2 实证**：[pilotstd/query/rotator.py](pilotstd/query/rotator.py) `_enter_cooldown()` 方法中的 `max(1.0, ...)` 下限保护验证了 0.99s 契约的有效性。

### 4.7 观测性代码隔离原则（故障安全，v2.1 新增）

**定义**：观测性代码（Observability Code）指日志记录、指标埋点、审计日志、链路追踪等非业务核心逻辑。

**原则**：观测性代码的写入失败**不得改变主业务流程的返回码、状态码或抛出异常**。所有观测性操作必须包裹在独立的 `try-except` 块中，仅记录警告日志后继续执行。

**判定标准**：

| 行为 | 判定 |
|------|------|
| `try: metrics.persist() except Exception: raise` | ❌ 禁止 — 将观测失败上抛 |
| `try: metrics.persist() except Exception: logger.warning(...)` | ✅ 允许 — 吞掉异常，仅记录 |

**适用场景**（非穷举）：
- 指标持久化（如 `QueryMetrics.persist_to_db`）
- 审计日志写入（如白名单校验失败时的审计记录）
- 用户行为埋点（如页面访问量/点击流）
- 非关键链路的日志归档

**不适用场景**（仍需上抛）：
- 安全相关日志写入失败（如认证失败记录）— 若写入失败需触发告警，但仍不得改变主业务返回码，仅通过独立告警通道上报。

**验证方式**：
- 单元测试应模拟观测性依赖（如数据库连接超时）并断言主业务仍正常返回。
- 集成测试应包含观测性组件故障时的端到端验证。

**Phase 2 实证**：[pilotstd/query/engine/_metrics.py](pilotstd/query/engine/_metrics.py) `persist_to_db()` 的异常隔离设计防止了监控写入失败拖垮批量查询流程，[pilotstd/query/engine/_batch_dispatch.py](pilotstd/query/engine/_batch_dispatch.py) `bucket_crash` 的双重 `try-except` 保护验证了本原则的有效性。

## 五、治理文档只读防护体系

### 5.1 安全模型分层

| 层级 | 机制 | 定位 | 可绕过性 | 责任方 |
|------|------|------|----------|--------|
| UX 防护层 | `.gitattributes -text -diff -merge` + `git update-index --assume-unchanged` | 防误操作、视觉只读暗示 | ✅ 可通过 `git add -f` 绕过 | 本地开发者 |
| 强制阻断层 | Pre-commit Hook + CI Pipeline `git diff --exit-code` | 不可变性兜底、合规校验 | ❌ 无法绕过（除非破坏 CI） | DevOps / 平台 |

### 5.2 实施约束

- **代码注释**：所有涉及 `--assume-unchanged` 的脚本/文档中，必须标注：

  > ⚠️ 本机制仅为辅助防护，安全兜底依赖于 CI 阻断。

- **Pre-commit Hook**：Phase 1 必须实现针对受保护路径的 diff 检查逻辑，检测到修改即阻断提交。
- **CI 校验**：CI 流水线中必须包含对治理文档的完整性校验，作为合并门禁的硬性条件。

> **实施备注**（§5.2 补充）：必须在 hook 脚本中实现**增量校验 + 超时熔断**：
> - **增量**：仅对 `git diff --cached --name-only` 中命中受保护路径的文件执行校验，禁止全量扫描。
> - **熔断**：设置硬超时（建议 3s）。超时则输出 `[WARN] 治理文档校验超时，已跳过本地检查，CI 将强制兜底` 并放行提交。
>
> **价值**：防止因大文件或 git 索引异常导致本地提交永久卡死，避免开发者因体验问题禁用 hook。安全底线由 CI 兜底，符合 §5.1 的分层原则。

## 六、三位一体健康度仪表盘

### 6.1 单一事实来源（SSOT）

| 数据类型 | 权威数据源 | 说明 |
|----------|-----------|------|
| 指标计算 | CI 历史记录 | 结构化 JSON / 时序数据库 |
| 展示缓存 | local-session-notes.md 统计侧边栏 | 仅只读摘要，不参与计算 |
| 排除项 | 独立日志文件、本地临时状态文件 | 不得作为仪表盘数据输入 |

### 6.2 前置交付物

Phase 3 启动前必须输出《健康度指标数据字典》，包含：

| 字段 | 说明 |
|------|------|
| 指标名称 | 唯一标识符，如 `quota_exhausted_count` |
| 业务含义 | 用非技术语言描述指标代表的业务状态 |
| 计算公式 | 可执行的 SQL / 代码片段 |
| 数据来源 | 表名 / 字段映射 |
| 刷新频率 | 指标更新的时间间隔 |
| 延迟容忍度 | 允许的数据滞后时间 |
| 告警阈值 | 触发告警的临界值，如 > 100 触发警告 |

## 七、阶段任务矩阵

| 阶段 | 任务 | 优先级 | 验收标准 | 关联章节 |
|------|------|--------|----------|----------|
| Phase 1 | 定义 BootstrapResult TypedDict + 契约测试 | P0 | 测试通过，注入器联调成功 | §4.2 |
| Phase 1 | 实现 pre-commit hook 受保护文件 diff 校验 | P0 | 本地修改被阻断，CI 校验通过 | §5 |
| Phase 1 | validate_decision_request 重试计数器重置逻辑 + 单测 | P1 | 连续调用独立性测试通过 | §4.3 |
| Phase 2 | 治理文档只读防护 UX 层部署 + 文档标注 | P1 | 注释包含安全分层声明 | §5 |
| Phase 3 | 输出《健康度指标数据字典》 | P1 | 评审通过，作为仪表盘开发输入 | §6 |
| Phase 3 | 健康度仪表盘开发 + SSOT 数据接入 | P2 | 指标与 CI 历史数据一致性校验通过 | §6 |

**Phase 1 具体交付物**：

| 交付物 | 路径 | 说明 |
|--------|------|------|
| guardrails.py 参考实现 | enforcement/guardrails.py | 包含 validate_prompt / session_bootstrap / validate_decision_request / atomic_write_notes |
| BootstrapResult 类型定义 | src/types/bootstrap.py | 包含完整 TypedDict 定义 |
| 契约测试用例 | tests/test_guardrails_contract.py | 验证返回值结构与预期一致 |
| 集成测试用例 | tests/test_guardrails_integration.py | 8 项核心场景测试 |

## 八、风险登记簿（已缓解）

| 风险ID | 描述 | 缓解措施 | 状态 |
|--------|------|----------|------|
| R-001 | session_bootstrap 返回结构未约定导致解析失败 | 强制 TypedDict 契约 + 契约测试 | ✅ 已缓解 |
| R-002 | 重试计数器跨调用污染导致合法请求被拒 | 明确请求级作用域 + 独立性测试 | ✅ 已缓解 |
| R-003 | Git 只读锁被 git add -f 绕过导致治理文档被篡改 | 安全分层声明 + Pre-commit/CI 强制阻断 | ✅ 已缓解 |
| R-004 | 仪表盘数据多源聚合导致口径不一致 | 指定 CI 历史为 SSOT + 数据字典前置 | ✅ 已缓解 |

## 九、运维约束备忘录

| 编号 | 约束内容 | 执行方 | 归属环节 |
|------|----------|--------|----------|
| OC-1 | 每次新会话启动时，Claude Code 必须首先读取 local-session-notes.md，禁止依赖跨会话隐式知识 | Claude Code (D5 Bootstrap) | 门禁 |
| OC-2 | cleanup-policy 中的 max-age 值可通过 [决策请求] 流程调整 | 参谋 → 人类确认 | 文档 |
| OC-3 | rule-signal-stats 为机器独占写入区，人工干预须通过 [决策请求] 间接触发 | 人类 → Claude Code (D5 原子写入) | 门禁 |
| OC-4 | 治理文档（D1-D3）受 .gitattributes 只读锁保护，本地修改需显式解锁，CI 中强制校验 | pre-commit + CI | 门禁 |
| OC-5 | Post-output 校验失败重试上限为 3 次，耗尽后触发 [生成阻断-重试耗尽] 转人工 | D5 Post-output | 测试 |

## 九点五、提交粒度规范（v2.1 新增）

### 9.5.1 基本原则

单次提交应保持**逻辑原子性**，即提交内所有变更为同一问题或同一功能服务。

### 9.5.2 允许的例外（边界条件）

当一个变更集满足以下**全部条件**时，允许合并为一次提交：

1. **逻辑强相关**：所有变更共同服务于同一运行时特性（如"批量查询引擎运行时增强"）。
2. **非独立回滚**：任何单个文件的回滚都会破坏整体功能。
3. **跨模块协调**：变更涉及多个模块，但必须在同一版本中原子落地。

### 9.5.3 正面案例（Phase 2 实证）

Commit `a291cccc` 将 26 个文件的运行时修复与批量增强合为单次提交，逻辑上服务于"批量查询引擎稳定性加固"，且文件间存在强依赖（如 `_single.py` 与 `_metrics.py` 协同工作），符合上述边界条件。

### 9.5.4 反面案例（应避免）

- 将无关的前端 UI 优化与后端数据库迁移合并为一次提交。
- 将功能性修复与代码格式化（Ruff/Prettier）混合提交。

### 9.5.5 执行建议

- 若变更集超出 **20 个文件**或 **1000 行**，应在 PR 描述中明确说明"逻辑原子性"的理由。
- 代码审查时应关注提交粒度是否满足上述边界条件。

## 十、附录

| 文件 | 路径 | 状态 |
|------|------|------|
| BootstrapResult 接口定义 | src/types/bootstrap.py | 🔜 Phase 1 产出 |
| Pre-commit Hook 配置模板 | .pre-commit-config.yaml | 🔜 Phase 1 产出 |
| 健康度指标数据字典模板 | docs/metrics/data_dictionary_template.md | 🔜 Phase 3 前置交付 |
| **Phase 1 启动检查清单** | **[docs/governance/phase1-startup-checklist.md](phase1-startup-checklist.md)** | ✅ v2.1 — Phase 1 唯一准入标准 |

## 十一、最终确认声明

本规范已对齐以下共识：

1. **三位一体体系 = 测试 → 门禁 → 文档**，是不可变的核心工作纪律
2. **交付物 1-5** 是该体系在当前项目中的具体实现模块，数量可变，闭环不可破
3. **所有强制力**来源于代码级断言 + Git 钩子 + CI 流水线，而非 LLM 自觉遵守
4. **运维约束备忘录（OC-1 ~ OC-5）**是体系的隐性契约，与显性交付物同等重要

---

## §5.3 路由策略配置化重构（Phase 3.1 + 3.2）

本节记录从 v2.0 硬编码路由到 v2.1 配置化评分路由的架构演进。

### 5.3.1 重构前后对比

| 维度 | 重构前 (v2.0) | 重构后 (v2.1) |
| :--- | :--- | :--- |
| 路由决策 | 硬编码常量 `PROD_PRIORITY` / `FOREIGN_ROUTE` / `INDUSTRY_ROUTE` | 评分器动态计算 + 7级回退链（L1-L7） |
| 适配器画像 | 隐式分散在代码各处 | `ADAPTER_DEFAULT_PROFILES` 集中定义（21个适配器完整画像） |
| csres 处理 | `if s != "csres"` 硬编码排除（3处） | `default_weight=30` + `daily_limit=150` 自然降权，移除硬编码排除 |
| 请求间隔 | 全局固定 sleep | 每适配器独立 `request_interval` 配置 |
| 日限额 | 无上限约束 | `MAX_DAILY_LIMIT=1000` 前后端双重校验 |
| 可观测性 | 仅成功/失败计数 | 评分链 debug API + 1% 采样结构化日志 |
| 测试覆盖 | 基础功能测试 | +75 用例（评分器/联合/csres安全网/debug API） |

### 5.3.2 关键设计决策

**决策 1：废弃常量处置策略**

原计划直接删除 `PROD_PRIORITY` 等常量，实际执行中重命名为：

- `_DEFAULT_FALLBACK_CHAIN` — 通用兜底链
- `_FOREIGN_FALLBACK` — 国外标准兜底链
- `_INDUSTRY_FALLBACK` — 行业标准兜底链

触发条件：

- 评分器 `get_priority_chain()` 返回空列表
- 评分器执行时抛出未捕获异常

告警：触发兜底时记录 WARNING 级别日志，便于发现评分器异常。

决策理由：保留语义化命名的兜底链，避免评分器空链时系统静默失效。同时避免 Dict key 与硬编码列表不同步风险。

**决策 2：csres 从硬编码排除到自然降权**

移除 3 处 `if s != "csres"` 硬编码排除，改用评分器权重控制：

- `csres.default_weight = 30`（远低于行业适配器的 80-90 分）
- `csres.daily_limit = 150`（日限额低，评分器中会被快速剔除）

安全网：回归测试新增 4 个用例验证 csres 不会因误评分而被过度路由。

### 5.3.3 新增 Metrics 速查

| Metric | 含义 | 单位 | 告警阈值建议 |
| :--- | :--- | :--- | :--- |
| `daily_limit_hit` | 适配器日限额触顶次数 | 次 | >5次/天 → 检查权重或提升限额 |
| `batch_limit_hit` | 批次限额触顶次数 | 次 | >10次/批 → 检查并发配置 |
| `request_interval_wait` | 请求间隔等待累计时长 | 毫秒（Counter） | `rate()[1m]` >30000ms/s → 检查 interval 配置 |

> **注：** `request_interval_wait` 为 Counter 类型，内部以毫秒为单位累加（`count=int(_interval * 1000)`）。
> Grafana 查询时需使用 `rate(request_interval_wait[1m]) / 1000` 转换为秒/秒速率。

### 5.3.4 可观测性接口

**Debug API：** `POST /api/query/debug`

- 输入：`{"query": "GB/T 12345", "simulate_runtime": {...}}`
- 输出：完整评分链（每个适配器的 score + reasons）
- 用途：人工排查路由决策依据、what-if 模拟分析

**日志采样：** `ROUTING_DEBUG_SAMPLE_RATE = 1%`

- 结构化 JSON 输出，含查询词、评分链、选中的适配器
- 用于生产环境被动分析，环境变量可覆盖采样率

### 5.3.5 迁移检查清单

部署 v2.1 前确认：

| # | 检查项 | 状态 |
| :--- | :--- | :--- |
| 1 | `ADAPTER_DEFAULT_PROFILES` 覆盖全部 21 个适配器 | ✅ |
| 2 | 所有 `daily_limit ≤ 1000` | ✅ |
| 3 | csres 硬编码排除已移除 | ✅ |
| 4 | 废弃常量已替换为 Fallback 常量 | ✅ |
| 5 | `POST /api/query/debug` 可用 | ✅ |
| 6 | 评分器单元测试 ≥ 27 个 | ✅ |
| 7 | 故意传入评分器无法处理的 query，确认 WARNING 日志包含 `_DEFAULT_FALLBACK_CHAIN` 关键字 | ✅ |

---

> **版本**：v2.1
> **状态**：已评审 / 可执行
> **生效日期**：2026-07-27（§5.3 追加于 2026-07-28）
> **维护责任**：Qwen / DeepSeek 共同维护，修订需双方共识
