"""G-02 回归：批次 found/not_found 必须写入 query_metrics。"""

from __future__ import annotations

from pilotstd.query.engine._batch import record_result_metrics


class _Metrics:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def set(self, key: str, value: int) -> None:
        self.values[key] = value


class _Found:
    def is_found(self) -> bool:
        return True


class _NotFound:
    def is_found(self) -> bool:
        return False


def test_records_found_and_not_found():
    m = _Metrics()
    record_result_metrics(m, [_Found(), _NotFound(), _Found()], 3)
    assert m.values == {"found": 2, "not_found": 1}


def test_total_wins_when_results_short():
    """分桶丢项时按总数算 not_found，避免把丢失项算成“未命中率为 0”。"""
    m = _Metrics()
    record_result_metrics(m, [_Found()], 5)
    assert m.values == {"found": 1, "not_found": 4}


def test_empty_results():
    m = _Metrics()
    record_result_metrics(m, [], 0)
    assert m.values == {"found": 0, "not_found": 0}
