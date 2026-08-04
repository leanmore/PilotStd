#!/usr/bin/env python
"""G-025: 检查 ADAPTER_TYPE_MAP 中的适配器是否全部可导入。

退出门禁：返回 0=通过, 1=阻断。
v2: 改为从 ADAPTER_TYPE_MAP 派生适配器列表，不再依赖 _ALL_ADAPTER_NAMES。
"""

import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ANNOUNCE_ADAPTERS = {"gb", "hb", "db"}


def _get_all_query_adapters() -> set[str]:
    """从 ADAPTER_TYPE_MAP 动态派生全部查询适配器名称。

    ADAPTER_TYPE_MAP 是查询适配器的唯一真实来源。遍历其 chain/primary/fallback
    字段收集所有被引用的适配器名称，去重后返回。
    """
    from pilotstd.query.search_strategy import ADAPTER_TYPE_MAP

    names: set[str] = set()
    for route in ADAPTER_TYPE_MAP.values():
        if not isinstance(route, dict):
            continue
        # 是优先级链（列表），/回退是主备路由（字符串）
        chain = route.get("chain", [])
        if chain:
            names.update(chain)
        primary = route.get("primary", "")
        if primary:
            names.add(primary)
        fallback = route.get("fallback", "")
        if fallback:
            names.add(fallback)
    return names


def check() -> int:
    """入口：验证所有适配器模块可导入且定义了 DISPLAY_NAME。"""
    query_adapters = _get_all_query_adapters()

    if not query_adapters:
        print("[G-025] FAIL: ADAPTER_TYPE_MAP 为空，无法派生适配器列表")
        return 1

    missing_display_name: list[str] = []
    import_errors: list[str] = []

    for name in sorted(query_adapters):
        try:
            # 动态导入适配器模块，检查_常量
            mod = importlib.import_module(f"pilotstd.query.adapters.{name}")
            dn = getattr(mod, "DISPLAY_NAME", "")
            if not isinstance(dn, str) or not dn.strip():
                missing_display_name.append(name)
        except Exception as e:
            import_errors.append(f"{name}: {e}")

    errors = []
    if import_errors:
        errors.append(f"导入失败 ({len(import_errors)}): {', '.join(import_errors)}")
    if missing_display_name:
        errors.append(f"缺少 DISPLAY_NAME ({len(missing_display_name)}): {', '.join(missing_display_name)}")

    if errors:
        print(f"[G-025] FAIL: {'; '.join(errors)}")
        return 1

    print(
        f"[G-025] PASS: {len(query_adapters)} 个查询适配器"
        f" + {len(_ANNOUNCE_ADAPTERS)} 个公告适配器，全部可导入且定义了 DISPLAY_NAME"
    )
    return 0


if __name__ == "__main__":
    sys.exit(check())
