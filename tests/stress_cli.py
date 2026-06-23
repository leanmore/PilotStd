# tests/stress_cli.py
# CLI冷启动阶段提取 — 从stress_driver.py委托调用，供独立运行和stress_all集成
#
# 用法:
#   python tests/stress_cli.py --source D:\标准 --output E:\标准 --config path\to\config.json

import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

# 必须先import stress_driver模块本体，才能设置其模块级全局变量（TS/RESULT_DIR）
import stress_driver
from stress_driver import (
    _step0_clear_db,
    _step1_cli_cold,
    _step1_precheck,
)


def _load_test_config(path: str) -> dict:
    """加载压测配置文件（不上传 git，仅本地使用）。"""
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_cli_phase(source, output, config_path, result_dir, yes, timeout_query=None, keep_db=False, db_path=None):
    """执行CLI冷启动阶段，委托给stress_driver.py已有函数。

    Returns:
        step1_data字典，含checkpoints和summary。
    """
    # 加载OCR配置
    cfg = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
    ocr_cfg = cfg.get("ocr", {})

    # 设置stress_driver.py的模块级全局变量（_step1_cli_cold内部依赖这两个变量）
    stress_driver.RESULT_DIR = result_dir
    stress_driver.TS = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 可选：清空数据库后再执行
    if not keep_db and db_path:
        _step0_clear_db(db_path)

    # 前置检查：源目录、输出目录、网络、复位、清表、selfcheck
    _step1_precheck(source, output, db_path)

    # 执行CLI冷启动全管线（scan→query→download→normalize→organize→expire→announce→task→recheck）
    step1 = _step1_cli_cold(source, output, timeout_query, ocr_cfg)

    # 确保step1.json已落盘（_step1_cli_cold正常分支内部已写入，此处兜底异常路径）
    step1_path = os.path.join(result_dir, "step1.json")
    if not os.path.exists(step1_path):
        with open(step1_path, "w", encoding="utf-8") as f:
            json.dump(step1, f, ensure_ascii=False, indent=2)

    return step1


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="PilotStd CLI冷启动压测（独立运行）")
    p.add_argument("--source", required=True, help="源目录")
    p.add_argument("--output", required=True, help="输出目录")
    p.add_argument("--config", default=None, help="压测配置文件路径（JSON）")
    p.add_argument("--result-dir", default="tests/.cache/test", help="结果输出目录")
    p.add_argument("--yes", action="store_true", help="跳过交互确认")
    p.add_argument("--keep-db", action="store_true", help="跳过清DB步骤，保留缓存")
    p.add_argument("--db-path", default=None, help="数据库路径（默认data/pilotstd.db）")
    args = p.parse_args()

    data = run_cli_phase(
        args.source,
        args.output,
        args.config,
        args.result_dir,
        args.yes,
        keep_db=args.keep_db,
        db_path=args.db_path,
    )
    summary = data.get("summary", {})
    print(f"CLI phase done: scan_count={summary.get('scan_count', 0)}")
