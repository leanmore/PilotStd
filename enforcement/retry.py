"""决策请求重试编排（A-4 专项，2026-10-18）。

`guardrails.validate_decision_request` 只校验**单次输出**；本模块把校验接进
真实重试循环，并保证耗尽时 `attempt_details` 是**逐轮累积**的真实数组，
而不是单元素退化数组。

调用方契约（生产 harness 注入生成器）：
    def generate(attempt: int, previous_attempts: list[dict]) -> str:
        # attempt 从 1 开始；previous_attempts 是此前各轮的
        # {"attempt", "reason", "errors"}，可用于让模型带上错误重试。
        ...

    from enforcement.retry import run_decision_with_retry
    final = run_decision_with_retry(generate, max_attempts=3)

- 生成器抛异常 → 该轮记为 `reason="transient"`，继续下一轮；
- 校验失败 → 该轮记为 `reason=<retry_reason>`（默认 validation），继续；
- 全部失败 → `_log_retry_exhaustion(..., attempt_details=details)` 后抛
  `RetryBudgetExhaustedError`（三字段可被日志系统解析）。
"""

from __future__ import annotations

from typing import Any, Callable

from .guardrails import (
    _MAX_RETRIES,
    EnforcementError,
    RetryBudgetExhaustedError,
    _log_retry_exhaustion,
    validate_decision_request,
)

AttemptDetails = list[dict[str, Any]]
Generator = Callable[[int, AttemptDetails], str]


def run_decision_with_retry(
    generate: Generator,
    *,
    max_attempts: int = _MAX_RETRIES,
    retry_reason: str = "validation",
) -> str:
    """执行生成器最多 `max_attempts` 次，逐轮校验；返回首个通过校验的输出。

    异常语义：生成器异常按 transient 记录；校验失败按 `retry_reason` 记录；
    耗尽抛 `RetryBudgetExhaustedError`，并先写结构化日志（含 attempt_details）。
    """
    if max_attempts < 1:
        # 次数下限：0/负数会让循环静默跳过，直接拒绝
        raise ValueError("max_attempts 必须 ≥ 1")

    details: AttemptDetails = []
    last_output = ""

    # 逐轮生成 → 校验 → 记录失败明细；明细会回传给下一轮生成器
    for attempt in range(1, max_attempts + 1):
        try:
            last_output = generate(attempt, [dict(item) for item in details])
        except Exception as exc:  # 生成器/下游异常 → transient
            # transient 与 validation 区分，供日志侧判断是抖动还是模板缺陷
            details.append(
                {
                    "attempt": attempt,
                    "reason": "transient",
                    "errors": [f"{type(exc).__name__}: {exc}"],
                }
            )
            continue

        try:
            validate_decision_request(
                last_output,
                retry_count=0,
                retry_reason=retry_reason,
                attempt_details=details,
            )
            return last_output
        except EnforcementError as exc:
            # 校验失败：记录本轮错误，继续下一轮（不中断）
            details.append(
                {
                    "attempt": attempt,
                    "reason": retry_reason,
                    "errors": [str(exc)],
                }
            )

    # 全部耗尽：先写三字段结构化日志，再抛阻断异常（禁止静默失败）
    _log_retry_exhaustion(
        last_output,
        len(details),
        retry_reason=retry_reason,
        attempt_details=details,
    )
    raise RetryBudgetExhaustedError(
        f"[生成阻断-重试耗尽] 决策请求在 {max_attempts} 次尝试后仍未通过校验"
    )
