#!/usr/bin/env python3
"""
Phase 3.3 路由参数调优分析脚本

运行前提：
  - 系统已部署 v2.1 并运行至少 2 周
  - query_metrics 表中有足够数据（各适配器日均请求 ≥ 50 次）

输出：
  - 每个适配器的日限额使用率、命中率、冷却触发频率
  - 建议调整的权重和限额参数（YAML 格式）
  - 每条建议附带置信度标注
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── 动态加载适配器基线配置 ──────────────────────────────
try:
    from pilotstd.query.site_config import ADAPTER_DEFAULT_PROFILES as ADAPTER_BASELINE

    _CONFIG_SOURCE = "dynamic"
except ImportError:
    print("⚠️  WARNING: 无法导入 ADAPTER_DEFAULT_PROFILES，使用硬编码 fallback")
    ADAPTER_BASELINE = {
        "std_gov": {"default_weight": 70, "daily_limit": 1000},
        "csres": {"default_weight": 30, "daily_limit": 150},
        "energy": {"default_weight": 80, "daily_limit": 800},
    }
    _CONFIG_SOURCE = "fallback"

# ── 配置 ────────────────────────────────────────────────
DB_PATH = Path("pilotstd/data/pilotstd.db")
REPORT_DAYS = 14  # 分析最近 N 天
MIN_SAMPLES = 50  # 最少样本数才给出建议
CONFIDENCE_HIGH = 500  # 高置信阈值
CONFIDENCE_MID = 100  # 中置信阈值


def get_confidence_label(total: int) -> str:
    """根据样本量返回置信度标注"""
    if total >= CONFIDENCE_HIGH:
        return "🟢 高置信"
    elif total >= CONFIDENCE_MID:
        return "🟡 中置信"
    else:
        return "🔴 低置信（仅供参考）"


def get_rate_limit(adapter_name: str, key: str, default: int = 500) -> int:
    """从 ADAPTER_BASELINE 安全读取 rate_limit 子字段。"""
    baseline = ADAPTER_BASELINE.get(adapter_name, {})
    rate_limit = baseline.get("rate_limit", {})
    if isinstance(rate_limit, dict):
        return rate_limit.get(key, default)
    return default


def fetch_metrics(conn, days=14):
    """从 query_metrics 表提取最近 N 天数据"""
    cutoff = datetime.now() - timedelta(days=days)
    cursor = conn.execute(
        """
        SELECT
            adapter_name,
            COUNT(*) as total_queries,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status = 'cooling_skip' THEN 1 ELSE 0 END) as cooling_count,
            SUM(CASE WHEN status = 'daily_limit_hit' THEN 1 ELSE 0 END) as daily_limit_hit,
            SUM(CASE WHEN status IN ('success','cooling_skip','daily_limit_hit') THEN 1 ELSE 0 END) as quota_consumed,
            AVG(response_time_ms) as avg_response_ms,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
        FROM query_metrics
        WHERE created_at >= ?
        GROUP BY adapter_name
    """,
        (cutoff.isoformat(),),
    )
    return {
        row[0]: {
            "total": row[1],
            "success": row[2],
            "cooling": row[3],
            "daily_hit": row[4],
            "quota_consumed": row[5],
            "avg_ms": row[6],
            "errors": row[7],
        }
        for row in cursor.fetchall()
    }


def generate_recommendations(metrics):
    """生成参数调优建议（含安全提权逻辑 + 置信度标注）"""
    recommendations = []

    for name, data in metrics.items():
        if data["total"] < MIN_SAMPLES:
            continue

        total = data["total"]
        hit_rate = data["success"] / total if total > 0 else 0
        cooling_rate = data["cooling"] / total if total > 0 else 0
        daily_hit_rate = data["daily_hit"] / total if total > 0 else 0
        error_rate = data["errors"] / total if total > 0 else 0
        daily_limit = get_rate_limit(name, "daily_limit", 500)
        # 修正：仅统计真正消耗配额的请求计算使用率
        daily_usage_rate = (data["quota_consumed"] / REPORT_DAYS) / max(daily_limit, 1)

        baseline = ADAPTER_BASELINE.get(name, {"default_weight": 50})
        suggestions = []
        new_weight = baseline.get("default_weight", 50)
        new_limit = daily_limit

        # 安全提权：仅当响应快、错误率低时才因低命中提权
        if hit_rate < 0.3 and baseline.get("default_weight", 50) < 90:
            if data["avg_ms"] and data["avg_ms"] < 2000 and error_rate < 0.1:
                new_weight = min(baseline["default_weight"] + 15, 95)
                suggestions.append(
                    f"提高权重 {baseline['default_weight']} → {new_weight}（命中率 {hit_rate:.1%}，响应快且错误率低）"
                )
            else:
                suggestions.append(
                    f"⚠️ 命中率仅 {hit_rate:.1%} 但响应慢({data['avg_ms']:.0f}ms)"
                    f"或错误率高({error_rate:.1%})，需人工排查，不建议自动提权"
                )

        # 日限额使用率低 → 降低限额
        if daily_usage_rate < 0.2 and daily_limit > 200:
            new_limit = max(int(daily_limit * 0.5), 100)
            suggestions.append(f"降低日限额 {daily_limit} → {new_limit}（使用率仅 {daily_usage_rate:.1%}）")

        # 冷却率高 → 降低权重
        if cooling_rate > 0.3:
            new_weight = max(baseline.get("default_weight", 50) - 15, 10)
            suggestions.append(f"降低权重 {baseline['default_weight']} → {new_weight}（冷却率 {cooling_rate:.1%}）")

        # 日限额触顶 → 提升限额
        if daily_hit_rate > 0.05:
            new_limit = min(int(daily_limit * 1.3), 1000)
            suggestions.append(f"提高日限额 {daily_limit} → {new_limit}（触顶率 {daily_hit_rate:.1%}）")

        if suggestions:
            recommendations.append(
                {
                    "adapter": name,
                    "confidence": get_confidence_label(total),
                    "total_samples": total,
                    "hit_rate": hit_rate,
                    "cooling_rate": cooling_rate,
                    "daily_usage_rate": daily_usage_rate,
                    "current_weight": baseline.get("default_weight", 50),
                    "suggested_weight": new_weight,
                    "current_limit": daily_limit,
                    "suggested_limit": new_limit,
                    "suggestions": suggestions,
                }
            )

    return recommendations


def main():
    print("=" * 60)
    print("Phase 3.3 路由参数调优分析")
    print(f"分析周期: 最近 {REPORT_DAYS} 天 | 最小样本: {MIN_SAMPLES}")
    print(f"配置来源: {_CONFIG_SOURCE}")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("   请确认系统已部署 v2.1 并运行至少 2 周")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    metrics = fetch_metrics(conn, REPORT_DAYS)
    conn.close()

    if not metrics:
        print("❌ 未查询到 query_metrics 数据")
        sys.exit(1)

    recommendations = generate_recommendations(metrics)

    if not recommendations:
        print("✅ 所有适配器指标正常，无需调优")
        return

    print("\n📊 调优建议汇总:\n")
    for rec in recommendations:
        print(f"【{rec['adapter']}】 {rec['confidence']}（n={rec['total_samples']}）")
        print(
            f"  命中率: {rec['hit_rate']:.1%} | 冷却率: {rec['cooling_rate']:.1%} | 日限额使用率: {rec['daily_usage_rate']:.1%}"
        )
        print(f"  当前权重: {rec['current_weight']} → 建议: {rec['suggested_weight']}")
        print(f"  当日限额: {rec['current_limit']} → 建议: {rec['suggested_limit']}")
        for s in rec["suggestions"]:
            print(f"  - {s}")
        print()

    # YAML 输出
    yaml_lines = [
        r
        for r in recommendations
        if r["suggested_weight"] != r["current_weight"] or r["suggested_limit"] != r["current_limit"]
    ]
    if yaml_lines:
        print("\n📋 YAML 配置片段（可复制至 site_config.py）:\n")
        print("# 基于数据分析的调优建议（请人工复核后应用）")
        for rec in yaml_lines:
            print(f'    "{rec["adapter"]}": {{')
            print(f'        "default_weight": {rec["suggested_weight"]},  # 原值: {rec["current_weight"]}')
            print(f'        "daily_limit": {rec["suggested_limit"]},      # 原值: {rec["current_limit"]}')
            print("    }")


if __name__ == "__main__":
    main()
