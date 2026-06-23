#!/usr/bin/env python3
"""自动更新 capabilities_registry.md 中的行号引用。

每次 pre-commit 时运行，扫描源代码中注册的函数/日志模式，获取最新行号，
回写到 capabilities_registry.md 对应条目。
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

# ── 追踪规则：每条对应 registry 中的一个条目 ──
# key: 条目在 registry 中的"功能模块"列的值（用于行内匹配）
# file: 源代码文件路径（相对于项目根目录）
# pattern: 匹配模式（函数名或正则）
# kind: 'func'（AST 查函数定义行号）或 'regex'（正则扫描行号）

TRACKERS: dict[str, dict] = {
    # ── docker/scheduler.py ──
    "调度器实例": {
        "file": "docker/scheduler.py",
        "pattern": r"scheduler = BackgroundScheduler\(\)",
        "kind": "regex",
    },
    "调度器公告包装": {
        "file": "docker/scheduler.py",
        "pattern": r'"announce" in job_id',
        "kind": "regex",
    },
    "调度器心跳循环": {
        "file": "docker/scheduler.py",
        "pattern": "def _heartbeat_loop",
        "kind": "func",
    },
    "调度器互斥锁": {
        "file": "docker/scheduler.py",
        "pattern": "def _acquire_scheduler_lock",
        "kind": "func",
    },
    "调度器优雅关闭": {
        "file": "docker/scheduler.py",
        "pattern": "def stop_scheduler",
        "kind": "func",
    },
    # ── docker/app.py ──
    "FastAPI 生命周期": {
        "file": "docker/app.py",
        "pattern": "async def lifespan",
        "kind": "func",
    },
    # ── engine.py ──
    "引擎进度心跳": {
        "file": "pilotstd/query/engine.py",
        "pattern": "def _progress_heartbeat",
        "kind": "func",
    },
    "引擎线程池": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"ThreadPoolExecutor\(max_workers=8\)",
        "kind": "regex",
    },
    "引擎 PROGRESS 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[PROGRESS\]",
        "kind": "regex",
    },
    "引擎 BUCKET 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[BUCKET\]",
        "kind": "regex",
    },
    "引擎 FUNNEL 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[FUNNEL\]",
        "kind": "regex",
    },
    "引擎 TIMELINE 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[TIMELINE\]",
        "kind": "regex",
    },
    "引擎 BASELINE 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[BASELINE\]",
        "kind": "regex",
    },
    "引擎 CACHE 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[CACHE\]",
        "kind": "regex",
    },
    "引擎 QUOTA/WATER 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[QUOTA\]|\[WATER\]",
        "kind": "regex",
    },
    "引擎 SCORE 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[SCORE\]",
        "kind": "regex",
    },
    "引擎 OVERFLOW 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[OVERFLOW\]",
        "kind": "regex",
    },
    "引擎 CHAIN/PENDING 日志": {
        "file": "pilotstd/query/engine.py",
        "pattern": r"\[CHAIN\]|\[PENDING\]",
        "kind": "regex",
    },
    # ── cache.py ──
    "缓存仓库": {
        "file": "pilotstd/query/cache.py",
        "pattern": "class CacheRepository",
        "kind": "regex",
    },
    # ── rotator.py ──
    "轮转器里程碑日志": {
        "file": "pilotstd/query/rotator.py",
        "pattern": r"\[轮转器\]",
        "kind": "regex",
    },
    "轮转器冷却日志": {
        "file": "pilotstd/query/rotator.py",
        "pattern": "冷却剩余",
        "kind": "regex",
    },
    # ── daily_quota.py ──
    "日配额追踪": {
        "file": "pilotstd/query/daily_quota.py",
        "pattern": "class DailyQuotaTracker",
        "kind": "regex",
    },
    # ── queue.py ──
    "任务队列执行": {
        "file": "pilotstd/task/queue.py",
        "pattern": r"def _run|def wrapped_handler|Thread\(target=wrapped_handler",
        "kind": "regex",
    },
    # ── download/engine.py ──
    "下载线程池": {
        "file": "pilotstd/download/engine.py",
        "pattern": r"ThreadPoolExecutor",
        "kind": "regex",
    },
    # ── announcement/ ──
    "公告引擎调度": {
        "file": "pilotstd/announcement/engine.py",
        "pattern": "class AnnounceEngine",
        "kind": "regex",
    },
    "公告基础并行": {
        "file": "pilotstd/announcement/base.py",
        "pattern": r"ThreadPoolExecutor\(max_workers",
        "kind": "regex",
    },
    "公告阶段耗时": {
        "file": "pilotstd/announcement/monitor.py",
        "pattern": "def (start_stage|end_stage|inc_api_call)",
        "kind": "regex",
    },
    "OCR 取消事件": {
        "file": "pilotstd/announcement/ocr.py",
        "pattern": r"threading\.Event\(\)",
        "kind": "regex",
    },
    # ── core/ ──
    "文件索引清理线程": {
        "file": "pilotstd/core/file_index.py",
        "pattern": r"threading\.Thread\(target=_run",
        "kind": "regex",
    },
    "文件监控": {
        "file": "pilotstd/scan/watcher.py",
        "pattern": "class FileWatcher",
        "kind": "regex",
    },
    # ── ui/ ──
    "主窗口 atexit": {
        "file": "pilotstd/ui/main_window.py",
        "pattern": r"atexit\.register",
        "kind": "regex",
    },
    "主窗口 SIGTERM": {
        "file": "pilotstd/ui/main_window.py",
        "pattern": r"signal\.signal\(signal\.SIGTERM",
        "kind": "regex",
    },
    "主窗口自动保存": {
        "file": "pilotstd/ui/main_window.py",
        "pattern": "def _on_auto_save",
        "kind": "func",
    },
    "主窗口暂停信号": {
        "file": "pilotstd/ui/main_window.py",
        "pattern": r"_pause_event\s*=",
        "kind": "regex",
    },
    "主窗口下载线程": {
        "file": "pilotstd/ui/main_window.py",
        "pattern": r"Thread\(target=_download,\s*daemon=True\)",
        "kind": "regex",
    },
    "工作者 QTimer": {
        "file": "pilotstd/ui/workers.py",
        "pattern": r"_buf_timer\s*=\s*QTimer",
        "kind": "regex",
    },
    "待确认冷却刷新": {
        "file": "pilotstd/ui/pending_query_dialog.py",
        "pattern": r"_refresh_timer\s*=\s*QTimer",
        "kind": "regex",
    },
    "节流进度发射器": {
        "file": "pilotstd/ui/controllers/auto_run_mixin.py",
        "pattern": "class _ThrottledProgress",
        "kind": "regex",
    },
    # ── tests/ ──
    "压力测试看门狗": {
        "file": "tests/stress_driver.py",
        "pattern": "def _progress_watchdog",
        "kind": "func",
    },
    "压力测试双流读取": {
        "file": "tests/stress_driver.py",
        "pattern": r"Thread\(target=read_stream",
        "kind": "regex",
    },
    "压力测试 Web 心跳": {
        "file": "tests/stress_web.py",
        "pattern": r"\[PROGRESS\]",
        "kind": "regex",
    },
}


def find_func_lineno(filepath: str, func_name: str) -> int | None:
    """用 AST 解析函数定义行号。"""
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except (OSError, SyntaxError) as e:
        print(f"  [WARN] AST 解析失败 {filepath}: {e}", file=sys.stderr)
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node.lineno
    return None


def find_regex_linenos(filepath: str, pattern: str) -> str:
    """用正则扫描匹配行号，返回逗号分隔列表（连续行合并为范围）。"""
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"  [WARN] 读取失败 {filepath}: {e}", file=sys.stderr)
        return ""
    matches = [i + 1 for i, line in enumerate(lines) if re.search(pattern, line)]
    if not matches:
        return ""
    # 压缩连续行为范围
    ranges: list[str] = []
    start = matches[0]
    end = start
    for m in matches[1:]:
        if m == end + 1:
            end = m
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = m
            end = m
    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)


def update_registry(root: Path) -> bool:
    """更新 registry 中的行号列。返回 True 表示有变更。"""
    registry_path = root / "docs" / "governance" / "capabilities_registry.md"
    if not registry_path.exists():
        print("[WARN] capabilities_registry.md 不存在，跳过", file=sys.stderr)
        return False

    with open(registry_path, encoding="utf-8") as f:
        lines = f.readlines()

    updated = False
    for key, info in TRACKERS.items():
        filepath = str(root / info["file"])
        if not Path(filepath).exists():
            continue

        # 获取当前最新行号
        if info["kind"] == "func":
            new_lineno = find_func_lineno(filepath, info["pattern"])
            new_str = f"L{new_lineno}" if new_lineno else ""
        else:
            new_str = find_regex_linenos(filepath, info["pattern"])
            if new_str:
                new_str = "L" + new_str
        if not new_str:
            continue

        # 在 registry 中定位该条目行并更新行号列
        for i, line in enumerate(lines):
            if not line.startswith("| "):
                continue
            if key not in line:
                continue
            parts = line.split("|")
            # 行号在第 4 列（index 3）
            if len(parts) < 5:
                continue
            old_lineno = parts[4].strip()  # 行号在第 5 列 (index 4)
            if old_lineno == new_str or old_lineno == "—":
                continue
            parts[4] = f" {new_str} "  # 更新行号列
            lines[i] = "|".join(parts)
            print(f"  [UPDATE] {key}: {old_lineno} → {new_str}")
            updated = True
            break
        else:
            print(f"  [WARN] 未在 registry 中找到条目: {key}", file=sys.stderr)

    if updated:
        with open(registry_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        subprocess.run(["git", "add", str(registry_path)], check=False)
    return updated


def main() -> int:
    root = Path.cwd()
    # 确保在项目根目录
    if not (root / "pilotstd").is_dir():
        print("[WARN] 未在项目根目录，跳过", file=sys.stderr)
        return 0
    changed = update_registry(root)
    if changed:
        print("[OK] capabilities_registry.md 行号已更新")
    else:
        print("[OK] capabilities_registry.md 行号无变化")
    return 0


if __name__ == "__main__":
    sys.exit(main())
