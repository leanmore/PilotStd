"""端点级测试：`/api/download/import` 与 `/api/quality/run`（体检 D-14）。

体检记录这两条路径"无端点级测试"（实测：`grep download/import|quality/run tests/` 零命中）。
本文件覆盖：

1. `/api/download/import` 的输入校验（text/file 互斥、必须二选一）；
2. 只含无效标准号时不提交下载（total=0 且不调用引擎）；
3. 有效标准号 → 调用引擎并回填统计/结果（含重复号只提交一次）；
4. 文件上传路径（读取内容 → UTF-8 解码 → 解析）；
5. `/api/quality/run` 直接返回 `quality_service.run_check()` 的结果。

鉴权不在此文件：这两个端点不挂 `@require_role`，登录/角色链路由
`tests/test_api_favorites_auth.py` 与 `tests/test_users_wechat_auth.py` 覆盖。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.download import router as download_router
from docker.api.quality import router as quality_router
from docker.manager import get_manager_dep
from tests._auth_helpers import admin_cookies


def _task(number: str = "GB/T 12345-2020", status: str = "success") -> SimpleNamespace:
    return SimpleNamespace(
        standard_number=number,
        query_result=SimpleNamespace(standard_name=f"{number} 名称"),
        status=SimpleNamespace(value=status),
        saved_path=f"/tmp/{number}.pdf",
        error_message=None,
    )


def _stats(**kwargs) -> SimpleNamespace:
    values = {"total": 1, "success": 1, "failed": 0, "skipped_adopted": 0, "skipped_exists": 0}
    values.update(kwargs)
    return SimpleNamespace(**values)


@pytest.fixture()
def mgr() -> MagicMock:
    manager = MagicMock()
    manager.download_by_numbers.return_value = ([_task()], _stats())
    manager.quality_service.run_check.return_value = {"ok": True, "checked": 3, "issues": []}
    return manager


@pytest.fixture()
def client(mgr: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(download_router)
    app.include_router(quality_router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app, cookies=admin_cookies())


def test_import_requires_text_or_file(client: TestClient, mgr: MagicMock) -> None:
    r = client.post("/api/download/import", data={})
    assert r.status_code == 400
    assert "text 或 file" in r.json()["detail"]
    mgr.download_by_numbers.assert_not_called()


def test_import_rejects_both_sources(client: TestClient, mgr: MagicMock) -> None:
    r = client.post(
        "/api/download/import",
        data={"text": "GB/T 12345-2020"},
        files={"file": ("list.txt", b"GB/T 12345-2020", "text/plain")},
    )
    assert r.status_code == 400
    assert "不可同时提供" in r.json()["detail"]
    mgr.download_by_numbers.assert_not_called()


def test_import_invalid_only_does_not_download(client: TestClient, mgr: MagicMock) -> None:
    r = client.post("/api/download/import", data={"text": "not_a_standard\nxyz"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] == []
    assert len(body["invalid"]) == 2
    assert body["total"] == 0
    assert body["results"] == []
    mgr.download_by_numbers.assert_not_called()


def test_import_valid_numbers_calls_engine(client: TestClient, mgr: MagicMock) -> None:
    r = client.post("/api/download/import", data={"text": "GB/T 12345-2020"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["success"] == 1
    assert body["results"][0]["standard_number"] == "GB/T 12345-2020"
    assert body["results"][0]["status"] == "success"
    mgr.download_by_numbers.assert_called_once_with(["GB/T 12345-2020"])


def test_import_duplicates_submitted_once(client: TestClient, mgr: MagicMock) -> None:
    r = client.post("/api/download/import", data={"text": "GB/T 12345-2020\nGB/T 12345-2020"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] == ["GB/T 12345-2020"]
    assert body["duplicates"] == ["GB/T 12345-2020"]
    mgr.download_by_numbers.assert_called_once_with(["GB/T 12345-2020"])


def test_import_from_uploaded_file(client: TestClient, mgr: MagicMock) -> None:
    r = client.post(
        "/api/download/import",
        files={"file": ("list.txt", "GB/T 12345-2020\nISO 9001:2015".encode(), "text/plain")},
    )
    assert r.status_code == 200
    assert r.json()["valid"] == ["GB/T 12345-2020", "ISO 9001:2015"]
    mgr.download_by_numbers.assert_called_once_with(["GB/T 12345-2020", "ISO 9001:2015"])


def test_quality_run_returns_service_result(client: TestClient, mgr: MagicMock) -> None:
    r = client.post("/api/quality/run")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "checked": 3, "issues": []}
    mgr.quality_service.run_check.assert_called_once_with()


def test_import_results_carry_backend_parsed_fields(client: TestClient) -> None:
    """P1-C1（2026-11-24）：下载结果必须带**后端解析字段**。

    前端归档此前只用自身正则解析标准号，对 API/ASME 等编号 38/40 全盲 →
    解析失败即静默跳过归档，下载件滞留 `/standards` 根目录。现由后端统一口径给出字段。
    """
    r = client.post("/api/download/import", data={"text": "GB/T 12345-2020"})
    item = r.json()["results"][0]
    assert item["logical_code"] == "GB/T"
    assert item["number"] == 12345
    assert item["year"] == 2020
    assert item["num_prefix"] == ""


def test_import_results_parse_api_typed_number(client: TestClient, mgr: MagicMock) -> None:
    """API 类型词编号（前端正则解析不出）也必须由后端给出字段。"""
    mgr.download_by_numbers.return_value = ([_task("API STD 610")], _stats())
    r = client.post("/api/download/import", data={"text": "API STD 610"})
    item = r.json()["results"][0]
    assert item["logical_code"] == "API"
    assert item["number"] == 610
    assert item["num_prefix"] == "STD"


def test_import_results_unparseable_keeps_empty_defaults(client: TestClient, mgr: MagicMock) -> None:
    """解析不出的标准号：四个字段保持默认空值，由前端回落自身解析。"""
    mgr.download_by_numbers.return_value = ([_task("Zzz 未知编号")], _stats())
    r = client.post("/api/download/import", data={"text": "GB/T 12345-2020"})
    item = r.json()["results"][0]
    assert item["logical_code"] == ""
    assert item["number"] == 0
    assert item["year"] == 0
    assert item["num_prefix"] == ""
