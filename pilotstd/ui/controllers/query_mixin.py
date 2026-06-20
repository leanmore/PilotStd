# pilotstd/ui/controllers/query_mixin.py
# 查询相关方法的混入类

import logging
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...i18n import _
from ...models import ParsedStdInfo
from ..pending_query_dialog import PendingQueryDialog
from ..workers import QueryWorker, RowUpdate

logger = logging.getLogger(__name__)


class QueryMixin:
    """查询相关方法，混入 MainWindow。"""

    def _on_query_result_ready(self, idx: int, result):
        """实时刷新表格行（字段回写由 manager._classify_after_query 统一完成）。"""
        parsed = self._parsed_results[idx]
        source_label = getattr(result, "source_site", "") or "未知"

        # 更新表格行（按序号查找行，支持排序后仍准确定位）
        row = self._find_row_by_seq(idx + 1)
        if row < 0:
            return
        cells = [
            (1, f"已查询({source_label})"),
            (3, result.standard_name or parsed.std_name),
            (4, result.status),
            (5, result.replaces if result.replaces != "网站无此分类" else ""),
            (6, result.publish_date if result.publish_date != "网站无此分类" else ""),
            (
                7,
                result.implementation_date
                if result.implementation_date != "网站无此分类"
                else "",
            ),
            (
                8,
                result.responsible_dept
                if result.responsible_dept != "网站无此分类"
                else "",
            ),
            (9, "采标" if result.is_adopted else ""),
        ]
        for col, text in cells:
            item = self.work_table.item(row, col)
            if item:
                item.setText(text)

        # 状态列颜色（生效状态=第5列，0-based index=4）
        status_item = self.work_table.item(row, 4)
        if status_item:
            s = result.status
            if s in ("现行",):
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            elif s == "即将实施":
                status_item.setForeground(Qt.GlobalColor.blue)
            elif s in ("废止", "已废止", "作废"):
                status_item.setForeground(Qt.GlobalColor.red)
            elif s == "待确认":
                status_item.setForeground(Qt.GlobalColor.darkYellow)
            if not result.is_downloadable and s not in (
                "废止",
                "已废止",
                "作废",
                "待确认",
            ):
                status_item.setForeground(Qt.GlobalColor.darkYellow)

    def _on_query_batch_ready(self, batch: list):
        """批量处理查询结果：一次刷新多行表格，减少 Qt 布局计算次数。"""
        for idx, result in batch:
            self._on_query_result_ready(idx, result)

    def _on_query(self):
        if not self._mgr_ready:
            return
        if not self._parsed_results:
            choice = self._stage_prereq_dialog(
                _("title_hint"), _("msg_scan_prereq"), _("task_scan")
            )
            if choice == "run_prereq":
                self._on_scan()
                return
            if choice == "cancel":
                return
            # choice == "skip": 强制执行查询
        self._current_task = "query"

        total = len(self._parsed_results)

        if total > 0:
            plan = self._mgr.plan_batch(total)
            csres_count = sum(c for s, c in plan if s == "csres")
            if csres_count > 0:
                self._mgr.get_quota_info()
                msg = _("query_quota_msg").format(total)
                reply = self._question_dlg(_("query_quota_title"), msg)
                if reply != QMessageBox.StandardButton.Yes:
                    return

        self.status_changed.emit("查询中...")
        self.btn_query.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_changed.emit(0)

        self._clear_table()

        for i, parsed in enumerate(self._parsed_results):
            self._add_table_row(
                RowUpdate(
                    seq=i + 1, parsed=parsed, work_status="查询中...", total=total
                )
            )
        QApplication.processEvents()

        self.btn_query.setEnabled(False)
        self.btn_auto.setEnabled(False)

        def on_progress(current: int):
            self._check_pause()
            self.progress_changed.emit(
                current
            )  # QueryWorker 已发射百分比(0-100)，无需二次换算

        self._query_worker = QueryWorker(
            self._mgr, self._parsed_results, pause_event=self._pause_event, parent=self
        )
        self._query_worker.batch_ready.connect(self._on_query_batch_ready)
        self._query_worker.progress.connect(on_progress)

        def on_query_finished(results):
            self.btn_query.setEnabled(True)
            self.btn_auto.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self._show_query_summary()

        def on_query_error(msg):
            self.btn_query.setEnabled(True)
            self.btn_auto.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.status_changed.emit(f"查询失败: {msg}")
            logger.error(f"查询线程异常: {msg}")

        self._query_worker.finished_signal.connect(on_query_finished)
        self._query_worker.error.connect(on_query_error)
        self._query_worker.start()

    def _show_pending_dialog(self, pending_items: list) -> bool:
        """显示待确认清单对话框。返回 True=用户确认丢弃，False=取消。"""
        dlg = QDialog(self)  # type: ignore[arg-type]
        dlg.setWindowTitle(_("title_pending_confirm"))
        dlg.setMinimumSize(800, 400)
        layout = QVBoxLayout(dlg)

        info = QLabel(_("msg_pending_info").format(count=len(pending_items)))
        info.setWordWrap(True)
        layout.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            [
                _("query_pending_col_std_number"),
                _("query_pending_col_source_filename"),
                _("query_pending_col_web_name"),
                _("query_pending_col_local_year"),
                _("query_pending_col_web_number"),
                _("query_pending_col_status"),
                _("query_pending_col_confidence"),
                _("query_pending_col_source_site"),
            ]
        )
        table.setRowCount(len(pending_items))
        from ...query.search_strategy import CONFIDENCE_SCORE

        for row, parsed in enumerate(pending_items):
            fn = getattr(parsed, "found_number", "") or ""
            site = getattr(parsed, "found_source_site", "") or ""
            actual_score = CONFIDENCE_SCORE.get(parsed.match_status, -1)
            score = str(actual_score) if actual_score >= 0 else "≤80"
            items = [
                parsed.get_full_number(),
                parsed.std_name or "（文件名无名称）",
                parsed.found_name or "（未找到）",
                str(parsed.year),
                fn,
                parsed.effect_status,
                str(score),
                site,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, col, item)
        table.resizeColumnsToContents()
        layout.addWidget(table)

        # 保存状态提示标签
        save_status = QLabel("")
        save_status.setStyleSheet("color: #2a7d2a; font-size: 9pt;")

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save_csv"))
        discard_btn = QPushButton(_("btn_discard_pending"))
        cancel_btn = QPushButton(_("btn_cancel"))
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(save_status)
        btn_layout.addStretch()
        btn_layout.addWidget(discard_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        confirmed = False

        def on_save():
            # 自动保存到 exe/data 目录，文件名带时间戳，不弹 QFileDialog
            from datetime import datetime

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = (
                os.path.dirname(sys.executable)
                if getattr(sys, "frozen", False)
                else os.getcwd()
            )
            path = os.path.join(save_dir, f"pending_standards_{ts}.csv")
            try:
                import csv

                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        [
                            _("query_pending_col_std_number"),
                            _("query_pending_col_source_filename"),
                            _("query_pending_col_web_name"),
                            _("query_pending_col_local_year"),
                            _("query_pending_col_web_number"),
                            _("query_pending_col_status"),
                            _("query_pending_col_confidence"),
                            _("query_pending_col_source_site"),
                        ]
                    )
                    for row in range(table.rowCount()):
                        writer.writerow(
                            [
                                (
                                    table.item(row, c).text()
                                    if table.item(row, c)
                                    else ""
                                )
                                for c in range(8)
                            ]
                        )
                save_status.setText(f"已保存: pending_standards_{ts}.csv")
                save_status.setStyleSheet("color: #2a7d2a; font-size: 9pt;")
            except OSError as e:
                save_status.setText(f"保存失败: {e}")
                save_status.setStyleSheet("color: #e74c3c; font-size: 9pt;")

        def on_discard():
            nonlocal confirmed
            confirmed = True
            dlg.accept()

        save_btn.clicked.connect(on_save)
        discard_btn.clicked.connect(on_discard)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()
        return confirmed

    def _show_query_summary(self):
        total = len(self._parsed_results)
        # 分类已由 manager._classify_after_query 完成，此处仅做 UI 统计

        # 处理待确认项
        pending = [p for p in self._parsed_results if p.next_action == "pending"]
        if pending:
            self._write_pending_to_db(pending)
        if pending and not self._suppress_dialogs:
            if self._show_pending_dialog(pending):
                self._parsed_results = [
                    p for p in self._parsed_results if p.next_action != "pending"
                ]
                self._resolve_pending_in_db(pending, "discarded")
                self._clear_table()
                new_total = len(self._parsed_results)
                for i, parsed in enumerate(self._parsed_results):
                    self._add_table_row(
                        RowUpdate(
                            seq=i + 1,
                            parsed=parsed,
                            work_status="已分类",
                            total=new_total,
                        )
                    )
                total = new_total
                self.status_changed.emit(
                    _("pending_discarded").format(len(pending), total)
                )

        # 分类统计
        archive_count = sum(
            1 for p in self._parsed_results if p.next_action == "archive"
        )
        normalize_count = sum(
            1 for p in self._parsed_results if p.next_action == "normalize"
        )
        expire_count = sum(1 for p in self._parsed_results if p.next_action == "expire")
        not_found_count = sum(
            1 for p in self._parsed_results if p.next_action == "not_found"
        )
        pending_count = sum(
            1 for p in self._parsed_results if p.next_action == "pending"
        )

        expired_moved = 0
        if expire_count > 0:
            expired_moved = self._auto_move_expired()

        self.status_changed.emit(f"查询完成: {total} 条")
        self._project.mark_dirty()
        self._register_task("查询", total, total)

        from ...core.notify import NotifyService

        NotifyService.get().show(
            _("query_toast_title"),
            _("query_toast_msg").format(
                total=total,
                archive=archive_count,
                pending=pending_count,
                expire=expire_count,
            ),
        )

        if not self._suppress_dialogs:
            lines = [_("query_results_total").format(total)]
            if archive_count > 0:
                lines.append(_("query_summary_archive").format(count=archive_count))
            if normalize_count > 0:
                lines.append(_("query_summary_normalize").format(count=normalize_count))
            if expire_count > 0:
                extra = (
                    f" ({_('expired_move_info').format(expired_moved)})"
                    if expired_moved
                    else ""
                )
                lines.append(
                    _("query_summary_expire").format(count=expire_count, extra=extra)
                )
            if pending_count > 0:
                lines.append(_("query_summary_pending").format(count=pending_count))
            if not_found_count > 0:
                lines.append(_("query_summary_not_found").format(count=not_found_count))

            # 逐文件状态详情（每类最多显示15个）
            detail_section = []
            cat_keys = {
                "archive": "query_cat_archive",
                "normalize": "query_cat_normalize",
                "expire": "query_cat_expire",
                "pending": "query_cat_pending",
                "not_found": "query_cat_not_found",
            }
            for cat_action in [
                "archive",
                "normalize",
                "expire",
                "pending",
                "not_found",
            ]:
                cat_label = _(cat_keys[cat_action])
                cat_items = [
                    p for p in self._parsed_results if p.next_action == cat_action
                ]
                if cat_items:
                    cat_details = []
                    for p in cat_items[:15]:
                        fname = (
                            os.path.basename(getattr(p, "source_path", "") or "")
                            or getattr(p, "raw_filename", "")
                            or p.get_full_number()
                        )
                        cat_details.append(f"    • {fname}")
                    if cat_details:
                        detail_section.append(f"  {cat_label}:")
                        detail_section.extend(cat_details)
                        if len(cat_items) > 15:
                            detail_section.append(
                                f"    ... 还有 {len(cat_items) - 15} 个"
                            )
            if detail_section:
                lines.append("")
                lines.extend(detail_section)

            download_count = sum(
                1 for p in self._parsed_results if p.next_action == "download"
            )
            actions = []
            if download_count > 0:

                def do_download():
                    self._switch_to_stage("download")
                    self._on_download()

                actions.append((f"开始下载({download_count}条)", do_download))
            if pending_count > 0:

                def do_pending():
                    self._switch_to_stage("pending")
                    pending_items = [
                        p for p in self._parsed_results if p.next_action == "pending"
                    ]
                    dlg = PendingQueryDialog(self._mgr, pending_items, self)
                    dlg.exec()

                actions.append((f"处理待确认({pending_count}条)", do_pending))
            if download_count == 0 and pending_count == 0:
                if normalize_count > 0:
                    actions.append((_("next_step_normalize"), self._on_normalize))
                elif archive_count > 0:
                    actions.append((_("next_step_save"), self._on_save_to_folder))
            self._show_stage_dialog_multi(
                _("query_results_title"), "\n".join(lines), actions
            )

        self._current_task = None

    def _on_pending_query(self):
        """待确认二次查询：导入 CSV，选择站点，执行独立查询。"""
        try:
            self._do_pending_query()
        except Exception as e:
            logger.exception("待确认查询异常")
            QMessageBox.critical(self, _("title_error"), f"待确认查询失败: {e}")

    def _do_pending_query(self):
        if not self._mgr_ready:
            return
        if self._parsed_results:
            QMessageBox.warning(self, _("title_hint"), _("workspace_not_empty"))
            return

        path, __ = QFileDialog.getOpenFileName(
            self, _("dialog_import_pending"), "", _("file_filter_csv")
        )
        if not path:
            return

        import csv

        parsed_list: list[ParsedStdInfo] = []
        failed_names: list[str] = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            QMessageBox.warning(self, _("title_hint"), _("csv_empty"))
            return
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if not row or not row[0].strip():
                continue
            std_num = row[0].strip()
            try:
                parsed = self._mgr.parse_standard_number(std_num + ".pdf")
            except Exception as e:
                logger.warning("解析标准号失败: %s — %s", std_num, e)
                failed_names.append(std_num)
                continue
            if parsed:
                parsed.std_name = (
                    row[1].strip()
                    if len(row) > 1 and row[1].strip()
                    else parsed.std_name
                )
                parsed_list.append(parsed)
            else:
                failed_names.append(std_num)

        if not parsed_list:
            QMessageBox.warning(self, _("title_hint"), _("csv_no_standards"))
            return

        msg = _("msg_csv_parse_result").format(count=len(parsed_list))
        if failed_names:
            msg += (
                f"，{_('msg_csv_unrecognized').format(count=len(failed_names))}:\n"
                + "\n".join(failed_names[:5])
            )
            if len(failed_names) > 5:
                msg += f"\n... 等共 {len(failed_names)} 条"
        msg += "\n\n是否继续？"
        reply = self._question_dlg(_("title_pending_query"), msg)
        if reply != QMessageBox.StandardButton.Yes:
            self.status_changed.emit("已取消待确认查询，工作区未变更。")
            return

        dlg = PendingQueryDialog(self._mgr, parsed_list, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.status_changed.emit("已取消待确认查询，工作区未变更。")
            return

        dlg.get_results()
        self._clear_table()
        self._parsed_results = parsed_list

        for i, parsed in enumerate(self._parsed_results):
            self._add_table_row(
                RowUpdate(
                    seq=i + 1,
                    parsed=parsed,
                    work_status="已查询",
                    total=len(self._parsed_results),
                )
            )

        total = len(self._parsed_results)
        found = sum(1 for p in self._parsed_results if p.found_name)
        self.status_changed.emit(f"待确认查询完成: {found}/{total}")

        QMessageBox.information(
            self,
            _("title_pending_query_complete"),
            _("msg_pending_query_complete").format(found=found, failed=total - found),
        )

    def _write_pending_to_db(self, pending_items: list) -> None:
        """将待确认项写入 pending_lookup 表（委托 manager）。"""
        self._mgr.record_pending(pending_items)

    def _resolve_pending_in_db(self, pending_items: list, resolution: str) -> None:
        """标记待确认项为已处理（委托 manager）。"""
        self._mgr.resolve_pending(pending_items, resolution)

    def _check_pending_lookup(self) -> None:
        """启动时检查待确认清单（委托 manager）。"""
        if not self._mgr_ready:
            return
        pending_rows = self._mgr.get_pending_items()
        if not pending_rows:
            return
        count = len(pending_rows)
        nums = [r["standard_number"] for r in pending_rows[:5]]
        msg = _("pending_lookup_msg").format(count) + "\n" + "\n".join(nums)
        if count > 5:
            msg += f"\n... 等共 {count} 条"
        msg += "\n" + _("pending_lookup_hint")
        QMessageBox.information(self, _("pending_lookup_title"), msg)  # type: ignore[arg-type]
