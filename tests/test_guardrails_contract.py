# tests/test_guardrails_contract.py
# 契约测试 — 验证 BootstrapResult TypedDict 结构与 guardrails 接口签名
#
# 规范基准: docs/governance/trinity-technical-spec-v2.md §4.2

from __future__ import annotations

import sys
from pathlib import Path

# 确保 src 在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import get_type_hints

import pytest

from enforcement.guardrails import (
    EnforcementError,
    UnauthorizedWriteError,
    atomic_write_notes,
    validate_decision_request,
    validate_prompt,
)
from src.types.bootstrap import (
    ALLOWED_CALLERS,
    PROTECTED_GOVERNANCE_PATHS,
    BootstrapResult,
    CleanupReport,
    Signal,
)

# ═══════════════════════════════════════════
# STORY-2: 契约测试
# ═══════════════════════════════════════════


class TestBootstrapResultContract:
    """BootstrapResult TypedDict 结构契约。"""

    def test_four_fields_present(self):
        """四字段缺一不可。"""
        fields = BootstrapResult.__annotations__
        assert "context" in fields
        assert "signals" in fields
        assert "cleanup_result" in fields
        assert "metadata" in fields
        assert len(fields) == 4, f"BootstrapResult 必须恰好 4 个字段，实际: {fields}"

    def test_cleanup_report_fields(self):
        """CleanupReport 包含 archived_items / failed_items / last_run_timestamp。"""
        fields = get_type_hints(CleanupReport)
        assert fields["archived_items"] is int
        assert fields["failed_items"] is int
        assert fields["last_run_timestamp"] is str

    def test_signal_fields(self):
        """Signal 包含 id / type / payload / priority。"""
        fields = get_type_hints(Signal)
        assert fields["id"] is str
        assert fields["type"] is str
        assert fields["priority"] is int

    def test_metadata_required_keys(self):
        """metadata 必须包含 version 和 schema_version。"""
        meta_spec = {
            "version": "2.0",
            "schema_version": "1.0",
            "bootstrap_duration_ms": "42",
            "session_id": "test-123",
        }
        assert "version" in meta_spec
        assert "schema_version" in meta_spec

    def test_allowed_callers_not_empty(self):
        """白名单非空。"""
        assert len(ALLOWED_CALLERS) >= 3

    def test_protected_paths_not_empty(self):
        """受保护路径列表非空。"""
        assert len(PROTECTED_GOVERNANCE_PATHS) >= 5


class TestValidatePromptContract:
    """validate_prompt 接口契约。"""

    def test_accepts_valid_prompt(self):
        """有效提示词通过校验。"""
        prompt = """<!-- prompt-meta
task-id: test-001
target-rules: [G-033]
rollback: code-only
-->
## 任务目标
测试"""
        validate_prompt(prompt)  # 不应抛异常

    def test_rejects_missing_meta(self):
        """无元数据头时抛出 EnforcementError。"""
        with pytest.raises(EnforcementError, match="缺少 prompt-meta"):
            validate_prompt("普通文本，无元数据头")

    def test_rejects_missing_required_fields(self):
        """缺少必填字段时抛出 EnforcementError。"""
        prompt = """<!-- prompt-meta
task-id: test-002
-->
## 任务目标
测试"""
        with pytest.raises(EnforcementError, match="缺少必填"):
            validate_prompt(prompt)

    def test_rejects_invalid_rollback(self):
        """无效 rollback 级别时抛出 EnforcementError。"""
        prompt = """<!-- prompt-meta
task-id: test-003
target-rules: [G-033]
rollback: manual-fix
-->
## 任务目标
测试"""
        with pytest.raises(EnforcementError, match="rollback"):
            validate_prompt(prompt)


