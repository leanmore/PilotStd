"""Extracted action/manager methods for MainWindow."""

from __future__ import annotations

import logging
import sys
import time as _time

from PyQt6.QtWidgets import QApplication, QMessageBox

from ....i18n import _
from ...workers import RowUpdate

logger = logging.getLogger("pilotstd.ui")


def get_pipeline_stats(self) -> dict:
    if not self._mgr_ready:
        return {}
    dl = self._mgr.get_stage_queue("download")
    ex = self._mgr.get_stage_queue("expire")
    pe = self._mgr.get_stage_queue("pending")
    exact = (
        sum(1 for p in self._parsed_results if getattr(p, "match_status", "") == "exact") if self._parsed_results else 0
    )
    return {
        "scan_count": len(self._parsed_results) if self._parsed_results else 0,
        "query_download": len(dl),
        "query_expire": len(ex),
        "query_pending": len(pe),
        "query_exact": exact,
        "query_total": len(dl) + len(ex) + len(pe),
    }


def _init_manager(self) -> None:
    if self._mgr_ready:
        return
    from ....manager import StandardManager

    mgr = StandardManager(config=self._config)
    self._mgr = mgr
    self._mgr_ready = True
    self._set_toolbar_enabled(True)
    self._apply_announce_cache_mode()
    self.status_bar.showMessage(_("ready"), 2000)
    self._check_download_queue()
    if self._config.get("watchdog.enabled", False):  # pragma: no cover — 需要真实 ConfigManager 触发
        mgr.start_watching()
    self._init_core()
    # 启动自检（仅在 PILOTSTD_SELF_CHECK=1 时执行）
    from ...core._self_check import run_self_check

    run_self_check(self)
    self._file_menu.setEnabled(True)


def _set_toolbar_enabled(self, enabled: bool) -> None:
    self.btn_select.setEnabled(enabled)
    self.btn_query.setEnabled(enabled)
    self.btn_download.setEnabled(enabled)
    self.btn_normalize.setEnabled(enabled)
    self.btn_save.setEnabled(enabled)
    self.btn_auto.setEnabled(enabled)
    self.btn_announce.setEnabled(enabled)
    self.btn_pause.setEnabled(enabled)


def _apply_announce_cache_mode(self, enabled: bool | None = None) -> None:
    if enabled is None:
        enabled = self._config.get("query.use_announcement_match", False)
    self.btn_announce.setEnabled(not enabled)


def _switch_to_stage(self, stage: str) -> None:
    if not self._mgr_ready:
        return
    items = self._mgr.get_stage_queue(stage)
    self._clear_table()
    total = len(items)
    for i, parsed in enumerate(items):
        self._add_table_row(RowUpdate(seq=i + 1, parsed=parsed, work_status=parsed.stage_status, total=total))
    self._update_button_states()


def _update_button_states(self) -> None:
    if not self._mgr_ready:
        return
    has_results = bool(self._parsed_results)
    has_download = bool(self._mgr.get_stage_queue("download"))
    has_archive = bool(self._mgr.get_stage_queue("all"))
    self.btn_query.setEnabled(has_results)
    self.btn_download.setEnabled(has_download)
    self.btn_normalize.setEnabled(has_archive)
    self.btn_save.setEnabled(has_archive)
    self.btn_cancel.setEnabled(False)


def _on_cancel(self) -> None:
    self._stop_workers()
    self._paused = False
    self._suppress_dialogs = False  # 重置，防止泄漏到后续手动操作
    self._pause_event.set()
    self.btn_pause.setText(_("toolbar_pause"))
    s = self.style()
    assert s is not None, "style() 不应为 None"
    self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPause))
    self.btn_query.setEnabled(True)
    self.btn_download.setEnabled(True)
    self.btn_cancel.setEnabled(False)
    self.progress_bar.setVisible(False)
    self._update_button_states()
    self.status_changed.emit(_("status_action_cancelled"))


