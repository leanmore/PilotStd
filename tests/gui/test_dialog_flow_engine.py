# tests/gui/test_dialog_flow_engine.py
"""DialogFlowEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 3 个静态方法的：正常路径、边界值、异常容错。
"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.dialog_flow_engine import DialogFlowEngine


@pytest.fixture
def engine() -> DialogFlowEngine:
    return DialogFlowEngine()


# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_label_to_task_type_keys(self):
        m = DialogFlowEngine.LABEL_TO_TASK_TYPE
        assert m["扫描"] == "SCAN"
        assert m["查询"] == "QUERY"
        assert m["下载"] == "DOWNLOAD"
        assert m["规范化"] == "ORGANIZE"

    def test_default_task_type(self):
        assert DialogFlowEngine.DEFAULT_TASK_TYPE == "SCAN"


# ═══════════════════════════════════════════════════════════════════
# get_task_type_name
# ═══════════════════════════════════════════════════════════════════


class TestGetTaskTypeName:
    def test_known_labels(self, engine):
        assert engine.get_task_type_name("扫描") == "SCAN"
        assert engine.get_task_type_name("查询") == "QUERY"
        assert engine.get_task_type_name("下载") == "DOWNLOAD"
        assert engine.get_task_type_name("规范化") == "ORGANIZE"

    def test_unknown_label_returns_default(self, engine):
        assert engine.get_task_type_name("未知任务") == "SCAN"

    def test_empty_string(self, engine):
        assert engine.get_task_type_name("") == "SCAN"

    def test_none(self, engine):
        assert engine.get_task_type_name(None) == "SCAN"  # type: ignore[arg-type]

    def test_int(self, engine):
        assert engine.get_task_type_name(123) == "SCAN"  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════
# validate_task_params
# ═══════════════════════════════════════════════════════════════════


class TestValidateTaskParams:
    def test_normal(self, engine):
        result = engine.validate_task_params("查询", 100, 95, 5)
        assert result["is_valid"] is True
        assert result["label"] == "查询"
        assert result["total"] == 100
        assert result["completed"] == 95
        assert result["failed"] == 5
        assert result["type_name"] == "QUERY"
        assert result["errors"] == []

    def test_default_failed(self, engine):
        result = engine.validate_task_params("下载", 50, 50)
        assert result["is_valid"] is True
        assert result["failed"] == 0

    def test_negative_total(self, engine):
        result = engine.validate_task_params("扫描", -1, 0, 0)
        assert result["is_valid"] is False
        assert len(result["errors"]) >= 1
        assert result["total"] == 0  # 标准化为 0

    def test_negative_completed(self, engine):
        result = engine.validate_task_params("查询", 10, -5, 0)
        assert result["is_valid"] is False
        assert result["completed"] == 0

    def test_negative_failed(self, engine):
        result = engine.validate_task_params("下载", 10, 10, -3)
        assert result["is_valid"] is False
        assert result["failed"] == 0

    def test_all_negative(self, engine):
        result = engine.validate_task_params("扫描", -1, -2, -3)
        assert result["is_valid"] is False
        assert len(result["errors"]) == 3

    def test_empty_label(self, engine):
        result = engine.validate_task_params("", 10, 5, 0)
        assert result["is_valid"] is False
        assert "标签" in result["errors"][0]

    def test_whitespace_label(self, engine):
        result = engine.validate_task_params("   ", 10, 5, 0)
        assert result["is_valid"] is False

    def test_none_label(self, engine):
        result = engine.validate_task_params(None, 10, 5, 0)  # type: ignore[arg-type]
        assert result["is_valid"] is False

    def test_non_int_total(self, engine):
        result = engine.validate_task_params("查询", "abc", 5, 0)  # type: ignore[arg-type]
        assert result["is_valid"] is False
        assert result["total"] == 0

    def test_zero_values(self, engine):
        result = engine.validate_task_params("扫描", 0, 0, 0)
        assert result["is_valid"] is True
        assert result["total"] == 0

    def test_unknown_label_type_name(self, engine):
        result = engine.validate_task_params("其他", 10, 5, 0)
        assert result["is_valid"] is True
        assert result["type_name"] == "SCAN"  # 默认

    def test_non_str_label_type_name(self, engine):
        result = engine.validate_task_params(999, 10, 5, 0)  # type: ignore[arg-type]
        assert result["type_name"] == "SCAN"

    def test_large_values(self, engine):
        result = engine.validate_task_params("查询", 1000000, 999999, 1)
        assert result["is_valid"] is True


# ═══════════════════════════════════════════════════════════════════
# format_task_error
# ═══════════════════════════════════════════════════════════════════


class TestFormatTaskError:
    def test_normal(self, engine):
        result = engine.format_task_error("数据库连接失败")
        assert "任务记录失败" in result
        assert "数据库连接失败" in result

    def test_empty_message(self, engine):
        result = engine.format_task_error("")
        assert "任务记录失败" in result

    def test_none_message(self, engine):
        result = engine.format_task_error(None)  # type: ignore[arg-type]
        assert "任务记录失败" in result
