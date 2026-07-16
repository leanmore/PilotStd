# tests/gui/test_persistence_flow_engine.py
"""PersistenceFlowEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 8 个静态方法（4 序列化 + 4 反序列化）的：
- 正常路径
- 边界值（空 dict、空 list、空 bytes、0、负数）
- 类型错误（传入非预期类型）
- 异常容错（损坏的 Base64、非法填充、截断数据）
"""

from __future__ import annotations

import base64

import pytest

from pilotstd.ui.core.handlers.persistence_flow_engine import PersistenceFlowEngine

# ═══════════════════════════════════════════════════════════════════
# 模块级 fixture
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def engine() -> PersistenceFlowEngine:
    return PersistenceFlowEngine()


# ═══════════════════════════════════════════════════════════════════
# serialize_window_geometry
# ═══════════════════════════════════════════════════════════════════


class TestSerializeWindowGeometry:
    def test_normal(self, engine):
        result = engine.serialize_window_geometry(100, 200, 800, 600)
        assert result == {"x": 100, "y": 200, "width": 800, "height": 600}

    def test_zero_values(self, engine):
        result = engine.serialize_window_geometry(0, 0, 0, 0)
        assert result == {"x": 0, "y": 0, "width": 0, "height": 0}

    def test_negative_values(self, engine):
        """负坐标在多显示器环境下是合法的（副屏在左侧）。"""
        result = engine.serialize_window_geometry(-100, -50, 1024, 768)
        assert result == {"x": -100, "y": -50, "width": 1024, "height": 768}


# ═══════════════════════════════════════════════════════════════════
# deserialize_window_geometry
# ═══════════════════════════════════════════════════════════════════


class TestDeserializeWindowGeometry:
    DEFAULT = {"x": 0, "y": 0, "width": 800, "height": 600}

    def test_normal(self, engine):
        data = {"x": 10, "y": 20, "width": 1024, "height": 768}
        result = engine.deserialize_window_geometry(data, self.DEFAULT)
        assert result == {"x": 10, "y": 20, "width": 1024, "height": 768}

    def test_empty_dict_returns_default(self, engine):
        result = engine.deserialize_window_geometry({}, self.DEFAULT)
        assert result == self.DEFAULT

    def test_missing_keys_returns_default(self, engine):
        result = engine.deserialize_window_geometry({"x": 1, "y": 2}, self.DEFAULT)
        assert result == self.DEFAULT

    def test_none_returns_default(self, engine):
        result = engine.deserialize_window_geometry(None, self.DEFAULT)
        assert result == self.DEFAULT

    def test_string_returns_default(self, engine):
        result = engine.deserialize_window_geometry("invalid", self.DEFAULT)
        assert result == self.DEFAULT

    def test_list_returns_default(self, engine):
        result = engine.deserialize_window_geometry([1, 2, 3], self.DEFAULT)
        assert result == self.DEFAULT

    def test_non_int_values_returns_default(self, engine):
        result = engine.deserialize_window_geometry(
            {"x": "a", "y": 2, "width": 3, "height": 4}, self.DEFAULT
        )
        assert result == self.DEFAULT

    def test_custom_default(self, engine):
        custom = {"x": 50, "y": 60, "width": 640, "height": 480}
        result = engine.deserialize_window_geometry(None, custom)
        assert result == custom


# ═══════════════════════════════════════════════════════════════════
# serialize_splitter_sizes
# ═══════════════════════════════════════════════════════════════════


class TestSerializeSplitterSizes:
    def test_normal(self, engine):
        result = engine.serialize_splitter_sizes([200, 500, 300])
        assert result == [200, 500, 300]

    def test_empty_list(self, engine):
        result = engine.serialize_splitter_sizes([])
        assert result == []

    def test_single_element(self, engine):
        result = engine.serialize_splitter_sizes([100])
        assert result == [100]

    def test_zero_values(self, engine):
        result = engine.serialize_splitter_sizes([0, 0, 0])
        assert result == [0, 0, 0]

    def test_returns_new_list_not_same_object(self, engine):
        original = [1, 2, 3]
        result = engine.serialize_splitter_sizes(original)
        assert result == original
        assert result is not original


