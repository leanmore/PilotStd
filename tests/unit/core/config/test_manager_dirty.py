"""ConfigManager 写盘语义受控测试（#31-P2 / R14-3a，2026-10-01）。

背景：原 `_load()` 在“文件已存在”分支里**无条件 `save()`** → 每构造一次 = 读一次 + 写一次；
热路径 `scorer.get_profile()` 每次新建实例，单批查询实测 ≈126 次整份 config.json 覆盖写
（≈0.58 s ／ ≈519 KiB），并放大“多实例 last-writer-wins 丢配置”窗口。

本文件锁定 P2 之后的 4 条契约（并要求“未改动不写盘”）：
  ① 首次创建（文件不存在）仍写盘；
  ② 补默认值 / 迁移旧键**有变更才写盘一次**；
  ③ 显式 `set()` + `save()` 仍持久化（且随后再构造不再写盘）；
  ④ 损坏文件仍先备份 `config.json.corrupted.<ts>` 再以默认值初始化并写盘；
  ⑤ 已存在且内容完整的配置：构造后 **零写盘**（mtime 与字节内容均不变）；
  ⑥ `reload()` 在内容无变更时同样零写盘。
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from pilotstd.core.config.manager import ConfigManager


def _snapshot(path: str) -> tuple[int, bytes]:
    """取文件（mtime_ns, 原始字节）快照——用于判定是否发生过写盘。"""
    st = os.stat(path)
    with open(path, "rb") as fh:
        return st.st_mtime_ns, fh.read()


def _make(filepath: str) -> ConfigManager:
    """在隔离的空库下构造 ConfigManager。

    构造期 `_get_fernet` 会做防呆查库（`crypto.py:54`），故把 `paths.get_db_path` 指向临时空库，
    避免误读真实开发库的旧凭证（同 `tests/test_core_config.py:333-340` 的做法）。
    """
    db = os.path.join(tempfile.mkdtemp(prefix="pilotstd_cfg_db_"), "empty.db")
    sqlite3.connect(db).close()
    with patch("pilotstd.core.config.paths.get_db_path", return_value=db):
        return ConfigManager(filepath=filepath)


class _SaveCounter:
    """统计 `ConfigManager.save()` 实际调用次数（写盘次数的最直接证据）。"""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: list[float] = []
        original = ConfigManager.save

        def _counting_save(self_cfg: ConfigManager, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(1.0)
            return original(self_cfg, *args, **kwargs)

        monkeypatch.setattr(ConfigManager, "save", _counting_save)

    @property
    def count(self) -> int:
        return len(self.calls)


def test_first_run_writes_file(tmp_path, monkeypatch):
    """契约①：文件不存在时仍用工厂默认值初始化**并写盘**。"""
    path = str(tmp_path / "config.json")
    counter = _SaveCounter(monkeypatch)

    cfg = _make(path)

    assert counter.count == 1, "首次创建必须写盘一次"
    assert os.path.exists(path)
    assert cfg.get("appearance.theme") == "经典白"
    assert cfg.get("storage.inbox_dir") == "/inbox"


def test_existing_complete_config_writes_nothing(tmp_path, monkeypatch):
    """核心契约⑤：已存在且完整的配置，构造后零写盘（mtime 与内容不变）——P2 的主目标。"""
    path = str(tmp_path / "config.json")
    _make(path)  # 首次创建写盘
    before = _snapshot(path)

    counter = _SaveCounter(monkeypatch)
    _make(path)

    assert counter.count == 0, "内容完整的配置构造后不得写盘"
    assert _snapshot(path) == before, "mtime/内容必须完全不变"


def test_missing_defaults_backfill_writes_once(tmp_path, monkeypatch):
    """契约②-a：文件存在但缺默认键 → 补全后写盘一次；再次构造零写盘。"""
    path = str(tmp_path / "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"scan": {"extensions": [".pdf"]}}, fh, ensure_ascii=False)

    counter = _SaveCounter(monkeypatch)
    cfg = _make(path)

    assert counter.count == 1, "补默认值属于“有变更”，应写盘一次"
    assert cfg.get("appearance.theme") == "经典白"
    assert cfg.get("scan.extensions") == [".pdf"], "用户已有值不得被默认值覆盖"
    on_disk = json.loads(open(path, encoding="utf-8").read())
    assert on_disk["appearance"]["theme"] == "经典白", "补全结果必须落盘"

    monkeypatch.undo()
    counter2 = _SaveCounter(monkeypatch)
    _make(path)
    assert counter2.count == 0, "第二次构造已无变更，不得再写盘"


def test_legacy_ui_keys_migrate_writes_once(tmp_path, monkeypatch):
    """契约②-b：旧版 `ui.*` 键迁移到 `appearance.*` 属于“有变更”→ 写盘一次，且幂等。"""
    path = str(tmp_path / "config.json")
    _make(path)  # 先得到一份完整配置
    data = json.loads(open(path, encoding="utf-8").read())
    data["ui"] = {"sort_column": "standard_number"}  # 注入旧键（v0.5.x 遗留）
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)

    counter = _SaveCounter(monkeypatch)
    cfg = _make(path)

    assert counter.count == 1, "迁移旧键属于“有变更”，应写盘一次"
    assert cfg.get("appearance.sort_column") == "standard_number"
    assert cfg.get("ui.sort_column") is None, "旧键应被清理"
    on_disk = json.loads(open(path, encoding="utf-8").read())
    assert on_disk["appearance"]["sort_column"] == "standard_number"
    assert "ui" not in on_disk or "sort_column" not in on_disk.get("ui", {})

    monkeypatch.undo()
    counter2 = _SaveCounter(monkeypatch)
    _make(path)
    assert counter2.count == 0, "迁移已完成后再次构造不得写盘"


def test_explicit_set_then_save_persists(tmp_path, monkeypatch):
    """契约③：`set()` 仍只改内存；显式 `save()` 才落盘；随后构造零写盘。"""
    path = str(tmp_path / "config.json")
    _make(path)
    before = _snapshot(path)

    counter = _SaveCounter(monkeypatch)
    cfg = _make(path)
    cfg.set("db.path", "/tmp/probe.sqlite")
    assert counter.count == 0 and _snapshot(path) == before, "set() 本身不得触发写盘"

    cfg.save()
    assert counter.count == 1
    after = _snapshot(path)
    assert after != before, "显式 save() 必须落盘"
    assert json.loads(open(path, encoding="utf-8").read())["db"]["path"] == "/tmp/probe.sqlite"

    monkeypatch.undo()
    counter2 = _SaveCounter(monkeypatch)
    cfg2 = _make(path)
    assert counter2.count == 0, "已持久化的配置再构造不得写盘"
    assert cfg2.get("db.path") == "/tmp/probe.sqlite"


def test_corrupted_config_backup_and_write(tmp_path, monkeypatch):
    """契约④：损坏文件仍先备份 `config.json.corrupted.<ts>`，再以默认值初始化并写盘。"""
    path = str(tmp_path / "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{invalid json")

    counter = _SaveCounter(monkeypatch)
    cfg = _make(path)

    assert counter.count == 1, "损坏后以默认值初始化应写盘一次"
    backups = [n for n in os.listdir(tmp_path) if n.startswith("config.json.corrupted")]
    assert len(backups) == 1, f"损坏文件应被备份一次，实际 {backups}"
    assert cfg.get("appearance.theme") == "经典白"


def test_reload_unchanged_writes_nothing(tmp_path, monkeypatch):
    """契约⑥：`reload()`（运行时配置同步）在磁盘内容无变更时零写盘。"""
    path = str(tmp_path / "config.json")
    cfg = _make(path)
    before = _snapshot(path)

    counter = _SaveCounter(monkeypatch)
    cfg.reload()

    assert counter.count == 0, "reload 无变更不得写盘"
    assert _snapshot(path) == before
    assert cfg.get("appearance.theme") == "经典白"
