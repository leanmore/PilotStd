"""P3 失败明细读侧测试：服务端解析/脱敏/分页 + 端点限幅。

分两层验证：
1. **管理器层**（`NotificationPolicyHelper` 之外的新方法 `ops.get_failed_items`）——用内存替身证明
   "解析容错 / 逐条脱敏 / 服务端分页 / 归属过滤"；
2. **端点层**——`page_size` 上限（>100 被拒）与路径存在（避免"只有实现没有接线"）。
"""

from __future__ import annotations

import json
from typing import Any

from pilotstd.core.notification._manager_ops import NotificationOps


class _FakeDB:
    """最小 DB 替身：只实现 `fetchall`（PRAGMA）与 `fetchone`（取 failed_items）。"""

    def __init__(self, raw: str | None, cols: list[str] | None = None) -> None:
        self._raw = raw
        self._cols = cols if cols is not None else ["id", "failed_items", "user_id"]

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [{"name": c} for c in self._cols]

    def fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        if self._raw is None:
            return None
        return {"failed_items": self._raw}


class _FakeMgr:
    """`NotificationOps` 只需要宿主的 `_db`（其 `_db` 是读 `manager._db` 的属性）。"""

    def __init__(self, db: _FakeDB) -> None:
        self._db = db


def _ops(raw: str | None, cols: list[str] | None = None) -> NotificationOps:
    return NotificationOps(_FakeMgr(_FakeDB(raw, cols)))


def _items(n: int) -> list[dict[str, str]]:
    return [
        {
            "standard_number": f"GB/T {1000 + i}-2020",
            "standard_name": "" if i % 2 == 0 else f"标准{i}",
            "error_type": "network" if i % 2 == 0 else "not_found",
            "error_message": f"下载失败 https://example.com/f/{i}.pdf?token=SECRETTOKEN{i}#x",
        }
        for i in range(n)
    ]


def test_pagination_is_server_side_and_capped_by_caller() -> None:
    """分页在服务端做：25 条 ⇒ 第 2 页（size=10）返回第 11–20 条，`total` 恒为 25。"""
    raw = json.dumps(_items(25), ensure_ascii=False)
    page1 = _ops(raw).get_failed_items(1, page=1, size=10)
    page3 = _ops(raw).get_failed_items(1, page=3, size=10)
    assert page1["total"] == 25 and len(page1["items"]) == 10
    assert page3["total"] == 25 and len(page3["items"]) == 5
    assert page1["items"][0]["standard_number"] == "GB/T 1000-2020"
    assert page3["items"][0]["standard_number"] == "GB/T 1020-2020"


def test_messages_are_redacted_on_the_way_out() -> None:
    """透出的 `error_message` **不得**含 URL 查询串（签名/会话）与长令牌。"""
    out = _ops(json.dumps(_items(3), ensure_ascii=False)).get_failed_items(1, page=1, size=10)
    joined = " ".join(it["error_message"] for it in out["items"])
    assert "SECRETTOKEN" not in joined and "token=" not in joined
    assert "https://example.com/f/0.pdf" in joined, "URL 主体应保留（可读性）"


def test_empty_name_falls_back_to_dash() -> None:
    """空标准名 ⇒ `-`（4 列口径与消息侧一致）。"""
    out = _ops(json.dumps(_items(2), ensure_ascii=False)).get_failed_items(1, page=1, size=10)
    assert out["items"][0]["standard_name"] == "-"
    assert out["items"][1]["standard_name"] == "标准1"


def test_defensive_json_parsing_never_raises() -> None:
    """坏 JSON / 非列表 / 缺键 / 无该行 ⇒ 安全返回空明细（不抛）。"""
    assert _ops("{半截").get_failed_items(1)["total"] == 0
    assert _ops('[1, 2]').get_failed_items(1)["total"] == 0
    assert _ops(None).get_failed_items(1)["total"] == 0
    out = _ops(json.dumps([{"error_type": "timeout"}], ensure_ascii=False)).get_failed_items(1)
    assert out["items"][0]["standard_number"] == "-"


def test_user_filter_applied_only_when_column_exists() -> None:
    """`user_id` 列存在时才加归属条件（老库/替身无该列不得因此报错）。"""
    raw = json.dumps(_items(1), ensure_ascii=False)
    assert _ops(raw, cols=["id", "failed_items"]).get_failed_items(1, user_id=7)["total"] == 1
    assert _ops(raw, cols=["id", "failed_items", "user_id"]).get_failed_items(1, user_id=7)["total"] == 1


def test_endpoint_is_wired_with_hard_page_size_cap() -> None:
    """端点层限幅：`page_size ∈ [1,100]` 且路由路径正确（禁止全量拉取）。

    为什么用**源码级**断言：FastAPI 的 `Query(..., ge=, le=)` 约束在 Pydantic v2 下存放于
    `metadata` 而非对象属性（首轮用 `getattr(q,'ge')` 踩空 ⇒ None）⇒ 直接钉住声明文本更稳，
    也与本仓既有"源码级契约测试"同款（如 4b 的批次键三处不变量）。
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "docker" / "api" / "notification_logs.py").read_text(
        encoding="utf-8"
    )
    assert '@router.get("/api/notification/logs/{log_id}/failed-items")' in src, "明细端点未接线"
    assert "page_size: int = Query(20, ge=1, le=100)" in src, "明细端点必须有 page_size 限幅（≤100）"
    assert "page: int = Query(1, ge=1)" in src, "明细端点必须有 page 下界约束"
