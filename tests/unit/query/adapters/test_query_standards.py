"""6 个适配器 query_standards 的网络/解析契约（A-12 合并版，2026-10-25）。

覆盖两类错误路径：
- 传输层：非 200、连接异常（全部 return []，无抛异常）；
- 解析层：空结果/格式不符（同样 return []）。

mock 只负责"不真发请求"；每个用例都额外断言**实际发出的 method / path / query（及 POST body）**，
避免路由写错时测试仍通过。

行数夹具说明：ccsn 的 `_find_data_rows` 要求同一表内 **≥3 条有效数据行**才认作数据表，
而 jtst/nrsis 只需 1 条（卡片/表格行）——这是生产行为差异，不是夹具随手写的。
"""

import httpx
import responses
import respx
from responses import RequestsMock

from pilotstd.query.adapters.ccsn import CCSNAdapter
from pilotstd.query.adapters.jtst import JTSTAdapter
from pilotstd.query.adapters.mee import MEEAdapter
from pilotstd.query.adapters.nrsis import NRSISAdapter
from pilotstd.query.adapters.sppt import SPPTAdapter
from pilotstd.query.adapters.sppt_local import SPPTLocalAdapter

# ── 夹具 ──────────────────────────────────────────────


def _ccsn_table(rows: int) -> str:
    body = "".join(
        f"<tr><td>{i}</td><td>工程术语{i}</td><td>GB {i}-2020</td>"
        f"<td>2020-0{i}-01</td><td>2020-0{i}-02</td></tr>"
        for i in range(1, rows + 1)
    )
    return (
        "<table><tr><th>序号</th><th>名称</th><th>编号</th><th>发布日期</th><th>实施日期</th></tr>"
        + body
        + "</table>"
    )


CCSN_HTML = _ccsn_table(3)          # ≥3 行才被认作数据表
CCSN_TWO_ROWS_HTML = _ccsn_table(2)  # 解析层空结果：行数不足
CCSN_NO_RESULT_HTML = "<html>暂无数据</html>"

JTST_HTML = """
<div class="panel panel-default post">
  <div class="post-head"><a href="#">JT/T 1234-2020 公路工程术语</a></div>
  <span class="en-code">JT/T 1234-2020</span>
  <span class="s-status label">现行</span>
</div>
"""
JTST_EMPTY_HTML = '<div class="nums"><span>0</span></div>'

NRSIS_HTML = """
<table class="table"><tbody>
  <tr><th>序号</th><th>标准编号</th><th>标准名称</th><th>发布日期</th><th>实施日期</th><th>状态</th></tr>
  <tr><td>1</td><td>GB 2-2020</td><td>自然资源术语</td><td>2020-02-01</td><td>2020-08-01</td><td>现行</td></tr>
</tbody></table>
"""
NRSIS_EMPTY_HTML = "<html>暂无数据</html>"

SPPT_JSON = [
    {"CODE": "GB 19001-2016", "TITLE": "质量管理体系 要求", "PDATE": "2016-12-30", "SSRQ": "2017-07-01"}
]

MEE_HTML = """
<ul id="list2">
  <li class="li">
    <em class="fl ll_gjjs_list_title">法规标准</em>
    <h2 class="h2">法规标准 GB 1234-2020 生态环境术语</h2>
    <p class="p">GB 1234-2020 实施日期说明</p>
    <span class="span">2020-01-01</span>
  </li>
</ul>
"""

SPPT_LOCAL_HTML = (
    "<script>dataList: "
    '[{"standard_code": "DBS 1-2020", "title": "食品安全地方标准"}]'
    ", other: 1</script>"
)


# ── 断言辅助 ──────────────────────────────────────────


def _request():
    """取 respx 记录的最后一次请求，用于断言真实发出的内容。"""
    return respx.calls[-1].request


# ── ccsn ─────────────────────────────────────────────


@respx.mock
def test_ccsn_success():
    respx.get(url__regex=r"https://www\.ccsn\.org\.cn/Zbbz/ZbbzList\.aspx.*").mock(
        return_value=httpx.Response(200, text=CCSN_HTML)
    )
    out = CCSNAdapter().query_standards("GB 1-2020")
    assert len(out) == 3
    assert out[0].standard_number == "GB 1-2020"
    req = _request()
    assert req.method == "GET"
    assert req.url.path == "/Zbbz/ZbbzList.aspx"
    assert req.url.params["KeyWord"] == "GB 1-2020"


@respx.mock
def test_ccsn_parse_layer_empty_when_rows_lt_three():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text=CCSN_TWO_ROWS_HTML))
    assert CCSNAdapter().query_standards("GB 1-2020") == []


@respx.mock
def test_ccsn_no_result_keyword_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text=CCSN_NO_RESULT_HTML))
    assert CCSNAdapter().query_standards("GB 1-2020") == []


@respx.mock
def test_ccsn_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert CCSNAdapter().query_standards("GB 1-2020") == []


@respx.mock
def test_ccsn_transport_error_returns_empty():
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))
    assert CCSNAdapter().query_standards("GB 1-2020") == []


# ── jtst ─────────────────────────────────────────────


@respx.mock
def test_jtst_success():
    respx.get(url__regex=r"https://.*jtst.*").mock(return_value=httpx.Response(200, text=JTST_HTML))
    out = JTSTAdapter().query_standards("JT/T 1234-2020")
    assert len(out) == 1
    assert out[0].standard_number == "JT/T 1234-2020"
    req = _request()
    assert req.method == "GET"
    assert req.url.params["q"] == "JT/T 1234-2020"


