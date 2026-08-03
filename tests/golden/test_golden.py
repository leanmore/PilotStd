"""Golden File regression: parse_announcement_detail vs human-annotated expected."""
from pilotstd.announcement.parser import parse_announcement_detail

CRITICAL_FIELDS = ("std_code", "std_name", "publish_date", "implementation_date")


def _normalize(items: list[dict]) -> list[dict]:
    """Sort by std_code + strip whitespace to eliminate ordering/format diffs."""
    for it in items:
        for k, v in it.items():
            if isinstance(v, str):
                it[k] = v.strip()
    return sorted(items, key=lambda x: x.get("std_code", ""))


class TestGoldenAccuracy:
    def test_items_count(self, golden_case):
        result_items, _ = _parse(golden_case)
        expected_count = len(golden_case["expected"]["items"])
        assert len(result_items) == expected_count, (
            f"[{golden_case['stem']}] item count mismatch: "
            f"got={len(result_items)}, expected={expected_count}"
        )

    def test_critical_fields_match(self, golden_case):
        result_items, _ = _parse(golden_case)
        got = _normalize(result_items)
        exp = _normalize(golden_case["expected"]["items"])

        mismatches = []
        for i, (g, e) in enumerate(zip(got, exp)):
            for field in CRITICAL_FIELDS:
                gv = g.get(field)
                ev = e.get(field)
                if gv != ev:
                    mismatches.append(
                        f"  item[{i}].{field}: "
                        f"got={gv!r}, expected={ev!r}"
                    )
        assert not mismatches, (
            f"[{golden_case['stem']}] critical field mismatch:\n"
            + "\n".join(mismatches)
        )


def _parse(case: dict) -> tuple:
    """Route fixture to parser based on file extension."""
    ext = case["ext"]
    if ext in (".html", ".htm"):
        html = case["raw_bytes"].decode("utf-8", errors="replace")
        return parse_announcement_detail(html=html)
    else:
        return parse_announcement_detail(
            html="<html><body></body></html>",
            attachment_bytes=case["raw_bytes"],
            attachment_filename=case["fixture_path"].name,
        )
