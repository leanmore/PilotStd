# 三位一体治理体系技术规范 v2.0

> **状态**：已评审 / 可执行
> **生效范围**：Phase 1 — Phase 3 全生命周期
> **版本日期**：2026-07-27
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
| `version` | string | 本规范文档的版本（如 "2.0"），用于人工对齐 |
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

> **版本**：v2.0
> **状态**：已评审 / 可执行
> **生效日期**：2026-07-27
> **维护责任**：Qwen / DeepSeek 共同维护，修订需双方共识
