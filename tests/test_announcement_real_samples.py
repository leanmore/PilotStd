"""真实公告样本回归（2026-11-03 抓取）：

- 2026 年第 45 号：21 项（修复前 HTML+附件两种破折号写法把 21 项算成 42 项）
- 2026 年第 30 号：509 条 = 508 条标准本体 + 1 条修改单；第 508 条必须是 GB/T 48012.2-2026

样本为源站详情页 HTML 原始副本（tests/fixtures/announcement_gb_2026_*.html），只读解析。
"""

import re
from pathlib import Path

from pilotstd.announcement.parser import normalize_std_code, parse_announcement_detail

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(name: str):
    html = (FIXTURES / name).read_text(encoding="utf-8")
    return parse_announcement_detail(html)


def test_mixed_bulk_and_amendment_title_is_not_amendment_only():
    """30 号标题同时含「508 项标准」和「1 项修改单」——必须按清单解析，不能走修改单分支。

    回归：`_is_amendment` 原来只看子串「修改单」，导致 reparse 该公告时
    `_parse_amendment` 从标题抠不出标准号 → 返回 0 条 → HTTP 400。
    """
    from pilotstd.announcement.adapters.samr_gb import SamrGbCrawler

    crawler = SamrGbCrawler()
    mixed = (
        "关于批准发布《碳素结构钢和低合金结构钢热轧厚钢板和钢带》等"
        "508项推荐性国家标准和1项推荐性国家标准修改单的公告"
    )
    assert crawler._is_amendment({"title": mixed}) is False

    pure = "关于发布GB/T 19411-2023《除湿机》第1号修改单的公告"
    assert crawler._is_amendment({"title": pure}) is True


def test_metadata_date_residue_is_dropped():
    """WPS 附件把上一列末尾的字一起带到名称列：`部 2026-11-01  249` 必须被丢弃。

    2026 年第30号附件实测多出 1 条残片（`GB/T 9634.3—2002` + 名称「部 2026-11-01 249」），
    不丢弃会让 508+1 变成 510。
    """
    from pilotstd.announcement.parser import _looks_like_metadata_row, parse_text_table

    assert _looks_like_metadata_row("部 2026-11-01  249") is True
    assert _looks_like_metadata_row("第 2026-11-01 249") is True
    assert _looks_like_metadata_row("2026-11-01") is True
    assert _looks_like_metadata_row("碳素结构钢和低合金结构钢热轧厚钢板和钢带") is False

    text = "1 GB/T 9634.3-2002 部 2026-11-01  249\n2 GB/T 711-2026 碳素结构钢\n"
    codes = {i["std_code"] for i in parse_text_table(text)}
    assert "GB/T 9634.3-2002" not in " ".join(codes)


def test_process_one_detail_yields_509_for_mixed_announcement(monkeypatch):
    """端到端（离线）：混合标题 + 真实详情页 HTML → 509 条入库行。"""
    from pilotstd.announcement import base as base_mod
    from pilotstd.announcement.adapters.samr_gb import SamrGbCrawler

    html = (FIXTURES / "announcement_gb_2026_30.html").read_text(encoding="utf-8")
    monkeypatch.setattr(base_mod, "_store_raw_content", lambda *a, **k: None)

    crawler = SamrGbCrawler()
    monkeypatch.setattr(crawler, "_fetch_detail", lambda pid: html)
    monkeypatch.setattr(crawler, "_download_attachment", lambda url: None)

    items = crawler._process_one_detail(
        {
            "pid": "D2A7BEA0A4985DA5622524E6D876F31E",
            "code": "2026年第30号",
            "title": (
                "关于批准发布《碳素结构钢和低合金结构钢热轧厚钢板和钢带》等"
                "508项推荐性国家标准和1项推荐性国家标准修改单的公告"
            ),
            "notice_date": "2026-07-02",
            "std_count": "509",
        },
        None,
        lambda pid: None,
    )
    assert len(items) == 509


def test_gb_2026_45_parses_21_items():
    items, meta = _parse("announcement_gb_2026_45.html")
    assert meta.get("title")
    assert len(items) == 21

    codes = [normalize_std_code(i["std_code"]) for i in items]
    assert len(codes) == len(set(codes)), "同一条标准不得解析成两行"

    # 名称尾部不得残留实施日期/行号（WPS 残渣）
    for it in items:
        assert not re.search(r"\d{4}-\d{2}-\d{2}", it["std_name"]), it


def test_gb_2026_30_parses_509_items_with_amendment_split():
    items, _ = _parse("announcement_gb_2026_30.html")
    assert len(items) == 509, f"508 标准 + 1 修改单，实际 {len(items)}"

    # 第 508 条是标准本体（修改单在第 509 条；章节标题不得把 506-508 吞进修改单）
    assert normalize_std_code(items[507]["std_code"]) == "GB/T 48012.2-2026"

    last = items[-1]
    assert "修改单" in last["std_name"], last["std_name"]

    body = [i for i in items if "修改单" not in i["std_name"]]
    assert len(body) == 508

    # 合法空值：代替标准号为空不能被当成解析失败（新增标准）
    assert any(i["replaces_code"] == "" for i in items)
