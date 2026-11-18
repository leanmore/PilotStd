"""时效性变更详情必须带旧状态（避免只显示“— 现行”）。"""

from pilotstd.core import _validity_pipeline as vp


def test_record_change_includes_previous_status(monkeypatch):
    monkeypatch.setattr(vp, "_std_name", lambda db, std: "测试标准")
    detail = vp._record_change(None, "GB 1-2020", "现行", {}, old_status="未知")
    assert detail["reason"] == "未知 → 现行"


def test_record_change_missing_old_status_uses_unknown(monkeypatch):
    monkeypatch.setattr(vp, "_std_name", lambda db, std: "测试标准")
    detail = vp._record_change(None, "GB 2-2020", "现行", {}, old_status=None)
    assert detail["reason"] == "未知 → 现行"