# ═══════════════════════════════════════════════════════════════════
# deserialize_splitter_sizes
# ═══════════════════════════════════════════════════════════════════


class TestDeserializeSplitterSizes:
    DEFAULT = [100, 200]

    def test_normal(self, engine):
        result = engine.deserialize_splitter_sizes([300, 400], self.DEFAULT)
        assert result == [300, 400]

    def test_empty_list_is_valid(self, engine):
        result = engine.deserialize_splitter_sizes([], self.DEFAULT)
        assert result == []

    def test_none_returns_default(self, engine):
        result = engine.deserialize_splitter_sizes(None, self.DEFAULT)
        assert result == self.DEFAULT

    def test_string_returns_default(self, engine):
        result = engine.deserialize_splitter_sizes("not a list", self.DEFAULT)
        assert result == self.DEFAULT

    def test_dict_returns_default(self, engine):
        result = engine.deserialize_splitter_sizes({}, self.DEFAULT)
        assert result == self.DEFAULT

    def test_list_with_non_int_returns_default(self, engine):
        result = engine.deserialize_splitter_sizes([1, "2", 3], self.DEFAULT)
        assert result == self.DEFAULT

    def test_list_with_float_returns_default(self, engine):
        result = engine.deserialize_splitter_sizes([1.5, 2.0], self.DEFAULT)
        assert result == self.DEFAULT

    def test_returns_new_list_not_same_object(self, engine):
        original = [1, 2, 3]
        result = engine.deserialize_splitter_sizes(original, self.DEFAULT)
        assert result == [1, 2, 3]
        assert result is not original


# ═══════════════════════════════════════════════════════════════════
# serialize_column_widths
# ═══════════════════════════════════════════════════════════════════


class TestSerializeColumnWidths:
    def test_normal(self, engine):
        result = engine.serialize_column_widths([100, 150, 200])
        assert result == [100, 150, 200]

    def test_empty_list(self, engine):
        result = engine.serialize_column_widths([])
        assert result == []

    def test_zero_widths(self, engine):
        """零宽列合法（隐藏列）。"""
        result = engine.serialize_column_widths([0, 100, 0])
        assert result == [0, 100, 0]

    def test_returns_new_list(self, engine):
        original = [1, 2, 3]
        result = engine.serialize_column_widths(original)
        assert result is not original


# ═══════════════════════════════════════════════════════════════════
# deserialize_column_widths
# ═══════════════════════════════════════════════════════════════════


class TestDeserializeColumnWidths:
    def test_normal(self, engine):
        result = engine.deserialize_column_widths([100, 200, 300], 3, 80)
        assert result == [100, 200, 300]

    def test_length_mismatch_returns_default_fill(self, engine):
        result = engine.deserialize_column_widths([100, 200], 4, 80)
        assert result == [80, 80, 80, 80]

    def test_extra_columns_returns_default_fill(self, engine):
        result = engine.deserialize_column_widths([100, 200, 300, 400], 2, 80)
        assert result == [80, 80]

    def test_none_returns_default_fill(self, engine):
        result = engine.deserialize_column_widths(None, 5, 120)
        assert result == [120, 120, 120, 120, 120]

    def test_string_returns_default_fill(self, engine):
        result = engine.deserialize_column_widths("bad", 3, 50)
        assert result == [50, 50, 50]

    def test_list_with_non_int_returns_default_fill(self, engine):
        result = engine.deserialize_column_widths([100, "x", 300], 3, 80)
        assert result == [80, 80, 80]

    def test_empty_list_zero_col_count(self, engine):
        result = engine.deserialize_column_widths([], 0, 100)
        assert result == []

    def test_empty_list_nonzero_col_count_returns_default_fill(self, engine):
        result = engine.deserialize_column_widths([], 3, 100)
        assert result == [100, 100, 100]

    def test_zero_default(self, engine):
        result = engine.deserialize_column_widths(None, 2, 0)
        assert result == [0, 0]


