# tests/perf/utils.py
"""性能测试专用工具函数"""

from __future__ import annotations

from pathlib import Path


def generate_minimal_pdf(path: Path, target_size_kb: int = 100) -> Path:
    """生成指定大小的最小有效 PDF，保证 pypdf/PdfReader 可正常读取。

    通过重复 stream 对象填充至目标大小。
    """
    base_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
    )

    padding_needed = max(0, target_size_kb * 1024 - len(base_content))
    padding_line = b"% " + b"X" * 998 + b"\n"
    repeat_count = padding_needed // len(padding_line) + 1
    padding = padding_line * repeat_count

    # Insert padding before %%EOF
    content = base_content[:-7] + padding + b"%%EOF\n"
    path.write_bytes(content)
    return path
