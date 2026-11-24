"""tests/test_upload_svg_xss.py — SVG 上传的存储型 XSS 防护（NEW-06，2026-11-23）。

背景：`_validate_image` 原对 SVG 只校验「以 <svg 或 <?xml 开头」，
而 `<?xml ...?><svg onload="alert(1)">` 能通过；`/api/backgrounds/{filename}`
又是同源 FileResponse（Content-Type=image/svg+xml），浏览器会按 SVG 文档执行脚本
→ 存储型 XSS。

本测试锁住：可执行构造必须被拒、纯图形 SVG 必须放行。
"""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docker.api.upload import _validate_image  # noqa: E402


def _check(payload: str) -> None:
    _validate_image(payload.encode("utf-8"), ".svg")


@pytest.mark.parametrize(
    "payload",
    [
        # 内嵌 `script`
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        # 事件属性（最常见、也最容易被漏掉的一种）
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>',
        '<svg onerror="alert(1)"></svg>',
        # foreignObject 里塞 HTML
        '<svg><foreignObject><iframe src="javascript:alert(1)"/></foreignObject></svg>',
        # 直接 javascript: 协议
        '<svg><a xlink:href="javascript:alert(1)"><text>x</text></a></svg>',
        # data:text/html
        '<svg><image href="data:text/html;base64,PHNjcmlwdD4="/></svg>',
        # XXE
        '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg>&xxe;</svg>',
        # 带 XML 声明 + 事件的组合（原实现会被 <?`xml` 前缀放过）
        '<?xml version="1.0"?><svg onload="alert(document.cookie)"></svg>',
    ],
)
def test_executable_svg_is_rejected(payload):
    """含脚本/事件/外部引用的 SVG 必须被拒（400）。"""
    with pytest.raises(HTTPException) as exc:
        _check(payload)
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        # 纯图形：渐变 + 矩形
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10" fill="url(#g)"/></svg>',
        # 带 XML 声明的纯图形
        '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg"><circle r="4"/></svg>',
        # 带注释的纯图形
        "<!-- 背景图 --><svg xmlns='http://www.w3.org/2000/svg'><path d='M0 0'/></svg>",
        # 大写标签也应放行（黑名单已 `lower`）
        '<SVG xmlns="http://www.w3.org/2000/svg"><RECT/></SVG>',
    ],
)
def test_pure_graphic_svg_is_accepted(payload):
    """纯图形 SVG（无脚本/事件）必须放行，避免误杀真实背景图。"""
    _check(payload)  # 不抛异常即通过


def test_non_svg_extension_unaffected():
    """非 SVG 扩展名不受本修复影响（PNG 魔数仍正常校验）。"""
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    _validate_image(png, ".png")  # 不抛异常

    with pytest.raises(HTTPException):
        _validate_image(b"not a png", ".png")
