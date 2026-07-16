# pilotstd/ui/core/handlers/cleanup_flow_engine.py
"""CleanupFlowEngine — 清理相关的纯逻辑层（零 Qt 依赖，纯内存操作）。

空目录检测和未识别文件分类的纯逻辑提取。
dir_tree 由 Handler 通过 os.scandir 构建后传入，Engine 不做文件系统 I/O。
"""

from __future__ import annotations

from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────
DEFAULT_EXCLUDE_PATTERNS: list[str] = [".DS_Store", "Thumbs.db"]
"""默认排除的文件名模式（系统垃圾文件），不视为有效子项。"""
DEFAULT_EXPIRE_FOLDER = "过期作废"
MAX_DEPTH = 1000


class CleanupFlowEngine:
    """清理流程的纯逻辑处理：空目录检测、未识别文件分类。"""

    # ═══════════════════════════════════════════════════════════════
    # 空目录扫描（纯内存分析）
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def scan_empty_dirs(
        dir_tree: dict[str, list[str]],
        exclude_patterns: list[str] | None = None,
        expire_folder_name: str = DEFAULT_EXPIRE_FOLDER,
    ) -> tuple[list[str], list[str]]:
        """纯内存分析：从目录树中识别空目录和仅含过期文件夹的目录。

        Args:
            dir_tree: {目录路径: [子项名称列表]}。子项名称不含路径，仅为 basename。
            exclude_patterns: 排除的文件名列表（如系统垃圾文件），匹配到的子项不计入。
            expire_folder_name: 过期文件夹名称。

        Returns:
            (empty_dirs, expire_only):
              empty_dirs — 排除无关项后无任何子项的目录路径列表
              expire_only — 排除无关项后仅剩一个子项且其名称等于 expire_folder_name 的目录
        """
        if exclude_patterns is None:
            exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

        if not isinstance(dir_tree, dict):
            return [], []

        exclude_set = frozenset(exclude_patterns)
        empty_dirs: list[str] = []
        expire_only: list[str] = []

        for dir_path, children in dir_tree.items():
            if not isinstance(children, list):
                continue
            remaining = [c for c in children if c not in exclude_set]
            if not remaining:
                empty_dirs.append(dir_path)
            elif len(remaining) == 1 and remaining[0] == expire_folder_name:
                expire_only.append(dir_path)

        return empty_dirs, expire_only

    # ═══════════════════════════════════════════════════════════════
    # 未识别文件按后缀分组
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def build_unrecognized_tree(
        files: list[str],
        known_extensions: set[str] | None = None,
    ) -> dict[str, list[str]]:
        """将文件列表按后缀分组，可选排除已知扩展名。

        Args:
            files: 文件完整路径列表
            known_extensions: 已知扩展名集合（含点号，如 {".pdf", ".doc"}），
                              此集合内的文件不归入未识别分组。

        Returns:
            {后缀: [文件路径列表]}，按键（后缀）字母序排列。
            后缀统一为小写，如 ".pdf"、".txt"。
        """
        if not isinstance(files, list):
            return {}

        known = known_extensions or set()
        grouped: dict[str, list[str]] = {}

        for fpath in files:
            if not isinstance(fpath, str):
                continue
            suffix = Path(fpath).suffix.lower()
            if known and suffix in known:
                continue
            if suffix not in grouped:
                grouped[suffix] = []
            grouped[suffix].append(fpath)

        return dict(sorted(grouped.items()))
