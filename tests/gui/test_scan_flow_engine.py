# tests/gui/test_scan_flow_engine.py
"""ScanFlowEngine 纯单元测试 — 零 Qt，毫秒级。"""

from __future__ import annotations

from pilotstd.ui.core.handlers.scan_flow_engine import ScanFlowEngine

# ═══════════════════════════════════════════════════════════════════
# parse_filename_to_std
# ═══════════════════════════════════════════════════════════════════


class TestParseFilename:
    def test_standard_gb_with_year(self):
        r = ScanFlowEngine.parse_filename_to_std("GB/T 12345-2020.pdf")
        assert r is not None
        assert r["logical_code"] == "GB/T"
        assert r["number"] == 12345
        assert r["year"] == 2020
        assert r["is_valid"] is True
        assert "12345" in r["std_number"]

    def test_standard_without_year(self):
        r = ScanFlowEngine.parse_filename_to_std("ISO 9001.pdf")
        assert r is not None
        assert "ISO" in r.get("logical_code", "")
        assert r["number"] == 9001
        assert r["year"] == 0

    def test_no_extension(self):
        r = ScanFlowEngine.parse_filename_to_std("GB 12345-2020")
        assert r is not None
        assert r["logical_code"] == "GB"
        assert r["number"] == 12345

    def test_special_characters(self):
        r = ScanFlowEngine.parse_filename_to_std("标准文件_GB_T_12345-2020(1).pdf")
        assert r is not None
        assert r["logical_code"] == "GB"
        assert r["number"] == 12345

    def test_empty_string(self):
        r = ScanFlowEngine.parse_filename_to_std("")
        assert r is None

    def test_none_input(self):
        r = ScanFlowEngine.parse_filename_to_std(None)
        assert r is None

    def test_not_a_string(self):
        r = ScanFlowEngine.parse_filename_to_std(12345)
        assert r is None


# ═══════════════════════════════════════════════════════════════════
# parse_pdf_header
# ═══════════════════════════════════════════════════════════════════


class TestParsePDFHeader:
    def test_standard_in_pdf_header(self):
        header = b"%PDF-1.4\n...GB/T 12345-2020...\nendobj"
        r = ScanFlowEngine.parse_pdf_header(header)
        assert r is not None
        assert r["logical_code"] == "GB/T"
        assert r["number"] == 12345
        assert r["year"] == 2020

    def test_no_standard_in_header(self):
        header = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj"
        r = ScanFlowEngine.parse_pdf_header(header)
        assert r is None

    def test_empty_bytes(self):
        r = ScanFlowEngine.parse_pdf_header(b"")
        assert r is None

    def test_none_input(self):
        r = ScanFlowEngine.parse_pdf_header(None)
        assert r is None

    def test_truncated_data(self):
        r = ScanFlowEngine.parse_pdf_header(b"%PDF-1.4\nGB")
        assert r is None

    def test_iso_in_pdf(self):
        header = b"%PDF-1.4\n...ISO 9001-2015...\ntrailer"
        r = ScanFlowEngine.parse_pdf_header(header)
        assert r is not None
        assert r["number"] == 9001
        assert r["year"] == 2015


# ═══════════════════════════════════════════════════════════════════
# filter_known_results
# ═══════════════════════════════════════════════════════════════════


class TestFilterKnown:
    def test_empty_results(self):
        r = ScanFlowEngine.filter_known_results([], {"GB/T 1"})
        assert r == []

    def test_all_known(self):
        results = [{"std_number": "GB/T 1"}, {"std_number": "GB/T 2"}]
        known = {"GB/T 1", "GB/T 2"}
        r = ScanFlowEngine.filter_known_results(results, known)
        assert r == []

    def test_partial_known(self):
        results = [{"std_number": "GB/T 1"}, {"std_number": "GB/T 2"}, {"std_number": "GB/T 3"}]
        known = {"GB/T 2"}
        r = ScanFlowEngine.filter_known_results(results, known)
        assert len(r) == 2
        assert r[0]["std_number"] == "GB/T 1"
        assert r[1]["std_number"] == "GB/T 3"

    def test_empty_known_set(self):
        results = [{"std_number": "GB/T 1"}]
        r = ScanFlowEngine.filter_known_results(results, set())
        assert r == results

    def test_none_known(self):
        results = [{"std_number": "GB/T 1"}]
        r = ScanFlowEngine.filter_known_results(results, None)
        assert r == results


