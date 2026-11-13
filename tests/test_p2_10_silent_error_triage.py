"""P2-10 批 1：静默吞错 triage 中被判「应可见」的三处升级为 warning 的受控测试。

对应决策（见 docs/debt/p2-10-silent-errors-triage.md 批 1）：
1. `ConfigManager._load()`：主配置损坏且 `.bak` 不可用 → 即将以默认值覆盖用户配置；
2. `docker/_static_token.py::_ensure_static_token_in_db()`：静态 API Key 落库失败；
3. `docker/scheduler.py::_prune_old_backups()`：备份目录不可读 → 保留策略静默失效。

三者都是"失败只在 debug 级可见"，生产日志看不到 → 用 caplog 锁定 WARNING。
"""

from __future__ import annotations

import json
import logging

import pytest

import docker._static_token as static_token
from docker.scheduler import _prune_old_backups
from pilotstd.core.config.manager import ConfigManager


@pytest.fixture(autouse=True)
def _restore_static_token_flag():
    """避免把模块级 _STATIC_TOKEN_INITIALIZED 的改动带给其它用例。"""
    original = static_token._STATIC_TOKEN_INITIALIZED
    yield
    static_token._STATIC_TOKEN_INITIALIZED = original


def test_corrupt_config_with_unusable_bak_warns(tmp_path, caplog):
    """主文件与 .bak 同时损坏 → 必须以 WARNING 留下"配置将被默认值覆盖"的证据。"""
    path = tmp_path / "config.json"
    path.write_text("{broken json", encoding="utf-8")
    (tmp_path / "config.json.bak").write_text("also broken", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="pilotstd.core.config.manager"):
        ConfigManager(str(path))

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("bak rollback failed" in r.getMessage() for r in warnings), [r.getMessage() for r in warnings]
    # 契约不变：损坏文件被备份、随后以默认值初始化
    assert any(p.name.startswith("config.json.corrupted.") for p in tmp_path.iterdir())
    assert json.loads(path.read_text(encoding="utf-8"))  # 默认值已写盘


def test_static_token_init_failure_warns(monkeypatch, caplog):
    """静态令牌落库异常 → WARNING（否则静态 API Key 永久不可用时启动日志无痕）。"""
    static_token._STATIC_TOKEN_INITIALIZED = False

    class _BrokenDB:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("db not ready")

    monkeypatch.setattr("pilotstd.core.db.Database", _BrokenDB)
    with caplog.at_level(logging.WARNING, logger="docker._static_token"):
        static_token._ensure_static_token_in_db()

    assert any("static token db init failed" in r.getMessage() for r in caplog.records)
    assert static_token._STATIC_TOKEN_INITIALIZED is False  # 未标记成功 → 下次请求会重试


def test_prune_backup_dir_unreadable_warns(tmp_path, caplog):
    """备份目录不存在/不可读 → 返回 [] 且 WARNING（保留策略失效不能静默）。"""
    missing = tmp_path / "nope"
    with caplog.at_level(logging.WARNING, logger="docker.scheduler"):
        removed = _prune_old_backups(str(missing))

    assert removed == []
    assert any("backup dir unreadable" in r.getMessage() for r in caplog.records)
