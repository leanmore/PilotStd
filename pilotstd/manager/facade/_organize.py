# 模块：项目/管理器/门面/_归类脚本
"""OrganizeHandler：归档、规范化、过期处理、兜底镜像，替代原 OrganizeMixin。"""
# 边界条件：同名文件追加序号而非覆盖（-256先比对）；废止标准走_自动追加过期作废子目录；
# /模板文件按源目录镜像归档（无标准号无法按代号归类，镜像保留原始结构便于追溯）

from __future__ import annotations

import json
import logging
import os
import warnings
from typing import TYPE_CHECKING, Any, Optional, cast

from ...core.notification import EVENT_ARCHIVE_COMPLETE
from ...core.std_utils import classify_std_code
from ...i18n import t
from ...models import ParsedStdInfo
from ...organizer.industry_lookup import INDUSTRY_MAP

if TYPE_CHECKING:
    from ._core import ManagerCore

logger = logging.getLogger(__name__)
# 归档处理器，封装所有归档方法，替代原


def _archive_category_stats(items: list[Any]) -> dict[str, int]:
    """按标准代号分类统计归档条目（C-2：复用 std_utils.classify_std_code）。

    行业标准进一步按行业映射细分（如 SH→石油化工、HG→化工），
    与模板"国标：N 条，石化：N 条，化工：N 条"对齐；未知代号归入"其他"。
    """
    from collections import Counter

    cat: Counter[str] = Counter()
    for p in items:
        code = getattr(p, "logical_code", "") or ""
        cls = classify_std_code(code)
        if cls == "gb":
            label = t("notification.archive.category.national")
        elif cls == "db":
            label = t("notification.archive.category.local")
        elif cls == "iso_iec":
            label = t("notification.archive.category.international")
        elif cls == "foreign":
            label = t("notification.archive.category.foreign")
        elif cls == "group":
            label = t("notification.archive.category.group")
        elif cls == "enterprise":
            label = t("notification.archive.category.enterprise")
        elif cls == "industry":
            base = code.replace("/", "").upper()
            label = INDUSTRY_MAP.get(base, t("notification.archive.category.industry"))
        else:
            label = t("notification.archive.category.other")
        cat[label] += 1
    return dict(cat)


