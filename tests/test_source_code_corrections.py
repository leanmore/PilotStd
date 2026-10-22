"""源站标准号纠错：按权威标准名称反查修正已知录入错误。"""

import json

from pilotstd.announcement.source_corrections import correct_std_code, reload_corrections


def test_video_item_name_maps_to_ga_t_1018() -> None:
    assert (
        correct_std_code(
            "announcement_hb",
            "2014年第4号(总第172号)",
            "视频中物品图像检验技术规范",
            "GA/T 1023-2013",
        )
        == "GA/T 1018-2013"
    )


def test_sparganosis_name_maps_to_ws_438() -> None:
    assert (
        correct_std_code(
            "announcement_hb",
            "2019年第8号(总第236号)",
            "裂头蚴病的诊断",
            "WS 439-2013",
        )
        == "WS 438-2013"
    )


def test_unrelated_name_is_unchanged() -> None:
    assert (
        correct_std_code(
            "announcement_hb",
            "2014年第4号(总第172号)",
            "视频中人像检验技术规范",
            "GA/T 1023-2013",
        )
        == "GA/T 1023-2013"
    )


def test_runtime_maintenance_list_can_add_entry(tmp_path, monkeypatch) -> None:
    path = tmp_path / "corrections.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "source_site": "announcement_hb",
                        "announce_no": "测试公告",
                        "std_name": "测试标准",
                        "wrong_code": "WS 1-2000",
                        "corrected_code": "WS 2-2000",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PILOTSTD_CODE_CORRECTIONS", str(path))
    reload_corrections()
    assert correct_std_code("announcement_hb", "测试公告", "测试标准", "WS 1-2000") == "WS 2-2000"
    reload_corrections()
