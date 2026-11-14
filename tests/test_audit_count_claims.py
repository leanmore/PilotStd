"""G-052 第二阶段（计数声明全覆盖审计）的受控测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "audit_count_claims.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_count_claims", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def test_scan_doc_finds_registered_claim_types() -> None:
    text = "本仓有 42 个 router 模块、124 个唯一 `/api` 路径、43 张表、32 个迁移模块。"
    hits = gate.scan_doc(text)
    names = {name for name, _, _ in hits}
    assert "router 模块数" in names
    assert "唯一 API 路径数" in names
    assert "迁移可解析表数" in names
    assert "迁移模块数" in names


def test_scan_doc_ignores_plain_numbers() -> None:
    assert gate.scan_doc("今天改了 3 个文件，跑了 12 个测试。") == []


def _doc(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_undeclared_claim_fails(tmp_path) -> None:
    _doc(tmp_path, "docs/a.md", "系统有 42 个 router 模块。\n")
    failures, _, _ = gate.check(["docs/a.md"], tmp_path, {}, set())
    assert len(failures) == 1
    assert "未登记" in failures[0]


def test_declared_doc_is_covered(tmp_path) -> None:
    _doc(tmp_path, "docs/a.md", "系统有 42 个 router 模块。\n")
    failures, _, _ = gate.check(["docs/a.md"], tmp_path, {}, {"docs/a.md"})
    assert failures == []


def test_doc_without_claims_is_ignored(tmp_path) -> None:
    _doc(tmp_path, "docs/a.md", "只改了一个错别字。\n")
    failures, _, _ = gate.check(["docs/a.md"], tmp_path, {}, set())
    assert failures == []


def test_exemption_requires_reason(tmp_path) -> None:
    path = tmp_path / "ex.json"
    path.write_text(json.dumps({"exemptions": {"docs/a.md": "  "}}), encoding="utf-8")
    entries, problems = gate.load_exemptions(path)
    assert entries == {}
    assert problems and "缺少理由" in problems[0]


def test_stale_exemption_warns(tmp_path) -> None:
    _doc(tmp_path, "docs/a.md", "无数字。\n")
    failures, warns, _ = gate.check(["docs/a.md"], tmp_path, {"docs/a.md": "历史条目"}, set())
    assert failures == []
    assert any("豁免已过期" in w for w in warns)
