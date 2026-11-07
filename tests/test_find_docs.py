"""文档检索脚本：关键词能命中标题和正文，压缩重复标题。"""

from scripts.find_docs import search


def test_find_docs_matches_heading_and_body(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "notify.md").write_text("# 通知未读数\n\n未读数与列表口径不一致。\n", encoding="utf-8")
    (docs / "other.md").write_text("# 其他\n\n无关内容。\n", encoding="utf-8")

    hits = search(docs, "通知 未读")

    assert hits
    assert hits[0]["path"] == "notify.md"
    assert "通知未读数" in hits[0]["hits"]


def test_find_docs_ignores_archive_dirs(tmp_path):
    docs = tmp_path / "docs"
    (docs / "archive").mkdir(parents=True)
    (docs / "archive" / "old.md").write_text("# 通知未读\n", encoding="utf-8")
    (docs / "current.md").write_text("# 通知未读当前\n", encoding="utf-8")

    hits = search(docs, "通知未读")

    assert hits
    assert all("archive" not in h["path"] for h in hits)


def test_find_docs_empty_query_returns_empty(tmp_path):
    assert search(tmp_path, "   ") == []
