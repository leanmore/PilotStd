#!/usr/bin/env python3
"""G-026: 检查 docker-compose.yml 中是否存在禁止挂载的目录。
防止误挂载 /app 导致容器无法启动。退出门禁：返回 0=通过, 1=阻断。"""

import sys
from pathlib import Path

_FORBIDDEN = {"/app"}
_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    compose = _ROOT / "docker-compose.yml"
    if not compose.exists():
        print("[G-026] SKIP: docker-compose.yml 不存在")
        return 0

    lines = compose.read_text(encoding="utf-8").split("\n")
    in_volumes = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("volumes:"):
            in_volumes = True
            continue
        # volumes 段结束（下一个顶级 key 或空行后非列表项）
        if in_volumes and not stripped.startswith("-") and not stripped.startswith("#") and stripped:
            if not stripped.startswith("volumes:"):
                in_volumes = False
                continue
        if in_volumes and stripped.startswith("-"):
            # 提取冒号后的容器内路径（如 "./output:/app/output" → "/app/output"）
            parts = stripped.lstrip("- ").split(":")
            if len(parts) >= 2:
                target = parts[1].strip()
                # 规范化路径去除尾部斜杠
                target = target.rstrip("/")
                if target in _FORBIDDEN:
                    print(f"[G-026] FAIL: {compose.name}:{i} 禁止挂载 {target}")
                    print(f"   {target} 是代码运行根目录，挂载会导致容器无法启动")
                    print("   请将文件写入 /app/data 或 /app/output")
                    return 1
    print("[G-026] PASS: 未发现禁止挂载目录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