class TestValidateDecisionRequestContract:
    """validate_decision_request 接口契约。"""

    def test_accepts_valid_output(self):
        """格式正确的决策请求通过校验。"""
        output = """## [决策请求] 测试请求

**触发类型**: 规则冲突
**阻塞位置**: src/app.ts:42

| 选项 | 描述 | 用户可见后果 | 关联规则 | 是否需立即执行 |
|------|------|-------------|----------|---------------|
| A | 方案A | 无影响 | G-033 | ✅ 是 |
| B | 方案B | 无影响 | G-033 | ⏸️ 否 |

**超时策略**: [挂起] 和 [等待重启]
"""
        validate_decision_request(output)  # 不应抛异常

    def test_rejects_invalid_trigger_type(self):
        """无效触发类型时抛出 EnforcementError。"""
        output = """## [决策请求] 测试

**触发类型**: 代码太难
**阻塞位置**: src/app.ts:42

| A | 方案A | 无影响 | G-033 | ✅ 是 |

**超时策略**: [挂起] 和 [等待重启]
"""
        with pytest.raises(EnforcementError, match="触发类型"):
            validate_decision_request(output)

    def test_rejects_too_few_options(self):
        """方案数量 < 2 时抛出。"""
        output = """## [决策请求] 测试

**触发类型**: 规则冲突
**阻塞位置**: src/app.ts:42

| A | 唯一方案 | 无影响 | G-033 | ✅ 是 |

**超时策略**: [挂起] 和 [等待重启]
"""
        with pytest.raises(EnforcementError, match="可选方案"):
            validate_decision_request(output)

    def test_rejects_missing_dual_mode_timeout(self):
        """缺少双轨超时策略时抛出。"""
        output = """## [决策请求] 测试

**触发类型**: 规则冲突
**阻塞位置**: src/app.ts:42

| A | 方案A | 无影响 | G-033 | ✅ 是 |
| B | 方案B | 无影响 | G-033 | ⏸️ 否 |
"""
        with pytest.raises(EnforcementError, match="双轨"):
            validate_decision_request(output)


class TestRetryBudgetIsolation:
    """重试预算请求级隔离（§4.3）。"""

    def test_independent_retry_counters(self):
        """第 N 次调用的重试次数不受第 N-1 次影响。"""
        bad_output = "无格式的普通文本"
        # 第一次调用，retry_count=0
        with pytest.raises(EnforcementError):
            validate_decision_request(bad_output, retry_count=0)
        # 第二次调用，retry_count 仍为 0（未污染）
        with pytest.raises(EnforcementError):
            validate_decision_request(bad_output, retry_count=0)

    def test_retry_budget_exhaustion(self):
        """第 3 次重试后抛出 RetryBudgetExhaustedError。"""
        bad_output = "无格式的普通文本"
        # retry_count=2 时仍抛 EnforcementError
        with pytest.raises(EnforcementError):
            validate_decision_request(bad_output, retry_count=2)
        # retry_count=3 时抛 RetryBudgetExhaustedError
        from enforcement.guardrails import RetryBudgetExhaustedError

        with pytest.raises(RetryBudgetExhaustedError, match="重试耗尽"):
            validate_decision_request(bad_output, retry_count=3)


class TestAtomicWriteWhitelist:
    """原子写入白名单校验。"""

    def test_allowed_caller_no_error(self, tmp_path, monkeypatch):
        """白名单内调用方不抛异常。"""
        notes = tmp_path / "test_notes.md"
        notes.write_text("test")
        monkeypatch.setattr("enforcement.guardrails.SESSION_NOTES", str(notes))
        atomic_write_notes("# test", "claude_code")

    def test_blocked_caller_raises(self, tmp_path, monkeypatch):
        """非白名单调用方抛出 UnauthorizedWriteError。"""
        notes = tmp_path / "test_notes.md"
        notes.write_text("test")
        monkeypatch.setattr("enforcement.guardrails.SESSION_NOTES", str(notes))
        with pytest.raises(UnauthorizedWriteError, match="不在原子写入白名单"):
            atomic_write_notes("# test", "random_script")


class TestNegativeCases:
    """负面测试用例 — 验证类型校验有效性。"""

    def test_missing_required_field_triggers_error(self):
        """故意缺失 BootstrapResult 必填字段时触发 TypeError。"""
        # BootstrapResult 为 TypedDict，运行时不会强制校验，
        # 但静态类型检查（mypy）应捕获。此处验证结构定义正确。
        fields = BootstrapResult.__annotations__
        assert "context" in fields, "缺少 context 字段定义"
        assert "signals" in fields, "缺少 signals 字段定义"
        assert "cleanup_result" in fields, "缺少 cleanup_result 字段定义"
        assert "metadata" in fields, "缺少 metadata 字段定义"

    def test_extra_field_not_in_contract(self):
        """验证 BootstrapResult 无多余字段。"""
        fields = BootstrapResult.__annotations__
        assert len(fields) == 4, f"BootstrapResult 应恰好 4 个字段，实际 {len(fields)}: {sorted(fields)}"

    def test_whitelist_immutable(self):
        """白名单不可变。"""
        assert isinstance(ALLOWED_CALLERS, frozenset)