class OrganizeHandler:
    """归档处理器 — 封装所有归档方法，替代原 OrganizeMixin。"""

    def __init__(self, core: "ManagerCore"):
        """初始化归档处理器，持有 ManagerCore 引用。"""
        self._core = core

    _FALLBACK_SKIP_FILES = frozenset({"Thumbs.db", "sync.ffs_db"})
    _FALLBACK_SKIP_PREFIX = "~$"

    def organize(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        word_source_root: Optional[str] = None,
    ) -> dict[str, Any]:
        """[已废弃] 使用 archive_standards() 替代。"""
        warnings.warn("organize() 已废弃，请使用 archive_standards()", DeprecationWarning, stacklevel=2)
        return self._core.organizer_svc.organize(  # type: ignore[no-any-return]
            parsed_list or self._core.parsed_results, word_source_root
        )

    def _dedup_standard(self, parsed: ParsedStdInfo, new_path: str) -> None:
        """去重：同标准号旧路径残留。"""
        self._core.organizer_svc._dedup_standard(parsed, new_path)

    def organize_stream(
        self,
        parsed_list: Optional[list[ParsedStdInfo]] = None,
        word_source_root: Optional[str] = None,
        on_progress: Any = None,
        on_result: Any = None,
    ) -> dict[str, Any]:
        """[已废弃] 流式归档。"""
        warnings.warn("organize_stream() 已废弃，请使用 archive_standards()", DeprecationWarning, stacklevel=2)
        items = parsed_list or self._core.parsed_results
        total = len(items)
        result: dict[str, Any] = {
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
                single = self._core.organizer_svc.organize([p], word_source_root)
                status = (
                    "已归档"
                    if single.get("moved", 0) > 0
                    else "跳过"
                    if single.get("skipped_exists", 0) > 0
                    else "归档失败"
                )
                result["moved"] += single.get("moved", 0)
                result["skipped_exists"] += single.get("skipped_exists", 0)
                result["failed"] += single.get("failed", 0)
                if on_result:
                    on_result(i, status)
            except Exception:
                if on_result:
                    on_result(i, "归档失败")
                result["failed"] += 1
            if on_progress:
                on_progress(i + 1, total)
        return result

    # ___—回填单个的_，优先查本地缓存
    def _backfill_std_name(self, parsed: ParsedStdInfo) -> ParsedStdInfo:
        """回填单个 ParsedStdInfo 的 std_name。"""
        if parsed.std_name:
            return parsed

        # 30:_存在且非空时直接回填，避免遗漏查询结果中的名称
        if parsed.found_name and parsed.found_name.strip():
            parsed.std_name = parsed.found_name.strip()
            return parsed

        std_no = f"{parsed.logical_code} {parsed.number}"
        if parsed.year:
            std_no += f"-{parsed.year}"
        try:
            row = self._core.db.fetchone(
                "SELECT result_json FROM standard_info_cache WHERE standard_number = ? LIMIT 1",
                (std_no,),
            )
            if row:
                try:
                    raw = row["result_json"]
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    name = data.get("standard_name", "") if isinstance(data, dict) else ""
                    if name:
                        parsed.std_name = name
                        logger.info("[CACHE] std_name 命中: %s -> %s", std_no, name)
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception:
            pass
        return parsed

    # 归档_—统一归档入口，所有端（命令行//用户界面）均通过此方法归档
    def archive_standards(
        self,
        parsed_list: list[ParsedStdInfo] | None = None,
        word_source_root: str | None = None,
        progress_callback: Any = None,
        on_result: Any = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """统一归档入口：所有端（CLI/Web/WinUI）均通过此方法归档。"""
        items = parsed_list if parsed_list is not None else self._core.parsed_results
        total = len(items)
        backfilled = 0
        for i, p in enumerate(items):
            orig = p.std_name
            self._backfill_std_name(p)
            if not orig and p.std_name:
                backfilled += 1
            if progress_callback:
                progress_callback(i + 1, total)
        if backfilled:
            logger.info("archive_standards: 回填 std_name %d/%d 条", backfilled, total)
        result = self._core.organizer_svc.organize(items, word_source_root, overwrite=overwrite)
        moved = result.get("moved", 0)
        _EXPIRE_STATUSES = frozenset({"废止", "已废止", "作废", "被代替", "过期"})
        if moved > 0:
            for p in items:
                std_no = f"{p.logical_code} {p.number}"
                if p.year:
                    std_no += f"-{p.year}"
                try:
                    if self._core.validity_checker:
                        self._core.validity_checker.register_new_standard(std_no, self._core.notification_mgr)
                except Exception as e:
                    logger.warning("注册新标准失败: %s, error=%s", std_no, e)
                # 废止标准同步触发__（与归档_同时触发）
                try:
                    if self._core.notification_mgr and getattr(p, "effect_status", "") in _EXPIRE_STATUSES:
                        self._core.notification_mgr.send_event(
                            "expire_standard_moved",
                            {"standard_number": std_no, "target_path": getattr(p, "source_path", "")},
                        )
                except Exception as e:
                    logger.warning("发送废止标准通知失败: %s, error=%s", std_no, e)
        try:
            if self._core.notification_mgr:
                # 归档目标目录从 organizer 明细行 "basename -> dst" 中提取（去重父目录）
                directories = sorted(
                    {
                        os.path.dirname(d.split(" -> ", 1)[1])
                        for d in result.get("details", [])
                        if " -> " in d
                    }
                )
                self._core.notification_mgr.send_event(
                    EVENT_ARCHIVE_COMPLETE,
                    {
                        "count": moved,
                        "directories": directories,
                        "category_stats": _archive_category_stats(items),
                    },
                )
        except Exception as e:
            logger.warning("发送归档完成通知失败: %s", e)
        # 收藏链路逐条归档完成事件由收藏下载任务中的下载完成事件覆盖
        # （收藏链为"下载即归档"一体链路，完成状态处已发送下载完成事件，
        #  本函数为手动/批量归档入口，无用户与记录标识上下文，无法逐条定位用户）
        return cast("dict[str, Any]", result)

    @staticmethod
    def _is_word_or_template(src_path: str) -> bool:
        from ..organizer_service import OrganizerService

        return OrganizerService._is_word_or_template(src_path)

    def organize_skipped_dirs(self, skipped_dirs: list[str], source_root: Optional[str] = None) -> dict[str, Any]:
        """将扫描时跳过的目录原封不动镜像到新库（委托 OrganizerService）。"""
        return self._core.organizer_svc.organize_skipped_dirs(skipped_dirs, source_root)  # type: ignore[no-any-return]

    @staticmethod
    def _resolve_industry_in_path(rel_path: str) -> str:
        from ..organizer_service import OrganizerService

        return OrganizerService._resolve_industry_in_path(rel_path)

    # 归类_回退—归档收尾：将源目录中所有残留文件按目录结构镜像到输出目录
    def organize_fallback(self, source_root: str) -> dict[str, Any]:
        """归档收尾：将源目录中所有残留文件按目录结构镜像到输出目录。"""
        pending_paths = frozenset(p.source_path for p in self._core.pending_list if getattr(p, "source_path", ""))
        return self._core.organizer_svc.organize_fallback(source_root, pending_paths)  # type: ignore[no-any-return]

    def merge_expire_from_source(self, root_dir: str, parsed_list: list[ParsedStdInfo]) -> int:
        """从源目录合并过期标准到「过期作废」目录（委托 OrganizerService）。"""
        return self._core.organizer_svc.merge_expire_from_source(root_dir, parsed_list)  # type: ignore[no-any-return]

    # 归类_—接受文件路径列表，解析后走完整归类_服务归档
    def organize_files(self, file_paths: list[str]) -> dict[str, Any]:
        """接受文件路径列表，解析后走完整 organizer_service 归档。"""
        parsed: list[ParsedStdInfo] = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self._core.parser.parse(os.path.basename(path))
            if info:
                info.source_path = path
                parsed.append(info)
        if not parsed:
            return {"moved": 0, "failed": 0, "skipped_exists": 0, "details": ["无有效文件"]}
        return self.archive_standards(parsed)  # type: ignore[no-any-return]

    # _—接受文件路径列表，解析后标记废止并走主线归档
    def expire_files(self, file_paths: list[str]) -> dict[str, Any]:
        """接受文件路径列表，解析后标记废止并走主线 organize() 归档。"""
        parsed: list[ParsedStdInfo] = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self._core.parser.parse(os.path.basename(path))
            if info:
                info.source_path = path
                info.effect_status = "废止"
                parsed.append(info)
        if not parsed:
            return {"moved": 0, "failed": 0, "details": ["无有效文件"]}
        return self._core.organizer_svc.organize(parsed)  # type: ignore[no-any-return]

    # _—返回文件规范化名称列表
    def normalize_files(self, file_paths: list[str]) -> list[dict[str, Any]]:
        """返回文件规范化名称列表。"""
        from ...core.file_utils import make_standard_filename
        from ...organizer.industry_lookup import get_folder_name

        results: list[dict[str, Any]] = []
        for path in file_paths:
            if not os.path.isfile(path):
                continue
            info = self._core.parser.parse(os.path.basename(path))
            if not info:
                continue
            results.append(
                {
                    "source": path,
                    "logical_code": info.logical_code,
                    "number": info.raw_number or str(info.number),
                    "year": info.year,
                    "normalized": make_standard_filename(
                        logical_code=info.logical_code,
                        number=info.number,
                        year=info.year,
                        std_name=info.std_name,
                        part=info.part,
                        language=info.language,
                        num_prefix=info.num_prefix,
                        num_suffix=info.num_suffix,
                        ext=info.ext,
                        raw_number=info.raw_number or None,
                    ),
                    "folder": get_folder_name(info.logical_code),
                }
            )
        return results

    @staticmethod
    def _make_archive_filename(parsed: ParsedStdInfo) -> str:
        """根据解析后的标准信息生成归档文件名。"""
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
            ext=getattr(parsed, "ext", ".pdf"),
            raw_number=parsed.raw_number or None,
        )

    def normalize_files_stream(
        self,
        parsed_list: list[ParsedStdInfo],
        on_progress: Any = None,
        on_batch: Any = None,
    ) -> list[dict[str, Any]]:
        """流式规范化（线程安全）。"""
        from ...organizer.industry_lookup import get_folder_name

        results: list[dict[str, Any]] = []
        total = len(parsed_list)
        batch: list[tuple[int, ParsedStdInfo, str]] = []
        try:
            for i, parsed in enumerate(parsed_list):
                src_path = getattr(parsed, "source_path", "") or ""
                name = self._make_archive_filename(parsed)
                folder = get_folder_name(parsed.logical_code)
                results.append(
                    {
                        "source": src_path,
                        "logical_code": parsed.logical_code,
                        "number": parsed.raw_number or str(parsed.number),
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
        except Exception as e:
            try:
                if self._core.notification_mgr:
                    self._core.notification_mgr.send_event(
                        "normalize_failed",
                        {"total": total, "error": str(e)},
                    )
            except Exception as e2:
                logger.warning("规范化失败通知发送失败: %s", e2)
            raise
        if on_batch and batch:
            on_batch(batch)

        try:
            if self._core.notification_mgr:
                self._core.notification_mgr.send_event(
                    "normalize_complete",
                    {"total": total, "success": len(results), "failed": 0},
                )
        except Exception as e:
            logger.warning("规范化完成通知发送失败: %s", e)

        return results
