# 专项：决策请求重试编排（A-4 收尾）

> 状态：**编排层已落地（2026-10-18）**；生产生成器由外部 harness 注入，本仓不调用 LLM。
> 关联：`enforcement/guardrails.py`（校验/埋点）、`enforcement/retry.py`（重试循环）。

## 为什么需要这一层

`validate_decision_request(output, retry_count)` 只校验**单次输出**，且重试计数由调用方维护。
原先仓内只有测试调用它，导致 `attempt_details` 只能退化成"单元素预览数组"——**三字段改造没有真正闭环**。

## 已实现

```python
from enforcement.retry import run_decision_with_retry

def generate(attempt: int, previous_attempts: list[dict]) -> str:
    # attempt 从 1 开始；previous_attempts 含此前各轮 {attempt, reason, errors}
    ...

final = run_decision_with_retry(generate, max_attempts=3)
```

| 行为 | 语义 |
|---|---|
| 生成器抛异常 | 该轮记 `reason="transient"`，继续下一轮 |
| 校验失败 | 该轮记 `reason=retry_reason`（默认 `validation`），继续 |
| 全部失败 | 先 `_log_retry_exhaustion(..., attempt_details=details)`，再抛 `RetryBudgetExhaustedError` |
| 成功 | 返回首个通过校验的输出；不写日志 |

测试：`tests/test_enforcement_retry.py`（4 例：二次成功/生成器异常/耗尽三字段/参数校验）。

## 生产接入契约（外部 harness）

本仓的"决策请求"由**外部 AI 生成器**产生（仓内无 LLM 调用，这是设计边界），因此接入点是一个
可注入的 `generate` 回调；harness 只需：

1. 实现 `generate(attempt, previous_attempts)`，把 `previous_attempts` 里的错误带回提示词；
2. 调用 `run_decision_with_retry`，捕获 `RetryBudgetExhaustedError` 作为生成阻断；
3. 日志采集侧按 `retry_reason` / `caller_stack` / `attempt_details`（JSON）聚合。

## 验收

- 耗尽日志的 `attempt_details` 为 **3 个元素**（每次尝试一条），`reason` 可区分 transient/validation；
- 第 2 次生成能拿到第 1 轮错误明细（用于"带错误重试"）。
