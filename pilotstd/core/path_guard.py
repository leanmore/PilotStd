# pilotstd/core/path_guard.py — 路径遍历防护统一校验函数
import os


def validate_path_in_root(path: str, root: str) -> str:
    """校验 path 解析后的真实路径在 root 范围内，否则 raise ValueError。

    返回 path 的规范化绝对路径。
    用于下载引擎、扫描器等需要确保写入路径不越界的场景。
    """
    real_path = os.path.realpath(path)
    real_root = os.path.realpath(root)
    if not real_path.startswith(real_root + os.sep) and real_path != real_root:
        raise ValueError(f"路径越界，拒绝写入: {path}")
    return real_path
