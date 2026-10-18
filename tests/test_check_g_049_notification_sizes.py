"""G-049 扩展（A-2）：通知模块热点文件防膨胀。

覆盖：配置覆盖范围、当前全部达标、超限/缺失判定。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_g_049_manager_size.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_g_049_manager_size", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def test_targets_cover_manager_and_hotspots() -> None:
    names = {path.name for path, _cap in gate.TARGETS}
    assert "manager.py" in names
    assert {
        "aggregate_buffer.py",
        "_builders_batch.py",
        "callback_service.py",
        "_builders_system.py",
        "_manager_ops.py",
        "renderer.py",
    } <= names
    # 静态规格数据表不纳入（避免每加渠道就红）
    assert "event_spec_data.py" not in names
    assert "channel_spec_data.py" not in names


def test_all_targets_currently_within_cap() -> None:
    for path, cap in gate.TARGETS:
        ok, effective = gate.check_file(path, cap)
        assert ok, f"{path} 有效行 {effective} > {cap}"


def test_over_limit_and_missing_fail(tmp_path, monkeypatch) -> None:
    heavy = tmp_path / "heavy.py"
    heavy.write_text("\n".join(["x = 1"] * 20), encoding="utf-8")
    ok, effective = gate.check_file(heavy, 5)
    assert not ok
    assert effective == 20

    ok, effective = gate.check_file(tmp_path / "missing.py", 100)
    assert not ok
    assert effective == 0
