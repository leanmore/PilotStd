# pilotstd/ui/core/handlers/file_tree_flow_engine.py
"""FileTreeFlowEngine — 文件树纯逻辑引擎（零 Qt 依赖，零文件 I/O）。

路径过滤、节点状态计算、扁平化转换。
不依赖 QTreeWidgetItem / os.scandir 等副作用模块。
"""

from __future__ import annotations

from typing import Any


class FileTreeFlowEngine:
    """文件树相关纯静态方法集合。"""

    @staticmethod
    def filter_by_extensions(paths: list[str], allowed_exts: list[str] | None = None) -> list[str]:
        """按扩展名白名单过滤路径列表。

        allowed_exts 为 None/空时返回全部。
        扩展名匹配不区分大小写，自动去除前导点。
        """
        if not allowed_exts:
            return list(paths)
        # 统一转小写并去除前导点，确保匹配一致
        lower_exts = {e.lower().lstrip(".") for e in allowed_exts}
        return [p for p in paths if "." in p and p.rsplit(".", 1)[-1].lower() in lower_exts]

    @staticmethod
    def compute_node_check_state(children_states: list[int]) -> int:
        """根据子节点勾选状态计算父节点三态值。

        返回: 0=全未选, 1=全选, 2=部分选
        （对应 Qt.Unchecked / Checked / PartiallyChecked）
        """
        if not children_states:
            return 0
        unique = set(children_states)
        if unique == {1}:
            return 1  # 全选
        if unique == {0}:
            return 0  # 全未选
        return 2  # 混合或部分选中

    @staticmethod
    def flatten_tree(nodes: list[dict[str, Any]], children_key: str = "children") -> list[dict[str, Any]]:
        """将嵌套树结构扁平化为列表（深度优先）。

        每个节点去除 children_key 避免循环引用。
        """
        result: list[dict[str, Any]] = []

        def _walk(items: list[dict[str, Any]]) -> None:
            """递归遍历嵌套树节点，深度优先。"""
            for node in items:
                flat = {k: v for k, v in node.items() if k != children_key}
                result.append(flat)
                kids = node.get(children_key)
                if kids:
                    _walk(kids)

        _walk(nodes)
        return result

    @staticmethod
    def build_path_index(flat_nodes: list[dict[str, Any]], path_key: str = "path") -> dict[str, dict[str, Any]]:
        """从扁平节点列表构建 path -> node 的快速查找索引。

        重复路径以最后一次出现为准。缺失 path_key 的节点被跳过。
        """
        # 字典推导式：path_key 存在则纳入索引，重复键后者覆盖前者
        return {node[path_key]: node for node in flat_nodes if path_key in node}
