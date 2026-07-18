# tests/fixtures/workspace_fixture.py
"""文件系统隔离夹具 — 提供临时工作空间，自动清理。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_workspace() -> str:
    """创建临时工作空间目录，测试结束后自动清理。

    用法:
        def test_file_operation(temp_workspace):
            src = os.path.join(temp_workspace, "src.txt")
            with open(src, "w") as f:
                f.write("content")
    """
    tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def temp_workspace_with_files(temp_workspace: str) -> dict[str, str]:
    """在临时工作空间中预置标准测试文件结构。

    返回 {"root": 工作空间路径, "files": [文件路径列表]}

    用法:
        def test_scan(temp_workspace_with_files):
            root = temp_workspace_with_files["root"]
    """
    root = Path(temp_workspace)

    # 创建测试文件结构
    files = [
        "GB_T 1.1-2020 标准化工作导则.pdf",
        "ISO 9001-2015 Quality Management.pdf",
        "subdir/DIN EN 1092.1-2018 Flanges.pdf",
        "subdir/expired/BS EN ISO 16852-2016.pdf",
    ]
    created = []
    for f in files:
        full = root / f
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("test content", encoding="utf-8")
        created.append(str(full))

    return {"root": str(root), "files": created}
