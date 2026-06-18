"""OCR 三云调度集成测试。"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.announcement.ocr import (
    OcrCounters,
    OcrResult,
    ProviderCooling,
    _pdf_page_count,
    _split_pdf_pages,
    create_ocr_provider,
)
from pilotstd.core.config import ConfigManager, get_data_dir


@pytest.fixture
def cfg():
    return ConfigManager(os.path.join(get_data_dir(), "config.json"))


@pytest.fixture
def scheduler(cfg):
    p = create_ocr_provider(
        {
            "baidu_api_key": cfg.get("ocr.baidu_api_key", ""),
            "baidu_secret_key": cfg.get("ocr.baidu_secret_key", ""),
            "tencent_secret_id": cfg.get("ocr.tencent_secret_id", ""),
            "tencent_secret_key": cfg.get("ocr.tencent_secret_key", ""),
            "aliyun_access_key_id": cfg.get("ocr.aliyun_access_key_id", ""),
            "aliyun_access_key_secret": cfg.get("ocr.aliyun_access_key_secret", ""),
        }
    )
    if p is None:
        pytest.skip("无可用 OCR provider")
    return p


def test_counters_monthly_reset():
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    c = OcrCounters(path)
    c.increment("baidu")
    assert c.get("baidu") == 1
    c2 = OcrCounters(path)
    assert c2.get("baidu") == 1
    os.unlink(path)


def test_split_pdf_pages():
    from io import BytesIO

    from PyPDF2 import PdfWriter

    w = PdfWriter()
    for _ in range(3):
        w.add_blank_page(100, 100)
    buf = BytesIO()
    w.write(buf)
    pdf = buf.getvalue()
    assert _pdf_page_count(pdf) == 3
    pages = _split_pdf_pages(pdf)
    assert len(pages) == 3
    # 单页 PDF 不拆
    w2 = PdfWriter()
    w2.add_blank_page(100, 100)
    buf2 = BytesIO()
    w2.write(buf2)
    single = _split_pdf_pages(buf2.getvalue())
    assert len(single) == 1


def test_cooling_qps():
    c = ProviderCooling()
    c.set("baidu", "qps")
    assert not c.is_hot("baidu")
    remaining = c.remaining("baidu")
    assert 200 < remaining <= 300


def test_scheduler_creates(scheduler):
    assert scheduler.name == "scheduler"


def test_ocr_result_ok():
    r = OcrResult(text="hello")
    assert r.ok and r.text == "hello"
    r2 = OcrResult(error="fail", error_code="18", error_type="qps")
    assert not r2.ok and r2.error == "fail"
    assert r2.error_type == "qps"


def test_ocr_result_pdf_pages():
    r = OcrResult(text="ok", pdf_pages=5)
    assert r.pdf_pages == 5


def test_counter_limits():
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    c = OcrCounters(path)
    assert c.can_accept("baidu", 800)
    assert not c.can_accept("baidu", 801)
    # 循环加到上限
    for _ in range(800):
        c.increment("baidu")
    assert not c.can_accept("baidu", 1)
    os.unlink(path)


def test_scheduler_legacy_mode():
    """旧 provider 模式仍工作——用假凭据仅测路由，不走真实 API。"""
    p = create_ocr_provider(
        {
            "provider": "baidu",
            "baidu_api_key": "test_key",
            "baidu_secret_key": "test_secret",
        }
    )
    assert p is not None
    assert p.name == "baidu"
