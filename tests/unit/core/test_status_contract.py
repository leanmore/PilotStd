"""API 状态契约测试（#32-C / R14-4c，2026-10-01）。

C 阶段把状态契约显式化：后端在原有 `status`（数据值，中文，**向后兼容**）之外
提供 `status_key`（稳定英文键），并让过滤参数同时接受英文键与历史中文值。
本文件锁定该契约：

① `status_key()` / `resolve_status_filter()` 纯函数语义（含别名归一与兜底）；
② `/api/standards/status`：item 带 `status_key`；`status=active` 与 `status=现行` 等价；
   非法值不生效（与旧实现一致）；
③ `/api/query/results`：结果带 `status_key`，**磁盘文件不被改写**；
④ `/api/pending/requery`：结果带 `status_key`；
⑤ `WechatIPService.get_status()`：带 `current_ip_known` 布尔键（前端不再比较 '未知'）。
"""

from __future__ import annotations

import json

import pytest

from pilotstd.core.status import Status, resolve_status_filter, status_key


class _StubStandardService:
    def __init__(self) -> None:
        self.seen_filters: list[dict[str, str] | None] = []

    def get_list(self, page: int = 1, size: int = 20, filters: dict[str, str] | None = None) -> dict:
        self.seen_filters.append(filters)
        return {
            "total": 1,
            "page": page,
            "size": size,
            "items": [{"id": 1, "standard_number": "GB/T 1-2020", "std_name": "示例", "status": Status.ACTIVE.value}],
        }


class _StubManager:
    def __init__(self) -> None:
        self.standard_service = _StubStandardService()


# ── ① 纯函数 ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (Status.ACTIVE.value, "active"),
        (Status.WITHDRAWN_NORMALIZED.value, "withdrawn"),
        (Status.WITHDRAWN.value, "withdrawn"),  # 双拼写归一到同一键
        (Status.UNKNOWN.value, "unknown"),
        ("", "unknown"),
        (None, "unknown"),
        ("不认识的值", "unknown"),
        (" active ", "active"),  # 空白剥离；入参已是英文键时幂等
    ],
)
def test_status_key(raw, expected):
    assert status_key(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("active", Status.ACTIVE.value),  # 英文键（新前端口径）
        ("withdrawn", Status.WITHDRAWN_NORMALIZED.value),  # 键归一 → 规范数据值
        ("unknown", Status.UNKNOWN.value),
        (Status.ACTIVE.value, Status.ACTIVE.value),  # 历史中文值（向后兼容）
        (Status.WITHDRAWN.value, Status.WITHDRAWN_NORMALIZED.value),  # 别名归一
        ("", None),
        (None, None),
        ("nonsense", None),  # 非法值不生效（同旧实现）
    ],
)
def test_resolve_status_filter(raw, expected):
    assert resolve_status_filter(raw) == expected


# ── ② 标准状态列表契约 ────────────────────────────────────────────────────


def test_standards_status_items_expose_status_key():
    """item 必须同时给出数据值 status 与英文键 status_key。"""
    from docker.api.standards import get_standards_status

    mgr = _StubManager()
    resp = get_standards_status(status=None, standard_no=None, name=None, page=1, page_size=20, mgr=mgr)

    item = resp["items"][0]
    assert item["status"] == Status.ACTIVE.value, "数据值字段保持不变（向后兼容）"
    assert item["status_key"] == "active"
    assert mgr.standard_service.seen_filters == [None]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("active", Status.ACTIVE.value),
        (Status.ACTIVE.value, Status.ACTIVE.value),
        ("Active", None),
        ("active ", Status.ACTIVE.value),
    ],
)
def test_standards_status_filter_accepts_key_and_legacy_value(raw, expected):
    """过滤入参：英文键与历史中文值都接受；`Active`（枚举名，非契约值）不生效。"""
    from docker.api.standards import get_standards_status

    mgr = _StubManager()
    get_standards_status(status=raw, standard_no=None, name=None, page=1, page_size=20, mgr=mgr)

    filters = mgr.standard_service.seen_filters[0]
    if expected is None:
        assert filters is None, "非法过滤值必须被忽略（与旧实现一致）"
    else:
        assert filters == {"status": expected}