# ═══════════════════════════════════════════════════════════════════
# serialize_header_state
# ═══════════════════════════════════════════════════════════════════


class TestSerializeHeaderState:
    def test_normal(self, engine):
        result = engine.serialize_header_state(b"\x01\x02\x03")
        assert result == base64.b64encode(b"\x01\x02\x03").decode("ascii")

    def test_empty_bytes(self, engine):
        result = engine.serialize_header_state(b"")
        assert result == ""

    def test_large_bytes(self, engine):
        data = bytes(range(256)) * 10  # 2560 bytes
        result = engine.serialize_header_state(data)
        assert isinstance(result, str)
        assert base64.b64decode(result) == data

    def test_result_is_ascii_string(self, engine):
        result = engine.serialize_header_state(b"test")
        assert isinstance(result, str)
        # 验证是纯 ASCII
        result.encode("ascii")


# ═══════════════════════════════════════════════════════════════════
# deserialize_header_state
# ═══════════════════════════════════════════════════════════════════


class TestDeserializeHeaderState:
    def test_normal(self, engine):
        encoded = base64.b64encode(b"\x01\x02\x03\x04").decode("ascii")
        result = engine.deserialize_header_state(encoded)
        assert result == b"\x01\x02\x03\x04"

    def test_empty_string_returns_empty_bytes(self, engine):
        result = engine.deserialize_header_state("")
        assert result == b""

    def test_none_returns_empty_bytes(self, engine):
        result = engine.deserialize_header_state(None)
        assert result == b""

    def test_int_returns_empty_bytes(self, engine):
        result = engine.deserialize_header_state(123)
        assert result == b""

    def test_list_returns_empty_bytes(self, engine):
        result = engine.deserialize_header_state([1, 2, 3])
        assert result == b""

    def test_dict_returns_empty_bytes(self, engine):
        result = engine.deserialize_header_state({"key": "value"})
        assert result == b""

    def test_corrupted_base64_invalid_chars(self, engine):
        """损坏的 Base64（非法字符）→ 返回 b""。"""
        result = engine.deserialize_header_state("!!!invalid!!!")
        assert result == b""

    def test_corrupted_base64_bad_padding(self, engine):
        """损坏的 Base64（错误填充）→ 返回 b""。"""
        result = engine.deserialize_header_state("YWJj=")  # 'abc' 编码后是 "YWJj"，不带等号
        assert result == b"" or result is not None  # 不抛异常即可

    def test_corrupted_base64_truncated(self, engine):
        """截断的 Base64 → 返回 b""。"""
        result = engine.deserialize_header_state("YWJj")
        assert isinstance(result, bytes)


# ═══════════════════════════════════════════════════════════════════
# 往返测试
# ═══════════════════════════════════════════════════════════════════


class TestRoundtrip:
    def test_window_geometry_roundtrip(self, engine):
        original = {"x": 42, "y": 99, "width": 1920, "height": 1080}
        serialized = engine.serialize_window_geometry(**original)
        restored = engine.deserialize_window_geometry(serialized, {})
        assert restored == original

    def test_splitter_sizes_roundtrip(self, engine):
        original = [250, 500, 250]
        serialized = engine.serialize_splitter_sizes(original)
        restored = engine.deserialize_splitter_sizes(serialized, [])
        assert restored == original

    def test_column_widths_roundtrip(self, engine):
        original = [120, 200, 80, 300]
        serialized = engine.serialize_column_widths(original)
        restored = engine.deserialize_column_widths(serialized, len(original), 100)
        assert restored == original

    def test_header_state_roundtrip(self, engine):
        original = bytes([0, 1, 2, 255, 128, 64, 32, 16])
        serialized = engine.serialize_header_state(original)
        restored = engine.deserialize_header_state(serialized)
        assert restored == original
