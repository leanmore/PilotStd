#!/usr/bin/env python3
"""阶段四：能力矩阵自动回填工具。

将 analyze_router_logs.py 产出的指标 YAML 安全合并回 config/site_capabilities.yaml：
- 只更新 historical_hit_rate、avg_latency_ms 两个字段
- 绝不覆盖 supported_types / is_international / search_reliability 等人工字段
- 更新前自动备份，更新后同步 capabilities_registry.md
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_YAML_PATH = Path(__file__).resolve().parent.parent / "config" / "site_capabilities.yaml"


def _backup() -> Path:
    """生成时间戳备份文件。"""
    bak = Path(f"{_YAML_PATH}.bak.{time.strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(_YAML_PATH, bak)
    return bak


def _sync_registry() -> bool:
    """运行 generate_capabilities.py 同步能力矩阵注册表。"""
    script = Path(__file__).resolve().parent / "generate_capabilities.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    return result.returncode == 0


def backfill(metrics_path: str) -> dict:
    """读指标 YAML（analyze_router_logs.py 产出），回填到 site_capabilities.yaml。

    只更新 status 下的 historical_hit_rate / avg_latency_ms，不触碰人工字段。
    """
    metrics = yaml.safe_load(Path(metrics_path).read_text(encoding="utf-8"))
    site_metrics = metrics.get("sites", {})

    data = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    updated = 0
    # 只更新 status 下的两个指标字段，不触碰人工维护字段
    for entry in data["sites"]:
        site_id = entry["site_id"]
        if site_id not in site_metrics:
            continue
        status = entry.setdefault("status", {})
        status["historical_hit_rate"] = site_metrics[site_id]["historical_hit_rate"]
        status["avg_latency_ms"] = site_metrics[site_id]["avg_latency_ms"]
        updated += 1

    # 更新前备份，更新后同步注册表
    bak = _backup()
    _YAML_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return {"backup": str(bak), "updated": updated, "registry_synced": _sync_registry()}


def main() -> int:
    """入口：解析指标 YAML 路径，执行回填。"""
    parser = argparse.ArgumentParser(description="将路由指标回填到 site_capabilities.yaml")
    parser.add_argument("metrics_yaml", help="analyze_router_logs.py 产出的指标 YAML 路径")
    args = parser.parse_args()

    if not Path(args.metrics_yaml).exists():
        print(f"❌ 指标文件不存在: {args.metrics_yaml}", file=sys.stderr)
        return 1

    result = backfill(args.metrics_yaml)
    print(f"✅ 回填完成：更新 {result['updated']} 个站点")
    print(f"   备份: {result['backup']}")
    print(f"   Registry 同步: {'成功' if result['registry_synced'] else '失败'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
