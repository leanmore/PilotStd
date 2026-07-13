#!/usr/bin/env python
"""Packaged L1 startup test: verify exe can start and --help works."""

import subprocess
import sys
import time
from pathlib import Path

EXE_PATH = Path("dist/PilotStd.exe")


def test_startup():
    if not EXE_PATH.exists():
        print(f"FAIL: {EXE_PATH} not found")
        return 1

    proc = subprocess.Popen(
        [str(EXE_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(5)

    if proc.poll() is not None:
        print(f"FAIL: process exited early, return code {proc.returncode}")
        return 1

    proc.terminate()
    proc.wait(timeout=3)
    print("PASS: startup test passed")
    return 0


def test_cli_help():
    result = subprocess.run(
        [str(EXE_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        print(f"FAIL: --help returned {result.returncode}")
        return 1

    if "usage" not in result.stdout.lower():
        print("FAIL: --help output does not contain 'usage'")
        return 1

    print("PASS: --help test passed")
    return 0


if __name__ == "__main__":
    sys.exit(test_startup() or test_cli_help())
