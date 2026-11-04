"""下载落盘防线（D2-1 / D2-2）：假 PDF 拒绝、原子落盘。"""

from types import SimpleNamespace

import pytest

from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import DownloadStatus, DownloadTask


class _Adapter:
    site_name = "fake_site"

    def __init__(self, content):
        self._content = content

    def can_handle(self, task):
        return True

    def download(self, task):
        return self._content


def _engine(tmp_path, content):
    return DownloadEngine(
        [_Adapter(content)],
        session_manager=SimpleNamespace(delay=lambda: None),
        save_root=str(tmp_path),
    )


def _task():
    return DownloadTask(
        standard_number="GB/T 1234-2020",
        source_site="fake_site",
        query_result=SimpleNamespace(standard_name="测试标准", is_adopted=False),
    )


def test_html_error_page_is_rejected(tmp_path):
    """站点返回 HTML 错误页时不得当 PDF 入库（旧实现只 warning 并标 SUCCESS）。"""
    result = _engine(tmp_path, b"<html><body>404 Not Found</body></html>").download_single(_task())

    assert result.status == DownloadStatus.FAILED
    assert result.saved_path == ""
    assert "非 PDF" in result.error_message
    assert list(tmp_path.glob("*.pdf")) == []
    assert list(tmp_path.glob("*.part")) == []


def test_valid_pdf_is_saved_atomically(tmp_path):
    result = _engine(tmp_path, b"%PDF-1.7\nfake-body").download_single(_task())

    assert result.status == DownloadStatus.SUCCESS
    assert result.saved_path.endswith(".pdf")
    assert open(result.saved_path, "rb").read().startswith(b"%PDF-")
    assert list(tmp_path.glob("*.part")) == []


def test_partial_write_cleans_tmp(tmp_path, monkeypatch):
    """写盘中途失败：不得留下 .part 或半截目标文件。"""
    engine = _engine(tmp_path, b"%PDF-1.7\nbody")
    real_open = open

    class _FailingFile:
        def __init__(self, path):
            self._path = path

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def write(self, _data):
            raise OSError("disk full")

        def flush(self):
            raise OSError("disk full")

        def fileno(self):
            return -1

    def fake_open(path, mode="r", *args, **kwargs):
        if "wb" in mode and str(path).endswith(".part"):
            return _FailingFile(path)
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    result = engine.download_single(_task())

    assert result.status == DownloadStatus.FAILED
    assert list(tmp_path.glob("*.part")) == []
    assert list(tmp_path.glob("*.pdf")) == []


@pytest.mark.parametrize(
    ("content", "ok"),
    [
        (b"%PDF-1.4 minimal", True),
        (b"<html>rate limited</html>", False),
        (b"", False),
    ],
)
def test_content_gate(tmp_path, content, ok):
    result = _engine(tmp_path, content).download_single(_task())
    assert (result.status == DownloadStatus.SUCCESS) is ok
