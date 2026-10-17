"""静默吞错第 7 批：配置备份 / 审计 detail / 熔断档位 / 鉴权兜底（体检 D-8）。

- `ConfigManager` 写前备份失败原 pass（丢一次写将无法回滚）；
- `read_audit` 的非法 detail 原 pass（保留原串但写入侧问题无痕迹）；
- `CircuitBreaker._durations` 配置读取失败原 pass（回退默认档位）；
- `docker/auth.py` 的 JWT 解析失败与审计身份反查失败原 pass。
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock


def test_audit_invalid_detail_logs(monkeypatch, caplog) -> None:
    from pilotstd.core import audit as audit_module

    fake_db = MagicMock()
    fake_db.fetchall.return_value = [{"id": 1, "user_id": 1, "action": "X", "resource": "r", "detail": "{bad"}]
    monkeypatch.setattr(audit_module, "Database", lambda *a, **k: fake_db)
    monkeypatch.setattr(audit_module, "get_db_path", lambda: "unused.db")

    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.audit"):
        rows = audit_module.read_audit(limit=1)
    assert rows[0]["detail"] == "{bad"  # 保留原字符串
    assert "audit detail is not valid JSON" in caplog.text
    fake_db.close.assert_called_once()


def test_config_pre_write_backup_failure_logs(tmp_path, monkeypatch, caplog) -> None:
    from pilotstd.core.config import manager as cfg_module

    path = tmp_path / "config.json"
    cfg = cfg_module.ConfigManager(str(path))
    cfg.set("ui.theme", "dark")

    def broken_copyfile(*args, **kwargs):
        raise OSError("backup denied")

    monkeypatch.setattr(cfg_module.shutil, "copyfile", broken_copyfile)

    with caplog.at_level(logging.DEBUG, logger="pilotstd.core.config.manager"):
        cfg.save()
    assert "pre-write backup failed" in caplog.text
    assert path.exists()  # 备份失败不阻断写盘


def test_circuit_breaker_durations_fallback_logs(monkeypatch, caplog) -> None:
    from pilotstd.announcement import _circuit_breaker as cb_module

    class _BrokenConfig:
        def get(self, key):
            raise RuntimeError("config unreadable")

    monkeypatch.setattr(cb_module, "ConfigManager", _BrokenConfig)
    breaker = cb_module.CircuitBreaker(lambda: "gb")

    with caplog.at_level(logging.DEBUG, logger="pilotstd.announcement._circuit_breaker"):
        durations = breaker._durations
    assert durations  # 回退到默认档位
    assert "read circuit breaker freeze_durations failed" in caplog.text
