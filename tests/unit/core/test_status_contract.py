"""API 状态契约测试（#32-C / R14-4c，2026-10-01）。

C 阶段把状态契约显式化：后端在原有 `status`（数据值，中文，**向后兼容**）之外
提供 `status_key`（稳定英文键），并让过滤参数同时接受英文键与历史中文值。
本文件锁定该契约：

① `status_key()` / `resolve_status_filter()` 纯函数语义（含别名归一与兜底）；
② `/api/standards/status`：item 带 `status_key`；`status=active` 与 `status=现行` 等价；
   `status=未生效` 与 `status=upcoming` 结果集一致（历史兼容别名）；
   **无法识别的 `status` 值显式 400**（不再静默忽略过滤）；
③ `/api/query/results`：结果带 `status_key`，**磁盘文件不被改写**；
④ `/api/pending/requery`：结果带 `status_key`；
⑤ `WechatIPService.get_status()`：带 `current_ip_known` 布尔键（前端不再比较 '未知'）。
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

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
        # 历史兼容别名：`未生效` 与 `即将实施` 是同一语义的两种写法（P1-5 §3.3 公告口径 10/10）
        ("未生效", "upcoming"),
        (Status.UPCOMING.value, "upcoming"),
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
        # Sentinel: 确保枚举 value 与现网中文契约一致（旧前端/老书签发来的就是这个中文值）
        ("现行", Status.ACTIVE.value),
        # 历史兼容别名（C3 存量清洗后自然收敛）：与「即将实施」/`upcoming` 解析为**同一取值**
        ("未生效", Status.UPCOMING.value),
        (Status.UPCOMING.value, Status.UPCOMING.value),
        ("", None),
        (None, None),
        ("nonsense", None),  # 无法识别 → 端点显式 400（见下方端点契约测试）
    ],
)
def test_resolve_status_filter(raw, expected):
    assert resolve_status_filter(raw) == expected


def test_not_effective_alias_resolves_identically_to_upcoming():
    """`未生效`/`即将实施`/`upcoming` 三种写法必须解析为同一过滤取值（结果集完全一致）。"""
    assert (
        resolve_status_filter("未生效")
        == resolve_status_filter(Status.UPCOMING.value)
        == resolve_status_filter("upcoming")
        == Status.UPCOMING.value
    )


def test_api_valid_statuses_derives_from_single_source():
    """**单一事实源**：`API_VALID_STATUSES` 由 `API_FILTER_ACCEPTED_VALUES` 派生（P1-5 §5.3）。

    `API_VALID_STATUSES` 过去只列 3 个展示桶，而端点实际接受 9 个中文值 + 8 个英文键 +
    历史兼容别名 —— 契约常量与实际行为不一致（docstring 也只列 3 个键）。本测试锁定：
    ① 常量与解析函数接受集合**逐项相等**；② 每个 `Status` 枚举值都在其中。
    """
    from pilotstd.core import status as status_dict

    accepted = status_dict.API_FILTER_ACCEPTED_VALUES
    assert status_dict.API_VALID_STATUSES == tuple(sorted(accepted)), "必须由单一事实源派生"
    assert len(set(status_dict.API_VALID_STATUSES)) == len(status_dict.API_VALID_STATUSES), "不得有重复项"
    # 枚举 × 接受性：9 个中文数据值全部被接受
    for member in Status:
        assert member.value in accepted
    # 英文契约键（前端筛选实际发送的值）全部被接受
    for english_key in status_dict.STATUS_EN_KEYS.values():
        assert english_key in accepted
    # 历史兼容别名同样被接受
    assert "未生效" in accepted
    # 反向：无法识别的取值一律不在接受集合内
    assert "nonsense" not in accepted
    assert "Active" not in accepted  # 枚举名不是契约值（大小写敏感）


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
        ("active ", Status.ACTIVE.value),
        ("withdrawn", Status.WITHDRAWN_NORMALIZED.value),
        ("upcoming", Status.UPCOMING.value),
        ("unknown", Status.UNKNOWN.value),
        (Status.UPCOMING.value, Status.UPCOMING.value),
        ("未生效", Status.UPCOMING.value),  # 历史兼容别名
    ],
)
def test_standards_status_filter_accepts_key_and_legacy_value(raw, expected):
    """过滤入参：英文键、历史中文值与历史兼容别名都接受，并按统一口径解析。"""
    from docker.api.standards import get_standards_status

    mgr = _StubManager()
    get_standards_status(status=raw, standard_no=None, name=None, page=1, page_size=20, mgr=mgr)

    assert mgr.standard_service.seen_filters[0] == {"status": expected}


def test_endpoint_accepts_every_value_of_the_single_source_contract():
    """**契约测试（枚举 × 端点接受性）**：`API_VALID_STATUSES` 每一项端点都必须接受。

    端点接受集合若比契约常量窄/宽，这里立刻红（历史问题：常量 3 值、实收 9 值）。
    """
    from docker.api.standards import get_standards_status
    from pilotstd.core import status as status_dict

    for raw in status_dict.API_VALID_STATUSES:
        mgr = _StubManager()
        get_standards_status(status=raw, standard_no=None, name=None, page=1, page_size=20, mgr=mgr)
        resolved = status_dict.resolve_status_filter(raw)
        assert resolved is not None, f"契约内取值 {raw!r} 必须可解析"
        assert mgr.standard_service.seen_filters[0] == {"status": resolved}


@pytest.mark.parametrize("raw", ["nonsense", "Active", "即将实施-", "现行,废止", "未 生效"])
def test_endpoint_rejects_unrecognized_status_with_400(raw):
    """**P0 防复发核心**：无法识别的 `status` 值必须显式 400，不得静默忽略过滤。"""
    from docker.api.standards import get_standards_status

    mgr = _StubManager()
    with pytest.raises(HTTPException) as excinfo:
        get_standards_status(status=raw, standard_no=None, name=None, page=1, page_size=20, mgr=mgr)

    assert excinfo.value.status_code == 400
    assert raw in str(excinfo.value.detail), "400 文案应回显非法取值，便于定位"
    assert mgr.standard_service.seen_filters == [], "非法值不得进入查询"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_endpoint_empty_status_means_no_filter(raw):
    """空值/纯空白 = 「全部」而不是非法值（前端未选筛选时不会传，但老客户端可能传空串）。"""
    from docker.api.standards import get_standards_status

    mgr = _StubManager()
    get_standards_status(status=raw, standard_no=None, name=None, page=1, page_size=20, mgr=mgr)
    assert mgr.standard_service.seen_filters == [None]


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
    from tests._auth_helpers import admin_request

    mgr = _StubRequeryManager()
    resp = requery_pending(admin_request(), numbers=["GB/T 1-2020"], site="", mgr=mgr)

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
