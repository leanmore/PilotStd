#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G-044 术语与禁用词门禁（第 5 批：术语表 + 禁用词治理）。

背景：`pilotstd/i18n/*.json` 中同一概念存在多种译法，且部分已由方案裁剪的
技术黑话/内部代号残留（实测：`适配器` 2 处、`堆栈` 1 处、`未命中` 1 处、
`失败` 用于"文件名无法解析" 1 处）。此前无任何门禁拦截。

判定规则（三条，仅前两条阻断）：
  1. **禁用词命中**（阻断）：`notification.*` 作用域内的值出现术语表的 `forbidden` 词组；
  2. **三语术语一致性**（阻断）：术语表 `keys` 登记的键，三语值必须与登记值严格相等
     ——防"改了简体忘改繁体"；
  3. `aliases` 命中（仅报告）：值内出现可接受的同义写法，提示但不阻断。

白名单三层（均为显式登记，禁止无理由豁免）：
  - `exempt_keys`：该键整体跳过术语/禁用词校验（配置字段名场景，如 webhook_url）；
  - `exempt_terms`：这些词在任何键内出现都不算禁用词（英文技术标识如 bot_token）；
  - 行内 `_allow_legacy`：值以该标记结尾时跳过（与 check_i18n_hardcoded 的基线策略同源）。

作用域：`meta.scope_keys`（当前 `notification.*`，208 键）。界面标签（478 键）的
用词自由度天然更高，且全量扫描会命中"保存项目/保存CSV"等**正确**用法。

用法：
  python scripts/check_terminology.py            # 门禁（CI / pre-commit）
  python scripts/check_terminology.py --report   # 仅报告不阻断（上线前空跑）
  python scripts/check_terminology.py --list     # 列出术语表与白名单
退出码：0 = 通过（可能带 aliases 提示）；1 = 存在禁用词命中或术语不一致。
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any

# Windows 控制台默认编码无法输出中文
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = PROJECT_ROOT / "pilotstd" / "i18n"
GLOSSARY = PROJECT_ROOT / "docs" / "governance" / "glossary.json"
LANGS = ("zh_CN", "zh_TW", "en")

# 行内豁免标记：值以该后缀结尾时跳过校验（避免"永远红"的门禁）
ALLOW_LEGACY_MARK = "_allow_legacy"


def _load_glossary() -> dict[str, Any]:
    """读取术语表；缺失或格式错误时抛出（门禁不得静默失效）。"""
    data: dict[str, Any] = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    return data


