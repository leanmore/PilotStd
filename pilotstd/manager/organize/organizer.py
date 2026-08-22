# 模块：项目/管理器/归类/归类脚本
# 核心归类逻辑—从归类_服务脚本拆分
# 负责便携文档按标准号分类移动、/模板镜像归档、内容去重、索引写入

import logging
import os
from typing import Any

from ...core.config import get_library_root
from ...core.file_utils import (
    hash_file_content,
    safe_move,
    strip_long_path,
)
from ...scan.parser import StandardParser
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
    ) -> None:
        """初始化归类核心，注入配置、文件索引、目录构建器、文件移动器。"""
        self._cfg = cfg
        self._file_index = file_index
        self._dir_builder = dir_builder
        self._file_mover = file_mover
        self._std_parser = StandardParser(self._cfg.get("scan.code_mapping", {}))
        self._skipped_source_files: set[str] = set()

    # 归类—主入口，遍历_逐条归档，每50条输出进度
    def organize(
        self: Any, parsed_list: list[Any], word_source_root: str | None = None, overwrite: bool = False
    ) -> dict[str, Any]:
        """将已处理的文件移动到分类目录。Word/模板文件按源目录镜像归档。"""
        items = parsed_list
        # 按(_,,)去重，防止同一废止标准重复归档
        seen: set[tuple[str, int, int]] = set()
        dedup_items: list[Any] = []
        for p in items:
            key = (getattr(p, "logical_code", ""), getattr(p, "number", 0), getattr(p, "year", 0))
            if key not in seen:
                seen.add(key)
                dedup_items.append(p)
        if len(dedup_items) < len(items):
            logger.info("organize 入口去重: %d → %d 条（按标准号去重）", len(items), len(dedup_items))
        items = dedup_items
        root = get_library_root(self._cfg)
        mover = self._file_mover
        on_exists = "overwrite" if overwrite else "skip"
        self._ensure_target_dir(root)
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
        _org_total, _org_count, _org_t0 = len(items), 0, 0.0
        import time as _time

        for p in items:
            _org_count += 1
            if _org_count == 1:
                _org_t0 = _time.monotonic()
            if _org_count % 50 == 0 or _org_count == _org_total:
                _elapsed = _time.monotonic() - _org_t0 if _org_t0 else 0
                _pct = int(_org_count / _org_total * 100) if _org_total > 0 else 0
                logger.info("归档进度: %d/%d (%d%%) 已耗时 %.0fs", _org_count, _org_total, _pct, _elapsed)
            if getattr(p, "next_action", "") == "pending":
                continue  # 待确认条目跳过归档
            src = getattr(p, "source_path", "")
            if not src or not os.path.isfile(src):
                result["details"].append(f"跳过（无源文件）: {p.get_full_number()}")
                continue
            if _is_word_or_template(src):
                self._organize_word_item(p, root, word_source_root, result, on_exists)
            else:
                self._organize_nonword_item(p, mover, result, _content_hashes, on_exists)
        self._log_organize_summary(result)
        return result

    def _ensure_target_dir(self, target_root: str) -> None:
        """确保目标目录存在。"""
        os.makedirs(target_root, exist_ok=True)

    def _organize_word_item(
        self, p: Any, root: str, word_source_root: str | None, result: dict, on_exists: str
    ) -> None:
        """Word 文件归档：有标准号→分类归档，无标准号→镜像源目录。"""
        src = getattr(p, "source_path", "")
        clean_src = strip_long_path(src)
        ext = os.path.splitext(clean_src)[1]

        parsed = self._std_parser.parse(os.path.basename(clean_src)) if self._std_parser else None

        if parsed and parsed.logical_code and parsed.number > 0 and parsed.year > 0:
            # 有标准号→走分类归档，复用便携文档路径生成，保留原扩展名
            dst = self._file_mover.normalize_filename(parsed)
            dst = os.path.splitext(dst)[0] + ext
            logical_code = parsed.logical_code
            number = parsed.number
            year = parsed.year
            std_name = parsed.std_name
        else:
            # 无标准号 → 镜像源目录
            if word_source_root:
                clean_root = strip_long_path(word_source_root)
                if clean_src.startswith(clean_root):
                    rel = os.path.relpath(clean_src, clean_root)
                else:
                    rel = os.path.basename(clean_src)
            else:
                rel = os.path.basename(clean_src)
            rel = _resolve_industry_in_path(rel)
            dst = os.path.join(root, rel)
            logical_code = "WORD"
            number = 0
            year = 0
            std_name = os.path.basename(clean_src)

        if not dst:
            logger.warning("Word 路径计算失败: %s", src)
            result["failed"] += 1
            result["details"].append(f"Word: 无法计算目标路径: {src}")
            return
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst) and on_exists != "overwrite":
                logger.debug("Word 目标已存在，跳过: %s", os.path.basename(src))
                result["skipped_exists"] += 1
                result["word_mirrored"] += 1
                self._skipped_source_files.add(clean_src)
                return
            safe_move(src, dst, on_exists=on_exists)
            result["moved"] += 1
            result["word_mirrored"] += 1
            result["details"].append(f"Word: {os.path.basename(src)} -> {dst}")
            if self._file_index:
                self._file_index.upsert(
                    file_path=dst,
                    logical_code=logical_code,
                    number=number,
                    year=year,
                    std_name=std_name,
                    status="现行",
                )
        except PermissionError:
            logger.warning("Word 归档失败(权限不足): %s — 请关闭占用程序后重试", os.path.basename(src))
            result["failed"] += 1
            result["details"].append(f"Word 归档失败(权限不足): {os.path.basename(src)} — 请关闭占用程序后重试")
        except OSError as e:
            logger.warning("Word 归档失败: %s - %s", os.path.basename(src), e)
            result["failed"] += 1
            result["details"].append(f"Word 归档失败: {os.path.basename(src)} - {e}")

    # _归类__—非文件：哈希去重后移动，更新索引
    def _organize_nonword_item(self, p: Any, mover: Any, result: dict, content_hashes: dict, on_exists: str) -> None:
        """非 Word 文件去重 + 移动 + 索引更新。"""
        src = getattr(p, "source_path", "")
        try:
            fhash = hash_file_content(src)
        except OSError:
            fhash = None
        if fhash and fhash in content_hashes:
            logger.info("内容重复，跳过: %s (已归档为 %s)", os.path.basename(src), content_hashes[fhash])
            result["dedup_skipped"] += 1
            return
        dst = mover.move_to_code_dir(src, p, on_exists=on_exists)
        if dst:
            result["moved"] += 1
            result["details"].append(f"{os.path.basename(src)} -> {dst}")
            if fhash:
                content_hashes[fhash] = dst
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
                    raw_number=p.raw_number or "",
                )
            # 6-0:归档成功后注册到表
            if fhash:
                try:
                    file_size = os.path.getsize(dst)
                except OSError:
                    file_size = 0
                self._register_standard(p, fhash, file_size)
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

    def _register_standard(self, parsed: Any, file_hash: str, file_size: int) -> None:
        """Q6-0: 将成功归档的标准注册到 standards 表。
        使用 INSERT OR IGNORE，四要素冲突时静默跳过。
        失败不回滚归档结果，仅记录错误日志。
        """
        sql = """
            INSERT OR IGNORE INTO standards (sha256, code, name, size, scan_status, updated_at)
            VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        """
        try:
            self._file_index.db.execute(sql, (file_hash, parsed.logical_code, parsed.std_name or "", file_size))
        except Exception as e:
            logger.error(
                "standards 表写入失败（文件已归档成功）: code=%s, hash=%s..., error=%s",
                getattr(parsed, "logical_code", "?"),
                file_hash[:16] if file_hash else "",
                e,
            )

    def _log_organize_summary(self, result: dict) -> None:
        """输出归类汇总日志。"""
        logger.info(
            "归类完成: %d 已移动 (Word: %d), %d 目标已存在(%d源保留), %d 内容去重跳过, %d 失败",
            result["moved"],
            result["word_mirrored"],
            result["skipped_exists"],
            result["skipped_source"],
            result["dedup_skipped"],
            result["failed"],
        )
        try:
            if result.get("failed", 0) > 0 and self._core.notification_mgr:  # type: ignore[attr-defined]  # organizer.py _core 属性由门面注入
                self._core.notification_mgr.send_event(  # type: ignore[attr-defined]
                    "archive_failed",
                    {"count": result["failed"], "error": "部分文件归档失败，请检查日志"},
                )
        except Exception as e:
            logger.warning("归档失败通知发送失败: %s", e)

    # __—相同标准号旧路径清理，避免分类变化导致双份文件
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
