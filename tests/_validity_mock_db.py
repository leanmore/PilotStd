"""按 SQL 分派返回值的 mock DB，用于 ValidityChecker 多表查询（L1/L2/L3）。"""

from unittest.mock import MagicMock


class SqlDispatchDB(MagicMock):
    """`fetchone(sql, params)` 按 SQL 关键字返回不同结果。

    新 L1 会先查 `announcement_match`、再查 `announcement_record`，
    旧的 `side_effect = [值, 值]` 顺序断言不再适用。
    """

    def __init__(self, match_row=None, record_row=None, validity_row=None, pragma_rows=None):
        super().__init__()
        self._rows = {
            "announcement_match": match_row,
            "announcement_record": record_row,
            "standard_validity": validity_row,
        }
        self.fetchall.return_value = pragma_rows if pragma_rows is not None else []
        self.fetchone.side_effect = self._dispatch

    def _dispatch(self, sql, params=None):
        text = str(sql)
        for table, row in self._rows.items():
            if table in text:
                return row
        return None