def _on_pause_toggle(self) -> None:
    self._paused = not self._paused
    s = self.style()
    assert s is not None, "style() 不应为 None"
    if self._paused:
        self.btn_pause.setText(_("toolbar_continue"))
        self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPlay))
        self.status_changed.emit(_("paused"))
        self._pause_event.clear()
    else:
        self.btn_pause.setText(_("toolbar_pause"))
        self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPause))
        self.status_changed.emit(_("resumed"))
        self._pause_event.set()


def _on_rule_query(self) -> None:
    from ...dialogs import ConfigPageDialog
    from ...pages.rules_page import RulesPage

    dlg = ConfigPageDialog(RulesPage(self._config), "网站规则配置（查询/下载）", self)
    dlg.exec()


def _on_rule_download(self) -> None:
    self._on_rule_query()


def _on_task_center(self) -> None:
    if not self._mgr_ready:
        return
    from ...pages.task_page import TaskCenterDialog

    dlg = TaskCenterDialog(self._mgr.task_queue, self)
    dlg.exec()


def _on_settings(self) -> None:
    from ...pages.settings_page import SettingsDialog

    dlg = SettingsDialog(self._config, self)
    dlg.exec()
    self._apply_language()
    self._apply_theme()
    self._apply_icon()
    self.status_changed.emit(_("settings_updated"))


def _try_check_update_throttle(self, current: str) -> bool:
    last_check = self._config.get("appearance.last_update_check", 0)
    if isinstance(last_check, (int, float)) and _time.time() - last_check < 86400:
        QMessageBox.information(self, _("title_no_update"), _("update_already_latest").format(current=current))
        return True
    return False


def _confirm_update_available(self, current: str, release: dict) -> bool:
    from pilotstd.platform.updater import is_newer_version

    latest = release["tag_name"]
    if not is_newer_version(latest, current):
        QMessageBox.information(self, _("title_no_update"), _("update_already_latest").format(current=current))
        return False
    body = release["body"][:500]
    reply = QMessageBox.question(
        self,
        _("title_update_found"),
        _("update_new_version_msg").format(current=current, latest=latest, body=body),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes


def _download_update_file(self, release: dict) -> None:
    """启动后台线程下载更新文件，完成后通过信号触发重启提示。

    不阻塞 UI 线程——下载在 QThread 中执行。
    """
    from pilotstd.ui.workers.update_download import UpdateDownloadWorker

    worker = UpdateDownloadWorker(release, self)
    worker.progress_msg.connect(lambda msg: self.status_changed.emit(msg))
    worker.download_ready.connect(self._prompt_restart)
    worker.download_failed.connect(
        lambda err: self.status_changed.emit(f"更新下载失败: {err}")
    )
    worker.finished.connect(worker.deleteLater)
    worker.start()


def _prompt_restart(self, bat_path: str) -> None:
    import subprocess

    reply = QMessageBox.question(
        self,
        _("update_restart_title"),
        _("update_download_ready"),
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
    )
    if reply == QMessageBox.StandardButton.Ok:
        subprocess.Popen(["cmd.exe", "/c", bat_path])
        QApplication.quit()


def _on_check_update(self) -> None:
    from pilotstd import __version__
    from pilotstd.platform.updater import check_latest_version

    current = f"v{__version__}"
    if self._try_check_update_throttle(current):
        return
    self._config.set("appearance.last_update_check", _time.time())
    self._config.save()
    self.status_changed.emit(_("checking_update"))
    try:
        release = check_latest_version()
        if not release:
            raise RuntimeError("无法获取最新版本信息")
        if not self._confirm_update_available(current, release):
            return
        if not getattr(sys, "frozen", False):
            import webbrowser

            webbrowser.open("https://github.com/leanmore/PilotStd/releases/latest")
            return
        self._download_update_file(release)  # 异步：QThread 完成后触发 _prompt_restart
    except Exception as e:  # pragma: no cover — 依赖 GitHub API 网络响应，单元测试 mock 不稳定
        logger.warning("检查更新失败: %s", e)
        QMessageBox.information(self, _("title_no_update"), _("update_connection_failed").format(current=current))


def _on_about(self) -> None:
    from pilotstd import __version__

    QMessageBox.about(self, _("about"), _("about_text").format(version=__version__))
