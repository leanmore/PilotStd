# tests/test_remaining_batch1_logs.py — U-3/U-4 批 1：归档/索引 11 条日志升级
"""锁定批 1 的 6 个代表点：失败路径必须打 WARNING（且原返回值契约不变）。

覆盖：config/manager 备份失败、download_utils CSV 解析失败、file_index 删记录失败、
file_utils 哈希计算失败、expire 过期目录合并失败、classifier final_name 落库失败。
"""

import logging
import threading
from types import SimpleNamespace

from pilotstd.core import download_utils as du
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.core.file_utils import hash_file_content


class _BadDB:
    def fetchall(self, *a, **k):  # noqa: ANN002, ANN003
        return [{"id": 1, "file_path": "Z:/definitely/missing.bin"}]

    def execute(self, *a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("db locked")


def test_config_backup_failure_warns(tmp_path, monkeypatch, caplog) -> None:
    """写前备份失败 → WARNING「配置备份失败，原配置仍在使用」。"""
    import pilotstd.core.config.manager as mgr_mod
    from pilotstd.core.config.manager import ConfigManager

    cfg = ConfigManager(str(tmp_path / "c.json"))
    cfg.set("ui.theme", "light")
    cfg.save()  # 首次写：无既有文件，不触发备份

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise OSError("disk full")

    monkeypatch.setattr(mgr_mod.shutil, "copyfile", _boom)
    cfg.set("ui.theme", "dark")
    with caplog.at_level(logging.WARNING):
        cfg.save()

    assert any("配置备份失败" in r.message for r in caplog.records)


def test_download_csv_parse_failure_warns(monkeypatch, caplog) -> None:
    """CSV 解析失败 → WARNING + 仍返回 []（与「没有任务」区分靠日志）。"""

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("bad csv")

    monkeypatch.setattr(du.csv, "DictReader", _boom)
    with caplog.at_level(logging.WARNING):
        assert du._parse_csv_content("standard_number\nGB 1\n") == []

    assert any("下载列表解析失败" in r.message for r in caplog.records)


def test_file_index_delete_failure_warns(caplog) -> None:
    """删除无效索引记录失败 → WARNING，返回删除数 0。"""
    repo = object.__new__(FileIndexRepository)
    repo._db = _BadDB()
    repo._validation_complete = threading.Event()
    repo._stop_event = threading.Event()

    with caplog.at_level(logging.WARNING):
        assert repo.validate_paths() == 0

    assert any("file_index 删除无效记录失败" in r.message for r in caplog.records)


def test_hash_file_content_failure_warns(tmp_path, caplog) -> None:
    """文件不可读 → WARNING + 空哈希（契约不变）。"""
    with caplog.at_level(logging.WARNING):
        assert hash_file_content(str(tmp_path / "missing.bin")) == ""

    assert any("文件哈希计算失败" in r.message for r in caplog.records)


def test_expire_merge_failure_warns(tmp_path, monkeypatch, caplog) -> None:
    """过期目录合并失败 → WARNING「过期目录处理失败」。"""
    import pilotstd.core.file_utils as fu
    from pilotstd.manager.organize.expire import merge_expire_from_source

    root = tmp_path / "root"
    src = tmp_path / "src"
    expire = src / "过期作废"
    root.mkdir()
    expire.mkdir(parents=True)
    (expire / "a.pdf").write_bytes(b"x")
    (src / "a.pdf").write_bytes(b"y")  # 源文件必须存在，否则不会进入合并循环

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise OSError("move blocked")

    monkeypatch.setattr(fu, "safe_move", _boom)
    parsed = [SimpleNamespace(source_path=str(src / "a.pdf"), logical_code="GB")]
    cfg = SimpleNamespace(get=lambda key, default=None: "过期作废")

    with caplog.at_level(logging.WARNING):
        merged = merge_expire_from_source(cfg, str(root), parsed)

    assert merged == 0
    assert any("过期目录处理失败" in r.message for r in caplog.records)


def test_classifier_persist_failure_warns(monkeypatch, caplog) -> None:
    """final_name 落库失败 → WARNING，不抛错（分类主流程继续）。"""
    import pilotstd.core.config as config_mod
    from pilotstd.manager.classifier import QueryClassifier

    def _boom():
        raise RuntimeError("db path broken")

    monkeypatch.setattr(config_mod, "get_db_path", _boom)
    items = [SimpleNamespace(final_name="新名", get_full_number=lambda: "GB/T 1-2020")]

    with caplog.at_level(logging.WARNING):
        QueryClassifier._persist_final_names(object.__new__(QueryClassifier), items)

    assert any("分类失败" in r.message for r in caplog.records)
