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
    return TestClient(app)


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