# ═══════════════════════════════════════════════════════════════════
# merge_results
# ═══════════════════════════════════════════════════════════════════


class TestMergeResults:
    def test_both_empty(self):
        r = ScanFlowEngine.merge_results([], [])
        assert r == []

    def test_new_only(self):
        new = [{"std_number": "GB/T 1", "std_name": "test"}]
        r = ScanFlowEngine.merge_results([], new)
        assert len(r) == 1
        assert r[0]["std_number"] == "GB/T 1"

    def test_existing_only(self):
        existing = [{"std_number": "GB/T 1"}]
        r = ScanFlowEngine.merge_results(existing, [])
        assert r == existing

    def test_no_overlap(self):
        existing = [{"std_number": "GB/T 1"}]
        new = [{"std_number": "GB/T 2"}]
        r = ScanFlowEngine.merge_results(existing, new)
        assert len(r) == 2
        stds = {x["std_number"] for x in r}
        assert stds == {"GB/T 1", "GB/T 2"}

    def test_partial_overlap_keep_richer(self):
        existing = [{"std_number": "GB/T 1", "std_name": ""}]
        new = [{"std_number": "GB/T 1", "std_name": "丰富的名称"}]
        r = ScanFlowEngine.merge_results(existing, new)
        assert len(r) == 1
        assert r[0]["std_name"] == "丰富的名称"

    def test_partial_overlap_keep_existing_richer(self):
        existing = [{"std_number": "GB/T 1", "std_name": "已有名称"}]
        new = [{"std_number": "GB/T 1", "std_name": ""}]
        r = ScanFlowEngine.merge_results(existing, new)
        assert len(r) == 1
        assert r[0]["std_name"] == "已有名称"

    def test_full_overlap(self):
        existing = [{"std_number": "A"}, {"std_number": "B"}]
        new = [{"std_number": "A"}, {"std_number": "B"}]
        r = ScanFlowEngine.merge_results(existing, new)
        assert len(r) == 2

    def test_mixed_overlap(self):
        existing = [
            {"std_number": "GB/T 1", "std_name": ""},
            {"std_number": "GB/T 2", "std_name": "名称2"},
        ]
        new = [
            {"std_number": "GB/T 1", "std_name": "名称1"},
            {"std_number": "GB/T 3", "std_name": "名称3"},
        ]
        r = ScanFlowEngine.merge_results(existing, new)
        assert len(r) == 3
        stds = {x["std_number"] for x in r}
        assert stds == {"GB/T 1", "GB/T 2", "GB/T 3"}


# ═══════════════════════════════════════════════════════════════════
# build_scan_stats
# ═══════════════════════════════════════════════════════════════════


class TestBuildStats:
    def test_empty_results(self):
        stats = ScanFlowEngine.build_scan_stats([])
        assert stats["total"] == 0
        assert stats["success"] == 0
        assert stats["failed"] == 0
        assert stats["with_name"] == 0
        assert stats["unique_codes"] == []

    def test_all_success(self):
        results = [
            {"is_valid": True, "logical_code": "GB/T", "std_name": "n1", "std_number": "GB/T 1"},
            {"is_valid": True, "logical_code": "GB/T", "std_name": "n2", "std_number": "GB/T 2"},
        ]
        stats = ScanFlowEngine.build_scan_stats(results)
        assert stats["total"] == 2
        assert stats["success"] == 2
        assert stats["failed"] == 0
        assert stats["with_name"] == 2
        assert stats["unique_codes"] == ["GB/T"]

    def test_mixed_status(self):
        results = [
            {"is_valid": True, "logical_code": "GB", "std_name": "", "std_number": "GB 1"},
            {"is_valid": False, "logical_code": "", "std_name": "", "std_number": ""},
            {"is_valid": True, "logical_code": "ISO", "std_name": "ISO标准", "std_number": "ISO 1"},
        ]
        stats = ScanFlowEngine.build_scan_stats(results)
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failed"] == 1
        assert stats["with_name"] == 1
        assert stats["unique_codes"] == ["GB", "ISO"]

    def test_none_results(self):
        stats = ScanFlowEngine.build_scan_stats(None)
        assert stats["total"] == 0

    def test_none_items_ignored(self):
        results = [{"is_valid": True, "logical_code": "GB", "std_name": "", "std_number": "GB 1"}, None]
        stats = ScanFlowEngine.build_scan_stats(results)
        assert stats["total"] == 2
        assert stats["success"] == 1
