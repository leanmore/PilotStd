"""采标判定收紧（D2-3）：词边界匹配，避免 MODBUS/“采用…方法”误判永久跳过下载。"""

import pytest

from pilotstd.query.search_strategy import is_adopted


@pytest.mark.parametrize(
    "name",
    [
        "采用通用试验方法",  # 旧实现命中“采用”→ 误判
        "MODBUS 通信协议",  # 旧实现命中“MOD”→ 误判
        "GB/T 1234-2020 基础规范",
        "采用本标准规定的试验方法",
        "ISO9000 族标准",  # 数字粘连不算独立词
    ],
)
def test_non_adopted_names(name):
    assert is_adopted(name) is False


@pytest.mark.parametrize(
    "name",
    [
        "采标标准",
        "采用国际标准的说明",
        "ISO 9001 质量管理体系",
        "IEC 61000 电磁兼容",
        "MOD 修改采用",
        "EQV 等效采用",
    ],
)
def test_adopted_names(name):
    assert is_adopted(name) is True


def test_english_name_word_boundary():
    assert is_adopted("", "Adoption of ISO 50001") is True
    assert is_adopted("", "MODBUS gateway") is False
