# tests/gui/test_file_tree_flow_engine.py
"""FileTreeFlowEngine 单元测试 — 纯 Python，不启动 QApplication。

覆盖 4 个静态方法的全分支 + 边界值。
"""

from __future__ import annotations

import pytest

from pilotstd.ui.core.handlers.file_tree_flow_engine import FileTreeFlowEngine


@pytest.fixture
def engine() -> FileTreeFlowEngine:
    return FileTreeFlowEngine()


class TestFilterByExtensions:
    def test_none_returns_all(self, engine):
        assert engine.filter_by_extensions(["a.txt", "b.pdf"], None) == ["a.txt", "b.pdf"]

    def test_empty_returns_all(self, engine):
        assert engine.filter_by_extensions(["a.txt"], []) == ["a.txt"]

    def test_case_insensitive_match(self, engine):
        result = engine.filter_by_extensions(["A.TXT", "b.Pdf", "c.md"], ["txt", "PDF"])
        assert result == ["A.TXT", "b.Pdf"]

    def test_no_extension_excluded(self, engine):
        result = engine.filter_by_extensions(["README", "a.txt"], ["txt"])
        assert result == ["a.txt"]

    def test_dot_prefix_stripped(self, engine):
        result = engine.filter_by_extensions(["a.txt"], [".txt"])
        assert result == ["a.txt"]


class TestComputeNodeCheckState:
    def test_all_checked(self, engine):
        assert engine.compute_node_check_state([1, 1, 1]) == 1

    def test_all_unchecked(self, engine):
        assert engine.compute_node_check_state([0, 0]) == 0

    def test_partial(self, engine):
        assert engine.compute_node_check_state([0, 1]) == 2

    def test_partial_with_already_partial_child(self, engine):
        assert engine.compute_node_check_state([0, 2]) == 2

    def test_empty_children(self, engine):
        assert engine.compute_node_check_state([]) == 0


class TestFlattenTree:
    def test_single_level(self, engine):
        nodes = [{"name": "a"}, {"name": "b"}]
        flat = engine.flatten_tree(nodes)
        assert len(flat) == 2
        assert all("children" not in n for n in flat)

    def test_nested(self, engine):
        nodes = [
            {
                "name": "root",
                "children": [
                    {"name": "child1"},
                    {"name": "child2", "children": [{"name": "grandchild"}]},
                ],
            }
        ]
        flat = engine.flatten_tree(nodes)
        names = [n["name"] for n in flat]
        assert names == ["root", "child1", "child2", "grandchild"]

    def test_empty_input(self, engine):
        assert engine.flatten_tree([]) == []


class TestBuildPathIndex:
    def test_basic_index(self, engine):
        nodes = [{"path": "/a", "id": 1}, {"path": "/b", "id": 2}]
        idx = engine.build_path_index(nodes)
        assert idx["/a"]["id"] == 1
        assert idx["/b"]["id"] == 2

    def test_duplicate_last_wins(self, engine):
        nodes = [{"path": "/a", "v": 1}, {"path": "/a", "v": 2}]
        idx = engine.build_path_index(nodes)
        assert idx["/a"]["v"] == 2

    def test_missing_path_key_skipped(self, engine):
        nodes = [{"name": "no_path"}, {"path": "/ok"}]
        idx = engine.build_path_index(nodes)
        assert len(idx) == 1
        assert "/ok" in idx
