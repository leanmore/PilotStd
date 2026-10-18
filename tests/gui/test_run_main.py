"""D-16：`_run_main.run()` 入口可测化（此前整函数 pragma 排除）。

用替身替换 QApplication/MainWindow/LoggerManager/ConfigManager/ProjectManager，
验证启动顺序与窗口展示；`app.exec()` 返回 0（不真的进入事件循环）。
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


def test_run_boots_window_and_exits(monkeypatch) -> None:
    from pilotstd.ui.main_window.parts import _run_main as run_main

    calls: dict[str, object] = {}

    class FakeApp:
        def __init__(self, argv):
            calls["argv"] = list(argv)
            self.aboutToQuit = type("Sig", (), {"connect": lambda self, fn: calls.update(quit_hooked=fn)})()

        def setStyle(self, style: str) -> None:
            calls["style"] = style

        def exec(self) -> int:
            calls["exec"] = True
            return 0

    class FakeWindow:
        def __init__(self, cfg, prj):
            calls["window"] = (cfg, prj)

        def _apply_theme(self) -> None:
            calls["theme"] = True

        def _apply_icon(self) -> None:
            calls["icon"] = True

        def show(self) -> None:
            calls["shown"] = True

        def _init_manager(self) -> None:
            calls["init_manager"] = True

        def show_welcome_if_needed(self) -> None:
            calls["welcome"] = True

    import pilotstd.ui.main_window as mw

    monkeypatch.setattr(run_main, "QApplication", FakeApp)
    monkeypatch.setattr(run_main, "qInstallMessageHandler", lambda handler: calls.update(handler=handler))
    monkeypatch.setattr(run_main, "QTimer", type("T", (), {"singleShot": staticmethod(lambda ms, fn: None)}))
    monkeypatch.setattr(mw, "MainWindow", FakeWindow)
    monkeypatch.setattr("pilotstd.core.config.ConfigManager", lambda: "cfg")
    monkeypatch.setattr("pilotstd.core.project.ProjectManager", lambda: "prj")
    monkeypatch.setattr("pilotstd.core.logger.LoggerManager", lambda level: calls.update(logger=level))
    monkeypatch.setattr("pilotstd.core.frozen.is_frozen", lambda: False)

    with pytest.raises(SystemExit) as exc:
        run_main.run()

    assert exc.value.code == 0
    assert calls["style"] == "Fusion"
    assert calls["window"] == ("cfg", "prj")
    assert calls["shown"] is True
    assert calls["exec"] is True
    assert "handler" in calls and "quit_hooked" in calls
