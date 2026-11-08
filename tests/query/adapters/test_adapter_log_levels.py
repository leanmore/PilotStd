"""tests/query/adapters/test_adapter_log_levels.py — 适配器失败日志级别契约（U34-B）。

背景：查询适配器过去把「整站请求失败 / 响应解析失败 / 业务码异常」记在 `debug`，
生产日志里看不见，与「查无结果」完全同形。本次把 24 处升为 `warning`，并保留 3 处
「替代标准字段」与 2 处「已有上游告警」为 `debug`（但要在日志里能区分网络/解析）。

本文件锁的是**日志级别契约**，不是解析结果正确性：
- 组 1/2：失败必须出 WARNING，且消息含站点 + 阶段（或状态码/业务码）；
- 组 3：替代标准字段保持 DEBUG，且「网络失败」与「解析失败」用不同文案；
- 组 4：上游已告警的位置不得再打 WARNING（避免同一失败两条告警）。

测试不追求覆盖全部 24 处，每组取代表；改级别若被回退，这里会红。
"""

import logging

import requests

from pilotstd.query.adapters.ccsn import CCSNAdapter
from pilotstd.query.adapters.csres import CsresAdapter
from pilotstd.query.adapters.energy import EnergyAdapter
from pilotstd.query.adapters.gongbiaoku import GongBiaoKuAdapter
from pilotstd.query.adapters.hbba import HbbaAdapter
from pilotstd.query.adapters.iso_gov import IsoGovAdapter
from pilotstd.query.adapters.jtst import JTSTAdapter
from pilotstd.query.adapters.mee import MEEAdapter
from pilotstd.query.adapters.miit import MIITAdapter
from pilotstd.query.adapters.ncha import NCHAAdapter
from pilotstd.query.adapters.njbz365 import Njbz365Adapter
from pilotstd.query.adapters.nrsis import NRSISAdapter
from pilotstd.query.adapters.sppt import SPPTAdapter
from pilotstd.query.adapters.sppt_local import SPPTLocalAdapter
from pilotstd.query.adapters.ttbz import TTBZAdapter

# ── 测试替身 ─────────────────────────────────────────────────────────────


class _Headers(dict):
    """requests.Session.headers 的最小替身（支持 update 与下标赋值）。"""


class _FakeResp:
    """httpx/requests 响应的最小替身。"""

    def __init__(self, status_code: int = 200, text: str = "", payload=None, json_error=None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self._json_error = json_error
        self.headers = {}
        self.encoding = "utf-8"
        self.url = "http://fake.local/"

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakeClient:
    """httpx.Client 替身：get/post 返回固定响应或直接抛异常。"""

    def __init__(self, *, get=None, post=None) -> None:  # noqa: ANN001
        self._get = get
        self._post = post
        self.headers = _Headers()

    def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if isinstance(self._get, BaseException):
            raise self._get
        return self._get

    def post(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        if isinstance(self._post, BaseException):
            raise self._post
        return self._post


class _FakeSession(_FakeClient):
    """requests.Session 替身（构造期会调用 headers.update）。"""


def _records(caplog, level: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def _has(caplog, level: int, needle: str) -> bool:
    return any(needle in msg for msg in _records(caplog, level))


# ── 组 1：整站请求失败 → WARNING ─────────────────────────────────────────


def test_ccsn_request_exception_is_warning(caplog) -> None:
    """ccsn GET 抛异常：必须 WARNING（原为 debug）。"""
    adapter = CCSNAdapter(client=_FakeClient(get=RuntimeError("conn refused")))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "ccsn.org.cn GET 搜索失败")


def test_ccsn_non_200_is_warning(caplog) -> None:
    """ccsn 非 200：必须 WARNING，并带 status（原为无日志）。"""
    adapter = CCSNAdapter(client=_FakeClient(get=_FakeResp(status_code=503)))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "status=503")


def test_gongbiaoku_request_exception_is_warning(caplog) -> None:
    adapter = GongBiaoKuAdapter(client=_FakeClient(get=RuntimeError("boom")))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "gongbiaoku 查询失败")


def test_jtst_non_200_is_warning(caplog) -> None:
    adapter = JTSTAdapter(client=_FakeClient(get=_FakeResp(status_code=500)))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "jtst 查询失败")


def test_mee_request_exception_is_warning(caplog) -> None:
    adapter = MEEAdapter(session=_FakeSession(get=RuntimeError("boom")))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "mee 查询失败")


def test_nrsis_retry_exhausted_is_warning(caplog, monkeypatch) -> None:
    """nrsis 重试耗尽：必须 WARNING，且写明重试次数（原为 debug）。"""
    from pilotstd.query.adapters import nrsis as nrsis_mod

    monkeypatch.setattr(nrsis_mod.time, "sleep", lambda *_a, **_k: None)
    adapter = NRSISAdapter(client=_FakeClient(get=RuntimeError("timeout")))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "nrsis 查询失败（已重试")


def test_sppt_json_failure_is_warning(caplog) -> None:
    """sppt JSON 解析失败：必须 WARNING（原为无日志）。"""
    adapter = SPPTAdapter(client=_FakeClient(get=_FakeResp(json_error=ValueError("bad json"))))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "sppt 响应 JSON 解析失败")


def test_sppt_local_datalist_failure_is_warning(caplog) -> None:
    """sppt_local dataList 全部模式失败：必须 WARNING（原为 debug）。"""
    adapter = SPPTLocalAdapter(client=_FakeClient(post=_FakeResp(text="<html>no data</html>")))
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")
    assert _has(caplog, logging.WARNING, "sppt_local dataList 所有模式均未命中")


