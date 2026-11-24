"""tests/test_check_g_056_doc_deadlinks.py — G-056 文档死链扫描（2026-11-23）。

背景（NEW-32）：`check_g_032_doc_health.py` 只校验「反引号包裹的全路径引用」，
**不检查 markdown 相对链接** `[文本](../foo/bar.md)`。实测 docs/ 下存在死链，
其中一条指向已归档（gitignore）的 `docs/plans/notification-redesign/...`。

本测试锁住扫描器的四条关键判定：
  1. 代码块内的伪链接不算死链（文档在讲"链接怎么写"时会产生大量假阳性）
  2. 行内代码内的伪链接同样不算
  3. 仓库根相对路径（`pilotstd/xxx.py`）视为有效（本仓文档惯例）
  4. 真正不存在的相对链接被判死链
  5. 归档目录（`.local/`、`archive/`）整目录跳过
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "check_g_056_doc_deadlinks.py"


def _load():
    """以文件路径加载门禁模块（scripts/ 不是包，与既有门禁测试同法）。"""
    spec = importlib.util.spec_from_file_location("check_g_056_doc_deadlinks", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()


def _write(base: Path, rel: str, content: str) -> None:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_fenced_code_links_ignored(tmp_path):
    """代码块里的 [x](y) 不算死链。"""
    docs = tmp_path / "docs"
    _write(
        docs,
        "a.md",
        "# A\n\n```markdown\n[示例](不存在的文件.md)\n```\n",
    )
    dead, total = m.scan(docs)
    assert dead == {}
    assert total == 0, "代码块内的伪链接不应计入总数"


def test_inline_code_links_ignored(tmp_path):
    """行内代码里的 [x](y) 不算死链。"""
    docs = tmp_path / "docs"
    _write(docs, "a.md", "# A\n\n写法是 `[文本](目标.md)` 这样。\n")
    dead, _ = m.scan(docs)
    assert dead == {}


def test_repo_root_relative_path_is_valid(tmp_path):
    """仓库根相对路径（本仓文档惯例）应视为有效。"""
    # 造一个"仓库内真实文件"
    real = tmp_path / "pilotstd" / "query" / "adapters" / "base.py"
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_text("# code", encoding="utf-8")

    docs = tmp_path / "docs"
    _write(docs, "a.md", "# A\n\n见 [适配器基类](pilotstd/query/adapters/base.py)。\n")

    # 让扫描器把 tmp_path 当成仓库根
    old_root = m.ROOT
    try:
        m.ROOT = tmp_path
        dead, _ = m.scan(docs)
    finally:
        m.ROOT = old_root
    assert dead == {}, "仓库根相对路径存在时应判有效"


def test_missing_relative_link_is_dead(tmp_path):
    """真正不存在的相对链接必须被判死链。"""
    docs = tmp_path / "docs"
    _write(docs, "a.md", "# A\n\n见 [不存在](../nowhere/missing.md)。\n")
    dead, _ = m.scan(docs)
    assert "docs/a.md" in dead
    assert len(dead["docs/a.md"]) == 1
    assert dead["docs/a.md"][0][1] == "../nowhere/missing.md"


def test_existing_relative_link_is_valid(tmp_path):
    """存在的相对链接不算死链。"""
    docs = tmp_path / "docs"
    _write(docs, "b.md", "# B\n")
    _write(docs, "a.md", "# A\n\n见 [B](b.md)。\n")
    # 扫描器用 m.ROOT 做「仓库内」边界校验，tmp_path 需临时充当仓库根
    old_root = m.ROOT
    try:
        m.ROOT = tmp_path
        dead, _ = m.scan(docs)
    finally:
        m.ROOT = old_root
    assert dead == {}


def test_archive_directories_skipped(tmp_path):
    """归档目录（.local/ 与 archive/）整目录跳过。"""
    docs = tmp_path / "docs"
    _write(docs, ".local/archive/x.md", "# X\n\n[死链](nowhere.md)\n")
    _write(docs, "archive/y.md", "# Y\n\n[死链](nowhere.md)\n")
    _write(docs, "ok.md", "# OK\n")
    dead, _ = m.scan(docs)
    assert dead == {}, "归档目录内的死链不应被计入"


def test_anchor_only_and_external_links_skipped(tmp_path):
    """纯锚点与外部 URL 跳过。"""
    docs = tmp_path / "docs"
    _write(
        docs,
        "a.md",
        "# A\n\n[锚点](#section) [外链](https://example.com/x) [邮件](mailto:a@b.c)\n",
    )
    dead, _ = m.scan(docs)
    assert dead == {}


def test_links_to_archived_dirs_are_skipped(tmp_path):
    """指向 `.local/` 与 `archive/` 的链接视为「已归档」而非死链。

    背景（CI 实测 2026-11-23）：`docs/.local/` 与 `docs/archive/` 被 gitignore / 不入库，
    本地有、**CI 干净检出时没有**。文档里这些链接是"历史出处"记录，
    不是给读者点的活链接 —— 判死链会导致「本地绿、CI 红」。
    """
    docs = tmp_path / "docs"
    _write(
        docs,
        "a.md",
        "# A\n\n"
        "[历史出处1](../../.local/archive/2026-11-08/docs/plans/x.md)\n"
        "[历史出处2](.local/archive/2026-11-08/docs/plans/y.md)\n"
        "[历史出处3](../archive/old/z.md)\n",
    )
    dead, _ = m.scan(docs)
    assert dead == {}, "指向归档目录的链接不应判死链（CI 干净检出时这些目录不存在）"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
