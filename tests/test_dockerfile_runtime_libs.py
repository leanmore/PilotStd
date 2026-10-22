"""Docker 镜像需包含 RapidOCR/OpenCV 在 slim 下的 X11/GL 运行库。"""

from pathlib import Path


def test_dockerfile_installs_opencv_runtime_libraries() -> None:
    text = Path("docker/Dockerfile").read_text(encoding="utf-8")
    for pkg in ("libxcb1", "libgl1", "libglib2.0-0", "libsm6", "libxext6"):
        assert pkg in text, pkg
