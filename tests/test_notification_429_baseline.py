"""A-6 统计脚本逻辑（本地库/验证库通用）。"""

import importlib.util
from pathlib import Path


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "notification_429_baseline.py"
    spec = importlib.util.spec_from_file_location("r429", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_counts_by_channel(capsys):
    mod = _load()
    stats = mod.summarize(
        [
            ("telegram", "failed", "HTTP 429: Too Many Requests"),
            ("telegram", "sent", ""),
            ("wechat", "failed", "other error"),
        ]
    )
    assert stats["telegram"]["r429"] == 1
    assert stats["telegram"]["total"] == 2
    assert stats["wechat"]["r429"] == 0
