"""Golden File regression: parse_announcement_detail vs human-annotated expected."""
import re

from pilotstd.announcement.parser import parse_announcement_detail

CRITICAL_FIELDS = ("std_code", "std_name", "publish_date", "implementation_date")


_DASHES = str.maketrans({ "—": "-", "–": "-", "－": "-", "−": "-" })


def _norm_date(value: str) -> str:
    """日期归一：中英文分隔符/前导零差异不改变语义（不同 PDF 抽取库输出形态不同）。"""
    text = value.translate(_DASHES).replace("年", "-").replace("月", "-").replace("日", "")
    parts = [part.strip() for part in text.split("-") if part.strip()]
    if len(parts) == 3 and parts[0].isdigit():
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return " ".join(text.split())


def _normalize(items: list[dict]) -> list[dict]:
    """Sort by std_code + collapse whitespace + normalize line endings.

    PDF 文本抽取在不同平台/库版本下会改变换行与空格；这些差异不改变语义，
    统一折叠后再比较，避免 golden 依赖运行环境。
    """
    for it in items:
        for k, v in it.items():
            if isinstance(v, str):
                if k in ("publish_date", "implementation_date"):
                    it[k] = _norm_date(v)
                elif k == "std_code":
                    it[k] = re.sub(r"\s+", " ", v.translate(_DASHES).replace("／", "/")).strip()
                elif k == "std_name":
                    # PDF 抽取会把 "WO 3 30" 与 "WO330" 视为不同；名称比较忽略空白
                    it[k] = re.sub(r"\s+", "", v)
                else:
                    it[k] = re.sub(r"\s+", " ", v.replace("\r\n", "\n")).strip()
    return sorted(items, key=lambda x: x.get("std_code", ""))


class TestGoldenAccuracy:
    def test_items_count(self, golden_case):
        result_items, _ = _parse(golden_case)
        expected_count = len(golden_case["expected"]["items"])
        message = (
            f"[{golden_case['stem']}] item count mismatch: "
            f"got={len(result_items)}, expected={expected_count}"
        )
        if len(result_items) != expected_count:
            # 转成 check-run 注解，CI 失败时可直接看到差异（Actions 日志本仓 token 不可读）
            print(f"::error title=golden-count::{message}")
        assert len(result_items) == expected_count, message

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
        if mismatches:
            print(f"::error title=golden-fields::[{golden_case['stem']}] " + " | ".join(mismatches[:6]))
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
