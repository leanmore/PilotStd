"""path_guard.py — 路径遍历防护全覆盖。"""

import os
import pytest
from unittest.mock import patch

from pilotstd.core.path_guard import get_allowed_roots, validate_path_in_root


class TestGetAllowedRoots:
    def test_config_root_only(self):
        with patch("os.path.realpath", side_effect=lambda x: x), patch.dict(
            os.environ, {}, clear=True
        ):
            roots = get_allowed_roots("/library")
            assert "/library" in roots

    def test_env_var_added(self):
        with patch("os.path.realpath", side_effect=lambda x: x), patch.dict(
            os.environ, {"STANDARD_ROOT": "/extra/standards"}
        ):
            roots = get_allowed_roots("/library")
            assert "/library" in roots
            assert "/extra/standards" in roots

    def test_duplicate_deduped(self):
        with patch("os.path.realpath", side_effect=lambda x: x), patch.dict(
            os.environ, {"STANDARD_ROOT": "/library"}
        ):
            roots = get_allowed_roots("/library")
            assert roots.count("/library") == 1

    def test_docker_extra_roots_included(self):
        with patch("os.path.realpath", side_effect=lambda x: x), patch.dict(
            os.environ, {}, clear=True
        ):
            roots = get_allowed_roots("/library")
            assert "/inbox" in roots
            assert "/standards" in roots

    def test_empty_config_root(self):
        with patch("os.path.realpath", side_effect=lambda x: x), patch.dict(
            os.environ, {}, clear=True
        ):
            roots = get_allowed_roots("")
            assert "/inbox" in roots
            assert "/standards" in roots


class TestValidatePathInRoot:
    def test_path_inside_root(self):
        """路径在根内 → 返回规范化路径。"""
        sep = os.sep
        with patch("os.path.realpath", side_effect=lambda x: x.replace("/", sep)):
            result = validate_path_in_root("/library/sub/file.pdf", "/library")
            assert "library" in result

    def test_path_equals_root(self):
        with patch("os.path.realpath", side_effect=lambda x: x):
            result = validate_path_in_root("/library", "/library")
            assert result == "/library"

    def test_path_outside_root_raises(self):
        sep = os.sep
        with patch("os.path.realpath", side_effect=lambda x: x.replace("/", sep)):
            with pytest.raises(ValueError, match="路径越界"):
                validate_path_in_root("/escape/file.pdf", "/library")
