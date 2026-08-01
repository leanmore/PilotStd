# 覆盖率分析辅助脚本 — 从 coverage report 提取高 ROI 补测模块
import re
import sys


def parse_coverage_report(filepath):
    """从覆盖率输出文件中解析每模块的覆盖率数据。"""
    modules = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            # 匹配 coverage 行: "pilotstd/path/file.py   120   45   62%"
            m = re.match(r"(\S+\.py)\s+(\d+)\s+(\d+)\s+(\d+)%", line)
            if m:
                path = m.group(1)
                stmts = int(m.group(2))
                missed = int(m.group(3))
                cov_pct = int(m.group(4))
                if stmts > 0:
                    modules.append({
                        "path": path,
                        "stmts": stmts,
                        "missed": missed,
                        "cov_pct": cov_pct,
                    })
    return modules


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "D:/PilotStd/coverage_history/coverage_full_output.txt"
    modules = parse_coverage_report(filepath)

    if not modules:
        print("未找到覆盖率数据，请确认文件路径: " + filepath)
        return

    # 按 missed 降序排列
    modules.sort(key=lambda m: m["missed"], reverse=True)

    total_stmts = sum(m["stmts"] for m in modules)
    total_missed = sum(m["missed"] for m in modules)
    total_cov = (total_stmts - total_missed) / total_stmts * 100 if total_stmts else 0

    print(f"=== 覆盖率基线 ===")
    print(f"TOTAL: {total_stmts} stmts, {total_missed} missed, {total_cov:.1f}%")
    print(f"距离 62% 还需覆盖: {int(total_stmts * 0.62 - (total_stmts - total_missed))} stmts")
    print()

    print(f"=== 前 20 未覆盖模块（按 missed 降序） ===")
    for i, m in enumerate(modules[:20]):
        print(f"{i+1:2d}. {m['path']:<60s} {m['stmts']:>4d} stmts  {m['missed']:>4d} missed  {m['cov_pct']:>3d}%")

    print()
    print("=== ROI 排序（missed ≥ 10, cov ≤ 50%） ===")
    high_roi = [m for m in modules if m["missed"] >= 10 and m["cov_pct"] <= 50]
    for i, m in enumerate(high_roi[:15]):
        print(f"{i+1:2d}. {m['path']:<60s} {m['stmts']:>4d} stmts  {m['missed']:>4d} missed  {m['cov_pct']:>3d}%")


if __name__ == "__main__":
    main()
