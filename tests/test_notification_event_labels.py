"""通知事件类型必须有前端三语标签，避免日志页显示英文 event key。"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _event_keys() -> set[str]:
    src = (ROOT / "pilotstd/core/notification/event_spec_data.py").read_text(encoding="utf-8")
    return {k for k in re.findall(r'key="([^"]+)"', src) if not k.startswith("notification.module.")}


def test_all_event_specs_have_three_language_labels() -> None:
    keys = _event_keys()
    for lang in ("zh-CN", "en", "zh-TW"):
        data = json.loads((ROOT / f"web/src/locales/{lang}.json").read_text(encoding="utf-8"))
        labels = data["notification"]["event"]
        missing = sorted(keys - set(labels))
        assert not missing, f"{lang} missing event labels: {missing}"
