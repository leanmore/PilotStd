"""G-052 文档漂移门禁：能识别死路由、未知配置键、未知表名，且当前仓库为 0 违规。"""

from scripts import check_docs_drift as gate


def test_repo_docs_are_clean():
    report = gate.scan_docs(gate.load_facts())
    assert report["violations"] == [], report["violations"]


def test_detects_injected_drift(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text(
        "# 坏文档\n\n"
        "调用 `GET /api/definitely-not-a-route`。\n"
        "配置项 `storage.not_a_real_key` 控制行为。\n"
        "数据表 `totally_fake_log` 保存记录。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "DOCS", docs)
    report = gate.scan_docs(gate.load_facts())
    kinds = {item["kind"] for item in report["violations"]}
    assert {"dead_api", "unknown_config", "unknown_table"} <= kinds


def test_main_returns_nonzero_on_drift(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text("`GET /api/nope-nope`\n", encoding="utf-8")
    monkeypatch.setattr(gate, "DOCS", docs)
    assert gate.main([]) == 1