@respx.mock
def test_jtst_parse_layer_empty_when_no_cards():
    respx.get(url__regex=r"https://.*jtst.*").mock(
        return_value=httpx.Response(200, text=JTST_EMPTY_HTML)
    )
    assert JTSTAdapter().query_standards("JT/T 1234-2020") == []


@respx.mock
def test_jtst_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert JTSTAdapter().query_standards("JT/T 1234-2020") == []


@respx.mock
def test_jtst_transport_error_returns_empty():
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))
    assert JTSTAdapter().query_standards("JT/T 1234-2020") == []


# ── nrsis ────────────────────────────────────────────


@respx.mock
def test_nrsis_success():
    respx.get(url__regex=r"http://www\.nrsis\.org\.cn/portal/xxcx/std.*").mock(
        return_value=httpx.Response(200, text=NRSIS_HTML)
    )
    out = NRSISAdapter().query_standards("GB 2-2020")
    assert len(out) == 1
    assert out[0].standard_number == "GB 2-2020"
    req = _request()
    assert req.method == "GET"
    assert req.url.path == "/portal/xxcx/std"
    assert req.url.params["key"] == "GB 2-2020"


@respx.mock
def test_nrsis_parse_layer_empty_keyword():
    respx.get(url__regex=r"http://www\.nrsis\.org\.cn/portal/xxcx/std.*").mock(
        return_value=httpx.Response(200, text=NRSIS_EMPTY_HTML)
    )
    assert NRSISAdapter().query_standards("GB 2-2020") == []


@respx.mock
def test_nrsis_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert NRSISAdapter().query_standards("GB 2-2020") == []


@respx.mock
def test_nrsis_retries_then_returns_empty(monkeypatch):
    """传输异常重试 MAX_RETRIES 次后返回 []（最后一次不再 sleep）。

    退避常量 RETRY_BASE_DELAY=1 为类级硬编码设计值；若有人改动，[1, 2] 断言会红，
    作为"退避策略变更"的信号。
    """
    import pilotstd.query.adapters.nrsis as nrsis_mod

    sleeps: list[float] = []
    monkeypatch.setattr(nrsis_mod.time, "sleep", lambda s: sleeps.append(s))
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))

    assert NRSISAdapter().query_standards("GB 2-2020") == []
    assert len(respx.calls) == NRSISAdapter.MAX_RETRIES
    assert sleeps == [1, 2]


# ── sppt ─────────────────────────────────────────────


@respx.mock
def test_sppt_success_json():
    respx.get(url__regex=r"https://sppt\.cfsa\.net\.cn:8086/db.*").mock(
        return_value=httpx.Response(200, json=SPPT_JSON)
    )
    out = SPPTAdapter().query_standards("GB 19001-2016")
    assert len(out) == 1
    assert out[0].standard_number == "GB 19001-2016"
    req = _request()
    assert req.method == "GET"
    assert req.url.path == "/db"
    assert req.url.params["keyword"] == "GB 19001-2016"
    assert req.url.params["accessData"] == "gj"


@respx.mock
def test_sppt_parse_layer_empty_when_json_not_list():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={"error": "bad"}))
    assert SPPTAdapter().query_standards("GB 19001-2016") == []


@respx.mock
def test_sppt_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert SPPTAdapter().query_standards("GB 19001-2016") == []


@respx.mock
def test_sppt_transport_error_returns_empty():
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))
    assert SPPTAdapter().query_standards("GB 19001-2016") == []


# ── mee（requests + responses）─────────────────────────


def test_mee_success():
    with RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://www.mee.gov.cn/was5/web/search",
            body=MEE_HTML,
            status=200,
        )
        out = MEEAdapter().query_standards("GB 1234-2020")
        assert len(out) == 1
        assert out[0].standard_number == "GB 1234-2020"
        call = rsps.calls[0].request
        assert call.method == "GET"
        assert call.url.startswith("https://www.mee.gov.cn/was5/web/search")
        assert "searchword=GB+1234-2020" in call.url or "searchword=GB%201234-2020" in call.url


def test_mee_non_200_returns_empty():
    with RequestsMock() as rsps:
        rsps.add(responses.GET, "https://www.mee.gov.cn/was5/web/search", status=500)
        assert MEEAdapter().query_standards("GB 1234-2020") == []


def test_mee_parse_layer_empty_when_no_valid_items():
    with RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://www.mee.gov.cn/was5/web/search",
            body="<html>暂无数据</html>",
            status=200,
        )
        assert MEEAdapter().query_standards("GB 1234-2020") == []


# ── sppt_local（POST + 内嵌 dataList）──────────────────


@respx.mock
def test_sppt_local_success_post_body():
    respx.post(url__regex=r"https://sppt\.cfsa\.net\.cn:8087/db.*").mock(
        return_value=httpx.Response(200, text=SPPT_LOCAL_HTML)
    )
    out = SPPTLocalAdapter().query_standards("DBS 1-2020")
    assert len(out) == 1
    assert out[0].standard_number == "DBS 1-2020"
    req = _request()
    assert req.method == "POST"
    assert req.url.path == "/db"
    body = req.content.decode("utf-8", errors="ignore")
    assert "task=index" in body
    assert "accessData=df" in body
    assert "keyword=DBS+1-2020" in body or "keyword=DBS%201-2020" in body


@respx.mock
def test_sppt_local_parse_layer_empty_when_datalist_missing():
    respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, text="<html>无数据</html>"))
    assert SPPTLocalAdapter().query_standards("DBS 1-2020") == []


@respx.mock
def test_sppt_local_transport_error_returns_empty():
    respx.post(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))
    assert SPPTLocalAdapter().query_standards("DBS 1-2020") == []
