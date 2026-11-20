"""scripts/backfill_announce_archive.py 的纯函数测试（不发网络请求）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "backfill_announce_archive.py"


def _load():
    spec = importlib.util.spec_from_file_location("backfill_announce_archive", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load()


def test_pending_filters_done_and_keeps_order():
    all_targets = [
        ("announcement_gb", "2022年第1号"),
        ("announcement_gb", "2023年第2号"),
        ("announcement_hb", "2022年第3号"),
    ]
    done = {"announcement_gb|2022年第1号"}
    assert m.pending(all_targets, done) == [
        ("announcement_gb", "2023年第2号"),
        ("announcement_hb", "2022年第3号"),
    ]


def test_pending_all_done_returns_empty():
    all_targets = [("announcement_gb", "2022年第1号")]
    assert m.pending(all_targets, {"announcement_gb|2022年第1号"}) == []


def test_state_file_roundtrip(tmp_path, monkeypatch):
    """断点续跑：写出的 done 集合能被再次读取（源|公告号 作为键）。"""
    state = tmp_path / "state.json"
    monkeypatch.setattr(m, "STATE", state)
    state.write_text('{"done": ["announcement_gb|2022年第1号"]}', encoding="utf-8")
    import json

    loaded = set(json.loads(state.read_text(encoding="utf-8"))["done"])
    assert m.pending([("announcement_gb", "2022年第1号")], loaded) == []
