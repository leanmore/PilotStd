"""tests/test_check_i18n_hardcoded.py — G-040 i18n 硬编码门禁的受控测试。

覆盖：干净文件通过 / 模板硬编码被检出 / 脚本字符串硬编码被检出 / 三类注释不计 /
`i18n-allow` 行内与上一行豁免 / 基线内文件通过 / 超出基线只报新增 / 新文件全报 /
`--update-baseline` 生成基线 / 排除规则（测试文件、.d.ts、locales）/ 仓库现有基线自检通过。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_i18n_hardcoded.py"


def _load_module():
    """以文件路径加载门禁脚本模块（scripts/ 不是包）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("check_i18n_hardcoded", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    """加载后的门禁模块。"""
    return _load_module()


def _write(tmp_path: Path, name: str, body: str) -> Path:
    """写一个待扫描的 fixture 文件并返回路径。"""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


CLEAN_VUE = """<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<template>
  <label>{{ t('settings.tasks.scan') }}</label>
</template>
"""

HARDCODED_VUE = """<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const err = t('common.error')
</script>

<template>
  <label>{{ t('settings.tasks.scan') }}</label>
  <span>这里写死了中文</span>
</template>
"""


# ── 扫描单元 ──────────────────────────────────────────────


def test_clean_vue_has_no_hits(gate, tmp_path: Path) -> None:
    """全部走 t() 的文件 → 无命中。"""
    assert gate.find_hardcoded(_write(tmp_path, "Clean.vue", CLEAN_VUE)) == []


def test_template_hardcoded_text_is_detected(gate, tmp_path: Path) -> None:
    """模板里的中文文本被检出，且带正确行号与片段。"""
    hits = gate.find_hardcoded(_write(tmp_path, "Bad.vue", HARDCODED_VUE))
    assert len(hits) == 1
    lineno, snippet = hits[0]
    assert lineno == 9
    assert "这里写死了中文" in snippet


def test_script_string_hardcoded_is_detected(gate, tmp_path: Path) -> None:
    """脚本里的中文字符串同样被检出（不只模板）。"""
    body = "export function f() {\n  return '加载失败'\n}\n"
    hits = gate.find_hardcoded(_write(tmp_path, "bad.ts", body))
    assert [n for n, _ in hits] == [2]


def test_comments_are_ignored(gate, tmp_path: Path) -> None:
    """行注释 / 块注释 / HTML 注释里的中文都不计。"""
    body = (
        "// 这是行注释的中文\n"
        "/* 块注释\n   里的中文 */\n"
        "<!-- 模板注释里的中文 -->\n"
        "export const ok = 1\n"
    )
    assert gate.find_hardcoded(_write(tmp_path, "Comments.vue", body)) == []


def test_url_with_double_slash_is_not_treated_as_comment(gate, tmp_path: Path) -> None:
    """`https://` 不是注释起点，其后的中文仍应被检出。"""
    body = "export const u = 'https://x/y 中文文案'\n"
    hits = gate.find_hardcoded(_write(tmp_path, "url.ts", body))
    assert [n for n, _ in hits] == [1]


def test_i18n_allow_marker_skips_same_and_next_line(gate, tmp_path: Path) -> None:
    """`i18n-allow` 在本行或上一行 → 该行豁免。"""
    body = (
        "export const a = '开发日志：开始'  // i18n-allow\n"
        "// i18n-allow\n"
        "export const b = '正则字符类'\n"
        "export const c = '未被豁免的中文'\n"
    )
    hits = gate.find_hardcoded(_write(tmp_path, "allow.ts", body))
    assert [n for n, _ in hits] == [4]


def test_scan_filters_out_tests_dts_and_locales(gate, tmp_path: Path) -> None:
    """排除规则：*.test.ts / *.spec.ts / *.d.ts / locales 目录。"""
    for name in ("a.test.ts", "b.spec.ts", "c.d.ts"):
        assert not gate.is_scannable(_write(tmp_path, name, "export const x = '中文'\n"))
    assert not gate.is_scannable(tmp_path / "locales" / "zh-CN.json")
    assert gate.is_scannable(tmp_path / "Comp.vue")


# ── CLI 行为（含基线） ────────────────────────────────────


def test_cli_fails_on_new_hardcoded_file(gate, tmp_path: Path, capsys) -> None:
    """新文件（不在基线）里出现中文 → 退出码 1，并打印文件:行号: 片段。"""
    bad = _write(tmp_path, "src/New.vue", HARDCODED_VUE)
    base = tmp_path / "baseline.txt"
    base.write_text("# empty\n", encoding="utf-8")

    assert gate.main(["--baseline", str(base), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "HARDCODED" in out and "New.vue:9" in out and "这里写死了中文" in out


def test_cli_passes_when_covered_by_baseline(gate, tmp_path: Path, capsys) -> None:
    """基线内文件（行数相等）→ 退出码 0。"""
    bad = _write(tmp_path, "src/Old.vue", HARDCODED_VUE)
    base = tmp_path / "baseline.txt"
    base.write_text(f"{gate.rel(bad)}::1\n", encoding="utf-8")

    assert gate.main(["--baseline", str(base), str(bad)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_reports_only_beyond_baseline(gate, tmp_path: Path, capsys) -> None:
    """存量文件新增一行硬编码 → 只报超出基线的那一行。"""
    body = "export const a = '存量一'\nexport const b = '存量二'\nexport const c = '新增的中文'\n"
    f = _write(tmp_path, "src/Grow.ts", body)
    base = tmp_path / "baseline.txt"
    base.write_text(f"{gate.rel(f)}::2\n", encoding="utf-8")

    assert gate.main(["--baseline", str(base), str(f)]) == 1
    out = capsys.readouterr().out
    assert "Grow.ts:3" in out and "新增的中文" in out
    assert "存量一" not in out


def test_cli_warns_on_stale_baseline_but_passes(gate, tmp_path: Path, capsys) -> None:
    """实际少于基线 → 提示可刷新但不阻断。"""
    f = _write(tmp_path, "src/Shrink.ts", "export const a = '一'\n")
    base = tmp_path / "baseline.txt"
    base.write_text(f"{gate.rel(f)}::5\n", encoding="utf-8")

    assert gate.main(["--baseline", str(base), str(f)]) == 0
    assert "STALE" in capsys.readouterr().out


def test_update_baseline_writes_current_counts(gate, tmp_path: Path) -> None:
    """--update-baseline 按当前存量重写基线。"""
    a = _write(tmp_path, "src/A.ts", "export const a = '一'\nexport const b = '二'\n")
    b = _write(tmp_path, "src/B.ts", CLEAN_VUE)
    base = tmp_path / "baseline.txt"

    assert gate.main(["--update-baseline", "--baseline", str(base), str(a), str(b)]) == 0
    text = base.read_text(encoding="utf-8")
    assert f"{gate.rel(a)}::2" in text
    assert gate.rel(b) not in text  # 无硬编码的文件不入基线


def test_report_mode_never_fails(gate, tmp_path: Path, capsys) -> None:
    """--report 只出排行，不判失败。"""
    _write(tmp_path, "src/R.ts", "export const a = '一'\n")
    assert gate.main(["--report", str(tmp_path / "src")]) == 0
    assert "存量报告" in capsys.readouterr().out


# ── 仓库自检 ──────────────────────────────────────────────


def test_repository_matches_its_baseline(gate) -> None:
    """真实仓库扫描必须与已入库基线一致（即当前无"超出基线"的新增硬编码）。"""
    files = gate.collect_files([])
    assert files, "未扫描到任何前端源码，检查 web/src 是否存在"
    hits = gate.scan(files)
    baseline = gate.load_baseline(gate.DEFAULT_BASELINE)
    assert baseline, "基线文件缺失或为空"
    beyond = {name: len(rows) for name, rows in hits.items() if len(rows) > baseline.get(name, 0)}
    assert beyond == {}, f"以下文件超出基线（新增硬编码中文）: {beyond}"
