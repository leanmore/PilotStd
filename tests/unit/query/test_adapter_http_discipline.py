"""方向 C 第三轮深扫的回归用例（2026-11-25）。

1. `nrsis`：HTTP 调用必须带 `timeout`（原缺失 → 站点不响应则无限挂起）
2. `ahbz`：`_search` 创建的 Session 必须关闭（原每次查询泄漏连接池）
3. `BaseAdapter._try_exact_search`：不得使用可变默认参数
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest


class TestNrsisTimeout:
    def test_http_call_has_timeout(self) -> None:
        from pilotstd.query.adapters.nrsis import NRSISAdapter

        client = MagicMock()
        adapter = NRSISAdapter(client=client)
        resp = MagicMock()
        resp.status_code = 200
        # 命中「空结果」关键词即可早退，测试只关心调用参数
        resp.content = "暂无数据".encode("utf-8")
        client.get.return_value = resp

        adapter.query_standards("DZ/T 1-2020")

        assert client.get.called
        _, kwargs = client.get.call_args
        assert "timeout" in kwargs, "nrsis HTTP 调用必须显式带 timeout（防无限挂起）"
        assert kwargs["timeout"] > 0


class TestAhbzSessionClosed:
    def test_search_closes_owned_session(self) -> None:
        from pilotstd.query.adapters import ahbz as ahbz_mod

        events: list[str] = []

        class FakeSession:
            headers: dict = {}

            def __enter__(self):
                events.append("enter")
                return self

            def __exit__(self, *args):
                events.append("exit")
                return False

        adapter = ahbz_mod.AhbzAdapter()
        with patch.object(ahbz_mod.requests, "Session", return_value=FakeSession()), patch.object(
            adapter, "_search_single", return_value=None
        ):
            adapter._search("GB/T 1-2020")

        assert events == ["enter", "exit"], f"Session 必须用 with 关闭，实际事件={events}"


class TestNoMutableDefault:
    def test_accepted_statuses_default_is_none(self) -> None:
        from pilotstd.query.adapters.base import BaseAdapter

        param = inspect.signature(BaseAdapter._try_exact_search).parameters["accepted_statuses"]
        assert param.default is None, "不得用可变 set 作默认参数（调用间共享）"

    def test_default_still_accepts_exact(self) -> None:
        """不传 accepted_statuses 时行为不变：仅接受 exact。"""
        from pilotstd.query.adapters.base import BaseAdapter

        class Dummy(BaseAdapter):
            @property
            def site_name(self) -> str:
                return "dummy"

            @property
            def site_label(self) -> str:
                return "dummy"

            def _search(self, search_term):  # noqa: ANN001
                from pilotstd.query.models import QueryResult

                return QueryResult(standard_number="GB/T 1-2020", standard_name="测试", source_site="dummy")

            def _parse_result(self, rec, search_term=""):  # noqa: ANN001, ANN201
                raise NotImplementedError

        dummy = Dummy()
        exact = dummy._try_exact_search("GB/T 1-2020", "GB/T", 1, 2020, None)
        assert exact is not None
        assert exact.match_status == "exact"
        # 状态不匹配时返回 None（默认口径确实只接受 exact）
        assert dummy._try_exact_search("GB/T 1-2020", "GB/T", 2, 2010, None) is None

    def test_call_does_not_mutate_shared_state(self) -> None:
        from pilotstd.query.adapters.base import BaseAdapter

        src = inspect.signature(BaseAdapter._try_exact_search).parameters["accepted_statuses"]
        assert src.default is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
