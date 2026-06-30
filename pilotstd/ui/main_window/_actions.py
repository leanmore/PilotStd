# pilotstd/ui/main_window/_actions.py
# MainWindow 动作处理器混入模块
"""MainWindow 动作处理器 — _on_* 方法、_init_manager 等。"""

import logging
import os
import sys
import threading

from PyQt6.QtWidgets import QApplication, QMessageBox

from ...i18n import _
from ..workers import RowUpdate

logger = logging.getLogger("pilotstd.ui")


class ActionsMixin:
    """动作处理器混入类 — 提供所有 _on_* 及业务逻辑方法。"""

    # ── 驱动器公开方法 ──────────────────────────────────────

    def get_pipeline_stats(self) -> dict:
        """供驱动器取交叉对比数据。需在 run_auto 全部 worker 完成后调用。"""
        if not self._mgr_ready:
            return {}
        dl = self._mgr.get_stage_queue("download")
        ex = self._mgr.get_stage_queue("expire")
        pe = self._mgr.get_stage_queue("pending")
        exact = (
            sum(1 for p in self._parsed_results if getattr(p, "match_status", "") == "exact")
            if self._parsed_results
            else 0
        )
        return {
            "scan_count": len(self._parsed_results) if self._parsed_results else 0,
            "query_download": len(dl),
            "query_expire": len(ex),
            "query_pending": len(pe),
            "query_exact": exact,
            "query_total": len(dl) + len(ex) + len(pe),
        }

    # ── 延迟初始化 ──────────────────────────────────────────

    def _init_manager(self) -> None:
        """延迟初始化 StandardManager——避免阻塞窗口显示。

        窗口先显示（工具栏灰色），后台加载所有子系统（DB/适配器/引擎/
        服务），完成后工具栏亮起。将 400-1200ms 的重量级初始化移出
        启动关键路径，用户从双击到看到窗口从 ~2s 缩短到 ~1s。

        可通过两种方式触发：
          1. QTimer 延迟调用（run() 中 window.show() 后 50ms）
          2. _mgr property 首次访问自动调用（向后兼容测试夹具）
        二次调用由 _mgr_ready 守卫防止重复初始化。
        """
        if self._mgr_ready:
            return
        from ...manager import StandardManager

        mgr = StandardManager(config=self._config)
        self._mgr = mgr  # 必须先设 backing field，避免下游 _mgr 访问触发递归
        self._mgr_ready = True
        self._set_toolbar_enabled(True)
        self._apply_announce_cache_mode()
        self.status_bar.showMessage(_("ready"), 2000)
        self._check_download_queue()
        self._check_pending_lookup()
        if self._config.get("watchdog.enabled", False):
            mgr.start_watching()

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        """统一控制工具栏按钮状态。管理器未就绪时禁用所有操作按钮。"""
        self.btn_select.setEnabled(enabled)
        self.btn_query.setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
        self.btn_normalize.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.btn_auto.setEnabled(enabled)
        self.btn_announce.setEnabled(enabled)
        self.btn_pause.setEnabled(enabled)

    def _apply_announce_cache_mode(self, enabled: bool | None = None) -> None:
        """根据配置控制公告检查按钮启用/禁用状态。
        Web 端公告缓存开启时禁用本地公告检查，避免双数据源混淆。
        """
        if enabled is None:
            enabled = self._config.get("query.use_announcement_match", False)
        self.btn_announce.setEnabled(not enabled)

    # ── 工作表阶段切换 ───────────────────────────────────

    def _switch_to_stage(self, stage: str) -> None:
        """清空 work_table，从 Manager.get_stage_queue(stage) 取数据填充。
        stage: 'scan' | 'all' | 'download' | 'pending' | 'archive_ready'
        """
        if not self._mgr_ready:
            return
        items = self._mgr.get_stage_queue(stage)
        self._clear_table()
        total = len(items)
        for i, parsed in enumerate(items):
            self._add_table_row(
                RowUpdate(
                    seq=i + 1,
                    parsed=parsed,
                    work_status=parsed.stage_status,
                    total=total,
                )
            )
        self._update_button_states()

    def _update_button_states(self) -> None:
        """根据当前数据状态动态启用/禁用工具栏按钮。"""
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

    # ── 取消 / 暂停 ──────────────────────────────────────

    def _on_cancel(self) -> None:
        """取消按钮：停止所有后台 Worker，恢复 UI 状态。"""
        self._stop_workers()
        self._paused = False
        self._pause_event.set()
        self.btn_pause.setText("暂停")
        s = self.style()
        assert s is not None, "style() 不应为 None"
        self.btn_pause.setIcon(s.standardIcon(s.StandardPixmap.SP_MediaPause))
        self.btn_query.setEnabled(True)
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._current_task = None
        self._update_button_states()
        self.status_changed.emit("操作已取消")

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

    def _check_pause(self) -> None:
        """轮询等待暂停解除。使用 QApplication.processEvents 处理当前队列事件，
        不递归处理新事件（避免 QEventLoop 的栈溢出），同时允许用户点击"继续"。"""
        import time as _time

        while self._paused:
            QApplication.processEvents()
            _time.sleep(0.05)

    # ── 规则/任务/设置 ──────────────────────────────────────

    def _on_rule_query(self) -> None:
        from ..dialogs import ConfigPageDialog
        from ..pages.rules_page import RulesPage  # 延迟导入

        dlg = ConfigPageDialog(
            RulesPage(self._config),
            "网站规则配置（查询/下载）",
            self,
        )
        dlg.exec()

    def _on_rule_download(self) -> None:
        self._on_rule_query()

    def _on_task_center(self) -> None:
        if not self._mgr_ready:
            return
        from ..pages.task_page import TaskCenterDialog  # 延迟导入

        dlg = TaskCenterDialog(self._mgr.task_queue, self)
        dlg.exec()

    def _on_settings(self) -> None:
        from ..pages.settings_page import SettingsDialog  # 延迟导入

        dlg = SettingsDialog(self._config, self)
        dlg.exec()
        self._apply_language()
        self._apply_theme()
        self._apply_icon()
        self.status_changed.emit("设置已更新")

    # ── 关于 / 更新 ──────────────────────────────────────

    def _try_check_update_throttle(self, current: str, _time) -> bool:
        """24h 节流检查——避免触发 GitHub API 限流（60次/h 无 Token）。返回 True 表示应跳过。"""
        last_check = self._config.get("appearance.last_update_check", 0)
        if isinstance(last_check, (int, float)) and _time.time() - last_check < 86400:
            QMessageBox.information(
                self,
                _("title_no_update"),
                _("update_already_latest").format(current=current),
            )
            return True
        return False

    def _confirm_update_available(self, current: str, release: dict) -> bool:
        """比对版本号 + 弹窗展示 changelog。返回用户是否确认下载。"""
        from pilotstd.platform.updater import is_newer_version

        latest = release["tag_name"]
        if not is_newer_version(latest, current):
            QMessageBox.information(
                self,
                _("title_no_update"),
                _("update_already_latest").format(current=current),
            )
            return False

        body = release["body"][:500]
        reply = QMessageBox.question(
            self,
            _("title_update_found"),
            _("update_new_version_msg").format(current=current, latest=latest, body=body),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _download_update_file(self, release: dict) -> str:
        """后台线程下载 + SHA256 校验 + 生成 update.bat。返回 bat 路径，失败抛异常。"""

        from pilotstd.platform.updater import (
            download_update,
            extract_sha256_from_body,
            generate_update_script,
        )

        download_url = release["download_url"]
        filename = release["filename"]
        self.status_changed.emit(_("update_downloading").format(filename=filename))

        dl_path = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), filename)
        sha256_expected = extract_sha256_from_body(release["body"])

        result: dict = {"ok": False, "error": ""}

        def _download() -> None:
            try:
                ok = download_update(download_url, dl_path, sha256_expected)
                if ok:
                    result["ok"] = True
                else:
                    result["error"] = "下载或校验失败"
            except Exception as e:
                result["error"] = str(e)

        t = threading.Thread(target=_download, daemon=True)
        t.start()
        t.join(timeout=300)
        if not result["ok"]:
            raise RuntimeError(result["error"] or "下载超时")

        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
        if not os.access(exe_dir, os.W_OK):
            raise PermissionError(f"无法写入 {exe_dir}\n请以管理员身份运行，或将程序移至用户目录")
        return generate_update_script(dl_path, exe_dir)

    def _prompt_restart(self, bat_path: str) -> None:
        """弹窗询问是否立即重启，确认后启动 update.bat 并退出应用。"""
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
        """半自动升级：检查 GitHub Release → 下载 → 写 update.bat → 提示重启。"""
        import time as _time

        from pilotstd import __version__
        from pilotstd.platform.updater import check_latest_version

        current = f"v{__version__}"

        if self._try_check_update_throttle(current, _time):
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

            # 源码运行模式不自动下载，引导手动 git pull
            if not getattr(sys, "frozen", False):
                import webbrowser

                webbrowser.open("https://github.com/leanmore/PilotStd/releases/latest")
                return

            bat_path = self._download_update_file(release)
            self._prompt_restart(bat_path)

        except Exception as e:
            logger.warning("检查更新失败: %s", e)
            QMessageBox.information(
                self,
                _("title_no_update"),
                _("update_connection_failed").format(current=current),
            )

    def _on_about(self) -> None:
        from pilotstd import __version__

        QMessageBox.about(self, _("about"), _("about_text").format(version=__version__))
