# pilotstd/ui/controllers/scan_mixin.py
# 扫描相关方法的混入类 — 从 main_window.py 提取以减少单体类体积

import logging
import os
from typing import Any

from PyQt6.QtWidgets import QApplication, QMessageBox

from ...core import file_utils as core
from ...i18n import _  # 直接从 i18n 导入，避免循环引用
from ..workers import RowUpdate, ScanWorker

logger = logging.getLogger(__name__)


class ScanMixin:
    """扫描相关方法，混入 MainWindow。"""

    def _run_scan(self, root_path: str) -> None:
        """执行文件扫描并填充工作区表格。单文件直接解析，目录递归扫描。
        若 _parsed_results 已有数据，弹出追加/覆盖选择。"""
        if not self._mgr_ready:
            return
        if not root_path or not os.path.exists(root_path):
            self.status_changed.emit("请先选择一个有效的文件或文件夹")
            return

        # 工作区非空 → 追加/覆盖保护
        if self._parsed_results and not self._suppress_dialogs:
            msg = _("scan_overwrite_warning").format(count=len(self._parsed_results))
            reply = self._question_dlg(_("scan_overwrite_title"), msg)
            if reply == QMessageBox.StandardButton.No:
                # 追加：保留旧数据，不清空表格
                pass
            else:
                # 覆盖
                self._clear_table()
                self._parsed_results.clear()
        else:
            self._clear_table()
            self._parsed_results.clear()
        QApplication.processEvents()

        if os.path.isfile(root_path):
            self._scan_single_file(root_path)
        else:
            self._scan_directory(root_path)

        self._project.mark_dirty()

    def _scan_single_file(self, file_path: str) -> None:
        """直接解析单个文件，优先从索引恢复。"""
        filename = os.path.basename(file_path)
        self.status_changed.emit(f"扫描文件: {filename}")
        self._scan_source_root = os.path.dirname(os.path.abspath(file_path))
        self._unrecognized_files = []

        parsed = None
        file_hash = ""

        # 尝试从索引恢复
        if self._mgr.file_index:
            file_hash = core.FileIndexRepository._hash_file(file_path)
            existing = self._mgr.get_file_index(file_path)
            if existing and existing["file_hash"] == file_hash and file_hash:
                parsed = self._mgr.restore_parsed_from_index(file_path)

        # 索引未命中，走解析路径
        if parsed is None:
            parsed = self._mgr.parse_standard_number(filename)

        # [TRACE] 指令A-3: 输出文件索引查找/解析结果
        logger.debug(
            "[TRACE-A] 扫描结果: 文件=%r 解析成功=%s 标准名称=%r 代号=%s 序号=%s 年份=%s",
            file_path,
            parsed is not None,
            parsed.std_name if parsed else "",
            parsed.logical_code if parsed else "",
            parsed.number if parsed else 0,
            parsed.year if parsed else 0,
        )

        if parsed:
            parsed.source_path = file_path
            self._parsed_results.append(parsed)
            self._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="已扫描", total=1))
            self.status_changed.emit("扫描完成: 1 个文件, 1 个识别成功")
            self._register_task("扫描", 1, 1, 0)
            # 写入索引
            self._mgr.upsert_file_index(
                file_path,
                parsed.logical_code,
                parsed.number,
                parsed.year,
                part=parsed.part,
                std_name=parsed.std_name,
                status="现行",
            )
        else:
            self.status_changed.emit(f"无法识别标准号: {filename}")
            logger.debug(f"解析失败: {filename}")
            self._unrecognized_files.append(file_path)

    def _scan_directory(self, dir_path: str) -> None:
        """后台线程扫描目录，主线程只通过信号更新 UI。"""
        self.status_changed.emit(f"扫描中: {dir_path}")
        self._scan_source_root = os.path.abspath(dir_path)
        self._unrecognized_files = []
        self.progress_changed.emit(0)

        self._scan_worker = ScanWorker(self._mgr, dir_path, pause_event=self._pause_event, parent=self)
        self._scan_worker.batch_ready.connect(self._on_scan_batch_ready)
        self._scan_worker.progress.connect(
            lambda cur, total: self.progress_changed.emit(int(cur / total * 100) if total else 0)
        )
        self._scan_worker.finished_signal.connect(self._on_scan_finished)
        self._scan_worker.error.connect(lambda msg: self.status_changed.emit(f"扫描失败: {msg}"))
        self._scan_worker.start()

    def _on_scan_batch_ready(self, batch_rows: list[Any]) -> None:
        """后台线程批量通知：追加已解析文件到表格和结果列表。"""
        for seq, parsed in batch_rows:
            self._parsed_results.append(parsed)
            self._add_table_row(
                RowUpdate(
                    seq=seq,
                    parsed=parsed,
                    work_status="已扫描",
                    total=len(self._parsed_results),
                )
            )

    def _on_scan_finished(self, success: int, failed: int) -> None:
        """扫描完成：汇总统计并弹窗。"""
        self._unrecognized_files = self._scan_worker.unrecognized
        total = success + failed
        self.status_changed.emit(f"扫描完成: {total} 个文件, {success} 个识别成功, {failed} 个无法识别")
        self._register_task("扫描", total, success, failed)
        self._project.mark_dirty()
        # 若项目已有保存路径，立即持久化（含未识别文件列表），避免重启后丢失
        if self._project.current_path:
            state = self._collect_state()
            self._project.save(self._project.current_path, state)

        if failed > 0 and not self._suppress_dialogs:
            QMessageBox.information(
                self,
                _("dialog_scan_result"),
                _("msg_scan_complete").format(success=success, failed=failed) + "\n\n" + _("msg_scan_hint"),
            )
        self._update_button_states()
