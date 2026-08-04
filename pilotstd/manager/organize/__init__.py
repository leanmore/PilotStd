# pilotstd/manager/organize/__init__.py
# 归类服务 — 从 organizer_service.py 拆分为 4 个子模块

from typing import Any

from ._utils import _is_word_or_template, _resolve_industry_in_path
from .expire import merge_expire_from_source as _merge_expire_from_source
from .mirror import OrganizerMirror
from .organizer import OrganizerCore


class OrganizerService(OrganizerCore):
    """归类服务：将标准文件按代号/名称归类到标准库目录。"""

    _is_word_or_template = staticmethod(_is_word_or_template)
    _resolve_industry_in_path = staticmethod(_resolve_industry_in_path)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mirror = OrganizerMirror(self._cfg)
        # OrganizerCore 创建了 _skipped_source_files 集合，
        # 共享引用给 mirror 以确保 organize_fallback 使用同一集合
        self._mirror._skipped_source_files = self._skipped_source_files

    def merge_expire_from_source(self, root_dir: str | None, parsed_list: list[Any]) -> int:
        """过期作废文件夹合并。委托给模块级纯函数，注入 self._cfg。"""
        return _merge_expire_from_source(self._cfg, root_dir, parsed_list)

    # ---- 镜像/兜底归档代理（委托 OrganizerMirror）----

    def organize_skipped_dirs(self, skipped_dirs: list[str], source_root: str | None = None) -> dict[str, Any]:
        return self._mirror.organize_skipped_dirs(skipped_dirs, source_root)

    def organize_fallback(self, source_root: str, pending_paths: frozenset[Any] = frozenset()) -> dict[str, Any]:
        return self._mirror.organize_fallback(source_root, pending_paths)


__all__ = ["OrganizerService"]
