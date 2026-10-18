"""D-16 收尾：`_on_check_update` 网络失败路径（原 pragma 排除）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PyQt6")


def test_on_check_update_failure_shows_message(qapp, monkeypatch) -> None:
    from pilotstd.ui.main_window.parts import _actions_ops as ops

    shown: list[tuple] = []
    monkeypatch.setattr(ops.QMessageBox, "information", lambda *a, **k: shown.append(a))
    monkeypatch.setattr(ops._time, "time", lambda: 123.0)

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr("pilotstd.platform.updater.check_latest_version", boom)

    fake_self = SimpleNamespace(
        _config=MagicMock(),
        status_changed=SimpleNamespace(emit=lambda msg: None),
        _try_check_update_throttle=lambda current: False,
        _confirm_update_available=lambda current, release: True,
    )

    ops._on_check_update(fake_self)

    assert len(shown) == 1
    fake_self._config.set.assert_called_once_with("appearance.last_update_check", 123.0)
    fake_self._config.save.assert_called_once()
