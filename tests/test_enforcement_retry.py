"""A-4 专项：决策请求重试编排（逐轮 attempt_details）。"""

from __future__ import annotations

import json
import logging

import pytest

from enforcement.retry import run_decision_with_retry

VALID = """## [决策请求] 测试请求

**触发类型**: 规则冲突
**阻塞位置**: src/app.ts:42

| 选项 | 描述 | 用户可见后果 | 关联规则 | 是否需立即执行 |
|------|------|-------------|----------|---------------|
| A | 方案A | 无影响 | G-033 | ✅ 是 |
| B | 方案B | 无影响 | G-033 | ⏸️ 否 |

**超时策略**: [挂起] 和 [等待重启]
"""

INVALID = """## [决策请求] 坏输出

**触发类型**: 不存在的类型
"""


def test_retry_succeeds_on_second_attempt_and_passes_previous_details() -> None:
    seen: list[list[dict]] = []

    def generate(attempt, previous):
        seen.append(previous)
        return INVALID if attempt == 1 else VALID

    assert run_decision_with_retry(generate, max_attempts=3) == VALID
    # 第 2 次生成时拿到第 1 轮的错误明细（用于"带错误重试"）
    assert len(seen) == 2
    assert seen[1][0]["attempt"] == 1
    assert seen[1][0]["reason"] == "validation"
    assert seen[1][0]["errors"]


def test_transient_generator_error_is_recorded() -> None:
    calls = {"n": 0}

    def generate(attempt, previous):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("network timeout")
        return VALID

    assert run_decision_with_retry(generate, max_attempts=3) == VALID


def test_exhaustion_logs_full_attempt_details(caplog) -> None:
    from enforcement.guardrails import RetryBudgetExhaustedError

    def generate(attempt, previous):
        return INVALID

    with caplog.at_level(logging.ERROR, logger="enforcement.guardrails"):
        with pytest.raises(RetryBudgetExhaustedError):
            run_decision_with_retry(generate, max_attempts=3)

    message = caplog.records[0].getMessage()
    assert "retry_reason=validation" in message
    payload = message.split("attempt_details=", 1)[1].split(" output_preview=", 1)[0]
    details = json.loads(payload)
    assert [item["attempt"] for item in details] == [1, 2, 3]
    assert all(item["reason"] == "validation" for item in details)
    assert all(item["errors"] for item in details)


def test_max_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        run_decision_with_retry(lambda a, p: VALID, max_attempts=0)
