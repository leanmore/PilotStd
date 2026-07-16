# tests/gui/test_project_flow_engine.py
"""ProjectFlowEngine 单元测试 — 纯 Python，不启动 QApplication。"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.project_flow_engine import ProjectFlowEngine


@pytest.fixture
def engine() -> ProjectFlowEngine:
    return ProjectFlowEngine()


# ═══════════════════════════════════════════════════════════════════
# serialize_project_state
# ═══════════════════════════════════════════════════════════════════


class TestSerializeProjectState:
    def test_normal(self, engine):
        data = {
            "work_table_rows": [{"seq": 1}],
            "current_path": "/data",
            "unrecognized_files": ["/tmp/x.pdf"],
        }
        result = engine.serialize_project_state(data)
        assert result["work_table_rows"] == [{"seq": 1}]
        assert result["current_path"] == "/data"
        assert result["unrecognized_files"] == ["/tmp/x.pdf"]

    def test_missing_keys_filled(self, engine):
        result = engine.serialize_project_state({})
        assert result == {"work_table_rows": [], "current_path": "", "unrecognized_files": []}

    def test_none_returns_defaults(self, engine):
        result = engine.serialize_project_state(None)  # type: ignore[arg-type]
        assert result["work_table_rows"] == []
        assert result["current_path"] == ""
        assert result["unrecognized_files"] == []

    def test_partial_data(self, engine):
        result = engine.serialize_project_state({"current_path": "/tmp"})
        assert result["current_path"] == "/tmp"
        assert result["work_table_rows"] == []
        assert result["unrecognized_files"] == []

    def test_extra_keys_stripped(self, engine):
        """额外键不出现在输出中。"""
        result = engine.serialize_project_state({"extra": "value", "current_path": "/x"})
        assert "extra" not in result
        assert result["current_path"] == "/x"


# ═══════════════════════════════════════════════════════════════════
# deserialize_project_state
# ═══════════════════════════════════════════════════════════════════


class TestDeserializeProjectState:
    def test_normal(self, engine):
        data = {"work_table_rows": [{"a": 1}], "current_path": "/p", "unrecognized_files": []}
        result = engine.deserialize_project_state(data)
        assert result["work_table_rows"] == [{"a": 1}]

    def test_empty_returns_defaults(self, engine):
        result = engine.deserialize_project_state({})
        assert result["work_table_rows"] == []

    def test_none_returns_defaults(self, engine):
        result = engine.deserialize_project_state(None)  # type: ignore[arg-type]
        assert result["current_path"] == ""


# ═══════════════════════════════════════════════════════════════════
# validate_project_path
# ═══════════════════════════════════════════════════════════════════


class TestValidateProjectPath:
    def test_normal(self, engine):
        assert engine.validate_project_path("/data/project.pilotstd") is True

    def test_windows_path(self, engine):
        assert engine.validate_project_path("C:\\Users\\test\\project.pilotstd") is True

    def test_empty_string(self, engine):
        assert engine.validate_project_path("") is False

    def test_whitespace_only(self, engine):
        assert engine.validate_project_path("   ") is False

    def test_none(self, engine):
        assert engine.validate_project_path(None) is False  # type: ignore[arg-type]

    def test_null_byte(self, engine):
        assert engine.validate_project_path("good.pdf\x00evil.exe") is False

    def test_path_traversal(self, engine):
        assert engine.validate_project_path("../../../etc/passwd") is False

    def test_path_too_long(self, engine):
        assert engine.validate_project_path("x" * 5000 + ".pilotstd") is False

    def test_relative_path(self, engine):
        assert engine.validate_project_path("project.pilotstd") is True

    def test_unicode_path(self, engine):
        assert engine.validate_project_path("/数据/项目.pilotstd") is True
