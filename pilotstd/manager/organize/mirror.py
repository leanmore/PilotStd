# 模块：pilotstd/manager/organize/mirror.py
# 镜像/兜底归档 — 从 organizer_service.py 拆分
# 原 OrganizerMirrorMixin，现为独立类 OrganizerMirror（组合注入 cfg）

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


class OrganizerMirror:
    """跳过目录镜像 + 兜底归档（组合注入到 OrganizerService）。"""

    def __init__(
        self,
        cfg: Any,
        fallback_skip_files: frozenset[str] | None = None,
        fallback_skip_prefix: str = "~$",
    ):
        self._cfg = cfg
        self._FALLBACK_SKIP_FILES = (
            fallback_skip_files
            if fallback_skip_files is not None
            else frozenset({".DS_Store", "Thumbs.db", "sync.ffs_db"})
        )
        self._FALLBACK_SKIP_PREFIX = fallback_skip_prefix
        self._skipped_source_files: set[str] = set()

    # organize_skipped_dirs — 将扫描时跳过的目录原封不动镜像到新库
    def organize_skipped_dirs(self, skipped_dirs: list[str], source_root: str | None = None) -> dict[str, Any]:
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
            rel_dst = self._resolve_skipped_relative(src_dir, root, source_root)
            if rel_dst[0] is None:
                continue
            _, dst = rel_dst
            if not self._check_path_traversal(dst, root, src_dir):
                result["failed"] += 1
                result["details"].append(f"跳过目录移动被拒绝(路径越界): {os.path.basename(src_dir)}")
                continue
            try:
                if os.path.exists(dst):
                    self._mirror_into_existing_dst(dst, src_dir, result)
                else:
                    self._mirror_whole_directory(dst, src_dir, result)
            except OSError as e:
                result["failed"] += 1
                result["details"].append(f"跳过目录移动失败: {os.path.basename(src_dir)} - {e}")
                logger.warning("跳过目录移动失败: %s - %s", os.path.basename(src_dir), e)
        logger.info("跳过目录归档: %d 已移动, %d 失败", result["moved"], result["failed"])
        return result

    def _resolve_skipped_relative(self, src_dir: str, root: str, source_root: str | None) -> tuple[str | None, str]:
        """路径清理 + relpath 计算 + 行业路径替换。返回 (rel_path, dst_path)。"""
        if not os.path.isdir(src_dir):
            return (None, "skipped: directory not found")
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
        return rel, dst

    def _check_path_traversal(self, dst: str, root: str, dirpath: str) -> bool:
        """校验目标路径不越界。返回 True 表示安全。"""
        if not os.path.realpath(dst).startswith(os.path.realpath(root) + os.sep):
            logger.error("路径越界被拒绝: %s", dst)
            return False
        return True

    # _mirror_into_existing_dst — 目标已存在时逐文件移动到目标目录
    def _mirror_into_existing_dst(self, dst: str, src_dir: str, result: dict) -> None:
        """目标已存在 → 逐文件移动到目标目录。"""
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

    def _mirror_whole_directory(self, dst: str, src_dir: str, result: dict) -> None:
        """目标不存在 → 整体移动目录。"""
        if self._cfg.get("file.clear_readonly", True):
            for _r, _ds, _fs in os.walk(src_dir):
                for _f in _fs:
                    try:
                        os.chmod(os.path.join(_r, _f), stat.S_IWRITE)
                    except OSError:
                        pass
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil = __import__("shutil")
        shutil.move(src_dir, dst)
        result["moved"] += 1
        result["details"].append(f"跳过目录: {os.path.basename(src_dir)} -> {dst}")

    # organize_fallback — 归档收尾：将源目录中残留文件按目录结构镜像到输出目录
    def organize_fallback(self, source_root: str, pending_paths: frozenset[Any] = frozenset()) -> dict[str, Any]:
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
