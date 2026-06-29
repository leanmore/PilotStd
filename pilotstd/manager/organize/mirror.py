# pilotstd/manager/organize/mirror.py
# 镜像/兜底归档 — 从 organizer_service.py 拆分

import logging
import os
import stat
from typing import Any

from ...core.config import get_library_root
from ...core.file_utils import (
    ensure_long_path,
    safe_move,
    strip_long_path,
)
from ._utils import _resolve_industry_in_path

logger = logging.getLogger(__name__)


class OrganizerMirrorMixin:
    """跳过目录镜像 + 兜底归档（混入 OrganizerService）。"""

    def organize_skipped_dirs(self: Any, skipped_dirs: list[str], source_root: str | None = None) -> dict[str, Any]:
        """将扫描时跳过的目录原封不动镜像到新库。"""
        root = get_library_root(self._cfg)
        result: dict[str, Any] = {
            "moved": 0,
            "failed": 0,
            "skipped_exists": 0,
            "word_mirrored": 0,
            "skipped_source": 0,
            "dedup_skipped": 0,
            "details": [],
        }
        for src_dir in skipped_dirs:
            if not os.path.isdir(src_dir):
                continue
            clean_src = src_dir[4:] if src_dir.startswith("\\\\?\\") else src_dir
            clean_root = source_root[4:] if source_root and source_root.startswith("\\\\?\\") else source_root
            if clean_root:
                try:
                    rel = os.path.relpath(clean_src, clean_root)
                except ValueError:
                    rel = os.path.basename(clean_src)
            else:
                rel = os.path.basename(clean_src)
            rel = _resolve_industry_in_path(rel)
            dst = os.path.join(root, rel)
            if not os.path.realpath(dst).startswith(os.path.realpath(root) + os.sep):
                logger.error("路径越界被拒绝: %s", dst)
                result["failed"] += 1
                result["details"].append(f"跳过目录移动被拒绝(路径越界): {os.path.basename(src_dir)}")
                continue
            try:
                if os.path.exists(dst):
                    for fname in os.listdir(src_dir):
                        src_file = os.path.join(src_dir, fname)
                        dst_file = os.path.join(dst, fname)
                        if os.path.isfile(src_file):
                            if safe_move(src_file, dst_file, on_exists="skip"):
                                result["moved"] += 1
                            else:
                                result["details"].append(f"跳过(目标已存在): {fname}")
                        elif os.path.isdir(src_file):
                            try:
                                os.makedirs(dst_file, exist_ok=True)
                                for sub_fname in os.listdir(src_file):
                                    sub_src = os.path.join(src_file, sub_fname)
                                    sub_dst = os.path.join(dst_file, sub_fname)
                                    if os.path.isfile(sub_src):
                                        if safe_move(sub_src, sub_dst, on_exists="skip"):
                                            result["moved"] += 1
                                    elif os.path.isdir(sub_src):
                                        if self._cfg.get("file.clear_readonly", True):
                                            for _r, _ds, _fs in os.walk(sub_src):
                                                for _f in _fs:
                                                    try:
                                                        os.chmod(os.path.join(_r, _f), stat.S_IWRITE)
                                                    except OSError:
                                                        pass
                                        shutil = __import__("shutil")
                                        shutil.move(sub_src, sub_dst)
                                        result["moved"] += 1
                            except OSError as e:
                                result["details"].append(f"跳过目录子项移动失败: {fname} - {e}")
                else:
                    if self._cfg.get("file.clear_readonly", True):
                        for _root, _dirs, _files in os.walk(src_dir):
                            for _f in _files:
                                try:
                                    os.chmod(os.path.join(_root, _f), stat.S_IWRITE)
                                except OSError:
                                    pass
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil = __import__("shutil")
                    shutil.move(src_dir, dst)
                    result["moved"] += 1
                    result["details"].append(f"跳过目录: {os.path.basename(src_dir)} -> {dst}")
            except OSError as e:
                result["failed"] += 1
                result["details"].append(f"跳过目录移动失败: {os.path.basename(src_dir)} - {e}")
                logger.warning("跳过目录移动失败: %s - %s", os.path.basename(src_dir), e)
        logger.info("跳过目录归档: %d 已移动, %d 失败", result["moved"], result["failed"])
        return result

    def organize_fallback(self: Any, source_root: str, pending_paths: frozenset[Any] = frozenset()) -> dict[str, Any]:
        """归档收尾：将源目录中所有残留文件按目录结构镜像到输出目录。"""
        source_root = ensure_long_path(source_root)
        root = get_library_root(self._cfg)
        clean_src_root = strip_long_path(source_root)

        result: dict[str, Any] = {
            "moved": 0,
            "failed": 0,
            "skipped_exists": 0,
            "word_mirrored": 0,
            "skipped": 0,
            "skipped_by_organize": 0,
            "skipped_pending": 0,
            "details": [],
        }
        for dirpath, dirnames, filenames in os.walk(source_root):
            for fname in filenames:
                if fname in self._FALLBACK_SKIP_FILES or fname.startswith(self._FALLBACK_SKIP_PREFIX):
                    result["skipped"] += 1
                    continue
                src = os.path.join(dirpath, fname)
                if src in pending_paths or strip_long_path(src) in pending_paths:
                    result["skipped_pending"] += 1
                    continue
                if src in self._skipped_source_files:
                    result["skipped_by_organize"] += 1
                    continue
                clean_dir = dirpath[4:] if dirpath.startswith("\\\\?\\") else dirpath
                clean_dir = clean_dir.lstrip("\\")
                try:
                    rel_dir = os.path.relpath(clean_dir, clean_src_root)
                except ValueError:
                    rel_dir = ""
                if rel_dir == ".":
                    rel_dir = ""
                rel_dir = _resolve_industry_in_path(rel_dir)
                dst = os.path.join(root, rel_dir, fname) if rel_dir else os.path.join(root, fname)
                try:
                    if safe_move(src, dst, on_exists="skip"):
                        result["moved"] += 1
                    else:
                        result["skipped"] += 1
                except OSError as e:
                    result["failed"] += 1
                    result["details"].append(f"兜底镜像失败: {fname} - {e}")
        logger.info(
            "兜底镜像完成: %d 已移动, %d 已跳过(%d因目标已存在, %d因待确认), %d 失败",
            result["moved"],
            result["skipped"],
            result["skipped_by_organize"],
            result["skipped_pending"],
            result["failed"],
        )
        logger.info(
            "[FALLBACK] 已移动=%d 已跳过=%d 因目标已存在跳过=%d 因待确认跳过=%d 失败=%d",
            result["moved"],
            result["skipped"],
            result["skipped_by_organize"],
            result["skipped_pending"],
            result["failed"],
        )
        return result
