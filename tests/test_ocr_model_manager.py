"""本地 OCR 模型包安装：不依赖网络，验证 wheel 解包与目标目录。"""

import io
import zipfile

from pilotstd.announcement.ocr import _model_manager


def test_install_wheel_bytes_extracts_models(tmp_path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in _model_manager.MODEL_FILES:
            zf.writestr(f"rapidocr_onnxruntime/models/{name}", b"onnx")
    target = _model_manager.install_wheel_bytes(buf.getvalue(), model_dir=tmp_path)
    assert target == tmp_path / "rapidocr" / _model_manager.MODEL_VERSION
    for name in _model_manager.MODEL_FILES:
        assert (target / name).read_bytes() == b"onnx"
    assert _model_manager.is_installed(tmp_path) is True
