# pilotstd/ui/core/_self_check.py
"""启动自检 — 在 MainWindow.__init__ 完成后调用，验证 Handler 组合模式的完整性。

仅在环境变量 PILOTSTD_SELF_CHECK=1 时执行，输出检查结果到 stderr。
检查失败不会阻止启动，仅输出警告。

用法:
    $env:PILOTSTD_SELF_CHECK = "1"
    python main.py
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger("pilotstd.self_check")


def _is_enabled() -> bool:
    """检查自检是否通过环境变量启用。"""
    return os.getenv("PILOTSTD_SELF_CHECK", "0") == "1"


def run_self_check(window: Any) -> bool:
    """运行所有检查，返回 True 表示全部通过。"""
    if not _is_enabled():
        return True

    print("[SELF_CHECK] ====== 架构完整性自检 ======", file=sys.stderr)
    all_ok = True

    all_ok &= _check_parsed_results_consistency(window)
    all_ok &= _check_core_attributes(window)
    all_ok &= _check_mgr_proxy(window)

    if all_ok:
        print("[SELF_CHECK] PASS: 全部检查通过", file=sys.stderr)
    else:
        print("[SELF_CHECK] FAIL: 发现不一致，详见上方输出", file=sys.stderr)
    print("[SELF_CHECK] ==============================", file=sys.stderr)
    return all_ok


def _check_parsed_results_consistency(window: Any) -> bool:
    """检查所有 Handler 的 _parsed_results 是否指向同一个列表对象。"""
    if not hasattr(window, "_core"):
        print("[SELF_CHECK] SKIP: _core 未初始化", file=sys.stderr)
        return True

    core = window._core
    # 需要检查一致性的 Handler 列表
    handler_names = ["scan", "query", "archive", "auto", "actions"]
    ref_id = None
    ref_handler = None
    all_ok = True

    for name in handler_names:
        handler = getattr(core, name, None)
        if handler is None:
            continue
        if not hasattr(handler, "_parsed_results"):
            continue
        # 检查各 Handler 的 _parsed_results 是否指向同一个列表对象
        hid = id(handler._parsed_results)
        if ref_id is None:
            ref_id = hid
            ref_handler = name
        elif hid != ref_id:
            print(
                f"[SELF_CHECK] FAIL: _parsed_results id 不一致 — {ref_handler}={ref_id}, {name}={hid}",
                file=sys.stderr,
            )
            all_ok = False

    if all_ok and ref_id is not None:
        print(
            f"[SELF_CHECK] OK: _parsed_results 引用一致 (id={ref_id}, 检查了 {len(handler_names)} 个 Handler)",
            file=sys.stderr,
        )
    return all_ok


def _check_core_attributes(window: Any) -> bool:
    """检查 MainWindowCore 的关键属性是否已初始化。"""
    if not hasattr(window, "_core"):
        print("[SELF_CHECK] SKIP: _core 未初始化", file=sys.stderr)
        return True

    core = window._core
    required_attrs = [
        "scan",
        "query",
        "download",
        "archive",
        "auto",
        "announce",
        "cleanup",
        "export",
        "actions",
    ]
    all_ok = True

    for attr in required_attrs:
        handler = getattr(core, attr, None)
        if handler is None:
            print(f"[SELF_CHECK] FAIL: MainWindowCore.{attr} 未初始化 (None)", file=sys.stderr)
            all_ok = False

    if all_ok:
        print(f"[SELF_CHECK] OK: 所有 {len(required_attrs)} 个 Handler 已初始化", file=sys.stderr)
    return all_ok


def _check_mgr_proxy(window: Any) -> bool:
    """检查 StandardManager 中 _core.xxx 是否有对应的属性代理。"""
    if not hasattr(window, "_mgr"):
        print("[SELF_CHECK] SKIP: _mgr 未初始化", file=sys.stderr)
        return True

    mgr = window._mgr
    # 检查已知的关键属性
    key_attrs = [
        "task_queue",
        "query_engine",
        "file_index",
        "download_engine",
        "router",
    ]
    all_ok = True

    for attr in key_attrs:
        try:
            getattr(mgr, attr)
        except AttributeError:
            print(
                f"[SELF_CHECK] FAIL: StandardManager 缺少属性代理: {attr}",
                file=sys.stderr,
            )
            all_ok = False

    if all_ok:
        print("[SELF_CHECK] OK: StandardManager 属性代理完整", file=sys.stderr)
    return all_ok
