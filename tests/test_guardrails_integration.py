# tests/test_guardrails_integration.py
# 集成测试 — 8 项核心场景（正常流 + 异常流 + 边界条件）
#
# 规范基准: docs/governance/trinity-technical-spec-v2.md §4, §5, §7
# Story: STORY-7

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from enforcement.guardrails import (
    _MAX_RETRIES,
    _VALID_TRIGGER_TYPES,
    EnforcementError,
    RetryBudgetExhaustedError,
    UnauthorizedWriteError,
    atomic_write_notes,
    session_bootstrap,
    validate_decision_request,
    validate_prompt,
)

# ═══════════════════════════════════════════
# 场景 1: 正常流 — session_bootstrap 成功
# ═══════════════════════════════════════════


def test_scenario_1_bootstrap_success(monkeypatch, tmp_path):
    """正常会话引导：notes 存在时返回完整 BootstrapResult。"""
    notes = tmp_path / "local-session-notes.md"
    notes.write_text("""<!-- rule-signal-stats
window: 30d
updated: 2026-07-27T18:58:00+08:00
signals: []
-->

## [anchors] Active Context Anchors

_(no active anchors.)_

## [decisions] Decision Records

_(no decision records.)_
""")
    monkeypatch.setattr("enforcement.guardrails.SESSION_NOTES", str(notes))

    result = session_bootstrap()
    assert "context" in result
    assert "signals" in result
    assert "cleanup_result" in result
    assert "metadata" in result
    meta = result["metadata"]
    assert meta["version"] == "2.0"
    assert meta["schema_version"] == "1.0"
    assert "bootstrap_duration_ms" in meta
    assert "session_id" in meta


# ═══════════════════════════════════════════
# 场景 2: 异常流 — notes 缺失
# ═══════════════════════════════════════════


def test_scenario_2_missing_notes_aborts(monkeypatch, tmp_path):
    """notes 缺失时抛出 EnforcementError 禁止启动。"""
    nonexistent = tmp_path / "nonexistent.md"
    monkeypatch.setattr("enforcement.guardrails.SESSION_NOTES", str(nonexistent))
    with pytest.raises(EnforcementError, match="不存在"):
        session_bootstrap()


# ═══════════════════════════════════════════
# 场景 3: 边界 — validate_prompt 完整校验链
# ═══════════════════════════════════════════


def test_scenario_3_full_prompt_validation():
    """完整 Pre-flight 校验链：合法→通过，非法→阻断。"""
    # 合法
    valid = """<!-- prompt-meta
task-id: full-001
target-rules: [G-033, ADR-007]
rollback: code-only
assumptions-max-age: 7d
-->
## 任务目标
全面测试"""
    validate_prompt(valid)

    # 非法：缺少 rollback
    invalid = """<!-- prompt-meta
task-id: full-002
target-rules: [G-033]
-->
## 任务目标
测试"""
    with pytest.raises(EnforcementError):
        validate_prompt(invalid)


# ═══════════════════════════════════════════
# 场景 4: 边界 — validate_decision_request 全字段
# ═══════════════════════════════════════════


def test_scenario_4_full_decision_validation():
    """决策请求全字段校验。"""
    valid = """## [决策请求] 测试标题

**触发类型**: 规则冲突
**当前任务**: 实现用户登录
**阻塞位置**: src/login.ts:42

### 问题描述
两种规则对密码强度要求矛盾。

| 选项 | 描述 | 用户可见后果 | 关联规则 | 是否需立即执行 |
|------|------|-------------|----------|---------------|
| A | 使用6位 | 密码强度降低 | G-033 | ✅ 是 |
| B | 使用8位 | 需用户重新设置 | ADR-007 | ⏸️ 否 |
| C | 保持现状 | 无变化 | 无直接关联 | 🔘 可选 |

**超时策略**: [挂起] 和 [等待重启]
"""
    validate_decision_request(valid)


# ═══════════════════════════════════════════
# 场景 5: 边界 — 重试预算完整生命周期
# ═══════════════════════════════════════════


def test_scenario_5_retry_lifecycle():
    """重试预算：0→1→2→耗尽。"""
    bad = "无格式文本"
    for i in range(_MAX_RETRIES):
        with pytest.raises(EnforcementError):
            validate_decision_request(bad, retry_count=i)
    with pytest.raises(RetryBudgetExhaustedError):
        validate_decision_request(bad, retry_count=_MAX_RETRIES)


# ═══════════════════════════════════════════
# 场景 6: 异常流 — 原子写入白名单违规
# ═══════════════════════════════════════════


def test_scenario_6_unauthorized_write_blocked(monkeypatch, tmp_path):
    """非白名单调用方写入被阻断 + 审计日志。"""
    notes = tmp_path / "test_notes.md"
    notes.write_text("original")
    monkeypatch.setattr("enforcement.guardrails.SESSION_NOTES", str(notes))

    with pytest.raises(UnauthorizedWriteError, match="不在原子写入白名单"):
        atomic_write_notes("# hacked", "evil_script")

    # 确认原始内容未被修改
    assert notes.read_text() == "original"


# ═══════════════════════════════════════════
# 场景 7: 正常流 — 白名单合法写入
# ═══════════════════════════════════════════


def test_scenario_7_authorized_write_succeeds(monkeypatch, tmp_path):
    """白名单内调用方写入成功。"""
    notes = tmp_path / "test_notes.md"
    notes.write_text("original")
    monkeypatch.setattr("enforcement.guardrails.SESSION_NOTES", str(notes))

    atomic_write_notes("# updated by claude_code", "claude_code")
    assert notes.read_text() == "# updated by claude_code"


# ═══════════════════════════════════════════
# 场景 8: 边界 — 触发类型全集
# ═══════════════════════════════════════════


@pytest.mark.parametrize("trigger_type", sorted(_VALID_TRIGGER_TYPES))
def test_scenario_8_all_valid_trigger_types(trigger_type):
    """所有 5 种触发类型均可通过校验。"""
    output = f"""## [决策请求] 测试{trigger_type}

**触发类型**: {trigger_type}
**阻塞位置**: src/test.ts:1

| 选项 | 描述 | 用户可见后果 | 关联规则 | 是否需立即执行 |
|------|------|-------------|----------|---------------|
| A | 方案 | 无影响 | G-033 | ✅ 是 |
| B | 备选 | 无影响 | G-033 | ⏸️ 否 |

**超时策略**: [挂起] 和 [等待重启]
"""
    validate_decision_request(output)
