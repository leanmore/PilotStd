# tests/perf/test_perf_baselines.py
"""性能回归基线——只记录不设卡，人工审阅趋势。

运行: pytest tests/perf/ -v
基线写入: .perf-baseline.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.perf.conftest import perf_benchmark


BASELINE_FILE = Path(".perf-baseline.json")


def _write_baseline(key: str, result: dict) -> None:
    baseline = {}
    if BASELINE_FILE.exists():
        baseline = json.loads(BASELINE_FILE.read_text())
    baseline[key] = result
    BASELINE_FILE.write_text(json.dumps(baseline, indent=2, ensure_ascii=False))


class TestPureLogicPerf:
    """纯逻辑函数性能基线"""

    def test_parse_cookie_string_perf(self):
        """Cookie 字符串解析延迟"""
        from pilotstd.wechat_ip.logic import parse_cookie_string

        cookie = "session=abc123; token=xyz789; user=test"
        result = perf_benchmark(parse_cookie_string, cookie, n=100)
        _write_baseline("parse_cookie_string", result)
        print(f"\n📊 parse_cookie_string: median={result['median']}s p95={result['p95']}s (n=100)")

    def test_merge_ip_list_perf(self):
        """IP 列表合并延迟"""
        from pilotstd.wechat_ip.logic import merge_ip_list

        result = perf_benchmark(merge_ip_list, "1.2.3.4;5.6.7.8;9.10.11.12", "13.14.15.16", n=200)
        _write_baseline("merge_ip_list", result)
        print(f"\n📊 merge_ip_list: median={result['median']}s p95={result['p95']}s (n=200)")

    def test_parse_app_urls_perf(self):
        """URL 列表解析延迟"""
        from pilotstd.wechat_ip.logic import parse_app_urls

        urls = "https://a.com, https://b.com, https://c.com, https://d.com, https://e.com"
        result = perf_benchmark(parse_app_urls, urls, n=200)
        _write_baseline("parse_app_urls", result)
        print(f"\n📊 parse_app_urls: median={result['median']}s p95={result['p95']}s (n=200)")


class TestPdfGenPerf:
    """PDF 生成工具性能基线"""

    def test_generate_100kb_pdf(self, tmp_path: Path):
        """~100KB PDF 生成延迟"""
        from tests.perf.utils import generate_minimal_pdf

        path = tmp_path / "test.pdf"

        def _gen():
            generate_minimal_pdf(path, target_size_kb=100)

        result = perf_benchmark(_gen, n=10)
        _write_baseline("pdf_gen_100kb", result)
        print(f"\n📊 pdf_gen_100kb: median={result['median']}s p95={result['p95']}s (n=10)")

    def test_generate_800kb_pdf(self, tmp_path: Path):
        """~800KB PDF 生成延迟"""
        from tests.perf.utils import generate_minimal_pdf

        path = tmp_path / "test.pdf"

        def _gen():
            generate_minimal_pdf(path, target_size_kb=800)

        result = perf_benchmark(_gen, n=10)
        _write_baseline("pdf_gen_800kb", result)
        print(f"\n📊 pdf_gen_800kb: median={result['median']}s p95={result['p95']}s (n=10)")
