"""Golden：真实公告的修改单与被代替字段（30/31 号）。"""

from pathlib import Path

from pilotstd.announcement.parser import parse_announcement_detail

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _parse(name: str):
    return parse_announcement_detail((FIXTURES / name).read_text(encoding="utf-8"))


def test_amendment_is_kept_as_separate_item():
    items, _ = _parse("announcement_gb_2026_30.html")
    amendments = [i for i in items if "修改单" in i["std_name"]]
    assert len(amendments) == 1
    assert len(items) == 509


def test_replaced_codes_are_present_and_parseable():
    items, _ = _parse("announcement_gb_2026_30.html")
    replaced = [i["replaces_code"] for i in items if i.get("replaces_code")]
    assert len(replaced) > 10
    # 被代替字段必须是完整标准号，不能是公告行号/日期
    assert all("-" in code and not code[:4].isdigit() for code in replaced[:20])
