# pilotstd/ui/controllers/archive_mixin.py
# 归档/规范化相关方法的混入类 — 从 main_window.py 提取以减少单体类体积

import logging
import os

from PyQt6.QtWidgets import QMessageBox

from ... import core
from ...i18n import _
from ..workers import ArchiveWorker, NormalizeWorker, RowUpdate

logger = logging.getLogger(__name__)


class ArchiveMixin:
    """归档/规范化相关方法，混入 MainWindow。"""

    def _on_normalize(self):
        self._current_task = "normalize"
        if not self._parsed_results:
            choice = self._stage_prereq_dialog(
                _("title_hint"), _("msg_scan_prereq"), _("task_scan")
            )
            if choice == "run_prereq":
                self._on_scan()
                return
            if choice == "cancel":
                return
            # choice == "skip": 强制执行
        # 标准名称缺失时提示查询补全（主线程弹出对话框）
        missing = [
            p.get_full_number()
            for p in self._parsed_results
            if not p.std_name and not p.found_name
        ]
        if missing:
            more = f"\n... 还有 {len(missing) - 5} 条" if len(missing) > 5 else ""
            reply = self._question_dlg(
                _("title_missing_name"),
                _("msg_missing_name").format(
                    count=len(missing), list="\n".join(missing[:5]), more=more
                ),
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_query()
        # 名称冲突检测：路由阶段标记为 name_conflict 的条目
        conflicts = [
            p
            for p in self._parsed_results
            if getattr(p, "stage_status", "") == "name_conflict"
        ]
        if conflicts and not self._suppress_dialogs:
            resolved = self._show_name_conflict_dialog(conflicts)
            # 用户取消的条目写入 pending_lookup
            for p in conflicts:
                if getattr(p, "stage_status", "") == "name_conflict":
                    self._mgr.record_pending([p])
            # 用户已选择的条目移回归档流程
            for p in resolved:
                p.stage_status = "archive_ready"
        elif conflicts:
            # 自动运行模式：直接写入 pending_lookup
            self._mgr.record_pending(conflicts)
        self._clear_table()
        # 后台线程计算规范文件名
        self._normalize_worker = NormalizeWorker(
            self._mgr, self._parsed_results, pause_event=self._pause_event, parent=self
        )
        self._normalize_worker.batch_ready.connect(self._on_normalize_batch_ready)
        self._normalize_worker.progress.connect(self.progress_changed.emit)

        def on_normalize_finished():
            count = len(self._parsed_results)
            self.status_changed.emit(_("normalize_complete").format(count))
            self._register_task("规范化", count, count)
            self._current_task = None
            if not self._suppress_dialogs:
                self._show_stage_dialog(
                    _("normalize_results_title"),
                    _("msg_normalize_done").format(count=count),
                    next_action=self._on_save_to_folder,
                    next_label=_("next_step_save"),
                )

        self._normalize_worker.finished_signal.connect(on_normalize_finished)
        self._normalize_worker.start()

    def _on_normalize_batch_ready(self, batch: list):
        """批量更新规范化结果到表格。"""
        for idx, parsed, name in batch:
            self._add_table_row(
                RowUpdate(
                    seq=idx + 1,
                    parsed=parsed,
                    work_status="已规范化",
                    std_name_override=name,
                    total=len(self._parsed_results),
                )
            )

    def _on_save_to_folder(self):
        """将文件以规范名称归档到标准库目录。后台线程执行文件操作。"""
        if not self._mgr_ready:
            return
        self._current_task = "archive"
        if not self._parsed_results:
            choice = self._stage_prereq_dialog(
                _("title_hint"), _("msg_scan_prereq"), _("task_scan")
            )
            if choice == "run_prereq":
                self._on_scan()
                return
            if choice == "cancel":
                return
            # choice == "skip": 强制执行
        root_dir = self._get_library_root()

        # 冲突预检（主线程，可弹窗）
        overwrite_all = False
        conflicts = []
        for i, parsed in enumerate(self._parsed_results):
            if not parsed.source_path or not os.path.exists(parsed.source_path):
                continue
            dst = ArchiveWorker.target_path(parsed, root_dir, self._config)
            if dst and os.path.exists(dst):
                conflicts.append((os.path.basename(parsed.source_path), dst))

        if conflicts and not self._suppress_dialogs:
            count = len(conflicts)
            sample = "\n".join(f"  {n} → {d}" for n, d in conflicts[:5])
            if count > 5:
                sample += f"\n  ... 等共 {count} 个"
            msg = _("msg_file_overwrite").format(count=count, sample=sample)
            reply = QMessageBox.question(
                self,
                _("title_file_exists"),
                msg,
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            overwrite_all = reply == QMessageBox.StandardButton.Yes

        # 后台线程执行文件移动
        self._archive_worker = ArchiveWorker(
            self._mgr,
            self._parsed_results,
            root_dir,
            config=self._config,
            overwrite=overwrite_all,
            pause_event=self._pause_event,
            parent=self,
        )
        self._archive_worker.batch_ready.connect(self._on_archive_batch_ready)
        self._archive_worker.progress.connect(self.progress_changed.emit)
        self._archive_worker.error.connect(
            lambda msg: logger.error("归档错误: %s", msg)
        )

        def on_archive_finished():
            saved = sum(1 for i, s in self._archive_results if s == "已归档")
            skipped = len(self._archive_results) - saved
            self.status_changed.emit(_("save_complete").format(saved, skipped))
            self._register_task("保存", len(self._archive_results), saved, skipped)
            # 写入 file_index
            for idx, status in self._archive_results:
                if status != "已归档":
                    continue
                parsed = self._parsed_results[idx]
                if parsed.source_path:
                    st = (
                        "被代替"
                        if parsed.effect_status == "被代替"
                        else (
                            "废止"
                            if parsed.effect_status in ("废止", "已废止", "作废")
                            else "现行"
                        )
                    )
                    self._mgr.upsert_file_index(
                        file_path=parsed.source_path,
                        logical_code=parsed.logical_code,
                        number=parsed.number,
                        year=parsed.year,
                        part=parsed.part,
                        std_name=parsed.std_name,
                        status=st,
                    )
            # 源目录过期文件合并
            self._merge_expire_from_source(root_dir)
            self._current_task = None
            if not self._suppress_dialogs:
                # 构造跳过文件详情（显示文件名及跳过原因）
                skip_details = []
                for idx, status in self._archive_results:
                    if status != "已归档" and idx < len(self._parsed_results):
                        p = self._parsed_results[idx]
                        fname = os.path.basename(
                            getattr(p, "source_path", "")
                            or getattr(p, "raw_filename", "")
                        )
                        skip_details.append(
                            _("msg_archive_skip_line").format(name=fname, reason=status)
                        )
                detail_text = ""
                if skip_details:
                    shown = skip_details[:20]
                    more = (
                        f"\n  ... {len(skip_details) - 20} more"
                        if len(skip_details) > 20
                        else ""
                    )
                    detail_text = (
                        _("msg_archive_skip_detail").format(
                            lines="\n".join(shown) + more
                        )
                        if more
                        else _("msg_archive_skip_detail").format(lines="\n".join(shown))
                    )
                self._show_stage_dialog(
                    _("save_results_title"),
                    _("msg_save_done").format(
                        saved=saved, skipped=skipped, detail=detail_text
                    ),
                    next_action=None,
                    next_label="",
                )

        self._archive_results = []
        self._archive_worker.finished_signal.connect(on_archive_finished)
        self._archive_worker.start()

    def _on_archive_batch_ready(self, batch: list):
        """批量更新归档结果到表格。"""
        self._archive_results.extend(batch)
        for idx, status in batch:
            self._update_download_row(idx, status)

    def _merge_expire_from_source(self, root_dir: str):
        """源文件夹中过期作废目录合并到标准库（委托 manager）。"""
        merged = self._mgr.merge_expire_from_source(root_dir, self._parsed_results)
        if merged:
            self.status_changed.emit(f"源过期目录合并: {merged} 个文件")

    def _auto_move_expired(self) -> int:
        """查询后将废止标准自动移入过期作废/（委托 manager）。"""
        expired = [p for p in self._parsed_results if p.next_action == "expire"]
        if not expired:
            return 0
        result = self._mgr.handle_expired(expired)
        moved = result.get("moved", 0)
        if moved:
            self.status_changed.emit(
                f"查询完成: 已自动将 {moved} 个废止标准移入过期作废/"
            )
        return moved

    def _get_library_root(self) -> str:
        """返回标准库根目录路径。"""
        return core.get_library_root(self._config)

    def _show_name_conflict_dialog(self, conflicts: list) -> list:
        """名称冲突弹窗：逐条让用户选择。返回用户已确认的条目列表。"""
        resolved = []
        for p in conflicts[:10]:  # 最多处理前 10 条，避免弹窗过多
            src = getattr(p, "source_name", "") or "（无）"
            qry = getattr(p, "found_name", "") or "（无）"
            full_num = p.get_full_number()
            msg = (
                f"标准号: {full_num}\n\n"
                f"源文件名称: {src}\n"
                f"网站查询名称: {qry}\n\n"
                f"请选择归档使用的名称:"
            )
            dlg = QMessageBox(parent=None)
            dlg.setWindowTitle(_("title_name_conflict"))
            dlg.setText(msg)
            dlg.setIcon(QMessageBox.Icon.Question)
            btn_src = dlg.addButton(
                _("btn_use_source_name"), QMessageBox.ButtonRole.AcceptRole
            )
            btn_qry = dlg.addButton(
                _("btn_use_query_name"), QMessageBox.ButtonRole.YesRole
            )
            dlg.addButton(  # 第三个按钮为取消，else 分支处理
                _("btn_cancel"), QMessageBox.ButtonRole.RejectRole
            )
            dlg.exec()
            clicked = dlg.clickedButton()
            if clicked == btn_src:
                p.final_name = src
                p.std_name = src
                p.stage_status = ""
                resolved.append(p)
            elif clicked == btn_qry:
                p.final_name = qry
                p.std_name = qry
                p.stage_status = ""
                resolved.append(p)
            # 取消：保持 stage_status="name_conflict"，由调用方写入 pending_lookup
        return resolved
