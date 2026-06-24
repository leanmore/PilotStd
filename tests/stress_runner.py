# tests/stress_runner.py
# 全量压力测试总入口 — 编排 CLI → Docker → WinUI 三阶段
#
# 用法:
#   python tests/stress_runner.py --source D:/标准 --output E:/标准 --config tests/test_config.json --yes
#   python tests/stress_runner.py --skip-cli --step1 <path> --yes

import argparse
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv as _load_dotenv

_load_dotenv(os.path.join(ROOT, ".env"))


def _parse_args():
    p = argparse.ArgumentParser(description="PilotStd 全量压力测试驱动器 v9.1")
    p.add_argument("--source", default="", help="源目录")
    p.add_argument("--output", default="", help="输出目录")
    p.add_argument("--config", default=None, help="压测配置文件路径")
    p.add_argument("--result-dir", default=None, help="结果目录")
    p.add_argument("--yes", action="store_true", help="跳过交互确认")
    p.add_argument("--skip-cli", action="store_true", help="跳过 CLI 阶段")
    p.add_argument("--skip-docker", action="store_true", help="跳过 Docker 阶段")
    p.add_argument("--skip-winui", action="store_true", help="跳过 WinUI 阶段")
    p.add_argument("--step1", default=None, help="复用已有 step1.json")
    p.add_argument("--timeout-query", type=int, default=None, help="查询超时秒数")
    p.add_argument("--timeout-auto", type=int, default=None, help="WinUI 超时秒数")
    p.add_argument("--keep-db", action="store_true", help="跳过清 DB")
    p.add_argument("--db-path", default=None, help="数据库路径")
    return p.parse_args()


def _load_test_config(path: str):
    from pilotstd.core.config import ConfigManager

    if not path or not os.path.exists(path):
        return {}
    return ConfigManager(filepath=os.path.abspath(path))


def main():
    args = _parse_args()

    TS = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULT_DIR = args.result_dir or os.path.join(ROOT, "logs", f"stress_{TS}")
    os.makedirs(RESULT_DIR, exist_ok=True)

    print(f"PilotStd 全量压力测试 v9.1 | {TS}")
    print(f"结果目录: {RESULT_DIR}")

    step1_data = {}
    step2_ok = True
    step3_ok = True
    skip_winui = args.skip_winui
    skip_docker = args.skip_docker

    # ── 第一阶段：CLI 冷启 ──
    if args.skip_cli:
        print("第一阶段跳过（--skip-cli）")
        step1_path = args.step1 or os.path.join(RESULT_DIR, "step1.json")
        if os.path.exists(step1_path):
            with open(step1_path, "r", encoding="utf-8") as f:
                step1_data = json.load(f)
            print(f"  从 {step1_path} 加载 step1 数据")
    else:
        from stress_cli import run_cli_phase

        step1_data = run_cli_phase(
            source=args.source,
            output=args.output,
            config_path=args.config,
            result_dir=RESULT_DIR,
            yes=args.yes,
            timeout_query=args.timeout_query,
            keep_db=args.keep_db,
            db_path=args.db_path,
        )

    # ── 第二阶段：Docker Web API ──
    if skip_docker:
        print("第二阶段跳过（--skip-docker）")
    else:
        from stress_docker import run_docker_phase

        step1_path = args.step1 or os.path.join(RESULT_DIR, "step1.json")
        step3_ok = run_docker_phase(
            config_path=args.config,
            step1_path=step1_path,
            result_dir=RESULT_DIR,
            yes=args.yes,
        )

    # ── 第三阶段：WinUI 热启 ──
    if skip_winui:
        print("第三阶段跳过（--skip-winui）")
    else:
        import subprocess

        step1_path = args.step1 or os.path.join(RESULT_DIR, "step1.json")
        step2_path = os.path.join(RESULT_DIR, "step2.json")
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                os.path.join(ROOT, "tests", "stress_winui.py"),
                "-v",
                "-s",
                "--source",
                args.source,
                "--output",
                args.output,
                "--step1",
                step1_path,
                "--step2",
                step2_path,
            ],
            capture_output=True,
            text=True,
            timeout=args.timeout_auto or 1800,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
        )
        step2_ok = r.returncode == 0
        if os.path.exists(step2_path):
            with open(step2_path, "r", encoding="utf-8") as f:
                step2_data = json.load(f)
            print(f"WinUI 甲轮完成: 判定={step2_data.get('verdict', '?')}")

        # 乙轮：web 缓存命中率验证（从 Docker 的 announce_sample.json 读取公告号）
        from stress_winui import run_winui_round_b

        test_config = _load_test_config(args.config)
        round_b = run_winui_round_b(RESULT_DIR, test_config)
        print(
            f"WinUI 乙轮完成: verdict={round_b['verdict']} "
            f"total={round_b['total']} hits={round_b['hits']} "
            f"rate={round_b['hit_rate']}"
        )
        step2_ok = step2_ok and round_b.get("verdict") != "FAIL"
        # 将乙轮结果回写到 step2.json
        if os.path.exists(step2_path):
            with open(step2_path, "r", encoding="utf-8") as f:
                step2_data = json.load(f)
            step2_data["round_b"] = round_b
            step2_data["verdict"] = (
                "PASS" if step2_data.get("verdict") == "PASS" and round_b.get("verdict") != "FAIL" else "FAIL"
            )
            with open(step2_path, "w", encoding="utf-8") as f:
                json.dump(step2_data, f, ensure_ascii=False, indent=2)

    # ── 汇总 ──
    cli_ok = bool(step1_data.get("checkpoints", {}).get("query", {}).get("rc", 0) == 0)
    overall = "PASS" if (cli_ok and step2_ok and step3_ok) else "FAIL"

    verdict = {
        "verdict": overall,
        "ts": TS,
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "version": "v9.1",
            "source_dir": args.source,
            "output_dir": args.output,
            "result_dir": RESULT_DIR,
        },
        "summary": {
            "overall_verdict": overall,
            "voting": {
                "cli": "PASS" if cli_ok else ("SKIP" if args.skip_cli else "FAIL"),
                "docker": "PASS" if step3_ok else ("SKIP" if args.skip_docker else "FAIL"),
                "winui": "PASS" if step2_ok else ("SKIP" if args.skip_winui else "FAIL"),
            },
            "blocker_failures": [],
        },
    }
    verdict_path = os.path.join(RESULT_DIR, "verdict.json")
    with open(verdict_path, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)
    print(f"判定: {overall}")
    print(f"结果: {RESULT_DIR}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