# ── 组 2：解析 / 业务码 → WARNING ────────────────────────────────────────


def test_miit_business_code_is_warning(caplog) -> None:
    """miit 业务码≠0：必须 WARNING（同文件 HTTP/JSON 失败已是 error）。"""
    adapter = MIITAdapter(client=_FakeClient(post=_FakeResp(payload={"code": 7})))
    with caplog.at_level(logging.DEBUG):
        adapter._fetch_candidates("GB 50001")
    assert _has(caplog, logging.WARNING, "miit 业务码异常")


def test_ncha_business_code_is_warning(caplog) -> None:
    """ncha 业务码≠200：必须 WARNING（同文件 HTTP/JSON 失败已是 error）。"""
    adapter = NCHAAdapter(client=_FakeClient(post=_FakeResp(payload={"code": 500, "msg": "err"})))
    with caplog.at_level(logging.DEBUG):
        adapter._fetch_candidates("GB 50001")
    assert _has(caplog, logging.WARNING, "ncha 业务码异常")


def test_iso_gov_json_failure_is_warning(caplog, monkeypatch) -> None:
    """iso_gov 响应 JSON 失效：必须 WARNING（原为完全无日志）。"""
    from pilotstd.query.adapters import iso_gov as iso_gov_mod

    monkeypatch.setattr(iso_gov_mod, "safe_get", lambda *_a, **_k: _FakeResp(json_error=ValueError("bad")))
    adapter = IsoGovAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        adapter._search_candidates("ISO 9001")
    assert _has(caplog, logging.WARNING, "iso_gov 响应 JSON 解析失败")


# ── 组 3：替代标准字段 → 保持 DEBUG，但区分网络/解析 ─────────────────────


def test_csres_replaces_keeps_debug_and_distinguishes_network(caplog, monkeypatch) -> None:
    """csres 替代标准：网络失败必须 DEBUG 且文案含「网络请求失败」。"""
    from pilotstd.query.adapters import csres as csres_mod

    def _raise(*_a, **_k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(csres_mod, "safe_get", _raise)
    adapter = CsresAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_detail_replaces("http://x/detail")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "csres 替代标准网络请求失败")
    assert not _has(caplog, logging.WARNING, "csres 替代标准")


def test_csres_replaces_distinguishes_parse_error(caplog, monkeypatch) -> None:
    """csres 替代标准：非网络异常必须 DEBUG 且文案含「解析失败」。"""
    from pilotstd.query.adapters import csres as csres_mod

    class _BadText(_FakeResp):
        @property
        def text(self):  # noqa: ANN201
            raise ValueError("decode failed")

    monkeypatch.setattr(csres_mod, "safe_get", lambda *_a, **_k: _BadText())
    adapter = CsresAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_detail_replaces("http://x/detail")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "csres 替代标准解析失败")
    assert not _has(caplog, logging.WARNING, "csres 替代标准")


def test_njbz365_replaces_wording_covers_network(caplog, monkeypatch) -> None:
    """njbz365 的 try 同时包了 safe_get：网络异常不得再被记成「解析失败」。"""
    from pilotstd.query.adapters import njbz365 as njbz_mod

    def _raise(*_a, **_k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(njbz_mod, "safe_get", _raise)
    adapter = Njbz365Adapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_replaces("1", "GB 50001")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "njbz365 替代标准网络请求失败")
    assert not _has(caplog, logging.DEBUG, "njbz365 替代标准解析失败")


def test_hbba_replaces_keeps_debug(caplog, monkeypatch) -> None:
    """hbba 替代标准：保持 DEBUG（不阻断主查询），且区分网络失败。"""
    from pilotstd.query.adapters import hbba as hbba_mod

    def _raise(*_a, **_k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(hbba_mod, "safe_get", _raise)
    adapter = HbbaAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        out = adapter._fetch_detail_replaces("pk-1")

    assert out == ""
    assert _has(caplog, logging.DEBUG, "hbba 替代标准网络请求失败")
    assert not _has(caplog, logging.WARNING, "hbba 替代标准")


# ── 组 4：上游已告警 → 保持 DEBUG，不重复 WARNING ────────────────────────


def test_ttbz_unexpected_exception_stays_debug(caplog, monkeypatch) -> None:
    """ttbz 意外异常：safe_post 已负责告警，此处只能 DEBUG，不得再 WARNING。"""
    from pilotstd.query.adapters import ttbz as ttbz_mod

    def _raise(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ttbz_mod, "safe_post", _raise)
    adapter = TTBZAdapter(session=_FakeSession())
    with caplog.at_level(logging.DEBUG):
        adapter.query_standards("GB 50001")

    assert _has(caplog, logging.DEBUG, "ttbz 网络请求异常")
    assert not _has(caplog, logging.WARNING, "ttbz 网络请求异常")


def test_energy_first_page_failure_is_warning(caplog) -> None:
    """energy 第 1 页全 fallback 失败：必须 WARNING（原为 debug）。"""
    adapter = EnergyAdapter(client=_FakeClient(get=RuntimeError("down")))
    with caplog.at_level(logging.DEBUG):
        adapter._fetch_candidates("GB 50001")
    assert _has(caplog, logging.WARNING, "energy 查询失败: 第 1 页请求失败")
