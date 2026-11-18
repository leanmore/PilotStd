"""superseded_by 年份倒退（旧标准误写为新标准）必须忽略。"""
from pilotstd.core.validity_checker import ValidityChecker


class _DB:
    def fetchone(self, sql, params):
        if "superseded_by" in sql:
            return {"superseded_by": "GB 30871-2014"}
        return {"std_name": "化学品生产单位特殊作业安全规范", "implement_date": "2015-06-01"}


def test_backward_superseded_by_ignored():
    svc = object.__new__(ValidityChecker)
    svc._db = _DB()
    assert svc._replacement_info("GB 30871-2022") == {}
