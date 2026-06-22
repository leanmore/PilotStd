# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
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

# 数据文件
root = Path(".")
# 定位 PyQt6 翻译文件目录（修复右键菜单英文问题）
qt_trans_dir = str(Path(PyQt6.__file__).parent / "Qt6" / "translations")
datas = [
    ("icon.ico", "."),
    ("assets", "assets"),
    ("data", "data"),
    ("pilotstd/i18n", "pilotstd/i18n"),
    (qt_trans_dir, "qt_translations"),
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx_exclude=["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll",
                 "onnxruntime.dll", "onnxruntime_providers_shared.dll"],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
