"""A-3：渠道 schema 互证门禁的 3 例自测。"""

import importlib.util
from pathlib import Path

from pilotstd.core.notification.channel_spec import CHANNEL_SPECS


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_channel_schema_parity.py"
    spec = importlib.util.spec_from_file_location("channel_schema_parity", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_all_channels_are_consistent():
    mod = _load()
    assert mod.collect_mismatches() == []


def test_missing_channel_class_is_reported():
    mod = _load()
    problems = mod.collect_mismatches(classes={})
    assert any("渠道类缺失" in p for p in problems)


def test_required_mismatch_is_reported():
    mod = _load()
    spec = next(s for s in CHANNEL_SPECS if s.name == "telegram")

    class Broken:
        def get_config_schema(self):
            return {"bot_token": {"required": False, "secret": True},
                    "chat_id": {"required": False, "secret": False}}

    problems = mod.collect_mismatches(specs=[spec], classes={"telegram": Broken})
    assert any("required 不一致" in p for p in problems)
