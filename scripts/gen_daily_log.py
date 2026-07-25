#!/usr/bin/env python3
"""从 Git log 生成当日进度日志草稿（时区：Asia/Shanghai）"""

import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
today = datetime.now(TZ).strftime("%Y-%m-%d")

result = subprocess.run(
    ["git", "log", f"--since={today}T00:00:00+08:00", "--format=%h %s", "--no-merges"], capture_output=True, text=True
)

commits = result.stdout.strip()
if not commits:
    print(f"## {today}\n\n无代码提交。")
else:
    header = f"## {today}\n\n### 提交记录\n```\n{commits}\n```"
    footer = "\n\n### 关键进展\n<!-- 执行者在此补充 -->"
    footer += "\n\n### 阻塞项\n<!-- 执行者在此补充 -->"
    print(header + footer)
