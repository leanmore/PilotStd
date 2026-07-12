# pilotstd/ui/core/handlers/_actions.py
"""ActionsHandler — 动作处理器（_on_* 方法、_init_manager 等），替代 ActionsMixin。"""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Any, Callable, Optional

from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from ...i18n import _
from ...workers import RowUpdate

logger = logging.getLogger("pilotstd.ui")


class ActionsHandler:
    """动作处理器 — 提供所有 _on_* 及业务逻辑方法。

    通过依赖注入替代多重继承，通过回调与 MainWindow UI 交互。
    """

    def __init__(
        self,
        config: Any,
        mgr: Any,
        project: Any,
        pause_event: threading.Event,
        status_callback: Callable[[str], None],
        progress_callback: Callable[[int], None],
        parsed_results: list[Any],
        get_selected_path: Callable[[], str],
        clear_table: Callable[[], None],
        stop_workers: Callable[[], None],
        update_button_states: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._mgr = mgr
        self._project = project
        self._pause_event = pause_event
        self._status = status_callback
        self._progress = progress_callback
        self._parsed_results = parsed_results
        self._get_selected_path = get_selected_path
        self._clear_table = clear_table
        self._stop_workers = stop_workers
        self._update_button_states = update_button_states
        self._parent = parent
        self._paused = False
        self._mgr_ready = False

    # ── 延迟初始化 ──────────────────────────────────────────

    def init_manager(
        self,
        set_toolbar_enabled_cb: Callable[[bool], None],
        on_ready_cb: Callable[[], None],
    ) -> None:
        """延迟初始化 StandardManager——避免阻塞窗口显示。"""
        if self._mgr_ready:
            return
        from ...manager import StandardManager

        mgr = StandardManager(config=self._config)
        self._mgr = mgr  # 必须先设 backing field，避免下游 _mgr 访问触发递归
        self._mgr_ready = True
        set_toolbar_enabled_cb(True)
        if self._config.get("watchdog.enabled", False):
            mgr.start_watching()
        on_ready_cb()

    # ── UI 状态管理 ────────────────────────────────────────

    def set_toolbar_enabled(self, toolbar_buttons: dict[str, Any], enabled: bool) -> None:
        """统一控制工具栏按钮状态。管理器未就绪时禁用所有操作按钮。"""
        keys = (
            "btn_select",
            "btn_query",
            "btn_download",
            "btn_normalize",
            "btn_save",
            "btn_auto",
            "btn_announce",
            "btn_pause",
        )
        for key in keys:
            btn = toolbar_buttons.get(key)
            if btn is not None:
                btn.setEnabled(enabled)

    def apply_announce_cache_mode(self, enabled: Optional[bool] = None, btn_announce: Optional[Any] = None) -> None:
        """根据配置控制公告检查按钮启用/禁用状态。"""
        if enabled is None:
            enabled = self._config.get("query.use_announcement_match", False)
        if btn_announce is not None:
            btn_announce.setEnabled(not enabled)

    # ── 工作表阶段切换 ───────────────────────────────────

    def switch_to_stage(self, stage: str, add_table_row_cb: Callable[[RowUpdate], None]) -> None:
        """清空 work_table，从 Manager.get_stage_queue(stage) 取数据填充。"""
        if not self._mgr_ready:
            return
        items = self._mgr.get_stage_queue(stage)
        self._clear_table()
        total = len(items)
        for i, parsed in enumerate(items):
            add_table_row_cb(
                RowUpdate(
                    seq=i + 1,
                    parsed=parsed,
                    work_status=parsed.stage_status,
                    total=total,
                )
            )
        self._update_button_states()

    def update_button_states(self, get_queue_sizes_cb: Callable[[], dict[str, int]]) -> None:
        """根据当前数据状态动态启用/禁用工具栏按钮。"""
        if not self._mgr_ready:
            return
        get_queue_sizes_cb()
        self._update_button_states()

    # ── 取消 / 暂停 ──────────────────────────────────────

    def on_cancel(
        self,
        reset_ui_cb: Callable[[], None],
        hide_progress_cb: Callable[[], None],
    ) -> None:
        """取消按钮：停止所有后台 Worker，恢复 UI 状态。"""
        self._stop_workers()
        self._paused = False
        self._pause_event.set()
        reset_ui_cb()
        hide_progress_cb()
        self._update_button_states()
        self._status(_("status_action_cancelled"))

    def on_pause_toggle(self, set_button_state_cb: Callable[[bool], None]) -> None:
        """暂停/继续切换。"""
        self._paused = not self._paused
        if self._paused:
            set_button_state_cb(True)
            self._status(_("paused"))
            self._pause_event.clear()
        else:
            set_button_state_cb(False)
            self._status(_("resumed"))
            self._pause_event.set()

    def check_pause(self) -> None:
        """轮询等待暂停解除。"""
        import time as _time

        while self._paused:
            QApplication.processEvents()
            _time.sleep(0.05)

    # ── 规则/任务/设置 ──────────────────────────────────────

    def on_rule_query(self) -> None:
        """打开网站规则配置。"""
        from ..dialogs import ConfigPageDialog
        from ..pages.rules_page import RulesPage  # 延迟导入

        dlg = ConfigPageDialog(
            RulesPage(self._config),
            "网站规则配置（查询/下载）",
            self._parent,
        )
        dlg.exec()

    def on_rule_download(self) -> None:
        self.on_rule_query()

    def on_task_center(self) -> None:
        """打开任务中心。"""
        if not self._mgr_ready:
            return
        from ..pages.task_page import TaskCenterDialog  # 延迟导入

        dlg = TaskCenterDialog(self._mgr.task_queue, self._parent)
        dlg.exec()

    def on_settings(self, on_settings_changed_cb: Callable[[], None]) -> None:
        """打开设置对话框。"""
        from ..pages.settings_page import SettingsDialog  # 延迟导入

        dlg = SettingsDialog(self._config, self._parent)
        dlg.exec()
        on_settings_changed_cb()
        self._status(_("settings_updated"))

    # ── 关于 / 更新 ──────────────────────────────────────

    def try_check_update_throttle(self, current: str) -> bool:
        """24h 节流检查——避免触发 GitHub API 限流。返回 True 表示应跳过。"""
        import time as _time

        last_check = self._config.get("appearance.last_update_check", 0)
        if isinstance(last_check, (int, float)) and _time.time() - last_check < 86400:
            QMessageBox.information(
                self._parent,
                _("title_no_update"),
                _("update_already_latest").format(current=current),
            )
            return True
        return False

    def confirm_update_available(self, current: str, release: dict) -> bool:
        """比对版本号 + 弹窗展示 changelog。返回用户是否确认下载。"""
        from pilotstd.platform.updater import is_newer_version

        latest = release["tag_name"]
        if not is_newer_version(latest, current):
            QMessageBox.information(
                self._parent,
                _("title_no_update"),
                _("update_already_latest").format(current=current),
            )
            return False

        body = release["body"][:500]
        reply = QMessageBox.question(
            self._parent,
            _("title_update_found"),
            _("update_new_version_msg").format(current=current, latest=latest, body=body),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def download_update_file(self, release: dict) -> str:
        """后台线程下载 + SHA256 校验 + 生成 update.bat。返回 bat 路径，失败抛异常。"""
        from pilotstd.platform.updater import (
            download_update,
            extract_sha256_from_body,
            generate_update_script,
        )

        download_url = release["download_url"]
        filename = release["filename"]
        self._status(_("update_downloading").format(filename=filename))

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
            self._parent,
            _("update_restart_title"),
            _("update_download_ready"),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Ok:
            subprocess.Popen(["cmd.exe", "/c", bat_path])
            QApplication.quit()

    def on_check_update(self) -> None:
        """半自动升级：检查 GitHub Release → 下载 → 写 update.bat → 提示重启。"""
        import time as _time

        from pilotstd import __version__
        from pilotstd.platform.updater import check_latest_version

        current = f"v{__version__}"

        if self.try_check_update_throttle(current):
            return

        self._config.set("appearance.last_update_check", _time.time())
        self._config.save()
        self._status(_("checking_update"))
        try:
            release = check_latest_version()
            if not release:
                raise RuntimeError("无法获取最新版本信息")

            if not self.confirm_update_available(current, release):
                return

            # 源码运行模式不自动下载，引导手动 git pull
            if not getattr(sys, "frozen", False):
                import webbrowser

                webbrowser.open("https://github.com/leanmore/PilotStd/releases/latest")
                return

            bat_path = self.download_update_file(release)
            self._prompt_restart(bat_path)

        except Exception as e:
            logger.warning("检查更新失败: %s", e)
            QMessageBox.information(
                self._parent,
                _("title_no_update"),
                _("update_connection_failed").format(current=current),
            )

    def on_about(self) -> None:
        """关于对话框。"""
        from pilotstd import __version__

        QMessageBox.about(self._parent, _("about"), _("about_text").format(version=__version__))
