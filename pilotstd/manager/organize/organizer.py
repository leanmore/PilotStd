# pilotstd/manager/organize/organizer.py
# 核心归类逻辑 — 从 organizer_service.py 拆分

import logging
import os
from typing import Any

from ...core.config import get_library_root
from ...core.file_utils import (
    hash_file_content,
    safe_move,
    strip_long_path,
)
from ._utils import _is_word_or_template, _resolve_industry_in_path

logger = logging.getLogger(__name__)


class OrganizerCore:
    """归类核心逻辑：PDF移动 + Word镜像 + 内容去重 + 索引写入。"""

    _FALLBACK_SKIP_FILES = frozenset({"Thumbs.db", "sync.ffs_db"})
    _FALLBACK_SKIP_PREFIX = "~$"

    def __init__(
        self,
        cfg: Any,
        file_index: Any,
        dir_builder: Any,
        file_mover: Any,
        expire_handler: Any,
    ) -> None:
        self._cfg = cfg
        self._file_index = file_index
        self._dir_builder = dir_builder
        self._file_mover = file_mover
        self._expire_handler = expire_handler
        self._skipped_source_files: set[str] = set()

    def organize(self: Any, parsed_list: list[Any], word_source_root: str | None = None) -> dict[str, Any]:
        """将已处理的文件移动到分类目录。Word/模板文件按源目录镜像归档。"""
        items = parsed_list
        root = get_library_root(self._cfg)
        mover = self._file_mover

        result: dict[str, Any] = {
            "moved": 0,
            "failed": 0,
            "skipped_exists": 0,
            "word_mirrored": 0,
            "skipped_source": 0,
            "dedup_skipped": 0,
            "details": [],
        }
        _content_hashes: dict[str, str] = {}
        _org_total = len(items)
        _org_count = 0
        _org_t0 = 0.0

        import time as _time

        for p in items:
            _org_count += 1
            if _org_count == 1:
                _org_t0 = _time.monotonic()
            if _org_count % 50 == 0 or _org_count == _org_total:
                _elapsed = _time.monotonic() - _org_t0 if _org_t0 else 0
                _pct = int(_org_count / _org_total * 100) if _org_total > 0 else 0
                logger.info("归档进度: %d/%d (%d%%) 已耗时 %.0fs", _org_count, _org_total, _pct, _elapsed)

        for p in items:
            if getattr(p, "next_action", "") == "pending":
                continue
            src = getattr(p, "source_path", "")
            if src and os.path.isfile(src):
                if _is_word_or_template(src):
                    clean_src = strip_long_path(src)
                    clean_root = strip_long_path(word_source_root) if word_source_root else ""
                    if clean_root and clean_src.startswith(clean_root):
                        rel = clean_src[len(clean_root) :].lstrip(os.sep)
                    else:
                        rel = os.path.basename(clean_src)
                    rel = _resolve_industry_in_path(rel)
                    dst = os.path.join(root, rel)
                    if dst:
                        try:
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            if os.path.exists(dst):
                                logger.debug("Word 目标已存在，跳过: %s", os.path.basename(src))
                                result["skipped_exists"] += 1
                                result["word_mirrored"] += 1
                                self._skipped_source_files.add(clean_src)
                                continue
                            safe_move(src, dst, on_exists="skip")
                            result["moved"] += 1
                            result["word_mirrored"] += 1
                            result["details"].append(f"Word: {os.path.basename(src)} -> {dst}")
                            if self._file_index:
                                self._file_index.upsert(
                                    file_path=dst,
                                    logical_code="WORD",
                                    number=0,
                                    year=0,
                                    std_name=os.path.basename(src),
                                    status="现行",
                                )
                        except PermissionError:
                            logger.warning("Word 归档失败(权限不足): %s — 请关闭占用程序后重试", os.path.basename(src))
                            result["failed"] += 1
                            result["details"].append(
                                f"Word 归档失败(权限不足): {os.path.basename(src)} — 请关闭占用程序后重试"
                            )
                        except OSError as e:
                            logger.warning("Word 归档失败: %s - %s", os.path.basename(src), e)
                            result["failed"] += 1
                            result["details"].append(f"Word 归档失败: {os.path.basename(src)} - {e}")
                    else:
                        logger.warning("Word 路径计算失败: %s", src)
                        result["failed"] += 1
                        result["details"].append(f"Word: 无法计算目标路径: {src}")
                else:
                    try:
                        fhash = hash_file_content(src)
                    except OSError:
                        fhash = None
                    if fhash and fhash in _content_hashes:
                        logger.info("内容重复，跳过: %s (已归档为 %s)", os.path.basename(src), _content_hashes[fhash])
                        result["dedup_skipped"] += 1
                        continue
                    dst = mover.move_to_code_dir(src, p)
                    if dst:
                        result["moved"] += 1
                        result["details"].append(f"{os.path.basename(src)} -> {dst}")
                        if fhash:
                            _content_hashes[fhash] = dst
                        self._dedup_standard(p, dst)
                        if self._file_index:
                            self._file_index.upsert(
                                file_path=dst,
                                logical_code=p.logical_code,
                                number=p.number,
                                year=p.year,
                                part=getattr(p, "part", None),
                                std_name=p.std_name or "",
                                status=getattr(p, "effect_status", "") or "现行",
                            )
                    elif os.path.exists(mover.normalize_filename(p)):
                        result["skipped_exists"] += 1
                        result["skipped_source"] += 1
                        self._skipped_source_files.add(src)
                        if self._cfg.get("organize.auto_clean_source", False):
                            try:
                                os.remove(src)
                            except OSError:
                                pass
                    else:
                        result["failed"] += 1
            else:
                result["details"].append(f"跳过（无源文件）: {p.get_full_number()}")
        logger.info(
            "归类完成: %d 已移动 (Word: %d), %d 目标已存在(%d源保留), %d 内容去重跳过, %d 失败",
            result["moved"],
            result["word_mirrored"],
            result["skipped_exists"],
            result["skipped_source"],
            result["dedup_skipped"],
            result["failed"],
        )
        return result

    def _dedup_standard(self: Any, parsed: Any, new_path: str) -> None:
        """去重：同标准号旧路径残留（分类变化导致双份文件）。"""
        if not self._file_index:
            return
        dups = self._file_index.find_by_standard(
            parsed.logical_code, parsed.number, parsed.year, getattr(parsed, "part", None)
        )
        for dup in dups:
            old_path = dup.get("file_path", "")
            if not old_path or old_path == new_path:
                continue
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                    logger.info("去重清理旧路径: %s", old_path)
                except OSError:
                    pass
            self._file_index.remove(old_path)
