#!/usr/bin/env python3
"""A-3：`channel_spec.schema` 与各渠道 `get_config_schema()` 互证门禁。

比较四件事（逐字段）：
- 键集合一致；
- `required` 一致；
- `secret` 与 spec 的 `password` 一致；
- 渠道类存在且其 `get_config_schema()` 可调用。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pilotstd.core.notification.channel_spec import CHANNEL_SPECS, legacy_schema
from pilotstd.i18n import t


def _classes():
    from pilotstd.core.notification.manager import _CHANNEL_CLASSES

    return _CHANNEL_CLASSES


def collect_mismatches(specs=None, classes=None) -> list[str]:
    specs = specs if specs is not None else CHANNEL_SPECS
    classes = classes if classes is not None else _classes()
    problems: list[str] = []
    for spec in specs:
        cls = classes.get(spec.name)
        if cls is None:
            problems.append(f"{spec.name}: 渠道类缺失")
            continue
        try:
            actual = cls.__new__(cls).get_config_schema()
        except Exception as exc:  # noqa: BLE001 - 门禁需报告失败原因
            problems.append(f"{spec.name}: get_config_schema() 调用失败: {exc}")
            continue
        expected = legacy_schema(spec, t)
        if set(actual) != set(expected):
            problems.append(
                f"{spec.name}: 键集合不一致 actual={sorted(actual)} expected={sorted(expected)}"
            )
            continue
        for key, exp in expected.items():
            act = actual[key]
            if bool(act.get("required")) != bool(exp.get("required")):
                problems.append(f"{spec.name}.{key}: required 不一致")
            if bool(act.get("secret")) != bool(spec_field_password(spec, key)):
                problems.append(f"{spec.name}.{key}: secret/password 不一致")
    return problems


def spec_field_password(spec, key: str) -> bool:
    for field in spec.fields:
        if field.name == key:
            return bool(field.password)
    return False


def main() -> int:
    problems = collect_mismatches()
    if problems:
        for p in problems:
            print(f"[FAIL] {p}")
        return 1
    print(f"[PASS] {len(CHANNEL_SPECS)} 个渠道 schema 与 get_config_schema() 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
