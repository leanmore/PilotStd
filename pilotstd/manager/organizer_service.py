# pilotstd/manager/organizer_service.py
# OrganizerService — 归类移动 + 过期处理，将已处理的文件归入分类目录

import logging
import os
import shutil
import stat
from typing import Any, List

from ..core.config import get_library_root
from ..core.file_utils import (
    ensure_long_path,
    hash_file_content,
    safe_move,
    strip_long_path,
)
from ..organizer.industry_lookup import (
    FOREIGN_CODES,
    INDUSTRY_MAP,
    NATIONAL_CODES,
    get_folder_name,
    is_db_code,
)

logger = logging.getLogger(__name__)


class OrganizerService:
    """归类服务：将标准文件按代号/名称归类到标准库目录，处理过期作废、Word镜像归档。

    目录结构：<标准库根目录>/<标准代号>/<标准名称>/<文件名>
    例如：D:/标准/GB 国家标准/GB 19001-2020 质量管理体系.pdf

    Word/模板文件按源目录镜像归档：<输出根>/<相对源根路径>/<文件名>
    """

    # 兜底镜像中需跳过的系统垃圾文件
    _FALLBACK_SKIP_FILES = frozenset({"Thumbs.db", "sync.ffs_db"})
    _FALLBACK_SKIP_PREFIX = "~$"  # Office 临时锁文件

    def __init__(self, cfg, file_index, dir_builder, file_mover, expire_handler):
        """注入依赖。

        Args:
            cfg: ConfigManager 实例
            file_index: FileIndexRepository 实例
            dir_builder: DirBuilder 实例
            file_mover: FileMover 实例
            expire_handler: ExpireHandler 实例
        """
        self._cfg = cfg
        self._file_index = file_index
        self._dir_builder = dir_builder
        self._file_mover = file_mover
        self._expire_handler = expire_handler
        # organize() 中目标已存在的源文件集合，供 organize_fallback() 跳过
        self._skipped_source_files: set = set()

    # ════════════════════════════════════════════════════════════════
    # 归类移动
    # ════════════════════════════════════════════════════════════════

    def organize(self, parsed_list: list, word_source_root: str | None = None) -> dict:
        """将已处理的文件移动到分类目录。

        目录结构：<标准库根目录>/<标准代号>/<标准名称>/<文件名>
        例如：D:/标准/GB 国家标准/GB 19001-2020 质量管理体系.pdf

        Word/模板文件按源目录镜像归档：
        <输出根>/<相对源根路径>/<文件名>
        """
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
        # 内容去重：全局限哈希表，防止同内容不同名文件重复归档
        _content_hashes: dict[str, str] = {}
        _org_total = len(items)
        _org_count = 0
        _org_t0 = 0.0  # 首次处理时赋值
        import time as _time

        for p in items:
            _org_count += 1
            # 每 50 条或首条输出进度（CLI 大目录归档时有用）
            if _org_count == 1:
                _org_t0 = _time.monotonic()
            if _org_count % 50 == 0 or _org_count == _org_total:
                _elapsed = _time.monotonic() - _org_t0 if _org_t0 else 0
                _pct = int(_org_count / _org_total * 100) if _org_total > 0 else 0
                logger.info(
                    "归档进度: %d/%d (%d%%) 已耗时 %.0fs",
                    _org_count,
                    _org_total,
                    _pct,
                    _elapsed,
                )
        for p in items:
            src = getattr(p, "source_path", "")
            if src and os.path.isfile(src):
                # Word/模板文件：按源目录镜像归档（与跳过目录一致，不加"其他资料"中间层）
                if self._is_word_or_template(src):
                    # 去掉 Windows 长路径前缀
                    clean_src = strip_long_path(src)
                    clean_root = (
                        strip_long_path(word_source_root) if word_source_root else ""
                    )
                    if clean_root and clean_src.startswith(clean_root):
                        rel = clean_src[len(clean_root) :].lstrip(os.sep)
                    else:
                        rel = os.path.basename(clean_src)
                    # Word镜像路径同步行业代号→完整目录名（与PDF归档一致）
                    rel = self._resolve_industry_in_path(rel)
                    dst = os.path.join(root, rel)
                    if dst:
                        try:
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            if os.path.exists(dst):
                                logger.debug(
                                    f"Word 目标已存在，跳过: {os.path.basename(src)}"
                                )
                                result["skipped_exists"] += 1
                                result["word_mirrored"] += 1
                                self._skipped_source_files.add(clean_src)
                                continue
                            safe_move(src, dst, on_exists="skip")
                            result["moved"] += 1
                            result["word_mirrored"] += 1
                            result["details"].append(
                                f"Word: {os.path.basename(src)} -> {dst}"
                            )
                            # Word 文件归档后写入索引（代号用 WORD 标记）
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
                            logger.warning(
                                "Word 归档失败(权限不足): %s — 请关闭占用程序后重试",
                                os.path.basename(src),
                            )
                            result["failed"] += 1
                            result["details"].append(
                                f"Word 归档失败(权限不足): {os.path.basename(src)} — 请关闭占用程序后重试"
                            )
                        except OSError as e:
                            logger.warning(
                                f"Word 归档失败: {os.path.basename(src)} - {e}"
                            )
                            result["failed"] += 1
                            result["details"].append(
                                f"Word 归档失败: {os.path.basename(src)} - {e}"
                            )
                    else:
                        logger.warning(f"Word 路径计算失败: {src}")
                        result["failed"] += 1
                        result["details"].append(f"Word: 无法计算目标路径: {src}")
                else:
                    # 内容去重：计算源文件哈希，全局比对
                    try:
                        fhash = hash_file_content(src)
                    except OSError:
                        fhash = None
                    if fhash and fhash in _content_hashes:
                        logger.info(
                            "内容重复，跳过: %s (已归档为 %s)",
                            os.path.basename(src),
                            _content_hashes[fhash],
                        )
                        result["dedup_skipped"] += 1
                        continue
                    dst = mover.move_to_code_dir(src, p)
                    if dst:
                        result["moved"] += 1
                        result["details"].append(f"{os.path.basename(src)} -> {dst}")
                        # 登记内容哈希
                        if fhash:
                            _content_hashes[fhash] = dst
                        # 去重：同标准号旧路径残留（分类变化导致双份文件）
                        self._dedup_standard(p, dst)
                        # 归档成功后写入文件索引
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
                        # 目标已存在（safe_move 返回 False）
                        result["skipped_exists"] += 1
                        result["skipped_source"] += 1
                        self._skipped_source_files.add(src)
                        # 配置开启时自动清理源文件（SHA-256 由 safe_move 内部确认）
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
            f"归类完成: {result['moved']} 已移动 (Word: {result['word_mirrored']}), "
            f"{result['skipped_exists']} 目标已存在({result['skipped_source']}源保留), "
            f"{result['dedup_skipped']} 内容去重跳过, {result['failed']} 失败"
        )
        return result

    # ════════════════════════════════════════════════════════════════
    # 去重
    # ════════════════════════════════════════════════════════════════

    def _dedup_standard(self, parsed, new_path: str):
        """去重：同标准号旧路径残留（分类变化导致双份文件）。"""
        if not self._file_index:
            return
        dups = self._file_index.find_by_standard(
            parsed.logical_code,
            parsed.number,
            parsed.year,
            getattr(parsed, "part", None),
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

    # ════════════════════════════════════════════════════════════════
    # Word/模板识别
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _is_word_or_template(src_path: str) -> bool:
        """通过扩展名判断是否为 Word/模板文件"""
        return src_path.lower().endswith((".doc", ".docx"))

    # ════════════════════════════════════════════════════════════════
    # 跳过目录镜像
    # ════════════════════════════════════════════════════════════════

    def organize_skipped_dirs(
        self, skipped_dirs: List[str], source_root: str | None = None
    ) -> dict:
        """将扫描时跳过的目录原封不动镜像到新库。

        不扫描、不解析、不改名、不改后缀、不改变目录层次——整体移动。
        目标路径 = <输出根>/<相对源根路径>，保留原始目录结构。
        """
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
            # 去掉 Windows 长路径前缀
            clean_src = src_dir[4:] if src_dir.startswith("\\\\?\\") else src_dir
            clean_root = (
                source_root[4:]
                if source_root and source_root.startswith("\\\\?\\")
                else source_root
            )
            if clean_root:
                try:
                    rel = os.path.relpath(clean_src, clean_root)
                except ValueError:
                    rel = os.path.basename(clean_src)
            else:
                rel = os.path.basename(clean_src)
            rel = self._resolve_industry_in_path(rel)
            dst = os.path.join(root, rel)
            # 校验目标路径在库根目录内，防止路径遍历
            if not os.path.realpath(dst).startswith(os.path.realpath(root) + os.sep):
                logger.error("路径越界被拒绝: %s", dst)
                result["failed"] += 1
                result["details"].append(
                    f"跳过目录移动被拒绝(路径越界): {os.path.basename(src_dir)}"
                )
                continue
            try:
                if os.path.exists(dst):
                    # 目标目录已存在 → 逐文件移动，不整目录跳过
                    for fname in os.listdir(src_dir):
                        src_file = os.path.join(src_dir, fname)
                        dst_file = os.path.join(dst, fname)
                        if os.path.isfile(src_file):
                            if safe_move(src_file, dst_file, on_exists="skip"):
                                result["moved"] += 1
                            else:
                                result["details"].append(f"跳过(目标已存在): {fname}")
                        elif os.path.isdir(src_file):
                            # 子目录递归处理
                            try:
                                os.makedirs(dst_file, exist_ok=True)
                                for sub_fname in os.listdir(src_file):
                                    sub_src = os.path.join(src_file, sub_fname)
                                    sub_dst = os.path.join(dst_file, sub_fname)
                                    if os.path.isfile(sub_src):
                                        if safe_move(
                                            sub_src, sub_dst, on_exists="skip"
                                        ):
                                            result["moved"] += 1
                                    elif os.path.isdir(sub_src):
                                        # 清除只读属性后移动子目录
                                        if self._cfg.get("file.clear_readonly", True):
                                            for _r, _ds, _fs in os.walk(sub_src):
                                                for _f in _fs:
                                                    try:
                                                        os.chmod(
                                                            os.path.join(_r, _f),
                                                            stat.S_IWRITE,
                                                        )
                                                    except OSError:
                                                        pass
                                        shutil.move(sub_src, sub_dst)
                                        result["moved"] += 1
                            except OSError as e:
                                result["details"].append(
                                    f"跳过目录子项移动失败: {fname} - {e}"
                                )
                else:
                    # 清除源目录下所有文件的只读属性，防止 shutil.move → rmtree 崩溃
                    if self._cfg.get("file.clear_readonly", True):
                        for _root, _dirs, _files in os.walk(src_dir):
                            for _f in _files:
                                try:
                                    os.chmod(os.path.join(_root, _f), stat.S_IWRITE)
                                except OSError:
                                    pass
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(src_dir, dst)
                    result["moved"] += 1
                    result["details"].append(
                        f"跳过目录: {os.path.basename(src_dir)} -> {dst}"
                    )
            except OSError as e:
                result["failed"] += 1
                result["details"].append(
                    f"跳过目录移动失败: {os.path.basename(src_dir)} - {e}"
                )
                logger.warning(f"跳过目录移动失败: {os.path.basename(src_dir)} - {e}")
        logger.info(f"跳过目录归档: {result['moved']} 已移动, {result['failed']} 失败")
        return result

    # ════════════════════════════════════════════════════════════════
    # 行业代号路径解析
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _resolve_industry_in_path(rel_path: str) -> str:
        """解析相对路径第一段中的行业代号为完整目录名。

        源目录的跳过子目录保留了原始行业代号（如 API），
        但主归档已将文件移至完整目录名（如 API 美国石油学会）。
        此方法将跳过目录的目标路径同步到与主归档一致。
        """
        if not rel_path:
            return rel_path
        parts = rel_path.split(os.sep, 1)
        first = parts[0]
        # 守卫条件：覆盖 INDUSTRY_MAP（国内行业）、NATIONAL_CODES（国标）、FOREIGN_CODES（国外）、DB 代码
        if (
            first in INDUSTRY_MAP
            or first in NATIONAL_CODES
            or first in FOREIGN_CODES
            or is_db_code(first)
        ):
            resolved = get_folder_name(first)
            if resolved != first:
                return os.path.join(resolved, parts[1]) if len(parts) > 1 else resolved
        return rel_path

    # ════════════════════════════════════════════════════════════════
    # 兜底镜像
    # ════════════════════════════════════════════════════════════════

    def organize_fallback(self, source_root: str) -> dict:
        """归档收尾：将源目录中所有残留文件按目录结构镜像到输出目录。

        不解析、不分类、不查询。跳过系统垃圾文件（Thumbs.db、~$* 等）。
        在正常归档和 organize_skipped_dirs 之后调用。
        """
        # Windows 长路径支持：统一使用 ensure_long_path
        source_root = ensure_long_path(source_root)
        root = get_library_root(self._cfg)
        # 去掉 \\?\ 前缀以计算相对路径
        clean_src_root = strip_long_path(source_root)

        result: dict[str, Any] = {
            "moved": 0,
            "failed": 0,
            "skipped_exists": 0,
            "word_mirrored": 0,
            "skipped": 0,
            "skipped_by_organize": 0,
            "details": [],
        }
        for dirpath, dirnames, filenames in os.walk(source_root):
            for fname in filenames:
                if fname in self._FALLBACK_SKIP_FILES or fname.startswith(
                    self._FALLBACK_SKIP_PREFIX
                ):
                    result["skipped"] += 1
                    continue
                src = os.path.join(dirpath, fname)
                # organize() 已确认目标存在的文件，fallback 不再搬运
                if src in self._skipped_source_files:
                    result["skipped_by_organize"] += 1
                    continue
                # 去掉可能的前缀，计算相对于源根目录的路径
                clean_dir = dirpath[4:] if dirpath.startswith("\\\\?\\") else dirpath
                clean_dir = clean_dir.lstrip("\\")
                try:
                    rel_dir = os.path.relpath(clean_dir, clean_src_root)
                except ValueError:
                    rel_dir = ""
                if rel_dir == ".":
                    rel_dir = ""
                rel_dir = self._resolve_industry_in_path(rel_dir)
                dst = (
                    os.path.join(root, rel_dir, fname)
                    if rel_dir
                    else os.path.join(root, fname)
                )
                try:
                    if safe_move(src, dst, on_exists="skip"):
                        result["moved"] += 1
                    else:
                        result["skipped"] += 1
                except OSError as e:
                    result["failed"] += 1
                    result["details"].append(f"兜底镜像失败: {fname} - {e}")
        logger.info(
            f"兜底镜像完成: {result['moved']} 已移动, {result['skipped']} 已跳过"
            f"({result['skipped_by_organize']}因目标已存在), {result['failed']} 失败"
        )
        return result

    # ════════════════════════════════════════════════════════════════
    # 过期处理
    # ════════════════════════════════════════════════════════════════

    def handle_expired(self, parsed_list: list) -> dict:
        """将查询结果为「废止」的标准移入 过期作废 目录。"""
        items = parsed_list

        pairs = []
        for p in items:
            src = getattr(p, "source_path", "")
            if src and os.path.isfile(src):
                pairs.append((src, p))

        return self._expire_handler.process_expired(pairs)

    def merge_expire_from_source(self, root_dir: str, parsed_list: list) -> int:
        """将源目录中的过期作废文件夹合并到标准库对应目录。返回合并文件数。"""
        import os as _os

        from ..core.file_utils import safe_move as _safe_move

        expire_folder = self._cfg.get("storage.expire_folder", "过期作废")
        source_dirs = set()
        for parsed in parsed_list:
            src = getattr(parsed, "source_path", "")
            if src and _os.path.exists(src):
                source_dirs.add(_os.path.dirname(src))
        merged = 0
        for src_dir in source_dirs:
            src_expire = _os.path.join(src_dir, expire_folder)
            if not _os.path.isdir(src_expire):
                continue
            for parsed in parsed_list:
                src = getattr(parsed, "source_path", "")
                if not src or not src.startswith(src_dir):
                    continue
                folder_name = get_folder_name(parsed.logical_code)
                tgt_expire = _os.path.join(root_dir, folder_name, expire_folder)
                _os.makedirs(tgt_expire, exist_ok=True)
                for item in _os.listdir(src_expire):
                    src_item = _os.path.join(src_expire, item)
                    tgt_item = _os.path.join(tgt_expire, item)
                    if _os.path.isfile(src_item) and not _os.path.exists(tgt_item):
                        try:
                            _safe_move(src_item, tgt_item, on_exists="skip")
                            merged += 1
                        except OSError:
                            pass
                try:
                    if not _os.listdir(src_expire):
                        _os.rmdir(src_expire)
                except OSError:
                    pass
        return merged
