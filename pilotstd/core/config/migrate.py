# 模块：项目/核心/配置/迁移脚本
# 配置迁移+规则导入导出—从配置脚本拆分

import json
import logging
import os
from typing import Any

_log = logging.getLogger("pilotstd.config")


# ──键名映射表：旧版.*→新版.*──
# 版本零5.使用"."前缀，版本零6起统一为"."
# 此映射确保老用户升级后配置不丢失
_UI_MIGRATION_MAP = {
    "ui.column_widths": "appearance.column_widths",
    "ui.window_geometry": "appearance.window_geometry",
    "ui.main_splitter": "appearance.main_splitter",
    "ui.right_splitter": "appearance.right_splitter",
    "ui.sort_column": "appearance.sort_column",
    "ui.sort_order": "appearance.sort_order",
    "ui.last_import_path": "appearance.last_import_path",
}


def _migrate_ui_keys(config: Any) -> None:
    """将旧版 ui.* 键迁移到 appearance.* 前缀（v0.5.x → v0.6 兼容）。"""
    # 遍历映射表，仅在新键不存在时才迁移，不覆盖已有的新键值
    for old, new in _UI_MIGRATION_MAP.items():
        val = config.get(old)
        if val is not None:
            if config.get(new) is None:
                config.set(new, val)
            # 从旧位置删除已迁移的键，清理残留数据
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
        # 规则以数据字符串形式存储在.规则中，需先解析
        rules_raw = config.get("sites.rules", "[]")
        if isinstance(rules_raw, str):
            try:
                rules = json.loads(rules_raw)
            except json.JSONDecodeError:
                # 存储的数据损坏时导出空列表，不阻断用户操作
                rules = []
        elif isinstance(rules_raw, list):
            rules = rules_raw
        else:
            rules = []
        # 统一导出格式：++规则列表
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

    # 兼容两种格式：{"规则":[...]}或直接的列表
    imported = data.get("rules", []) if isinstance(data, dict) else data
    if not isinstance(imported, list):
        _log.error("规则数据格式无效：期望列表或对象")
        return -1

    # 读取已有规则（同样兼容字符串/列表两种存储格式）
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

    # 按去重合并：同名规则不重复导入
    added = 0
    for rule in imported:
        if not isinstance(rule, dict) or "name" not in rule:
            continue
        if not any(r.get("name") == rule["name"] for r in existing):
            # 只保留预定义的字段，过滤掉导入文件中的未知字段
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

    # 写回数据字符串存储，并立即落盘
    config.set("sites.rules", json.dumps(existing, ensure_ascii=False))
    config.save()
    return added
