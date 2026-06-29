# pilotstd/core/config/migrate.py
# 配置迁移 + 规则导入导出 — 从 config.py 拆分

import json
import logging
import os
from typing import Any

_log = logging.getLogger("pilotstd.config")


def _migrate_ui_keys(config: Any) -> None:
    """将旧版 ui.* 键迁移到 appearance.* 前缀（v0.5.x → v0.6 兼容）。"""
    _map = {
        "ui.column_widths": "appearance.column_widths",
        "ui.window_geometry": "appearance.window_geometry",
        "ui.main_splitter": "appearance.main_splitter",
        "ui.right_splitter": "appearance.right_splitter",
        "ui.sort_column": "appearance.sort_column",
        "ui.sort_order": "appearance.sort_order",
        "ui.last_import_path": "appearance.last_import_path",
    }
    for old, new in _map.items():
        val = config.get(old)
        if val is not None:
            if config.get(new) is None:
                config.set(new, val)
            node: Any = config._data
            parts = old.split(".")
            for p in parts[:-1]:
                if isinstance(node, dict) and p in node:
                    node = node[p]
                else:
                    node = None
                    break
            if node and isinstance(node, dict) and parts[-1] in node:
                del node[parts[-1]]


def export_rules(config: Any, file_path: str) -> bool:
    """将当前所有规则导出到 JSON 文件。返回 True/False。"""
    try:
        rules_raw = config.get("sites.rules", "[]")
        if isinstance(rules_raw, str):
            try:
                rules = json.loads(rules_raw)
            except json.JSONDecodeError:
                rules = []
        elif isinstance(rules_raw, list):
            rules = rules_raw
        else:
            rules = []
        payload = {
            "version": "1.0",
            "description": "PilotStd 网站规则导出",
            "rules": rules,
        }
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except (OSError, json.JSONDecodeError) as e:
        _log.error("导出规则失败: %s", e)
        return False


def import_rules(config: Any, file_path: str) -> int:
    """从 JSON 文件导入规则并合并到已有配置。返回成功导入的规则数，-1 表示失败。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _log.error("读取规则文件失败: %s", e)
        return -1

    imported = data.get("rules", []) if isinstance(data, dict) else data
    if not isinstance(imported, list):
        _log.error("规则数据格式无效：期望列表或对象")
        return -1

    rules_raw = config.get("sites.rules", "[]")
    if isinstance(rules_raw, str):
        try:
            existing = json.loads(rules_raw)
        except json.JSONDecodeError:
            existing = []
    elif isinstance(rules_raw, list):
        existing = rules_raw
    else:
        existing = []

    added = 0
    for rule in imported:
        if not isinstance(rule, dict) or "name" not in rule:
            continue
        if not any(r.get("name") == rule["name"] for r in existing):
            existing.append(
                {
                    "name": rule.get("name", ""),
                    "type": rule.get("type", ""),
                    "url": rule.get("url", ""),
                    "xpath": rule.get("xpath", ""),
                    "regex": rule.get("regex", ""),
                    "captcha": rule.get("captcha", ""),
                }
            )
            added += 1

    config.set("sites.rules", json.dumps(existing, ensure_ascii=False))
    config.save()
    return added
