# tests/test_event_verify_declaration.py
"""P6/P7 甲案：事件「声明式可验证性」门禁测试（2026-10-06）。

**设计口径（用户裁定）**：
- 防漂移门禁必须**声明式**（注册即必填字段），**不是过程式**（不必每次跑全量插桩）；
- **不要求 42/42 运行时覆盖**：极难触发的环境相关事件（凭证轮换、库损坏类告警）显式声明即可；
- 因此 `EventSpec.verify` **无默认值**（漏填在 import 期即 `TypeError`），并由覆盖审计做第二道
  静态校验：取值落闭集、非 `e2e` 必带**机器可读枚举理由**、`e2e` 不得带理由。

本文件覆盖三件事：
1. **注册期必填**：`verify` 缺失时构造 `EventSpec` 直接 `TypeError`（无需任何测试运行即可兜底）；
2. **真实树自洽**：42 条声明的 `verify`/`verify_reason` 全部合规且理由落在闭集内；
3. **审计函数行为**：对越界/缺理由/`e2e` 带理由三类反例**必须报错**（防"门禁写了但不管用"）。
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _notification_spec_read import (  # noqa: E402
    VERIFY_REASON_CODES,
    VERIFY_VALUES,
    spec_field_problems,
)

from pilotstd.core.notification.event_spec import EVENT_SPECS, EventSpec  # noqa: E402


def _meta(**overrides: object) -> dict:
    """构造一个**字段齐全**的规格元数据（其余字段取真实声明，保证只有被测项不同）。"""
    base = dict(next(iter({s.key: _spec_fields(s) for s in EVENT_SPECS}.values())))
    base.update(overrides)
    return base


def _spec_fields(spec: EventSpec) -> dict:
    return {f.name: getattr(spec, f.name) for f in dataclasses.fields(spec)}


def _problems(meta: dict) -> list[str]:
    return spec_field_problems(
        event=str(meta.get("key", "")),
        meta=meta,
        packs={"zh_CN": {}, "en": {}, "zh_TW": {}},  # module_key 校验在别处覆盖，此处不关心
        level_order=("info", "warning", "error"),
        aggregation_values=("aggregate", "bypass"),
        builder_defs={},
    )


class TestVerifyIsRequiredAtRegistration:
    """注册期必填（**声明式**兜底：漏填即 import 失败，不需要跑任何测试）。"""

    def test_missing_verify_raises_type_error(self) -> None:
        fields = _spec_fields(EVENT_SPECS[0])
        fields.pop("verify")
        with pytest.raises(TypeError):
            EventSpec(**fields)  # type: ignore[arg-type]

    def test_field_has_no_default(self) -> None:
        field = next(f for f in dataclasses.fields(EventSpec) if f.name == "verify")
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


class TestRealTreeIsSelfConsistent:
    """真实 42 条声明合规（并**不**要求它们全部运行时覆盖）。"""

    def test_all_values_in_closed_set(self) -> None:
        for spec in EVENT_SPECS:
            assert spec.verify in VERIFY_VALUES, f"{spec.key}: verify={spec.verify!r}"

    def test_non_e2e_carry_machine_readable_reason(self) -> None:
        for spec in EVENT_SPECS:
            if spec.verify == "e2e":
                assert spec.verify_reason == "", f"{spec.key}: e2e 不应带理由"
            else:
                assert spec.verify_reason in VERIFY_REASON_CODES, f"{spec.key}: 理由码越界"

    def test_coverage_is_not_required_to_be_total(self) -> None:
        """口径固化：允许存在 `manual`/`ui_only` 事件（极难触发者**不必**强行覆盖）。"""
        declared = {s.verify for s in EVENT_SPECS}
        assert declared <= set(VERIFY_VALUES)
        assert any(s.verify != "e2e" for s in EVENT_SPECS), (
            "若所有事件都是 e2e，说明分类失去意义；环境相关事件应显式声明为 manual/ui_only"
        )


class TestAuditFunctionRejectsViolations:
    """审计函数对三类反例必须报错（防止门禁形同虚设）。"""

    def test_unknown_verify_value_is_rejected(self) -> None:
        problems = _problems(_meta(verify="whatever", verify_reason=""))
        assert any("verify 越界" in p for p in problems), problems

    def test_non_e2e_without_reason_is_rejected(self) -> None:
        problems = _problems(_meta(verify="manual", verify_reason=""))
        assert any("必须带 verify_reason" in p for p in problems), problems

    def test_unknown_reason_code_is_rejected(self) -> None:
        problems = _problems(_meta(verify="manual", verify_reason="凭经验觉得难触发"))
        assert any("verify_reason 越界" in p for p in problems), problems

    def test_e2e_with_reason_is_rejected(self) -> None:
        problems = _problems(_meta(verify="e2e", verify_reason="real_chain_only"))
        assert any("不应带理由" in p for p in problems), problems

    def test_valid_combination_has_no_verify_problem(self) -> None:
        problems = _problems(_meta(verify="ui_only", verify_reason="ui_only"))
        assert not any("verify" in p for p in problems), problems
