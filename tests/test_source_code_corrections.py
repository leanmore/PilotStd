"""源站标准号纠错：按权威标准名称反查修正已知录入错误。"""

from pilotstd.announcement.source_corrections import correct_std_code


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
