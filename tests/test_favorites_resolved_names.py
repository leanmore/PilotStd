"""B3-b：收藏接口名称统一的契约测试（`docker/api/favorites.py::_apply_resolved_names`）。

锁三条保证（对应裁定 (A) 与 D8）：
1) **键名只能是 `standard_name`**：覆盖后必须 `pop` 掉 `std_name`（既不新增冗余键、也不留旧键）；
2) **未命中必须回退表内原值**：批量映射查不到的号，沿用原 `std_name` ⇒ **绝不出现 None/空串**
   （前端名称列不空白的最后防线）；
3) **命中则取回退链结果**：与 DB 后其它消费方（下载通知等）同名同值，消除 P3（同名不同值）。
另锁一条性能约束：**空列表零查询**（不得为无数据的请求建连接/发 SQL）。
"""

from unittest.mock import patch

from docker.api.favorites import _apply_resolved_names


class _Db:
    """最小 DB 替身（本用例只为满足签名；查询由 `fetch_resolved_names` 的打桩接管）。"""


def test_resolved_name_wins_and_key_is_renamed():
    """命中映射 ⇒ 值＝回退链结果，键名改为 standard_name，旧键 std_name 被移除。"""
    records = [{"standard_number": "GB/T 1-2020", "std_name": "解析名（阶段①）"}]
    with patch("docker.api.favorites.fetch_resolved_names", return_value={"GB/T 1-2020": "决策名（阶段③）"}) as mocked:
        _apply_resolved_names(_Db(), records)

    assert records[0]["standard_name"] == "决策名（阶段③）"
    assert "std_name" not in records[0], "D8：不得保留旧键 std_name"
    mocked.assert_called_once()  # 一次批量，严禁逐条
    # 批量入参应当是"当前批次里出现过的标准号"
    assert mocked.call_args.args[1] == ["GB/T 1-2020"]


def test_unmatched_falls_back_to_stored_value():
    """★ 最后防线：批量映射未返回该号 ⇒ 回退表内原值，绝不 None/空串。"""
    records = [{"standard_number": "GB/T 2-2020", "std_name": "表内旧名"}]
    with patch("docker.api.favorites.fetch_resolved_names", return_value={}):
        _apply_resolved_names(_Db(), records)

    assert records[0]["standard_name"] == "表内旧名"
    assert records[0]["standard_name"] is not None
    assert "std_name" not in records[0]


def test_empty_records_skips_query():
    """空列表 ⇒ 不建连接、不发查询（列表为空时不得产生无谓 IO）。"""
    with patch("docker.api.favorites.fetch_resolved_names") as mocked:
        _apply_resolved_names(_Db(), [])
    assert not mocked.called


def test_multiple_records_use_single_batch_call():
    """多行只调一次批量入口（N+1 防线）。"""
    records = [
        {"standard_number": "A", "std_name": "甲"},
        {"standard_number": "B", "std_name": "乙"},
        {"standard_number": "C", "std_name": "丙"},
    ]
    with patch(
        "docker.api.favorites.fetch_resolved_names",
        return_value={"A": "决策甲", "C": "决策丙"},
    ) as mocked:
        _apply_resolved_names(_Db(), records)

    assert mocked.call_count == 1
    assert [r["standard_name"] for r in records] == ["决策甲", "乙", "决策丙"]
    assert all("std_name" not in r for r in records)


def test_blank_standard_number_keeps_original_value():
    """标准号缺失/为空的行：映射必然命中不到 ⇒ 仍须保留原值（不得清空）。"""
    records = [{"standard_number": "", "std_name": "无名旧值"}]
    with patch("docker.api.favorites.fetch_resolved_names", return_value={}):
        _apply_resolved_names(_Db(), records)
    assert records[0]["standard_name"] == "无名旧值"