def _load_pack(lang: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    return data


def _key_line_index(path: Path) -> dict[str, int]:
    """解析语言包文本，返回 {键: 行号}（供输出文件:行号）。"""
    index: dict[str, int] = {}
    pattern = re.compile(r'^\s*"((?:[^"\\]|\\.)+)"\s*:')
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = pattern.match(line)
        if match:
            index[match.group(1)] = lineno
    return index


def _in_scope(key: str, scope_keys: list[str]) -> bool:
    """作用域判定：支持 `notification.*` 这类前缀通配。"""
    for pattern in scope_keys:
        if pattern.endswith(".*"):
            if key.startswith(pattern[:-1]):  # 保留末尾的 "."
                return True
        elif key == pattern:
            return True
    return False


def _check_key(
    key: str,
    packs: dict[str, dict[str, str]],
    glossary: dict[str, Any],
    exempt_keys: set[str],
    exempt_terms: list[str],
    forbidden: list[tuple[str, str]],
    aliases: list[tuple[str, str]],
    scope_keys: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """校验单个键，返回 (阻断项, 提示项, 术语一致性问题)。"""
    errors: list[str] = []
    warns: list[str] = []
    if key in exempt_keys or not _in_scope(key, scope_keys):
        return errors, warns, []

    value = packs["zh_CN"].get(key)
    if not isinstance(value, str):
        return errors, warns, []
    if value.rstrip().endswith(ALLOW_LEGACY_MARK):
        return errors, warns, []

    # 检测 1：禁用词（词组）；exempt_terms 命中时该处跳过
    scrubbed = value
    for term in exempt_terms:
        scrubbed = scrubbed.replace(term, "")
    for variant, term_id in forbidden:
        if variant and variant in scrubbed:
            errors.append(f"命中禁用词「{variant}」— 术语 {term_id}")

    # 检测 3：aliases 命中（仅提示）
    for variant, term_id in aliases:
        if variant and variant in scrubbed:
            warns.append(f"使用了可接受但不推荐的写法「{variant}」（首选写法见术语 {term_id}）")
    return errors, warns, []


def _check_term_consistency(
    glossary: dict[str, Any], packs: dict[str, dict[str, str]]
) -> list[str]:
    """检测 2：术语表 keys 登记的三语值必须与语言包严格相等。"""
    problems: list[str] = []
    for term in glossary.get("terms", []):
        for key in term.get("keys", []):
            for lang in LANGS:
                expected = term.get(lang)
                actual = packs[lang].get(key)
                if key not in packs[lang]:
                    problems.append(
                        f"术语 {term['id']}: {lang} 缺少登记键 {key}"
                    )
                elif actual != expected:
                    problems.append(
                        f"术语 {term['id']} 不一致: {key} 的 {lang} 期望 {expected!r} 实际 {actual!r}"
                    )
    return problems


def _report_locations(keys: list[str], indexes: dict[str, dict[str, int]]) -> list[str]:
    """把键映射为 `文件:行号`（zh_CN 为准）。"""
    out: list[str] = []
    for key in keys:
        lineno = indexes["zh_CN"].get(key)
        rel = "pilotstd/i18n/zh_CN.json"
        out.append(f"  {rel}:{lineno}" if lineno else f"  {rel} <未定位>")
    return out


def main(argv: list[str]) -> int:
    """门禁入口：加载术语表与三语语言包，执行三条检测并返回退出码。

    `--report` 仅报告不阻断（上线前空跑验证用）；`--list` 打印术语表与白名单。
    """
    report_only = "--report" in argv
    list_only = "--list" in argv

    try:
        glossary = _load_glossary()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error::术语表读取失败: {GLOSSARY} — {exc}")
        return 1

    packs = {lang: _load_pack(lang) for lang in LANGS}
    scope_keys: list[str] = glossary["meta"]["scope_keys"]
    exempt_keys = set(glossary.get("exempt_keys", []))
    exempt_terms: list[str] = glossary.get("exempt_terms", [])
    terms = glossary.get("terms", [])

    forbidden: list[tuple[str, str]] = [
        (variant, term["id"]) for term in terms for variant in term.get("forbidden", [])
    ]
    aliases: list[tuple[str, str]] = [
        (variant, term["id"]) for term in terms for variant in term.get("aliases", [])
    ]

    if list_only:
        print(f"术语表: {GLOSSARY}（{len(terms)} 条术语，作用域 {scope_keys}）")
        for term in terms:
            keys = term.get("keys", [])
            print(f"  [{term['id']}] zh_CN={term['zh_CN']!r} 键={len(keys)} 禁用={term.get('forbidden', [])}")
        print(f"豁免键 {len(exempt_keys)} 个；豁免词 {len(exempt_terms)} 个")
        return 0

    indexes = {lang: _key_line_index(I18N_DIR / f"{lang}.json") for lang in LANGS}

    blocking: list[tuple[str, str]] = []  # (键, 问题)
    hints: list[tuple[str, str]] = []
    for key, value in packs["zh_CN"].items():
        errors, warns, _ = _check_key(
            key, packs, glossary, exempt_keys, exempt_terms, forbidden, aliases, scope_keys
        )
        for problem in errors:
            blocking.append((key, problem))
        for problem in warns:
            hints.append((key, problem))

    consistency = _check_term_consistency(glossary, packs)

    print("=" * 68)
    print(f"G-044 术语与禁用词检查（{len(terms)} 条术语，作用域 {scope_keys}）")
    print("=" * 68)
    print(f"  扫描键: {len(packs['zh_CN'])}（作用域内 {sum(1 for k in packs['zh_CN'] if _in_scope(k, scope_keys))}）")
    print(f"  阻断项: {len(blocking)} + 术语不一致 {len(consistency)}")
    print(f"  提示项: {len(hints)}")
    print()

    if blocking:
        for key, problem in blocking:
            print(f"::error::{key} {problem}")
        for loc in _report_locations([k for k, _ in blocking], indexes):
            print(loc)
        print()
    if consistency:
        for problem in consistency:
            print(f"::error::术语不一致: {problem}")
        print()
    if hints:
        for key, problem in hints:
            print(f"::warning::{key} {problem}")
        print()

    if blocking or consistency:
        if report_only:
            print(f"[--report] 空跑模式：发现 {len(blocking) + len(consistency)} 项，不判失败。")
            return 0
        print("FAIL: 请按术语表修正文案，或在 glossary.json 中显式登记豁免（须带理由）。")
        return 1

    print("PASS: 作用域内无禁用词命中，术语三语一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
