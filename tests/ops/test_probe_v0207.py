"""`scripts/ops/probe_v0207.py`（v0.207.0 部署专项验收）的受控测试。

用假客户端替代真实 HTTP（不联网、不依赖生产），覆盖三种形态：
1. **全绿**：版本/状态/数据/统计都符合部署后期望 → 退出码 0；
2. **版本未升级**：`/api/system/version` 仍 0.206.0 → 必须 FAIL（这正是本次版本号缺陷的症状）；
3. **状态口径回退**：`?status=未生效` 返回全表 → 必须 FAIL。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

OPS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ops"
sys.path.insert(0, str(OPS_DIR))

import _probe_common as common  # noqa: E402
import probe_v0207  # noqa: E402


class FakeResp:
    """最小响应：状态码 + JSON 载荷。"""

    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {"content-type": "application/json"}
        self.text = "{}"

    def json(self) -> Any:
        return self._payload


class FakeClient:
    """假客户端：按路径返回构造好的收益/异常形态。"""

    def __init__(self, *, system_version: str = "0.207.0", wei_total: int = 30, whole: int = 776) -> None:
        self.base_url = "http://fake.local:9028"
        self.system_version = system_version
        self.wei_total = wei_total
        self.whole = whole

    def login(self) -> None:
        return None

    def csrf_headers(self) -> dict:
        return {}

    def get(self, path: str, params: dict | None = None):  # noqa: ANN201
        params = params or {}
        if path == "/api/health":
            return FakeResp(200, {"status": "ok", "version": "a" * 40, "schema_version": 76})
        if path == "/api/system/version":
            return FakeResp(200, {"version": self.system_version, "tag": f"v{self.system_version}"})
        if path == "/api/standards/status":
            status = str(params.get("status") or "")
            if status == "faq":
                return FakeResp(400, {"detail": "bad status"})
            if status == "":
                return FakeResp(200, {"total": self.whole})
            return FakeResp(200, {"total": self.wei_total})
        if path == "/api/stats":
            return FakeResp(200, {"current": 572, "expired": 174, "pending": 0, "upcoming": 30})
        return FakeResp(404, {"detail": "Not Found"})

    def post(self, path: str, json: dict | None = None, headers: dict | None = None):  # noqa: ANN001, ANN201
        sql = str((json or {}).get("sql") or "")
        if "file_index WHERE status='未生效'" in sql:
            return FakeResp(200, {"success": True, "rows": [{"c": 0}]})
        if "favorite_downloads" in sql:
            return FakeResp(200, {"success": True, "rows": [{"c": 0}]})
        if "notification_log WHERE user_id=1" in sql:
            return FakeResp(200, {"success": True, "rows": [{"c": 0}]})
        if "COUNT(*) AS c FROM file_index" in sql:
            return FakeResp(200, {"success": True, "rows": [{"c": 776}]})
        return FakeResp(200, {"success": True, "rows": [{"c": 0}]})


def _run(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> common.Report:
    monkeypatch.setattr(probe_v0207.common, "build_client", lambda options, session=None: client)
    parser_args = common.ProbeOptions(base_url="http://fake.local:9028", timeout=1.0)
    import argparse

    ns = argparse.Namespace(**vars(parser_args))
    return probe_v0207.run(ns)


class TestV0207Acceptance:
    def test_all_green_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        report = _run(monkeypatch, FakeClient())
        failed = [c.name for c in report.checks if c.status == common.STATUS_FAIL]
        assert failed == [], f"不应有失败项: {failed}"
        assert report.exit_code() == common.EXIT_OK

    def test_old_version_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        report = _run(monkeypatch, FakeClient(system_version="0.206.0"))
        names = {c.name for c in report.checks if c.status == common.STATUS_FAIL}
        assert "version.system_version" in names
        assert report.exit_code() == common.EXIT_FAIL

    def test_wei_sheng_xiao_whole_table_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 旧缺陷形态：未生效 返回全表
        report = _run(monkeypatch, FakeClient(wei_total=776))
        names = {c.name for c in report.checks if c.status == common.STATUS_FAIL}
        assert "status.not_whole_table" in names
