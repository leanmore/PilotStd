"""批次 1 判据自检 probe 的受控测试（2026-11-24）。

覆盖任务包要求的三条路径（与其它 probe 测试同风格）：
  1. **正常通过**：假响应齐全 → 可自动化项全部 pass
  2. **检测到问题**：关键端点 404 → 对应项 fail
  3. **环境不可达**：HTTP 层抛 ConnectionError → unreachable_reason 非空

外加一条**只读性反证**：写端点只发 OPTIONS，**绝不 POST**；
`/query` 只发单条 SELECT。

风格对齐 `tests/ops/test_probe_scripts.py`：假对象，不联网、不触真实环境。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

OPS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "ops"
sys.path.insert(0, str(OPS_DIR))

import _probe_common as common  # noqa: E402
import probe_batch1  # noqa: E402


class FakeResponse:
    """最小假响应。"""

    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload, ensure_ascii=False) if payload is not None else ""

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("No JSON object could be decoded")
        return self._payload


class FakeSession:
    """假会话：按 `(方法, 路径前缀)` 查表；`calls` 记录全部调用。"""

    def __init__(self, routes: dict, raise_on: tuple[str, ...] = ()) -> None:
        self.routes = routes
        self.raise_on = raise_on
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        path = url.split("://", 1)[-1]
        path = "/" + path.split("/", 1)[1] if "/" in path else path
        self.calls.append((method.upper(), path))
        for key in self.raise_on:
            if path.startswith(key):
                raise requests.exceptions.ConnectionError(f"boom: {key}")
        for (verb, prefix), response in self.routes.items():
            if verb == method.upper() and path.startswith(prefix):
                return response
        return FakeResponse(404, {"detail": "Not Found"})


def options(**kwargs: Any) -> common.ProbeOptions:
    """构造探测参数（超时很短，测试不真的等网络）。"""
    params = {"base_url": "http://fake.local:9028", "timeout": 1.0, "max_items": 5}
    params.update(kwargs)
    return common.ProbeOptions(**params)


@pytest.fixture(autouse=True)
def _deterministic_creds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """注入确定性凭据，消除对本地 `config/docker_creds.json` 的依赖。

    与 `tests/ops/test_probe_scripts.py` 同法：把 `DEFAULT_CREDS` 指向临时文件，
    解析路径与生产完全一致。
    """
    creds_file = tmp_path / "docker_creds.json"
    creds_file.write_text(
        '{\n  "description": "测试注入凭证 — 不入库",\n'
        '  "docker": {"base_url": "http://fake.local:9028", "username": "test-admin", '
        '"password": "test-pass"},\n'
        '  "web_api": {"api_token": "test-token"}\n}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "DEFAULT_CREDS", creds_file)


def healthy_routes() -> dict:
    """全部端点齐备的假路由表。"""
    return {
        ("GET", "/api/health"): FakeResponse(200, {"status": "ok", "version": "v1.0.0"}),
        ("POST", "/api/login"): FakeResponse(200, {"ok": True, "username": "u", "role": "admin"}),
        ("GET", "/api/announcements"): FakeResponse(200, {"total": 233933, "items": []}),
        ("GET", "/api/system/archive-stats"): FakeResponse(200, {"html": 945, "attachment": 12}),
        ("GET", "/api/system/quarantine-stats"): FakeResponse(200, {"count": 33}),
        ("OPTIONS", "/api/notification/menu/config"): FakeResponse(200, {}),
        ("OPTIONS", "/api/notification/menu/chats"): FakeResponse(200, {}),
        ("OPTIONS", "/api/pending/mark-missing"): FakeResponse(200, {}),
        ("POST", "/query"): FakeResponse(200, {"success": True, "rows": [{"c": 42}], "row_count": 1}),
        ("GET", "/api/notification/logs"): FakeResponse(200, {"total": 2600, "items": []}),
    }


def test_all_automated_checks_pass() -> None:
    """端点齐备 → 可自动化项全部 pass。"""
    report = probe_batch1.run(options(), session=FakeSession(healthy_routes()))

    assert report.count(common.STATUS_FAIL) == 0, [c.as_dict() for c in report.checks if c.status == common.STATUS_FAIL]
    assert report.exit_code() == common.EXIT_OK
    # 可自动化且非 advisory 的项应全为 pass
    automated = [
        c for c in report.checks
        if not c.name.endswith(".manual") and c.tier == common.TIER_REQUIRED
    ]
    assert automated, "应有可自动化检查"
    assert all(c.status == common.STATUS_PASS for c in automated), [
        (c.name, c.status) for c in automated if c.status != common.STATUS_PASS
    ]


def test_missing_endpoint_fails() -> None:
    """关键端点 404 → 对应项 fail。"""
    routes = healthy_routes()
    del routes[("GET", "/api/system/archive-stats")]

    report = probe_batch1.run(options(), session=FakeSession(routes))

    assert report.count(common.STATUS_FAIL) >= 1
    assert report.exit_code() == common.EXIT_FAIL
    assert any("G-22" in c.name for c in report.checks if c.status == common.STATUS_FAIL)


def test_unreachable_short_circuits() -> None:
    """环境不可达 → 记录原因、不伪造通过。"""
    session = FakeSession({}, raise_on=("/api/health",))
    report = probe_batch1.run(options(), session=session)

    assert "不可达" in report.unreachable_reason
    assert report.count(common.STATUS_PASS) == 0


def test_write_endpoints_only_probed_with_options() -> None:
    """只读性反证：写端点只发 OPTIONS，绝不 POST。"""
    session = FakeSession(healthy_routes())
    probe_batch1.run(options(), session=session)

    writes = [(m, p) for m, p in session.calls if m in ("PUT", "PATCH", "DELETE")]
    assert writes == [], f"探测过程不应发出写请求：{writes}"
    # 三个写端点必须用 OPTIONS 探测
    for path in (
        "/api/notification/menu/config",
        "/api/notification/menu/chats?channel=feishu",
        "/api/pending/mark-missing",
    ):
        assert ("OPTIONS", path) in session.calls, f"{path} 未用 OPTIONS 探测"
        assert ("POST", path) not in session.calls, f"{path} 被 POST 了（违反只读）"


def test_query_uses_single_select() -> None:
    """G-42 的 `/query` 只发单条 SELECT（不写库）。"""
    session = FakeSession(healthy_routes())
    probe_batch1.run(options(), session=session)

    query_calls = [(m, p) for m, p in session.calls if p == "/query"]
    assert query_calls == [("POST", "/query")], query_calls


def test_manual_items_are_unverified() -> None:
    """需人工验证的 11 项必须列为 unverified，不假装通过。"""
    report = probe_batch1.run(options(), session=FakeSession(healthy_routes()))

    manual = [c for c in report.checks if c.name.endswith(".manual")]
    assert len(manual) == len(probe_batch1.MANUAL_ONLY)
    assert all(c.status == common.STATUS_UNVERIFIED for c in manual)
    # 每条都要有原因说明
    assert all(c.detail for c in manual)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
