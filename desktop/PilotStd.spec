# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 运行时路径注入：确保打包后能正确找到项目根目录的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import PyQt6
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 收集 pilotstd 下所有子模块
hiddenimports = collect_submodules("pilotstd")

# 收集 ddddocr（验证码识别库）及其 ONNX 模型文件
try:
    hiddenimports += collect_submodules("ddddocr")
except Exception:
    pass
try:
    import ddddocr

    ddddocr_root = Path(ddddocr.__file__).parent
    for model_file in ddddocr_root.glob("*.onnx"):
        datas.append((str(model_file), "ddddocr"))
except Exception:
    pass

# 数据文件（spec 在 desktop/ 下，路径加 ../ 回溯到项目根目录）
root = Path("..")
qt_trans_dir = str(Path(PyQt6.__file__).parent / "Qt6" / "translations")
datas = [
    ("icon.ico", "."),
    ("assets/icons", "assets/icons"),
    ("../data", "data"),
    ("../pilotstd/i18n", "pilotstd/i18n"),
    (qt_trans_dir, "qt_translations"),
]

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 服务端 Web 框架
        "uvicorn",
        "uvicorn.*",
        "fastapi",
        "fastapi.*",
        "starlette",
        "starlette.*",
        # 定时任务
        "apscheduler",
        "apscheduler.*",
        # JWT 认证
        "jose",
        "jose.*",
        "passlib",
        "passlib.*",
        # 系统监控（仅 Linux 容器需要）
        "psutil",
        "psutil.*",
        # 防止被 pandas/PIL 隐式拖入的 GUI 工具包
        "tkinter",
        "tkinter.*",
        "tcl",
        "tcl.*",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PilotStd",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Widgets.dll",
        "onnxruntime.dll",
        "onnxruntime_providers_shared.dll",
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
