#!/usr/bin/env python3
"""观测能力自检脚本 —— 对照能力登记簿验证非功能性能力是否存活。

用法:
    python tests/test_observability.py --check-all       # 检查所有 required 能力
    python tests/test_observability.py --module pilotstd/query/engine.py
    python tests/test_observability.py --required-only   # 仅 required 级别
    python tests/test_observability.py --verbose         # 详细扫描过程

退出码: 0=全部通过, 1=存在 FAIL
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pilotstd.query.engine import PROGRESS_TAG

ROOT = Path(__file__).resolve().parent.parent

# ── 硬性规则（登记簿之外的内置检查） ──────────────────────────────
# 格式: (文件路径, 检查类型, 特征模式, 描述)
_HARD_RULES: list[tuple[str, str, str, str]] = [
    (
        "pilotstd/query/engine.py",
        "观测日志",
        PROGRESS_TAG,
        f"query/engine.py 必须包含 {PROGRESS_TAG} 日志输出 (required)",
    ),
    (
        "tests/stress_driver.py",
        "后台线程",
        "threading.Thread",
        "stress_driver.py 必须包含 daemon 线程或定时器启动逻辑 (required)",
    ),
    (
        "tests/stress_web.py",
        "观测日志",
        PROGRESS_TAG,
        f"stress_web.py 必须包含 {PROGRESS_TAG} 日志输出 (required)",
    ),
    (
        "pilotstd/query/engine.py",
        "观测日志",
        "[BASELINE]",
        "query/engine.py 必须包含 [BASELINE] 日志输出 (required)",
    ),
    (
        "pilotstd/query/rotator.py",
        "观测日志",
        "[ROTATOR]",
        "query/rotator.py 必须包含 [ROTATOR] 日志输出 (required)",
    ),
]


@dataclass
class CapabilityEntry:
    module_path: str
    name: str
    description: str
    location: str  # e.g. "engine.py:390-410"
    cap_type: str  # 后台线程 / 观测日志 / 缓存 / ...
    necessity: str  # required / recommended / optional
    status: str  # active / migrating / deprecated

    @property
    def is_active_required(self) -> bool:
        return self.status == "active" and self.necessity == "required"


@dataclass
class CheckResult:
    entry: CapabilityEntry
    passed: bool
    detail: str = ""
    source: str = ""  # "registry" or "hard_rule"


@dataclass
class ScanReport:
    results: list[CheckResult] = field(default_factory=list)
    verbose: bool = False

    def add(self, result: CheckResult) -> None:
        self.results.append(result)
        icon = " PASS" if result.passed else "FAIL"
        tag = f"[{result.source}]"
        print(f"  {icon} {tag} {result.entry.name}")
        if not result.passed and result.detail:
            print(f"         {result.detail}")
        elif self.verbose and result.detail:
            print(f"         {result.detail}")

    def summary(self) -> tuple[int, int, int]:
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        return passed, failed, total


# ── 登记簿解析 ──────────────────────────────────────────────────────


def _parse_row(line: str) -> Optional[CapabilityEntry]:
    """解析 Markdown 表格行: | module | name | desc | loc | type | nec | date | status |"""
    # 跳过表头分隔行
    if re.match(r"^\|[\s\-:|]+\|$", line):
        return None
    # 提取单元格（跳过首尾 |）
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 8:
        return None
    # 跳过表头
    if cells[0] in ("模块路径", "模块路径 "):
        return None
    return CapabilityEntry(
        module_path=cells[0].strip("` "),
        name=cells[1].strip(),
        description=cells[2].strip(),
        location=cells[3].strip(),
        cap_type=cells[4].strip(),
        necessity=cells[5].strip(),
        status=cells[7].strip().replace("**", ""),
    )


def load_registry(path: str) -> list[CapabilityEntry]:
    """从 capabilities_registry.md 加载所有所需能力条目。"""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    entries: list[CapabilityEntry] = []
    in_table = False
    for line in lines:
        if line.startswith("|") and "模块路径" in line:
            in_table = True
            continue
        if in_table and line.startswith("|"):
            entry = _parse_row(line.rstrip())
            if entry:
                entries.append(entry)
        elif in_table and not line.startswith("|"):
            in_table = False
        # 下一个表格
        if line.startswith("## ") and "迁移中" not in line:
            in_table = False
    return entries


# ── AST 特征检测 ─────────────────────────────────────────────────────


def _read_file_safe(file_path: str) -> Optional[str]:
    """安全读取文件内容（UTF-8）。"""
    full = ROOT / file_path
    if not full.exists():
        return None
    try:
        return full.read_text(encoding="utf-8")
    except Exception:
        return None


def _check_thread_pattern(content: str) -> bool:
    """检查是否包含线程创建模式。"""
    patterns = [
        "threading.Thread(",
        "Thread(target=",
        "daemon=True",
        "ThreadPoolExecutor(",
        "QTimer(",
    ]
    return any(p in content for p in patterns)


def _check_log_pattern(content: str, marker: str) -> bool:
    """检查是否包含指定日志标记。"""
    # 去除 backtick 包裹
    clean = marker.strip("`")
    return clean in content


def _check_cache_pattern(content: str) -> bool:
    """检查是否包含缓存模式。"""
    patterns = [
        "CacheRepository",
        "class Cache",
        "use_cache",
        "cache_hit",
    ]
    return any(p in content for p in patterns)


def _check_signal_pattern(content: str) -> bool:
    """检查信号/生命周期/优雅关闭模式。"""
    patterns = [
        "atexit.register",
        "signal.signal(",
        "@app.on_event",
        "startup",
        "shutdown",
        "scheduler.shutdown",
        "stop_scheduler",
        "_heartbeat_stop.set",
    ]
    return any(p in content for p in patterns)


def _classify_cap_type(cap_type: str) -> str:
    """归类能力类型到检测函数。"""
    if "线程" in cap_type or "QTimer" in cap_type or "Event" in cap_type or "线程池" in cap_type:
        return "thread"
    if "日志" in cap_type:
        return "log"
    if "缓存" in cap_type:
        return "cache"
    if "信号" in cap_type or "退出" in cap_type or "生命周期" in cap_type:
        return "signal"
    return "unknown"


def check_entry(entry: CapabilityEntry) -> CheckResult:
    """对单条能力执行特征检测。"""
    content = _read_file_safe(entry.module_path)
    if content is None:
        return CheckResult(
            entry,
            False,
            f"文件不存在或无法读取: {entry.module_path}",
            source="registry",
        )

    cat = _classify_cap_type(entry.cap_type)
    passed = False
    detail = ""

    if cat == "thread":
        passed = _check_thread_pattern(content)
        detail = "[OK] thread pattern detected" if passed else "[MISS] no thread pattern"
    elif cat == "log":
        # 从能力名称提取日志标记（如 {PROGRESS_TAG}、[BUCKET] 等）
        marker_match = re.search(r"\[([A-Z_]+)\]", entry.name)
        if marker_match:
            marker = f"[{marker_match.group(1)}]"
            passed = _check_log_pattern(content, marker)
            detail = f"[OK] found {marker}" if passed else f"[MISS] {marker} not found"
        else:
            passed = True
            detail = "无法提取日志标记，默认通过"
    elif cat == "cache":
        passed = _check_cache_pattern(content)
        detail = "[OK] cache pattern detected" if passed else "[MISS] no cache pattern"
    elif cat == "signal":
        passed = _check_signal_pattern(content)
        detail = "[OK] signal pattern detected" if passed else "[MISS] not detected"
    else:
        passed = True
        detail = "未知类型，默认通过"

    return CheckResult(entry, passed, detail, source="registry")


# ── 硬性规则检查 ─────────────────────────────────────────────────────


def check_hard_rules() -> list[CheckResult]:
    """执行硬性规则检查。"""
    results: list[CheckResult] = []
    for file_path, cap_type, pattern, desc in _HARD_RULES:
        content = _read_file_safe(file_path)
        if content is None:
            results.append(
                CheckResult(
                    CapabilityEntry(file_path, desc, "", "", cap_type, "required", "active"),
                    False,
                    f"文件不存在: {file_path}",
                    source="hard_rule",
                )
            )
            continue
        if cap_type == "观测日志":
            passed = pattern in content
        elif cap_type == "后台线程":
            passed = _check_thread_pattern(content)
        else:
            passed = True
        results.append(
            CheckResult(
                CapabilityEntry(file_path, desc, "", "", cap_type, "required", "active"),
                passed,
                f"[OK] found {pattern}" if passed else f"[MISS] {pattern} not found",
                source="hard_rule",
            )
        )
    return results


# ── 主入口 ────────────────────────────────────────────────────────────


def main() -> int:
    # Windows GBK 编码兼容
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    p = argparse.ArgumentParser(description="观测能力自检脚本")
    p.add_argument("--check-all", action="store_true", help="检查所有已登记能力")
    p.add_argument("--module", type=str, help="仅检查指定模块")
    p.add_argument("--required-only", action="store_true", help="仅检查 required 级别")
    p.add_argument("--verbose", action="store_true", help="输出详细扫描过程")
    args = p.parse_args()

    registry_path = ROOT / "docs" / "governance" / "capabilities_registry.md"
    if not registry_path.exists():
        print("ERROR: registry not found: docs/governance/capabilities_registry.md")
        return 1

    report = ScanReport(verbose=args.verbose)

    # ── 从登记簿加载 ──
    if args.check_all or args.required_only or args.module:
        all_entries = load_registry(str(registry_path))

        # 过滤
        if args.required_only:
            entries = [e for e in all_entries if e.is_active_required]
        elif args.module:
            mod = args.module.replace("\\", "/")
            entries = [e for e in all_entries if e.module_path == mod or mod in e.module_path]
            if not entries:
                print(f"WARN:️  未找到模块 {args.module} 的登记条目")
        else:
            entries = [e for e in all_entries if e.is_active_required]

        if args.verbose:
            print(f"从登记簿加载 {len(all_entries)} 条，筛选后 {len(entries)} 条待检查\n")

        for entry in entries:
            result = check_entry(entry)
            report.add(result)

    # ── 硬性规则 ──
    if args.check_all:
        print()
        for result in check_hard_rules():
            report.add(result)

    # ── 汇总 ──
    passed, failed, total = report.summary()
    print(f"\n{'=' * 50}")
    print(f"汇总: {passed} 通过 / {total} 总检查")
    if failed:
        print(f"FAIL: {failed} items")
    else:
        print(" 全部通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
