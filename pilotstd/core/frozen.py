# pilotstd/core/frozen.py — PyInstaller/Nuitka 统一打包检测
import sys


def is_frozen() -> bool:
    """返回 True 表示当前运行在打包后的 exe 环境中。
    兼容 PyInstaller (sys.frozen) 和 Nuitka (__compiled__)。
    """
    return getattr(sys, "frozen", False) or "__compiled__" in dir(__builtins__)
