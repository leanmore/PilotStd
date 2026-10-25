"""A-12a：ccsn / jtst / nrsis 的 query_standards 正常与错误路径。

错误路径契约（2026-10-25 核对源码）：传输异常与非 200 均 **return []**，不抛异常。
本文件只加测试，不改生产代码；若未来行为变化，测试应暴露差异。
"""

import httpx
import respx

from pilotstd.query.adapters.ccsn import CCSNAdapter
from pilotstd.query.adapters.jtst import JTSTAdapter
from pilotstd.query.adapters.nrsis import NRSISAdapter

CCSN_HTML = """
<table>
  <tr><th>序号</th><th>名称</th><th>编号</th><th>发布日期</th><th>实施日期</th></tr>
  <tr><td>1</td><td>工程建设术语</td><td>GB 1-2020</td><td>2020-01-01</td><td>2020-07-01</td></tr>
  <tr><td>2</td><td>工程建设术语二</td><td>GB 2-2020</td><td>2020-02-01</td><td>2020-08-01</td></tr>
  <tr><td>3</td><td>工程建设术语三</td><td>GB 3-2020</td><td>2020-03-01</td><td>2020-09-01</td></tr>
</table>
"""

JTST_HTML = """
<div class="panel panel-default post">
  <div class="post-head"><a href="#">JT/T 1234-2020 公路工程术语</a></div>
  <span class="en-code">JT/T 1234-2020</span>
  <span class="s-status label">现行</span>
</div>
"""

NRSIS_HTML = """
<table class="table"><tbody>
  <tr><th>序号</th><th>标准编号</th><th>标准名称</th><th>发布日期</th><th>实施日期</th><th>状态</th></tr>
  <tr><td>1</td><td>GB 2-2020</td><td>自然资源术语</td><td>2020-02-01</td><td>2020-08-01</td><td>现行</td></tr>
</tbody></table>
"""


@respx.mock
def test_ccsn_success():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text=CCSN_HTML))
    out = CCSNAdapter().query_standards("GB 1-2020")
    # _find_data_rows 要求同表至少 3 条有效行，否则视为"非数据表"
    assert len(out) == 3
    assert out[0].standard_number == "GB 1-2020"


@respx.mock
def test_ccsn_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert CCSNAdapter().query_standards("GB 1-2020") == []


@respx.mock
def test_ccsn_transport_error_returns_empty():
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))
    assert CCSNAdapter().query_standards("GB 1-2020") == []


@respx.mock
def test_jtst_success():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text=JTST_HTML))
    out = JTSTAdapter().query_standards("JT/T 1234-2020")
    assert len(out) == 1
    assert out[0].standard_number == "JT/T 1234-2020"


@respx.mock
def test_jtst_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert JTSTAdapter().query_standards("JT/T 1234-2020") == []


@respx.mock
def test_jtst_transport_error_returns_empty():
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))
    assert JTSTAdapter().query_standards("JT/T 1234-2020") == []


@respx.mock
def test_nrsis_success():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text=NRSIS_HTML))
    out = NRSISAdapter().query_standards("GB 2-2020")
    assert len(out) == 1
    assert out[0].standard_number == "GB 2-2020"


@respx.mock
def test_nrsis_non_200_returns_empty():
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(500))
    assert NRSISAdapter().query_standards("GB 2-2020") == []


@respx.mock
def test_nrsis_retries_then_returns_empty(monkeypatch):
    """传输异常重试 MAX_RETRIES 次后返回 []（最后一次不再 sleep）。"""
    import pilotstd.query.adapters.nrsis as nrsis_mod

    sleeps: list[float] = []
    monkeypatch.setattr(nrsis_mod.time, "sleep", lambda s: sleeps.append(s))
    respx.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("boom"))

    assert NRSISAdapter().query_standards("GB 2-2020") == []
    assert len(sleeps) == NRSISAdapter.MAX_RETRIES - 1  # 1s、2s；最后一次直接 return
    assert sleeps == [1, 2]
