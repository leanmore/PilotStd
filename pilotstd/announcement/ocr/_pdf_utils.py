# 模块：项目///__工具脚本
# 便携文档工具函数—从_脚本拆分，供内部和测试使用

import logging
import sys

logger = logging.getLogger(__name__)


def _split_pdf_pages(pdf_bytes: bytes) -> list[bytes]:
    """pypdf 拆 PDF 为单页 bytes 列表。失败降级为 [pdf_bytes]。"""
    try:
        from io import BytesIO

        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(BytesIO(pdf_bytes))
        total = len(reader.pages)
        if total <= 1:
            return [pdf_bytes]
        pages = []
        for i in range(total):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            buf = BytesIO()
            writer.write(buf)
            pages.append(buf.getvalue())
        return pages
    except Exception:
        logger.warning("pypdf 拆页失败，降级为整文件处理")
        return [pdf_bytes]


def _pdf_page_count(pdf_bytes: bytes) -> int:
    """返回 PDF 总页数。失败返回 1。"""
    try:
        from io import BytesIO

        from pypdf import PdfReader

        return len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception:
        # 已知可忽略：页数统计失败默认 1 页
        return 1


def _set_thread_priority_idle() -> None:
    """Windows: 当前线程设为 THREAD_PRIORITY_IDLE(-15)。非 Windows 静默跳过。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetCurrentThread()
        ctypes.windll.kernel32.SetThreadPriority(handle, -15)
    except Exception:
        pass
