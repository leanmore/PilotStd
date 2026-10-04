# tests/test_notification_stage2a_stage.py
"""阶段 2a（2026-10-02）：`stage.py` 阶段开关（建立机制，本批不消费）。

## 判据

1. **未设环境变量 → 默认值 = `HIGHEST_STABLE_STAGE`**（本批为 `1`）；
2. **合法值**：`0`/`1`/`2`/`2.5`/`3`/`4`（含字符串形态与 `2.0` 等价形态）；
3. **非法值**（`"abc"` / `"9"` / `"2.6"` / `"-1"`）→ **回退默认值 + warning**，不抛；
4. **空值**（`""` / `"   "`）→ 视为未设置；
5. **谓词**：`is_mapping_enabled()`（≥2）、`is_aggregation_key_v2()`（≥2.5）、
   `is_interaction_enabled()`（≥3）在边界值上的取值正确；
6. **默认安全**：本批默认（1）下三个谓词**全为假**——即新能力一个都没开。
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification.stage import (  # noqa: E402
    ENV_STAGE,
    HIGHEST_STABLE_STAGE,
    KNOWN_STAGES,
    current_stage,
    is_aggregation_key_v2,
    is_interaction_enabled,
    is_mapping_enabled,
)


class TestCurrentStage(unittest.TestCase):
    def test_default_when_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_STAGE, None)
            self.assertEqual(current_stage(), HIGHEST_STABLE_STAGE)

    def test_default_is_two_after_enable_batch(self):
        """2b-启用批把默认值提为 2（映射生效）；回滚 = 设 `NOTIFY_REDESIGN_STAGE=1`。

        演化：2a 纯新增时为 1（映射不生效）→ 2b-接入仍为 1（接入但不生效）→
        2b-启用提为 **2**（本批的行为变更点）。
        """
        self.assertEqual(HIGHEST_STABLE_STAGE, 2.0)

    def test_known_stages_set(self):
        self.assertEqual(set(KNOWN_STAGES), {0.0, 1.0, 2.0, 2.5, 3.0, 4.0})

    def test_valid_values(self):
        for raw, expected in (("0", 0.0), ("1", 1.0), ("2", 2.0), ("2.5", 2.5), ("3", 3.0), ("4", 4.0)):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {ENV_STAGE: raw}):
                    self.assertEqual(current_stage(), expected)

    def test_float_equivalence(self):
        """`2` 与 `"2.0"` 等价（数值比较，不按字符串比较）。"""
        with patch.dict(os.environ, {ENV_STAGE: "2.0"}):
            self.assertEqual(current_stage(), 2.0)

    def test_whitespace_tolerated(self):
        with patch.dict(os.environ, {ENV_STAGE: "  2.5  "}):
            self.assertEqual(current_stage(), 2.5)

    def test_empty_means_unset(self):
        for raw in ("", "   "):
            with self.subTest(raw=repr(raw)):
                with patch.dict(os.environ, {ENV_STAGE: raw}):
                    self.assertEqual(current_stage(), HIGHEST_STABLE_STAGE)

    def test_invalid_values_fall_back_with_warning(self):
        """★ 非法值：回退默认 + warning，**不抛**（基础设施开关不该让链路起不来）。"""
        for raw in ("abc", "9", "2.6", "-1", "2,5", "阶段2"):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {ENV_STAGE: raw}):
                    with self.assertLogs("pilotstd.core.notification.stage", level="WARNING"):
                        self.assertEqual(current_stage(), HIGHEST_STABLE_STAGE)

    def test_never_raises(self):
        for raw in ("abc", "9", "2.6", "", "  ", "nan", "inf", "1e309"):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {ENV_STAGE: raw}):
                    try:
                        current_stage()
                    except Exception as e:  # noqa: BLE001
                        self.fail(f"current_stage 不得抛异常：{raw!r} → {type(e).__name__}: {e}")


class TestPredicates(unittest.TestCase):
    CASES = (
        # (环境值, mapping, agg_v2, interaction)
        ("0", False, False, False),
        ("1", False, False, False),  # ← 一行回滚档：映射关闭
        ("2", True, False, False),  # ← 2b-启用后的默认档
        ("2.5", True, True, False),
        ("3", True, True, True),
        ("4", True, True, True),
    )

    def test_boundaries(self):
        for raw, mapping, agg_v2, interaction in self.CASES:
            with self.subTest(stage=raw):
                with patch.dict(os.environ, {ENV_STAGE: raw}):
                    self.assertEqual(is_mapping_enabled(), mapping)
                    self.assertEqual(is_aggregation_key_v2(), agg_v2)
                    self.assertEqual(is_interaction_enabled(), interaction)

    def test_default_enables_mapping_only(self):
        """★ 默认档（2）下的安全性：只开"映射"这一项，聚合键 v2 / 交互仍关闭。

        这是 2b-启用批的行为边界——启用映射**不得**顺带开启后续阶段的能力。
        """
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_STAGE, None)
            self.assertTrue(is_mapping_enabled())
            self.assertFalse(is_aggregation_key_v2())
            self.assertFalse(is_interaction_enabled())

    def test_rollback_to_one_disables_mapping(self):
        """★ 一键回滚：`NOTIFY_REDESIGN_STAGE=1` 即可让映射不生效（无需回滚代码）。"""
        with patch.dict(os.environ, {ENV_STAGE: "1"}):
            self.assertFalse(is_mapping_enabled())


class TestConsumptionBoundary(unittest.TestCase):
    """消费边界：`stage.py` 只被 `_manager_ops.py` 引用。

    演化：2a 时断言"无任何生产消费者"；2b-接入把 `is_mapping_enabled()` 接进
    `NotificationOps.apply_mapping`；随后因 manager.py 有效行超 G-010 阻断线，
    实现从 manager.py 迁到 `_manager_ops.py`（manager.py 只保留一行 `self.ops.apply_mapping(...)`
    调用），故消费者就是 `_manager_ops.py` 一个。这样"多处接入导致开关语义分叉"仍会被拦住。
    """

    CONSUMER = "_manager_ops.py"

    def test_only_one_consumer(self):
        from pathlib import Path

        consumers: list[str] = []
        for path in Path("pilotstd").rglob("*.py"):
            if path.name in ("stage.py", self.CONSUMER):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "notification.stage" in text or "from .stage import" in text:
                consumers.append(str(path))
        self.assertEqual(consumers, [], f"stage.py 只应由 {self.CONSUMER} 消费，实测多出: {consumers}")

    def test_impl_module_is_the_consumer(self):
        from pathlib import Path

        text = Path(f"pilotstd/core/notification/{self.CONSUMER}").read_text(encoding="utf-8")
        self.assertIn("is_mapping_enabled", text, "stage 的谓词应由 _manager_ops.apply_mapping 消费")

    def test_manager_delegates_via_ops(self):
        """manager.py 不再直接 import stage；投影调用随编排迁至 `_dispatcher.py`（步 C B2）。

        判据不变：stage 的谓词只由 `_manager_ops.apply_mapping` 消费，
        manager.py 自身不得出现 `is_mapping_enabled`（避免开关语义分叉）。
        """
        from pathlib import Path

        dispatcher = Path("pilotstd/core/notification/_dispatcher.py").read_text(encoding="utf-8")
        self.assertIn("host.ops.apply_mapping(msg, event_type, event_data)", dispatcher)
        manager = Path("pilotstd/core/notification/manager.py").read_text(encoding="utf-8")
        self.assertNotIn("is_mapping_enabled", manager)


if __name__ == "__main__":
    unittest.main()
