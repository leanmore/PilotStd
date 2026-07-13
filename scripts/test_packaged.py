#!/usr/bin/env python
"""打包后 L1 启动测试：验证 exe 存在 + 能启动 + --help 正常。"""

import subprocess
import sys
import time
from pathlib import Path

EXE_PATH = Path("dist/PilotStd.exe")


def test_startup() -> int:
    """启动 exe，等 5 秒后确认进程未退出（说明 GUI 正常启动）。"""
    if not EXE_PATH.exists():
        print(f"FAIL: {EXE_PATH} 不存在")
        return 1
    proc = subprocess.Popen(
        [str(EXE_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(5)
    if proc.poll() is not None:
        print(f"FAIL: 进程过早退出，返回码 {proc.returncode}")
        return 1
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    print("PASS: 启动测试通过")
    return 0


def test_cli_help() -> int:
    """验证 --help 输出正常。"""
    result = subprocess.run(
        [str(EXE_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        print(f"FAIL: --help 返回码 {result.returncode}")
        print(f"stderr: {result.stderr}")
        return 1
    if "usage" not in result.stdout.lower():
        print(f"FAIL: --help 输出不包含 usage\nstdout: {result.stdout}")
        return 1
    print("PASS: --help 测试通过")
    return 0


if __name__ == "__main__":
    ec = test_startup() or test_cli_help()
    sys.exit(ec)
