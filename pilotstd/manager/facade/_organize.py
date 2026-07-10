# pilotstd/manager/facade/_organize.py
# StandardManager 归档混入模块
"""OrganizeMixin：归档、规范化、过期处理、兜底镜像。"""

from __future__ import annotations

import json
import logging
import os
import warnings
from typing import Any, List, Optional

from ...core.notification import EVENT_ARCHIVE_COMPLETE
from ...models import ParsedStdInfo

logger = logging.getLogger(__name__)


class OrganizeMixin:
    """归档混入类 — 统一归档入口 + 回填 + 过期 + 兜底。"""

    _organizer_svc: Any
    _parsed_results: Any
    _pending_list: Any

    _FALLBACK_SKIP_FILES = frozenset({"Thumbs.db", "sync.ffs_db"})
    _FALLBACK_SKIP_PREFIX = "~$"

    def organize(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        word_source_root: Optional[str] = None,
    ) -> dict[str, Any]:
        """[已废弃] 使用 archive_standards() 替代。"""
        warnings.warn("organize() 已废弃，请使用 archive_standards()", DeprecationWarning, stacklevel=2)
        return self._organizer_svc.organize(  # type: ignore[no-any-return]
            parsed_list or self._parsed_results, word_source_root
        )

    def _dedup_standard(self, parsed: ParsedStdInfo, new_path: str) -> None:
        """去重：同标准号旧路径残留。"""
        self._organizer_svc._dedup_standard(parsed, new_path)

    def organize_stream(
        self,
        parsed_list: Optional[list[ParsedStdInfo]] = None,
        word_source_root: Optional[str] = None,
        on_progress: Any = None,
        on_result: Any = None,
    ) -> dict[str, Any]:
        """[已废弃] 流式归档。"""
        warnings.warn("organize_stream() 已废弃，请使用 archive_standards()", DeprecationWarning, stacklevel=2)
        items = parsed_list or self._parsed_results
        total = len(items)
        result = {
            "moved": 0,
            "failed": 0,
            "skipped_exists": 0,
            "word_mirrored": 0,
            "skipped_source": 0,
            "dedup_skipped": 0,
            "details": [],
        }
        for i, p in enumerate(items):
            try:
                single = self._organizer_svc.organize([p], word_source_root)
                status = (
                    "已归档"
                    if single.get("moved", 0) > 0
                    else ("跳过" if single.get("skipped_exists", 0) > 0 else "归档失败")
                )
                result["moved"] += single.get("moved", 0)
                result["skipped_exists"] += single.get("skipped_exists", 0)
                result["failed"] += single.get("failed", 0)
                if on_result:
                    on_result(i, status)
            except Exception:
                if on_result:
                    on_result(i, "归档失败")
                result["failed"] += 1  # type: ignore[operator]
            if on_progress:
                on_progress(i + 1, total)
        return result

    def _backfill_std_name(self, parsed: ParsedStdInfo) -> ParsedStdInfo:
        """回填单个 ParsedStdInfo 的 std_name。"""
        if parsed.std_name:
            return parsed
        _std_no = f"{parsed.logical_code} {parsed.number}"
        if parsed.year:
            _std_no += f"-{parsed.year}"
        try:
            _row = self.db.fetchone(
                "SELECT result_json FROM standard_info_cache WHERE standard_number = ? LIMIT 1", (_std_no,)
            )
            if _row:
                try:
                    _raw = _row["result_json"]
                    _data = json.loads(_raw) if isinstance(_raw, str) else _raw
                    _name = _data.get("standard_name", "") if isinstance(_data, dict) else ""
                    if _name:
                        parsed.std_name = _name
                        logger.info("[CACHE] std_name 命中: %s -> %s", _std_no, _name)
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception:
            pass
        logger.info("[CACHE] std_name 未命中: %s，尝试实时查询", _std_no)
        try:
            _results = self.query_engine.query_standards(
                [
                    (
                        parsed.logical_code,
                        parsed.number,
                        parsed.year,
                        parsed.std_name,
                        getattr(parsed, "part", None),
                        getattr(parsed, "num_prefix", ""),
                    )
                ]
            )
            _result = _results[0] if _results else None
            if _result and _result.standard_name:
                parsed.std_name = _result.standard_name
                logger.info("[CACHE] 实时查询成功: %s -> %s，已写入缓存", _std_no, _result.standard_name)
            else:
                logger.info("[CACHE] 实时查询失败: %s", _std_no)
        except Exception:
            logger.info("[CACHE] 实时查询异常: %s", _std_no)
        return parsed

    def archive_standards(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        word_source_root: str | None = None,
        progress_callback: Any = None,
        on_result: Any = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """统一归档入口：所有端（CLI/Web/WinUI）均通过此方法归档。"""
        _items = parsed_list if parsed_list is not None else self._parsed_results
        _total = len(_items)
        _backfilled = 0
        for _i, _p in enumerate(_items):
            _orig = _p.std_name
            self._backfill_std_name(_p)
            if not _orig and _p.std_name:
                _backfilled += 1
            if progress_callback:
                progress_callback(_i + 1, _total)
        if _backfilled:
            logger.info("archive_standards: 回填 std_name %d/%d 条", _backfilled, _total)
        result = self._organizer_svc.organize(_items, word_source_root, overwrite=overwrite)
        if result.get("moved", 0) > 0:
            for _p in _items:
                _std_no = f"{_p.logical_code} {_p.number}"
                if _p.year:
                    _std_no += f"-{_p.year}"
                try:
                    self.validity_checker.register_new_standard(_std_no, self.notification_mgr)
                except Exception:
                    pass
            try:
                self.notification_mgr.send_event(EVENT_ARCHIVE_COMPLETE, {"count": result["moved"]})
            except Exception:
                pass
        return result

    @staticmethod
    def _is_word_or_template(src_path: str) -> bool:
        """通过扩展名判断是否为 Word/模板文件。"""
        from ..organizer_service import OrganizerService

        return OrganizerService._is_word_or_template(src_path)

    def organize_skipped_dirs(self, skipped_dirs: List[str], source_root: Optional[str] = None) -> dict[str, Any]:
        """将扫描时跳过的目录原封不动镜像到新库。"""
        return self._organizer_svc.organize_skipped_dirs(skipped_dirs, source_root)  # type: ignore[no-any-return]

    @staticmethod
    def _resolve_industry_in_path(rel_path: str) -> str:
        """解析相对路径第一段中的行业代号为完整目录名。"""
        from ..organizer_service import OrganizerService

        return OrganizerService._resolve_industry_in_path(rel_path)

    def organize_fallback(self, source_root: str) -> dict[str, Any]:
        """归档收尾：将源目录中所有残留文件按目录结构镜像到输出目录。"""
        pending_paths = frozenset(p.source_path for p in self._pending_list if getattr(p, "source_path", ""))
        _ps_by_ms: dict[str, int] = {}
        for p in self._pending_list:
            ms = getattr(p, "match_status", "") or "(empty)"
            _ps_by_ms[ms] = _ps_by_ms.get(ms, 0) + 1
        logger.info("[PENDING_SUMMARY] 总数=%d 按匹配状态=%s", len(self._pending_list), _ps_by_ms)
        logger.info(
            "[PENDING] 待确认路径总数: %d (采样: %s)", len(pending_paths), [p[:80] for p in list(pending_paths)[:5]]
        )
        return self._organizer_svc.organize_fallback(source_root, pending_paths)  # type: ignore[no-any-return]

    def handle_expired(self, parsed_list: Optional[List[ParsedStdInfo]] = None) -> dict[str, Any]:
        """将查询结果为「废止」的标准移入 过期作废 目录。"""
        return self._organizer_svc.handle_expired(parsed_list)  # type: ignore[no-any-return]

    def merge_expire_from_source(self, root_dir: str, parsed_list: list[ParsedStdInfo]) -> int:
        """将源目录中的过期作废文件夹合并到标准库。"""
        return self._organizer_svc.merge_expire_from_source(root_dir, parsed_list)  # type: ignore[no-any-return]

    def organize_files(self, file_paths: list[str]) -> dict[str, Any]:
        """接受文件路径列表，解析后走完整 organizer_service 归档。"""
        parsed = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self.parser.parse(os.path.basename(path))
            if info:
                info.source_path = path
                parsed.append(info)
        if not parsed:
            return {
                "moved": 0,
                "failed": 0,
                "skipped_exists": 0,
                "word_mirrored": 0,
                "skipped_source": 0,
                "dedup_skipped": 0,
                "details": ["无有效文件"],
            }
        return self.archive_standards(parsed)  # type: ignore[no-any-return]

    def expire_files(self, file_paths: list[str]) -> dict[str, Any]:
        """接受文件路径列表，解析后过期处理。"""
        items = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self.parser.parse(os.path.basename(path))
            if info:
                items.append((path, info))
        if not items:
            return {"moved": 0, "failed": 0, "details": ["无有效文件"]}
        return self._organizer_svc.handle_expired(items)  # type: ignore[no-any-return]

    def normalize_files(self, file_paths: list[str]) -> list[dict[str, Any]]:
        """返回文件规范化名称列表。"""
        from ...core.file_utils import make_standard_filename
        from ...organizer.industry_lookup import get_folder_name

        results = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self.parser.parse(os.path.basename(path))
            if not info:
                continue
            norm_name = make_standard_filename(
                logical_code=info.logical_code,
                number=info.number,
                year=info.year,
                std_name=info.std_name,
                part=info.part,
                language=info.language,
                num_prefix=info.num_prefix,
                num_suffix=info.num_suffix,
                ext=info.ext,
            )
            folder = get_folder_name(info.logical_code)
            results.append(
                {
                    "source": path,
                    "logical_code": info.logical_code,
                    "number": info.number,
                    "year": info.year,
                    "normalized": norm_name,
                    "folder": folder,
                }
            )
        return results

    @staticmethod
    def _make_archive_filename(parsed: ParsedStdInfo) -> str:
        """根据已解析元数据统一生成归档文件名。"""
        from ...core.file_utils import make_standard_filename

        return make_standard_filename(
            logical_code=parsed.logical_code,
            number=parsed.number,
            year=parsed.year,
            std_name=parsed.std_name,
            part=getattr(parsed, "part", None),
            language=getattr(parsed, "language", ""),
            num_prefix=getattr(parsed, "num_prefix", ""),
            num_suffix=getattr(parsed, "num_suffix", ""),
            ext=getattr(parsed, "ext", "pdf"),
        )

    def normalize_files_stream(
        self, parsed_list: list[ParsedStdInfo], on_progress: Any = None, on_batch: Any = None
    ) -> list[dict[str, Any]]:
        """流式规范化（线程安全）。"""
        from ...organizer.industry_lookup import get_folder_name

        results = []
        total = len(parsed_list)
        batch = []
        for i, parsed in enumerate(parsed_list):
            src_path = getattr(parsed, "source_path", "") or ""
            name = self._make_archive_filename(parsed)
            folder = get_folder_name(parsed.logical_code)
            results.append(
                {
                    "source": src_path,
                    "logical_code": parsed.logical_code,
                    "number": parsed.number,
                    "year": parsed.year,
                    "normalized": name,
                    "folder": folder,
                }
            )
            batch.append((i, parsed, name))
            if on_batch and len(batch) >= 50:
                on_batch(batch)
                batch = []
            if on_progress:
                on_progress(i + 1, total)
        if on_batch and batch:
            on_batch(batch)
        return results
