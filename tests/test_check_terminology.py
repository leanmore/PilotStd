"""G-044 术语门禁（`scripts/check_terminology.py`）专属测试。

**为什么新增本文件**：2026-10-07 为消除 6 条「按语境豁免」的别名误报，给门禁加了第四层白名单
`alias_exempt_keys`（**仅跳过检测 3 别名提示**）。按 P-104「门禁不绕过」，必须用测试**证明未削弱**：
即便某键被登记为按语境豁免，检测 1（禁用词，阻断）与检测 2（登记键三语严格相等，阻断）**仍照旧生效**。

导入范式与 `tests/test_check_i18n_hardcoded.py` 一致（scripts/ 不是包 ⇒ 以文件路径加载）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_terminology.py"


def _load_module():
    """以文件路径加载门禁脚本模块。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_terminology", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    """加载后的门禁模块。"""
    return _load_module()


def _check(gate, key: str, value: str, aliases, forbidden=()):
    """构造最小 packs/glossary 跑 `_check_key`，返回 (阻断项, 提示项)。"""
    packs = {"zh_CN": {key: value}}
    errors, warns, _ = gate._check_key(
        key,
        packs,
        {},
        set(),
        [],
        list(forbidden),
        list(aliases),
        ["notification.*"],
    )
    return errors, warns


class TestAliasHint:
    """检测 3：别名命中仅提示（不阻断）。"""

    def test_alias_hit_produces_hint(self, gate):
        """未登记语境豁免时，别名命中产生提示。"""
        errors, warns = _check(gate, "notification.demo.key", "这是一条消息", [("消息", "notice", frozenset())])
        assert errors == []
        assert any("可接受但不推荐" in w for w in warns)

    def test_alias_exempt_key_skips_hint(self, gate):
        """登记 `alias_exempt_keys` 的键，别名命中不再提示。"""
        errors, warns = _check(
            gate,
            "notification.demo.key",
            "这是一条测试消息",
            [("消息", "notice", frozenset({"notification.demo.key"}))],
        )
        assert errors == []
        assert warns == []


class TestNoWeakening:
    """P-104：按语境豁免**不得**削弱阻断能力。"""

    def test_forbidden_still_blocks_even_when_alias_exempt(self, gate):
        """被按语境豁免的键，命中禁用词仍必须**阻断**。"""
        errors, warns = _check(
            gate,
            "notification.demo.key",
            "保存完成",
            [("保存", "archive", frozenset({"notification.demo.key"}))],
            forbidden=[("保存完成", "archive")],
        )
        assert any("禁用词" in e for e in errors), "禁用词必须仍然阻断"
        assert warns == []

    def test_exempt_does_not_affect_other_keys(self, gate):
        """豁免只作用于登记键：其它键的别名命中照旧提示。"""
        packs = {"zh_CN": {"notification.other.key": "这是一条消息"}}
        errors, warns, _ = gate._check_key(
            "notification.other.key",
            packs,
            {},
            set(),
            [],
            [],
            [("消息", "notice", frozenset({"notification.demo.key"}))],
            ["notification.*"],
        )
        assert errors == []
        assert any("可接受但不推荐" in w for w in warns)


class TestScopeAndTermConsistency:
    """作用域与检测 2 的基本形态（回归护栏）。"""

    def test_out_of_scope_key_skipped(self, gate):
        """作用域外的键不参与三条检测。"""
        errors, warns = _check(gate, "app.title", "这是一条消息", [("消息", "notice", frozenset())])
        assert (errors, warns) == ([], [])

    def test_registered_key_strict_mismatch_still_blocks(self, gate):
        """检测 2：术语表登记键的三语值与语言包不相等 ⇒ 阻断（与本次改动无关，防回归）。"""
        mod = gate
        glossary = {
            "terms": [
                {
                    "id": "notice",
                    "zh_CN": "通知",
                    "zh_TW": "通知",
                    "en": "Notice",
                    "keys": ["notification.demo.key"],
                }
            ]
        }
        packs = {
            "zh_CN": {"notification.demo.key": "消息"},
            "zh_TW": {"notification.demo.key": "通知"},
            "en": {"notification.demo.key": "Notice"},
        }
        problems = mod._check_term_consistency(glossary, packs)
        assert problems, "登记键三语不一致必须报错"
