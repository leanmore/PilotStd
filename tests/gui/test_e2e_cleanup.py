# tests/gui/test_e2e_cleanup.py
"""E2E 测试 — CleanupHandler 核心路径。"""

from __future__ import annotations

import os

import pytest


@pytest.mark.e2e
def test_scan_empty_dirs_finds_empty(window, qtbot, tmp_path):
    """scan_empty_dirs: 扫描包含空目录的文件夹 → 返回空目录列表。"""
    # 创建目录结构：root / empty_A / empty_B / non_empty /
    empty_a = tmp_path / "empty_A"
    empty_a.mkdir()
    empty_b = tmp_path / "empty_B"
    empty_b.mkdir()
    non_empty = tmp_path / "non_empty"
    non_empty.mkdir()
    (non_empty / "file.txt").write_text("data")

    handler = window._core.cleanup
    empty_dirs, expire_only, expire_folder = handler.scan_empty_dirs(str(tmp_path))

    assert len(empty_dirs) == 2, f"应有 2 个空目录, 实际 {len(empty_dirs)}"
    paths = [os.path.basename(d) for d in empty_dirs]
    assert "empty_A" in paths
    assert "empty_B" in paths
    assert expire_only == []


@pytest.mark.e2e
def test_scan_empty_dirs_detects_expire_only(window, qtbot, tmp_path):
    """scan_empty_dirs: 目录仅含过期文件夹 → 归入 expire_only。"""
    expire_name = "过期作废"
    std_dir = tmp_path / "GB 1"
    std_dir.mkdir()
    expire_dir = std_dir / expire_name
    expire_dir.mkdir()

    handler = window._core.cleanup
    # 设置配置中的过期文件夹名
    window._config.set("storage.expire_folder", expire_name)
    empty_dirs, expire_only, folder = handler.scan_empty_dirs(str(tmp_path))

    assert len(expire_only) == 1, f"应有 1 个仅含过期目录, 实际 {len(expire_only)}"
    assert os.path.basename(expire_only[0]) == "GB 1"
    assert folder == expire_name
    assert empty_dirs == []