# ── ③ 查询结果契约 ────────────────────────────────────────────────────────


def test_query_results_expose_status_key_without_rewriting_file(tmp_path, monkeypatch):
    from docker.api import query as query_api

    payload = [
        {"standard_number": "GB/T 1-2020", "status": Status.ACTIVE.value},
        {"standard_number": "GB 713-2014", "status": Status.WITHDRAWN_NORMALIZED.value},
        {"standard_number": "XX", "status": "自定义"},
    ]
    path = tmp_path / "query_results.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(query_api, "QUERY_RESULTS_FILE", str(path))

    resp = query_api.get_query_results()

    assert [r["status_key"] for r in resp["results"]] == ["active", "withdrawn", "unknown"]
    assert [r["status"] for r in resp["results"]] == [Status.ACTIVE.value, Status.WITHDRAWN_NORMALIZED.value, "自定义"]
    assert path.read_text(encoding="utf-8") == before, "响应加工不得改写磁盘上的结果文件"


def test_query_results_missing_file_returns_empty(monkeypatch, tmp_path):
    from docker.api import query as query_api

    monkeypatch.setattr(query_api, "QUERY_RESULTS_FILE", str(tmp_path / "nope.json"))
    assert query_api.get_query_results() == {"results": []}


# ── ④ 待确认重查契约 ──────────────────────────────────────────────────────


class _StubResult:
    def __init__(self, number: str, name: str, status: str) -> None:
        self.standard_number = number
        self.standard_name = name
        self.status = status
        self.source_site = "std_gov"


class _StubRequeryManager:
    def __init__(self) -> None:
        self.resolved: list[tuple[list[str], str]] = []

    def query_by_numbers(self, numbers, preferred_site: str = ""):
        return [_StubResult("GB/T 1-2020", "示例", Status.ACTIVE.value)], None

    def resolve_pending_by_numbers(self, numbers, reason: str) -> None:
        self.resolved.append((list(numbers), reason))


def test_pending_requery_exposes_status_key():
    from docker.api.pending import requery_pending

    mgr = _StubRequeryManager()
    resp = requery_pending(numbers=["GB/T 1-2020"], site="", mgr=mgr)

    row = resp["results"][0]
    assert row["status"] == Status.ACTIVE.value
    assert row["status_key"] == "active"
    assert mgr.resolved == [(["GB/T 1-2020"], "confirmed")]


# ── ⑤ 企业微信 IP 状态契约 ────────────────────────────────────────────────


class _StubCfg:
    def get(self, key: str, default=None):  # type: ignore[no-untyped-def]
        return default


class _StubWechatMgr:
    cfg = _StubCfg()


def test_wechat_ip_status_exposes_known_flag(monkeypatch):
    """`current_ip_known` 取代前端的 `current_ip !== '未知'` 中文比较。"""
    from pilotstd.manager.wechat_ip_service import WechatIPService

    svc = WechatIPService(_StubWechatMgr())
    monkeypatch.setattr(svc, "_get_secret", lambda: "secret")  # type: ignore[method-assign]
    monkeypatch.setattr("pilotstd.wechat_ip.detector.detect_ip", lambda: None)
    monkeypatch.setattr("pilotstd.wechat_ip.browser.validate_cookie", lambda *a, **k: False)
    monkeypatch.setattr("pilotstd.wechat_ip.cookie_mgr.decrypt_cookie", lambda *a, **k: "cookie")

    unknown = svc.get_status()
    assert unknown["current_ip"] == Status.UNKNOWN.value
    assert unknown["current_ip_known"] is False

    monkeypatch.setattr("pilotstd.wechat_ip.detector.detect_ip", lambda: "1.2.3.4")
    known = svc.get_status()
    assert known["current_ip"] == "1.2.3.4"
    assert known["current_ip_known"] is True
