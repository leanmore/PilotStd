# pilotstd/scan/scanner.py
# 文件系统扫描器（防御性遍历，跳过指定目录）

import logging
import os
from typing import Any, List, Optional

from ..core.file_utils import hash_file_content, normalize_std_filename
from ..models import FileInfo, ScanResult

logger = logging.getLogger(__name__)


class FileScanner:
    """防御性文件扫描器，支持跳过特定目录、长路径前缀、异常容错、内容去重。

    去重机制（两层）：
      1. 内存 HashSet — 本批次内相同 SHA-256 的文件只保留第一个
      2. file_index 查哈希 — 跨扫描持久化去重，可选
    """

    def __init__(self, config_manager: Any, log: Optional[logging.Logger] = None,
                 file_index: Optional[Any] = None):
        """
        Args:
            config_manager: 配置管理器，需提供 get(key, default) 方法
            log: 日志记录器，若为 None 则使用全局 logger
            file_index: 可选，FileIndexRepository 实例，用于跨扫描内容去重
        """
        self.skip_dir_names = config_manager.get("scan.skip_folders", ["过期作废"])
        self.supported_exts = config_manager.get("scan.extensions", [".pdf", ".doc", ".docx", ".txt"])
        self.skip_file_keywords = config_manager.get("scan.exclude_patterns", [])
        self.skip_query_exts = config_manager.get("scan.skip_query_exts", [".doc", ".docx"])
        self.log = log or logger
        # 去重：内存哈希集合（本批次）+ 可选的持久化索引（跨扫描）
        self._seen_hashes: set[str] = set()
        self._file_index = file_index
        self._dup_count = 0  # 去重计数

    def scan(self, root_paths: List[str]) -> ScanResult:
        """扫描多个根目录，返回 ScanResult"""
        from ..core.file_utils import ensure_long_path
        result = ScanResult()
        for root in root_paths:
            safe_root = ensure_long_path(root)

            if not os.path.exists(safe_root):
                result.add_warning(f"路径不存在: {root}")
                self.log.warning(f"路径不存在，跳过: {root}")
                continue

            self._scan_recursive(safe_root, result)
        return result

    def _scan_recursive(self, start_dir: str, result: ScanResult):
        """栈遍历扫描目录（非递归，避免深层目录爆栈）。"""
        stack = [start_dir]
        while stack:
            current_dir = stack.pop()
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name in self.skip_dir_names:
                                    # 记录跳过目录路径，供归档阶段原样移动
                                    result.skipped_dirs.append(entry.path)
                                    msg = f"跳过目录(将原样归档): {entry.path}"
                                    result.add_warning(msg)
                                    self.log.info("跳过目录: %s", entry.name)
                                    continue
                                stack.append(entry.path)
                            elif not entry.is_file():
                                continue
                            # 以下处理文件
                            if not self._is_supported(entry.name):
                                continue
                            # 关键词排除
                            if self._should_skip_by_keyword(entry.name):
                                result.stats.skipped += 1
                                self.log.info("扫描跳过: %s", os.path.basename(entry.path))
                                continue
                            try:
                                stat = entry.stat()
                            except OSError as e:
                                result.add_warning(f"获取文件状态失败 {entry.path}: {e}")
                                self.log.warning(f"stat失败: {entry.path} - {e}")
                                continue
                            # 内容级去重：计算 SHA-256，本批次 + 跨扫描两层过滤
                            try:
                                file_hash = hash_file_content(entry.path)
                                # 第1层：本批次已见过
                                if file_hash in self._seen_hashes:
                                    self._dup_count += 1
                                    self.log.debug(f"内容重复(本批次): {entry.path}")
                                    continue
                                # 第2层：跨扫描持久化索引（仅校验完成后启用）
                                if self._file_index is not None:
                                    if self._file_index.is_validation_complete:
                                        existing = self._file_index.find_by_hash(file_hash)
                                        if existing is not None:
                                            self._dup_count += 1
                                            self.log.debug(f"内容重复(已归档): {entry.path} -> {existing.get('file_path', '?')}")
                                            continue
                                self._seen_hashes.add(file_hash)
                            except OSError:
                                file_hash = ""  # 读取失败不阻塞扫描

                            # Word/模板文件标记为跳过查询，但仍保留在扫描结果中供归档
                            file_status = "word_template" if self._is_skip_query_file(entry.name) else "pending"
                            file_info = FileInfo(
                                full_path=entry.path,
                                filename=normalize_std_filename(entry.name),
                                size=stat.st_size,
                                mtime=stat.st_mtime,
                                status=file_status
                            )
                            result.add_file(file_info)
                            logger.debug("扫描: %s -> %s", file_status, entry.name)
                        except PermissionError as e:
                            result.add_warning(f"无权限访问: {entry.path}")
                            self.log.warning(f"权限错误: {entry.path} - {e}")
                        except OSError as e:
                            result.add_warning(f"文件系统错误: {entry.path} - {e}")
                            self.log.warning(f"OS错误: {entry.path} - {e}")
                        except (ValueError, RuntimeError) as e:
                            result.add_warning(f"处理错误 {entry.path}: {str(e)}")
                            self.log.exception(f"处理条目异常: {entry.path}")
            except PermissionError as e:
                result.add_warning(f"无权限遍历目录: {current_dir}")
                self.log.warning(f"无法遍历目录 {current_dir}: {e}")
            except OSError as e:
                if e.winerror in (206, 123):  # 超长路径等Windows错误
                    result.add_warning(f"遍历目录失败(路径过长): {current_dir}")
                    self.log.warning(f"路径过长: {current_dir} - {e}")
                    continue
                raise
            except (ValueError, RuntimeError) as e:
                result.add_warning(f"遍历目录失败 {current_dir}: {str(e)}")
                self.log.exception(f"遍历目录异常: {current_dir}")

    def _is_supported(self, filename: str) -> bool:
        return any(filename.lower().endswith(ext) for ext in self.supported_exts)

    def _should_skip_by_keyword(self, filename: str) -> bool:
        """检查文件名是否包含排除关键词"""
        for kw in self.skip_file_keywords:
            if kw in filename:
                return True
        return False

    def _is_skip_query_file(self, filename: str) -> bool:
        """检查文件是否属于跳过查询的类型（如 Word 模板）"""
        return any(filename.lower().endswith(ext) for ext in self.skip_query_exts)

    @property
    def dup_count(self) -> int:
        """本次扫描去重跳过的文件数。"""
        return self._dup_count
