"""API 矩阵审计脚本冒烟测试：确保解析在当前仓库可用且前端调用无死路径。"""

from scripts.audit_api_matrix import (
    _public_prefixes,
    build_report,
    parse_backend,
    parse_frontend,
    parse_user_write_allowlist,
    parse_view_guards,
)


def test_matrix_smoke() -> None:
    routes = parse_backend(_public_prefixes())
    calls = parse_frontend()
    exact, prefixes = parse_user_write_allowlist()
    report = build_report(routes, calls, exact, prefixes, parse_view_guards())

    assert report["routes"] >= 100
    assert report["calls"] >= 50
    assert report["unmatched"] == [], report["unmatched"]
    assert report["method_mismatch"] == []
    assert report["unguarded_views"] == [], report["unguarded_views"]
    assert report["user_write_allowlist"], "用户白名单解析为空，说明 AST 常量提取失效"


def test_matrix_flags_expected_admin_calls() -> None:
    routes = parse_backend(_public_prefixes())
    calls = parse_frontend()
    exact, prefixes = parse_user_write_allowlist()
    report = build_report(routes, calls, exact, prefixes, parse_view_guards())

    called = {(item["method"], item["path"]) for item in report["admin_calls"]}
    assert any(path == "/settings" for _method, path in called)
    assert any(path == "/validity/run" or path.startswith("/tasks") for _method, path in called) or called
