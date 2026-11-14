"""G-054 GUI 单文件覆盖率棘轮的受控测试（P2-08）。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_gui_coverage_ratchet.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_gui_coverage_ratchet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load()


def _summary(path: Path, mapping: dict[str, float]) -> Path:
    payload = {"total": {"lines": {"pct": 0}}}
    for rel, pct in mapping.items():
        payload[str(path.parent / rel)] = {"lines": {"pct": pct}}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _baseline(path: Path, files: dict[str, float], type_only=(), tolerance=0.5) -> Path:
    payload = {
        "_meta": {"tolerance_pp": tolerance},
        "files": {rel: {"lines": pct} for rel, pct in files.items()},
        "type_only": list(type_only),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _run(tmp_path: Path, summary: Path, baseline: Path) -> int:
    return gate.main(["--summary", str(summary), "--baseline", str(baseline)])


def test_equal_coverage_passes(tmp_path, capsys) -> None:
    summary = _summary(tmp_path / "sum.json", {"src/a.vue": 74.56})
    baseline = _baseline(tmp_path / "base.json", {"src/a.vue": 74.5})
    assert _run(tmp_path, summary, baseline) == 0
    assert "PASS" in capsys.readouterr().out


def test_drop_beyond_tolerance_fails(tmp_path, capsys) -> None:
    summary = _summary(tmp_path / "sum.json", {"src/a.vue": 73.0})
    baseline = _baseline(tmp_path / "base.json", {"src/a.vue": 74.56})
    assert _run(tmp_path, summary, baseline) == 1
    assert "下降超过" in capsys.readouterr().out


def test_small_drop_within_tolerance_passes(tmp_path) -> None:
    summary = _summary(tmp_path / "sum.json", {"src/a.vue": 74.2})
    baseline = _baseline(tmp_path / "base.json", {"src/a.vue": 74.56}, tolerance=0.5)
    assert _run(tmp_path, summary, baseline) == 0


def test_rise_reports_tightening_hint(tmp_path, capsys) -> None:
    summary = _summary(tmp_path / "sum.json", {"src/a.vue": 80.0})
    baseline = _baseline(tmp_path / "base.json", {"src/a.vue": 74.56})
    assert _run(tmp_path, summary, baseline) == 0
    assert "可收紧基线" in capsys.readouterr().out


def test_missing_tracked_file_fails(tmp_path, capsys) -> None:
    summary = _summary(tmp_path / "sum.json", {"src/other.vue": 50.0})
    baseline = _baseline(tmp_path / "base.json", {"src/a.vue": 74.56})
    assert _run(tmp_path, summary, baseline) == 1
    assert "未出现在覆盖率报告里" in capsys.readouterr().out


def test_type_only_file_is_soft(tmp_path, capsys) -> None:
    summary = _summary(tmp_path / "sum.json", {"src/types.ts": 80.0})
    baseline = _baseline(tmp_path / "base.json", {}, type_only=["src/types.ts"])
    assert _run(tmp_path, summary, baseline) == 0
    assert "纯类型文件行覆盖率" in capsys.readouterr().out


def test_missing_summary_exits_2(tmp_path) -> None:
    rc = gate.main(
        ["--summary", str(tmp_path / "nope.json"), "--baseline", str(tmp_path / "base.json")]
    )
    assert rc == 2


def test_absolute_windows_keys_are_normalized() -> None:
    assert gate.normalize_key(r"D:\repo\web\src\views\TaskView.vue") == "src/views/TaskView.vue"
    assert gate.normalize_key("/home/ci/web/src/utils/taskPipeline.ts") == "src/utils/taskPipeline.ts"
