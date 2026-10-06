#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs 联动同步检查 · **触发规则表与匹配器**（T-41/2-B 从 `docs_sync_check.py` 拆出，守 G-010）。

职责：声明「哪些变更需要同步哪些文档」的规则表，以及把 git 变更匹配到规则上的函数。
依赖：规则表用到的谓词来自 `_docs_sync_io.py`（单向依赖，无环）。
"""

from __future__ import annotations

from pathlib import Path

from _docs_sync_io import (
    _has_any_source_change,
    _has_docker_changes,
    _has_handler_or_mixin_change,
    _has_index_or_readme_changes,
    _has_new_or_deleted_pyfiles,
    _has_workflow_changes,
    _is_feat_or_fix_commit,
    _test_files_changed_significantly,
)

TRIGGER_RULES = [
    {
        "name": "模块结构变化",
        "match_fn": _has_new_or_deleted_pyfiles,
        "targets": [("docs/archive/specs/模块与功能清单.md", "claude", False)],
    },
    {
        "name": "架构模式变化（Handler/Mixin）",
        "match_fn": lambda t, d: _has_handler_or_mixin_change(t, d),
        "targets": [
            ("docs/architecture/architecture.md", "claude", True),
            # 2026-09-27：旧簿 architecture/technical-debt-registry.md 已废止归档，
            # 技术债唯一数据源改为 docs/technical-debt.md（Handler/Mixin 变化须同步登记其"已接受决策/已清理"）
            ("docs/technical-debt.md", "claude", True),
        ],
    },
    {
        "name": "测试文件数大幅变化",
        "match_fn": _test_files_changed_significantly,
        "targets": [("docs/development.md", "claude", True)],
    },
    {
        "name": "Docker 基础设施变更",
        "match_fn": _has_docker_changes,
        "targets": [("docs/guides/Docker使用指南.md", "claude", True)],
    },
    {
        "name": "索引/README 路径变更",
        "match_fn": _has_index_or_readme_changes,
        "targets": [("docs/index.md", "claude", True)],
    },
    {
        "name": "CI/CD 工作流变更",
        "match_fn": _has_workflow_changes,
        "targets": [("docs/development.md", "claude", True)],
    },
    {
        "name": "feat:/fix: 提交",
        "match_fn": lambda t, d, m: _is_feat_or_fix_commit(m),
        "targets": [("CHANGELOG.md", "claude", True)],
    },
    {
        "name": "源代码变更（通用 STATUS 更新）",
        "match_fn": _has_any_source_change,
        "targets": [("STATUS.md", "claude", False)],
    },
]


def _match_trigger_rules(staged_files, diff_text, commit_msg):
    """逐一检查触发规则，返回去重后的 (trigger_name, doc_path, strategy, in_repo) 列表"""
    triggered = []
    for rule in TRIGGER_RULES:
        fn = rule["match_fn"]
        n = fn.__code__.co_argcount
        try:
            # T-16 修复（2026-09-27）：原实现用字典字面量做 arity 分派
            # （`{3: fn(a,b,c), 2: fn(a,b), 1: fn(a)}.get(n)`）——Python 会**先求值全部三个调用**，
            # 于是每个规则都因参数个数不符抛 TypeError 被 except 吞掉 → **8 条规则全部从未触发过**。
            # 改为按 arity 只调用一次。
            if n >= 3:
                matched = fn(staged_files, diff_text, commit_msg)
            elif n == 2:
                matched = fn(staged_files, diff_text)
            else:
                matched = fn(staged_files)
        except Exception as e:
            print(f"  ⚠ 规则「{rule['name']}」异常: {e}")
            continue
        if not matched:
            continue
        print(f"  🔔 触发规则: {rule['name']}")
        for doc, strategy, in_repo in rule["targets"]:
            if any(Path(f).name == Path(doc).name for _, f in staged_files):
                print(f"    -> {doc} 已在暂存区，跳过")
                continue
            triggered.append((rule["name"], doc, strategy, in_repo))
    # 去重
    seen, deduped = set(), []
    for tn, doc, s, r in triggered:
        k = (doc, s, r)
        if k not in seen:
            seen.add(k)
            deduped.append((tn, doc, s, r))
    return deduped
