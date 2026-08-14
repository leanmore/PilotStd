# tests/perf/conftest.py
"""性能测试公共 fixture 与采样工具"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import pytest

from tests.perf.utils import generate_minimal_pdf

# ── Fixtures ──────────────────────────────────────────


@pytest.fixture
def perf_sample_pdf(tmp_path: Path) -> Path:
    """~100KB 测试 PDF，专用于性能基线"""
    return generate_minimal_pdf(tmp_path / "perf_sample.pdf", target_size_kb=100)


@pytest.fixture
def perf_ocr_pdf(tmp_path: Path) -> Path:
    """~800KB 测试 PDF，用于 OCR 性能基线"""
    return generate_minimal_pdf(tmp_path / "perf_ocr_sample.pdf", target_size_kb=800)


# ── 采样工具 ──────────────────────────────────────────


def perf_benchmark(fn, *args, n: int = 5, **kwargs) -> dict:
    """执行 fn n 次，返回 {median, p95, samples}。

    使用 perf_counter 确保高精度计时。
    """
    samples: list[float] = []
    for _ in range(n):
        start = time.perf_counter()
        fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        samples.append(elapsed)

    sorted_samples = sorted(samples)
    p95_idx = min(int(n * 0.95), n - 1)

    return {
        "median": round(statistics.median(sorted_samples), 4),
        "p95": round(sorted_samples[p95_idx], 4),
        "samples": [round(s, 4) for s in sorted_samples],
        "n": n,
    }
