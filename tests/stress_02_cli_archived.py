# CLI 全命令压力测试 — 第二层
# 用法: python tests/stress_02_cli.py [--source D:\标准] [--output E:\标准]
# 零人工操作，全自动化

import sys, os, time, logging, subprocess, json, shutil, threading, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_p = argparse.ArgumentParser(description="CLI 全命令压力测试 — 第二层")
_p.add_argument("--source", required=True, help="源目录，如 D:\\标准")
_p.add_argument("--output", required=True, help="输出目录，如 E:\\标准")
import sys as _sys; _args = _p.parse_args([]) if "pytest" in _sys.argv[0] else _p.parse_args()
SOURCE_DIR = _args.source
OUTPUT_DIR = _args.output

_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_path = os.path.join(_log_dir, f"stress_cli_{time.strftime('%Y%m%d_%H%M%S')}.log")

_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
_fh = logging.FileHandler(_log_path, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S"))
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_root.addHandler(_ch)
_root.addHandler(_fh)
for _mod in ('urllib3', 'requests', 'lxml'):
    logging.getLogger(_mod).setLevel(logging.WARNING)
logger = logging.getLogger("stress_cli")

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_python = sys.executable

_checks = []
def _check(label, ok, detail=""):
    _checks.append((label, ok, detail))
    logger.info("  %s %s%s", "PASS" if ok else "FAIL", label,
                f" — {detail}" if detail else "")

def _verdict():
    total = len(_checks)
    passed = sum(1 for _, ok, _ in _checks if ok)
    logger.info("=" * 60)
    logger.info("判定: %s (%d/%d)", "PASS" if passed == total else "FAIL", passed, total)
    for label, ok, detail in _checks:
        if not ok:
            logger.info("  FAIL %s — %s", label, detail)
    logger.info("=" * 60)
    return passed == total


def run_cli(args, timeout=120):
    """通过 python -m 直接运行 CLI 模块。返回 (returncode, stdout, stderr)。
    避免 -c 代码中嵌入中文路径被 Windows 命令行 GBK 编码破坏。"""
    cmd = [_python, "-m", "pilotstd.cli.commands"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, cwd=_project_root,
                                encoding="utf-8", errors="replace",
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def run_cli_with_heartbeat(args, timeout=120, label="", hb_interval=30.0):
    """带心跳线程的 CLI 调用——长耗时命令期间定时输出进度，防止误判卡死。

    心跳线程每隔 hb_interval 秒输出一次。
    """
    stop_event = threading.Event()
    start_time = time.time()

    def _beat():
        while not stop_event.wait(hb_interval):
            elapsed = time.time() - start_time
            logger.info("[心跳] %s 仍在运行... (已耗时 %.0fs)", label, elapsed)

    hb_thread = threading.Thread(target=_beat, daemon=True)
    hb_thread.start()
    try:
        return run_cli(args, timeout=timeout)
    finally:
        stop_event.set()


# ════════════════════════════════════════════════════════════════
# 开始
# ════════════════════════════════════════════════════════════════

t0 = time.time()
logger.info("=" * 60)
logger.info("CLI 压力测试 v1 | %s", time.strftime("%Y-%m-%d %H:%M:%S"))
logger.info("源: %s  输出: %s", SOURCE_DIR, OUTPUT_DIR)
logger.info("日志: %s", _log_path)
logger.info("=" * 60)

# 清理上游测试（stress_01）遗留的站点冷却状态，避免影响 CLI 测试
_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "pilotstd.db")
if os.path.exists(_db_path):
    try:
        from pilotstd.core.db import Database as _Database
        _db = _Database(_db_path)
        _db.execute("DELETE FROM rotator_state")
        logger.info("已重置站点冷却状态")
    except Exception as _e:
        logger.debug("重置冷却状态跳过: %s", _e)

_scan_dir = SOURCE_DIR
# 遍历收集目录下实际 PDF/Word 文件，供 normalize/move 等需要文件路径的命令使用
_scan_files = []
for _root, _dirs, _files in os.walk(SOURCE_DIR):
    for _f in _files:
        if _f.lower().endswith(('.pdf', '.doc', '.docx', '.txt')) and not _f.startswith('~$'):
            _scan_files.append(os.path.join(_root, _f))
            if len(_scan_files) >= 5:
                break
    if len(_scan_files) >= 5:
        break
if not _scan_files:
    # 没文件时回退传目录（至少保证命令不崩溃）
    _scan_files = [SOURCE_DIR]

# --- scan (3 场景) ---
logger.info("--- scan ---")
rc, out, err = run_cli(["scan", _scan_dir, "--format", "csv"], timeout=60)
_check("CLI scan: CSV输出", rc == 0 and len(out) > 50, f"rc={rc}, {len(out)}字符")

rc, out, err = run_cli(["scan", _scan_dir, "--format", "json"], timeout=60)
_check("CLI scan: 返回码=0(JSON)", rc == 0, f"rc={rc}" + (f" err={err[:60]}" if err else ""))
_scan_json_ok = False
try:
    data = json.loads(out)
    _scan_json_ok = isinstance(data, list)
except Exception:
    pass
_check("CLI scan: JSON可解析", _scan_json_ok)

_empty_dir = os.path.join(OUTPUT_DIR, "_stress_cli_empty")
os.makedirs(_empty_dir, exist_ok=True)
rc, out, err = run_cli(["scan", _empty_dir], timeout=15)
_check("CLI scan: 空目录不崩溃", rc == 0, f"rc={rc}")
shutil.rmtree(_empty_dir, ignore_errors=True)

# --- query ---
logger.info("--- query ---")
_tmp_qf = os.path.join(OUTPUT_DIR, "_stress_qlist.txt")
with open(_tmp_qf, "w", encoding="utf-8") as f:
    f.write("GB/T 1-2020\nGB 150-2011\n")
rc, out, err = run_cli_with_heartbeat(["query", "--file", _tmp_qf], timeout=180,
                                         label="query批量查询")
_check("CLI query: 批量查询", rc == 0, f"rc={rc}" + (f" err={err[:60]}" if err else ""))
os.remove(_tmp_qf)

# --- announce ---
logger.info("--- announce ---")
# 按类型拆分调用，避免 check_all 三个适配器串行累加超时
for _t, _label in [("gb", "GB"), ("hb", "HB"), ("db", "DB")]:
    rc, out, err = run_cli_with_heartbeat(
        ["announce", "--since", "2026-01-01", "--limit", "3", "--type", _t],
        timeout=120, label=f"announce --type {_t} --since")
    _check(f"CLI announce: --type {_t} --since 2026-01", rc == 0,
           f"rc={rc}" + (f" err={err[:60]}" if err else ""))

# --- task ---
logger.info("--- task ---")
rc, out, err = run_cli(["task", "--limit", "5"], timeout=15)
_check("CLI task: 队列状态", rc == 0, f"rc={rc}" + (f" err={err[:60]}" if err else ""))

# --- normalize (2 场景) ---
logger.info("--- normalize ---")
rc, out, err = run_cli(["normalize"] + _scan_files, timeout=60)
_check("CLI normalize: CSV输出", rc == 0, f"rc={rc}" + (f" err={err[:60]}" if err else ""))

rc, out, err = run_cli(["normalize"] + _scan_files + ["--format", "json"], timeout=60)
_norm_json_ok = False
try:
    data = json.loads(out)
    _norm_json_ok = isinstance(data, list)
except Exception:
    pass
_check("CLI normalize: JSON可解析", _norm_json_ok)

# --- move (2 场景) ---
logger.info("--- move ---")
_move_target = os.path.join(OUTPUT_DIR, "_stress_move_test")
rc, out, err = run_cli(["move"] + _scan_files + ["--root", _move_target, "--dry-run"], timeout=60)
_check("CLI move: --dry-run预览", rc == 0, f"rc={rc}, {len(out)}字符输出")

rc, out, err = run_cli(["move"] + _scan_files + ["--root", _move_target], timeout=120)
_check("CLI move: 实际移动", rc == 0, f"rc={rc}" + (f" err={err[:80]}" if err else ""))
if os.path.exists(_move_target):
    shutil.rmtree(_move_target, ignore_errors=True)

# --- expire ---
logger.info("--- expire ---")
rc, out, err = run_cli(["expire"] + _scan_files, timeout=30)
_check("CLI expire: 处理过期", rc == 0, f"rc={rc}")

# --- announce --type ---
logger.info("--- announce --type ---")
for _t, _label in [("gb", "GB"), ("hb", "HB"), ("db", "DB")]:
    rc, out, err = run_cli_with_heartbeat(
        ["announce", "--since", "2026-05-01", "--limit", "3", "--type", _t],
        timeout=180, label=f"announce --type {_t}")
    _check(f"CLI announce: --type {_t}", rc == 0,
           f"rc={rc}" + (f" err={err[:60]}" if err else ""))
# 无 --type 全查
rc, out, err = run_cli_with_heartbeat(
    ["announce", "--since", "2026-05-20", "--limit", "1"], timeout=300,
    label="announce无type全查")
_check("CLI announce: 无--type全查", rc == 0, f"rc={rc}")

# --- auto ---
logger.info("--- auto ---")
rc, out, err = run_cli(["auto", SOURCE_DIR, "--no-cache"], timeout=1800)
_check("CLI auto: 一键处理", rc == 0, f"rc={rc}" + (f" err={err[:80]}" if err else ""))
_check("CLI auto: 输出含scan", "scan" in out.lower() or "扫描" in out, f"out={out[:100]}")

# --- organize ---
logger.info("--- organize ---")
rc, out, err = run_cli(["organize", "--format", "json"], timeout=300)
_check("CLI organize: 归档", rc == 0, f"rc={rc}")
_check("CLI organize: JSON可解析", out.strip().startswith("{") if out else False,
       f"out={out[:80]}")

# --- pending ---
logger.info("--- pending ---")
_pending_csv = os.path.join(OUTPUT_DIR, "_stress_pending.csv")
rc, out, err = run_cli(["pending", "--output", _pending_csv], timeout=30)
_check("CLI pending: 导出", rc == 0, f"rc={rc}")
_check("CLI pending: CSV存在", os.path.isfile(_pending_csv),
       f"size={os.path.getsize(_pending_csv)}B" if os.path.isfile(_pending_csv) else "文件缺失")

# --- query --no-cache vs cached ---
logger.info("--- query 缓存对比 ---")
_nums_file = os.path.join(OUTPUT_DIR, "_stress_query_nums.txt")
with open(_nums_file, "w") as _f:
    _f.write("GB/T 19001-2016\nSH/T 1610-2011\n")
_t0 = time.monotonic()
rc, out1, _ = run_cli(["query", "--file", _nums_file, "--no-cache"], timeout=120)
_t_nocache = time.monotonic() - _t0
_t0 = time.monotonic()
rc, out2, _ = run_cli(["query", "--file", _nums_file], timeout=120)
_t_cached = time.monotonic() - _t0
_check("CLI query: no-cache可执行", rc == 0, f"{_t_nocache:.1f}s")
_check("CLI query: cached更快", _t_cached <= _t_nocache * 1.1 if _t_nocache > 0 else None,
       f"no-cache={_t_nocache:.1f}s cached={_t_cached:.1f}s" if _t_cached > 0 else "SKIP")

# ── 清理临时文件 ──
for _tmp_file in [_pending_csv, _nums_file, _tmp_qf]:
    try:
        if os.path.exists(_tmp_file):
            os.remove(_tmp_file)
    except OSError:
        pass

# ════════════════════════════════════════════════════════════════
# 汇总
# ════════════════════════════════════════════════════════════════
total_time = time.time() - t0
logger.info("=" * 60)
logger.info("CLI 压力测试完成 (%.1fs)", total_time)
logger.info("日志: %s", _log_path)
_verdict()
