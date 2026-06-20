# tests/stress_driver.py
# 全量压力测试驱动器 — 按 docs/testing/本机源码全量压力测试方案.md v4.2 执行
#
# 用法（Docker 连接信息见 docs/testing/本机源码全量压力测试方案.md）:
#   python tests/stress_driver.py --source D:\标准 --output E:\标准 --skip-docker
#   python tests/stress_driver.py --source D:\标准 --output E:\标准 --docker-url <地址> --docker-user <用户名> --docker-pass <密码>
#
# 执行流程:
#   第〇步  复位源目录 + 清 DB
#   第一步  CLI 冷启（一+三+四+五+六写+七） → 写 step1.json
#          复位源目录
#   第二步  WinUI 热启（一交叉+二+三+四交叉+六读） → 交叉对比 → 写 step2.json
#   第三步  Docker Web API（补充） → 写 step3.json
#   第四步  汇总判定

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime

# 强制 stdout 使用 utf-8 编码（Windows 默认 GBK 无法输出 Docker 日志中的 Unicode 字符）
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 模块级常量：由 main() 在运行时赋值，避免 mypy [name-defined]
TS: str = ""
RESULT_DIR: str = ""

# ── CLI 参数 ──────────────────────────────────────────────────


def _parse_args():
    p = argparse.ArgumentParser(description="PilotStd 全量压力测试驱动器")
    p.add_argument("--source", required=True, help="源目录，如 D:\\标准")
    p.add_argument("--output", required=True, help="输出目录，如 E:\\标准")
    p.add_argument(
        "--timeout-query", type=int, default=None, help="查询超时秒数（默认不限）"
    )
    p.add_argument(
        "--timeout-auto", type=int, default=None, help="auto 超时秒数（默认不限）"
    )
    p.add_argument("--skip-winui", action="store_true", help="跳过 WinUI 步骤")
    p.add_argument("--skip-docker", action="store_true", help="跳过 Docker 步骤")
    p.add_argument("--skip-cli", action="store_true", help="跳过 CLI 冷启步骤")
    p.add_argument(
        "--docker-url",
        default=os.environ.get("PILOTSTD_BASE_URL", ""),
        help="Docker API 地址（需设置环境变量 PILOTSTD_BASE_URL）",
    )
    p.add_argument(
        "--docker-user",
        default=os.environ.get("PILOTSTD_USERNAME", ""),
        help="Docker 管理员用户名（需设置环境变量 PILOTSTD_USERNAME）",
    )
    p.add_argument(
        "--docker-pass",
        default=os.environ.get("PILOTSTD_PASSWORD", ""),
        help="Docker 管理员密码（需设置环境变量 PILOTSTD_PASSWORD）",
    )
    p.add_argument(
        "--db-path", default=None, help="数据库路径（默认 data/pilotstd.db）"
    )
    p.add_argument("--yes", action="store_true", help="跳过所有交互确认（CI/自动模式）")
    p.add_argument(
        "--keep-db", action="store_true", help="跳过清 DB 步骤（保留缓存和索引）"
    )
    p.add_argument(
        "--winui-only", action="store_true", help="仅执行 WinUI 步骤（跳过CLI冷启）"
    )
    p.add_argument(
        "--step1", default=None, help="step1.json 路径（winui-only 模式时由总入口传入）"
    )
    p.add_argument(
        "--result-dir",
        default=None,
        help="结果目录（由 stress_all 传入，统一输出位置）",
    )
    p.add_argument(
        "--config", default=None, help="压测配置文件路径（JSON，含 Docker/OCR 凭证）"
    )
    p.add_argument(
        "--stop-after",
        default=None,
        choices=["cli"],
        help="在第一阶段完成后退出: cli=CLI冷启后停止（不执行WinUI/Docker）",
    )
    return p.parse_args()


def _load_test_config(path: str) -> dict:
    """加载压测配置文件（不上传 git，仅本地使用）。"""
    import json as _json

    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return _json.load(f)


def _log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)


# ── 第〇步：环境自检 + 复位 + 清 DB ──────────────────────────


def _step0_verify_credentials(
    docker_url: str, docker_user: str, docker_pass: str
) -> tuple:
    """凭证预检：登录 Docker API 验证凭证有效性。

    Returns:
        (ok: bool, detail: str) — ok=True 表示凭证有效，detail 为描述信息
    """
    import urllib.parse as _up
    import urllib.request as _ur

    if not docker_url:
        return (False, "未配置 Docker URL")
    login_url = f"{docker_url}/api/login"
    data = f"username={_up.quote(docker_user)}&password={_up.quote(docker_pass)}"
    try:
        req = _ur.Request(
            login_url,
            data=data.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        resp = _ur.urlopen(req, timeout=10)
        if resp.status == 200:
            set_cookie = resp.headers.get("set-cookie", "")
            has_token = "pilotstd_token" in set_cookie
            if has_token:
                return (True, f"登录成功 user={docker_user} url={docker_url}")
            else:
                return (False, "登录响应缺少 pilotstd_token cookie")
        else:
            return (False, f"HTTP {resp.status}")
    except Exception as e:
        err = str(e)
        if "timed out" in err.lower() or "time" in err.lower():
            return (False, f"连接超时: {docker_url}")
        return (False, f"凭证预检异常: {err[:80]}")


def _step0_check_preconditions(
    source_dir: str, output_dir: str, skip_docker: bool, docker_url: str
):
    """逐项自检前置条件，不满足的直接退出。"""
    all_ok = True

    # Python 版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info < (3, 12):
        _log(f"❌ Python 版本过低: {py_ver}，需要 ≥3.12")
        all_ok = False
    else:
        _log(f"✅ Python {py_ver}")

    # 源目录存在且有文件
    if not os.path.isdir(source_dir):
        _log(f"❌ 源目录不存在: {source_dir}")
        all_ok = False
    else:
        fcount = sum(1 for _ in os.scandir(source_dir))
        if fcount == 0:
            _log(f"❌ 源目录为空: {source_dir}")
            all_ok = False
        else:
            _log(f"✅ 源目录: {source_dir} ({fcount} 个条目)")

    # 输出目录可写
    try:
        os.makedirs(output_dir, exist_ok=True)
        _log(f"✅ 输出目录: {output_dir}")
    except OSError as e:
        _log(f"❌ 输出目录不可写: {output_dir} — {e}")
        all_ok = False

    # 网络
    try:
        import urllib.request

        urllib.request.urlopen("https://www.baidu.com", timeout=5)
        _log("✅ 外网可达")
    except Exception as e:
        _log(f"❌ 外网不可达: {e}")
        all_ok = False

    # Docker
    if not skip_docker:
        try:
            import urllib.request

            r = urllib.request.urlopen(f"{docker_url}/api/health", timeout=5)
            if r.status == 200:
                _log(f"✅ Docker: {docker_url}")
            else:
                _log(f"⚠️ Docker 健康检查异常: {docker_url} status={r.status}")
        except Exception as e:
            _log(f"⚠️ Docker 不可达: {docker_url} — {e}（将自动跳过）")

    if not all_ok:
        _log("前置条件不满足，退出。")
        sys.exit(1)
    _log("前置条件全部满足")


def _step0_clear_db(db_path: str | None = None):
    """清空四表，保留 schema 和用户设置。"""
    from pilotstd.core.config import get_data_dir
    from pilotstd.core.db import Database

    if db_path is None:
        db_path = os.path.join(get_data_dir(), "pilotstd.db")
    if not os.path.exists(db_path):
        _log(f"DB 不存在，跳过清表: {db_path}")
        return
    db = Database(db_path)
    tables = [
        "standard_info_cache",
        "announcement_cache",
        "pending_lookup",
        "file_index",
        "rotator_state",
    ]
    # 清空前记录各表行数
    counts = {}
    for t in tables:
        try:
            row = db.fetchone(f"SELECT COUNT(*) as c FROM {t}")
            counts[t] = row["c"] if row else 0
        except Exception:
            counts[t] = -1
    _log(f"即将清空四表（当前数据量）: {counts}")
    for t in tables:
        try:
            db.execute(f"DELETE FROM {t}")
        except Exception as e:
            _log(f"  清表 {t} 失败: {e}")
    _log(f"DB 四表已清空: {', '.join(tables)}")


def _step0_reset_source(source_dir: str, output_dir: str):
    """将输出目录中被归档移走的文件迁回源目录。"""
    if not os.path.isdir(output_dir):
        return
    moved = 0
    for root, dirs, files in os.walk(output_dir):
        # 跳过非分类文件夹（downloads, logs 等）
        rel = os.path.relpath(root, output_dir)
        if (
            rel.startswith("logs")
            or rel.startswith("downloads")
            or rel.startswith("_stress")
        ):
            continue
        for f in files:
            src = os.path.join(root, f)
            # 找到源目录中对应的子目录
            # 简单策略：按分类文件夹层级反推
            parts = rel.split(os.sep)
            if len(parts) >= 2:
                target_dir = os.path.join(source_dir, *parts[0:2])
            else:
                target_dir = source_dir
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            dst = os.path.join(target_dir, f)
            try:
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                    moved += 1
            except Exception:
                pass
    if moved:
        _log(f"复位源目录: {moved} 个文件迁回 {source_dir}")


# ── 子进程安全执行工具 ───────────────────────────────────────


def _safe_run(cmd: list, timeout: int, step_name: str, env: dict):
    """运行子进程，流式读取 stderr 实时输出。超时/异常不崩溃。

    Returns:
        dict: {"stdout": str, "stderr": str, "returncode": int} or {"error": str}
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        # 同时读取 stdout 和 stderr，避免管道缓冲区写满导致死锁
        def read_stream(stream, lines_list, prefix):
            for line in stream:
                line = line.rstrip()
                if line:
                    _log(f"  {line}")
                lines_list.append(line)

        t_stdout = threading.Thread(
            target=read_stream, args=(proc.stdout, stdout_lines, "  "), daemon=True
        )
        t_stderr = threading.Thread(
            target=read_stream, args=(proc.stderr, stderr_lines, "  "), daemon=True
        )
        t_stdout.start()
        t_stderr.start()

        try:
            proc.wait(timeout=timeout)
            t_stdout.join(timeout=1)
            t_stderr.join(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            _log(f"    {step_name}: 超时 ({timeout}s)")
            return {"error": "timeout"}

        return {
            "stdout": proc.stdout.read(),  # type: ignore[union-attr]
            "stderr": "\n".join(stderr_lines),
            "returncode": proc.returncode,
        }
    except Exception as e:
        _log(f"    {step_name}: 异常 {e}")
        return {"error": str(e)}


# ── 第一步：CLI 冷启 ─────────────────────────────────────────


def _step1_cli_cold(
    source_dir: str, output_dir: str, timeout_query: int, ocr_config: dict | None = None
):
    """CLI 冷启分阶段。依次执行全管线，记录数据到 step1.json。"""
    _log("=" * 50)
    _log("第一步：CLI 冷启分阶段")

    python = sys.executable
    cli_module = "pilotstd.cli.commands"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    if ocr_config:
        env["OCR_BAIDU_API_KEY"] = ocr_config.get("baidu_api_key", "")
        env["OCR_BAIDU_SECRET_KEY"] = ocr_config.get("baidu_secret_key", "")
        env["OCR_TENCENT_SECRET_ID"] = ocr_config.get("tencent_secret_id", "")
        env["OCR_TENCENT_SECRET_KEY"] = ocr_config.get("tencent_secret_key", "")
        env["OCR_ALIYUN_ACCESS_KEY_ID"] = ocr_config.get("aliyun_access_key_id", "")
        env["OCR_ALIYUN_ACCESS_KEY_SECRET"] = ocr_config.get(
            "aliyun_access_key_secret", ""
        )
        _providers = []
        if ocr_config.get("baidu_api_key"):
            _providers.append("百度")
        if ocr_config.get("tencent_secret_id"):
            _providers.append("腾讯")
        if ocr_config.get("aliyun_access_key_id"):
            _providers.append("阿里云")
        _log(f"OCR 凭证已注入环境变量: {', '.join(_providers) if _providers else '无'}")

    results: dict = {"step": 1, "ts": TS, "checkpoints": {}}

    # scan — 快速扫描，保持 subprocess.run + 异常保护
    _log("  1.1 scan...")
    t0 = time.time()
    scan_count = 0
    scan_stdout = ""
    try:
        r = subprocess.run(
            [
                python,
                "-m",
                cli_module,
                "--storage-root",
                output_dir,
                "scan",
                source_dir,
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        scan_stdout = r.stdout if r.stdout else ""
        if r.returncode == 0:
            try:
                scan_data = json.loads(r.stdout if r.stdout else "[]")
                scan_count = len(scan_data)
            except json.JSONDecodeError:
                scan_count = len(
                    [line for line in (r.stdout or "").splitlines() if line.strip()]
                )
        results["checkpoints"]["scan"] = {
            "count": scan_count,
            "rc": r.returncode,
            "elapsed_s": round(time.time() - t0, 1),
        }
        _log(
            f"    scan: {scan_count} 条, rc={r.returncode}, {results['checkpoints']['scan']['elapsed_s']}s"
        )
    except subprocess.TimeoutExpired:
        _log("    scan: 超时")
        results["checkpoints"]["scan"] = {
            "count": 0,
            "error": "timeout",
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        _log(f"    scan: 异常 {e}")
        results["checkpoints"]["scan"] = {
            "count": 0,
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 1),
        }

    # query
    _log("  1.2 query...")
    # 写标准号列表文件供 query --file 使用
    nums_file = os.path.join(RESULT_DIR, "step1_scan_nums.txt")
    query_failed = False
    with open(nums_file, "w", encoding="utf-8") as f:
        if scan_count > 0 and results["checkpoints"]["scan"].get("rc", 1) == 0:
            try:
                for item in json.loads(scan_stdout):
                    code = item.get("code", "")
                    number = item.get("number", None)
                    if code and number is not None:
                        fn = item.get("full_number", "")
                        if not fn:
                            # 兼容旧 scan JSON 缺少 full_number 的情况
                            suffix = item.get("num_suffix", "")
                            fn = f"{code} {number}{suffix}"
                            part = item.get("part")
                            if part is not None:
                                fn += f".{part}"
                            fn += f"-{item.get('year', '')}"
                        f.write(fn + "\n")
            except json.JSONDecodeError:
                pass

    # query — 流式读取 + 异常保护（查询可能耗时 30+ 分钟）
    t0 = time.time()
    r = _safe_run(
        [
            python,
            "-m",
            cli_module,
            "--storage-root",
            output_dir,
            "query",
            "--file",
            nums_file,
        ],
        timeout=timeout_query or 3600,
        step_name="query",
        env=env,
    )
    # 从 query 输出解析分类计数 + 逐桶统计
    dl_count = ex_count = pe_count = exact_count = 0
    bucket_stats = {}  # {key: total}
    funnel = {}  # {total, ok, overflow, pending}
    timeline_elapsed = 0.0
    cooldown_count = 0
    csres_info = {}  # {processed, failures}
    overflow_count = 0
    water_level = {}  # {ahbz_remain, njbz_remain}
    parse_failures = 0  # 日志解析失败行数
    # 需要解析的日志标记关键字集合
    _PARSE_MARKERS = (
        "[BUCKET]",
        "[FUNNEL]",
        "[TIMELINE]",
        "[COOLDOWN]",
        "[ROTATOR]",
        "[CSRES_INTERVAL]",
        "[CSRES]",
        "[OVERFLOW]",
        "[WATER]",
    )
    if "error" not in r:
        # 预初始化 query checkpoint，供循环内解析代码追加数据
        results["checkpoints"]["query"] = {}
        for line in (r.get("stdout", "") + r.get("stderr", "")).splitlines():
            _matched = False  # 本行是否有正则匹配成功
            if "download=" in line and "expire=" in line:
                m = re.search(r"download=(\d+).*?expire=(\d+).*?pending=(\d+)", line)
                if m:
                    _matched = True
                    dl_count, ex_count, pe_count = (
                        int(m.group(1)),
                        int(m.group(2)),
                        int(m.group(3)),
                    )
            m2 = re.search(r"(\d+)\s+精确", line)
            if m2:
                _matched = True
                exact_count = int(m2.group(1))
            # 逐桶日志解析
            m3 = re.match(
                r".*\[BUCKET\]\s+(\S+)\s+total=(\d+)\s+done=(\d+)\s+overflow=(\d+)\s+elapsed=([\d.]+)",
                line,
            )
            if m3:
                _matched = True
                bucket_stats[m3.group(1)] = {
                    "total": int(m3.group(2)),
                    "done": int(m3.group(3)),
                    "overflow": int(m3.group(4)),
                    "elapsed_s": float(m3.group(5)),
                }
            m4 = re.match(
                r".*\[FUNNEL\]\s+total=(\d+)\s+ok=(\d+)\s+overflow=(\d+)\s+pending=(\d+)",
                line,
            )
            if m4:
                _matched = True
                funnel = {
                    "total": int(m4.group(1)),
                    "ok": int(m4.group(2)),
                    "overflow": int(m4.group(3)),
                    "pending": int(m4.group(4)),
                }
            m5 = re.match(
                r".*\[TIMELINE\]\s+query_bucketed_done\s+total=(\d+)\s+elapsed=([\d.]+)",
                line,
            )
            if m5:
                _matched = True
                timeline_elapsed = float(m5.group(2))
            if "[COOLDOWN]" in line:
                cooldown_count += 1
                # 解析新版结构化格式: [COOLDOWN] site=X action=enter reason=Y cooldown_s=Z
                cs = re.search(r"\[COOLDOWN\]\s+site=(\S+)\s+action=(\S+)", line)
                if cs:
                    _matched = True
                    site_name = cs.group(1)
                    action = cs.group(2)
                    if "cooldown_details" not in results["checkpoints"]["query"]:
                        results["checkpoints"]["query"]["cooldown_details"] = {}
                    cdetails = results["checkpoints"]["query"]["cooldown_details"]
                    if site_name not in cdetails:
                        cdetails[site_name] = {}
                    cdetails[site_name][action] = cdetails[site_name].get(action, 0) + 1
            # 解析 ROTATOR 里程碑日志
            mr = re.match(
                r".*\[ROTATOR\]\s+site=(\S+)\s+request_count=(\d+)/(\d+)\s+\((\d+)%\)\s+daily_count=(\d+)/(\d+)",
                line,
            )
            if mr:
                _matched = True
                if "rotator_milestones" not in results["checkpoints"]["query"]:
                    results["checkpoints"]["query"]["rotator_milestones"] = []
                results["checkpoints"]["query"]["rotator_milestones"].append(
                    {
                        "site": mr.group(1),
                        "request_count": int(mr.group(2)),
                        "max_requests": int(mr.group(3)),
                        "pct": int(mr.group(4)),
                        "daily_count": int(mr.group(5)),
                        "daily_limit": int(mr.group(6)),
                    }
                )
            # 解析 CSRES_INTERVAL 日志（每条约 5-10s）
            mi = re.match(
                r".*\[CSRES_INTERVAL\]\s+actual=([\d.]+)s\s+target=([\d.]+)s", line
            )
            if mi:
                _matched = True
                if "csres_intervals" not in results["checkpoints"]["query"]:
                    results["checkpoints"]["query"]["csres_intervals"] = []
                results["checkpoints"]["query"]["csres_intervals"].append(
                    {"actual": float(mi.group(1)), "target": float(mi.group(2))}
                )
            m6 = re.match(r".*\[CSRES\]\s+processed=(\d+)\s+failures=(\d+)", line)
            if m6:
                _matched = True
                csres_info = {
                    "processed": int(m6.group(1)),
                    "failures": int(m6.group(2)),
                }
            m7 = re.match(r".*\[OVERFLOW\]\s+events=(\d+)", line)
            if m7:
                _matched = True
                overflow_count = int(m7.group(1))
            m8 = re.match(
                r".*\[WATER\]\s+ahbz_overflow_remain=(\d+)\s+njbz365_remain=(\d+)", line
            )
            if m8:
                _matched = True
                water_level = {
                    "ahbz_remain": int(m8.group(1)),
                    "njbz_remain": int(m8.group(2)),
                }
            # 检测含标记但解析失败的行
            _has_marker = any(mk in line for mk in _PARSE_MARKERS)
            if _has_marker and not _matched:
                parse_failures += 1
        results["checkpoints"]["query"].update(
            {
                "download": dl_count,
                "expire": ex_count,
                "pending": pe_count,
                "exact": exact_count,
                "total": dl_count + ex_count + pe_count,
                "rc": r.get("returncode", 0),
                "elapsed_s": round(time.time() - t0, 1),
                "parse_failures": parse_failures,
            }
        )
        if bucket_stats:
            results["checkpoints"]["query"]["bucket_stats"] = bucket_stats
        if funnel:
            results["checkpoints"]["query"]["funnel"] = funnel
        if timeline_elapsed:
            results["checkpoints"]["query"]["funnel_elapsed_s"] = timeline_elapsed
        results["checkpoints"]["query"]["cooldown_count"] = cooldown_count
        if csres_info:
            results["checkpoints"]["query"]["csres"] = csres_info
        if overflow_count:
            results["checkpoints"]["query"]["overflow_events"] = overflow_count
        if water_level:
            results["checkpoints"]["query"]["water_level"] = water_level
        _log(
            f"    query: download={dl_count} expire={ex_count} pending={pe_count} exact={exact_count}, rc={r.get('returncode', 0)}"
        )
        if bucket_stats:
            _log(f"    bucket_stats: {bucket_stats}")
        if funnel:
            _log(
                f"    funnel: total={funnel['total']} ok={funnel['ok']} overflow={funnel['overflow']} pending={funnel['pending']} elapsed={timeline_elapsed}s"
            )
        if csres_info:
            _log(
                f"    csres: processed={csres_info['processed']} failures={csres_info['failures']}"
            )
        if overflow_count:
            _log(f"    overflow_events: {overflow_count}")
        if water_level:
            _log(
                f"    water: ahbz_remain={water_level['ahbz_remain']} njbz_remain={water_level['njbz_remain']}"
            )
    else:
        query_failed = True
        results["checkpoints"]["query"] = {
            "error": r["error"],
            "elapsed_s": round(time.time() - t0, 1),
        }
        _log(f"    query 失败: {r['error']}，跳过后续下载步骤")

    # download（如果有可下载的） — 流式读取 + 异常保护
    dl_success = 0
    if dl_count > 0 and not query_failed:
        _log(f"  1.3 download ({dl_count} 条)...")
        t0 = time.time()
        r = _safe_run(
            [python, "-m", cli_module, "--storage-root", output_dir, "download"],
            timeout=timeout_query or 3600,
            step_name="download",
            env=env,
        )
        if "error" not in r:
            dl_success = (r.get("stdout", "") + r.get("stderr", "")).count("成功") + (
                r.get("stdout", "") + r.get("stderr", "")
            ).count("跳过")
            results["checkpoints"]["download"] = {
                "success": dl_success,
                "rc": r.get("returncode", 0),
                "elapsed_s": round(time.time() - t0, 1),
            }
            _log(f"    download: {dl_success} 成功/跳过, rc={r.get('returncode', 0)}")
        else:
            results["checkpoints"]["download"] = {
                "success": 0,
                "error": r["error"],
                "elapsed_s": round(time.time() - t0, 1),
            }
            _log(f"    download 失败: {r['error']}")
    elif query_failed:
        results["checkpoints"]["download"] = {
            "success": 0,
            "rc": 0,
            "elapsed_s": 0,
            "skipped": "query_failed",
        }
        _log("    download: query 失败，跳过")
    else:
        results["checkpoints"]["download"] = {"success": 0, "rc": 0, "elapsed_s": 0}
        _log("    download: 队列为空，跳过")

    # normalize — 异常保护
    _log("  1.4 normalize...")
    t0 = time.time()
    try:
        r = subprocess.run(
            [
                python,
                "-m",
                cli_module,
                "--storage-root",
                output_dir,
                "normalize",
                source_dir,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        results["checkpoints"]["normalize"] = {
            "rc": r.returncode,
            "elapsed_s": round(time.time() - t0, 1),
        }
        _log(f"    normalize: rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    normalize: 超时")
        results["checkpoints"]["normalize"] = {
            "error": "timeout",
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        _log(f"    normalize: 异常 {e}")
        results["checkpoints"]["normalize"] = {
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 1),
        }

    # organize — 异常保护
    _log("  1.5 organize...")
    t0 = time.time()
    org_moved = 0
    try:
        r = subprocess.run(
            [
                python,
                "-m",
                cli_module,
                "--storage-root",
                output_dir,
                "organize",
                "--format",
                "json",
                "--source",
                source_dir,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        try:
            org_data = json.loads(r.stdout.splitlines()[-1] if r.stdout else "{}")
            org_moved = org_data.get("moved", 0)
        except json.JSONDecodeError:
            pass
        results["checkpoints"]["organize"] = {
            "moved": org_moved,
            "rc": r.returncode,
            "elapsed_s": round(time.time() - t0, 1),
        }
        # 汇报 file_index 写入量
        _fi_count = 0
        try:
            from pilotstd.core.config import get_data_dir as _gdd
            from pilotstd.core.db import Database as _DB

            _fi_db = _DB(os.path.join(_gdd(), "pilotstd.db"))
            _fi_row = _fi_db.fetchone("SELECT COUNT(*) as c FROM file_index")
            _fi_count = _fi_row["c"] if _fi_row else 0
        except Exception:
            pass
        results["checkpoints"]["organize"]["file_index_rows"] = _fi_count
        _log(
            f"    organize: moved={org_moved}, file_index={_fi_count} rows, rc={r.returncode}"
        )
    except subprocess.TimeoutExpired:
        _log("    organize: 超时")
        results["checkpoints"]["organize"] = {
            "moved": 0,
            "error": "timeout",
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        _log(f"    organize: 异常 {e}")
        results["checkpoints"]["organize"] = {
            "moved": 0,
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 1),
        }

    # ── 关键步骤失败检测：scan/query/normalize/organize 任一失败则终止 ──
    _critical_ok = all(
        results["checkpoints"].get(s, {}).get("rc", 1) == 0
        for s in ("scan", "query", "normalize", "organize")
    )
    if not _critical_ok:
        _failed = [
            s
            for s in ("scan", "query", "normalize", "organize")
            if results["checkpoints"].get(s, {}).get("rc", 1) != 0
        ]
        _log(f"关键步骤失败: {', '.join(_failed)}，跳过 expire/announce/task/recheck")
        # 为非关键步骤填充跳过状态
        for _s in ("expire", "announce", "task", "recheck"):
            results["checkpoints"].setdefault(
                _s,
                {"rc": 0, "skipped": True, "elapsed_s": 0, "reason": "关键步骤已失败"},
            )
        # 直接跳到汇总
        announce_info = {}
        results["summary"] = {
            "scan_count": scan_count,
            "query_download": dl_count,
            "query_expire": ex_count,
            "query_pending": pe_count,
            "query_exact": exact_count,
            "download_success": dl_success,
            "organize_moved": org_moved,
            "announce_rc": 1,
            "announce_total": 0,
        }
        step1_path = os.path.join(RESULT_DIR, "step1.json")
        with open(step1_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        _log(f"第一步提前终止: {step1_path}")
        return results

    # expire — 异常保护
    _log("  1.6 expire...")
    t0 = time.time()
    try:
        r = subprocess.run(
            [
                python,
                "-m",
                cli_module,
                "--storage-root",
                output_dir,
                "expire",
                output_dir,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        results["checkpoints"]["expire"] = {
            "rc": r.returncode,
            "elapsed_s": round(time.time() - t0, 1),
        }
        _log(f"    expire: rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    expire: 超时")
        results["checkpoints"]["expire"] = {
            "error": "timeout",
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        _log(f"    expire: 异常 {e}")
        results["checkpoints"]["expire"] = {
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 1),
        }

    # announce（公告闭环 + 三表写完）— 各类型限制 10 条
    _log("  1.7 announce gb/hb/db (各10条)...")
    t0 = time.time()
    announce_rc = 0
    announce_total = 0
    try:
        import os as _os

        from pilotstd.announcement.adapters.samr_db import SamrDbAdapter
        from pilotstd.announcement.adapters.samr_gb import SamrGbAdapter
        from pilotstd.announcement.adapters.samr_hb import SamrHbAdapter
        from pilotstd.announcement.matcher import AnnouncementMatcher
        from pilotstd.announcement.ocr import create_ocr_provider
        from pilotstd.core.config import ConfigManager, get_data_dir
        from pilotstd.core.db import Database
        from pilotstd.query.network import CHROME_UA, safe_request

        cfg = ConfigManager(_os.path.join(get_data_dir(), "config.json"))
        db_path = _os.path.join(get_data_dir(), "pilotstd.db")
        db = Database(db_path)
        matcher = AnnouncementMatcher(db)

        # OCR 凭证优先从 --config JSON 读取，空值回退到 ConfigManager
        _ocr_cfg = ocr_config or {}
        _ocr_baidu_key = _ocr_cfg.get("baidu_api_key") or cfg.get(
            "ocr.baidu_api_key", ""
        )
        _ocr_baidu_sec = _ocr_cfg.get("baidu_secret_key") or cfg.get(
            "ocr.baidu_secret_key", ""
        )
        _ocr_tc_id = _ocr_cfg.get("tencent_secret_id") or cfg.get(
            "ocr.tencent_secret_id", ""
        )
        _ocr_tc_key = _ocr_cfg.get("tencent_secret_key") or cfg.get(
            "ocr.tencent_secret_key", ""
        )
        _ocr_ali_id = _ocr_cfg.get("aliyun_access_key_id") or cfg.get(
            "ocr.aliyun_access_key_id", ""
        )
        _ocr_ali_key = _ocr_cfg.get("aliyun_access_key_secret") or cfg.get(
            "ocr.aliyun_access_key_secret", ""
        )
        _ocr_local = {
            "baidu_api_key": _ocr_baidu_key,
            "baidu_secret_key": _ocr_baidu_sec,
            "tencent_secret_id": _ocr_tc_id,
            "tencent_secret_key": _ocr_tc_key,
            "aliyun_access_key_id": _ocr_ali_id,
            "aliyun_access_key_secret": _ocr_ali_key,
        }
        ocr_provider = (
            create_ocr_provider(_ocr_local) if any(_ocr_local.values()) else None
        )
        _log(f"    OCR provider: {ocr_provider.name if ocr_provider else 'None'}")

        for atype, AdapterCls in [
            ("gb", SamrGbAdapter),
            ("hb", SamrHbAdapter),
            ("db", SamrDbAdapter),
        ]:
            try:
                adapter = AdapterCls()

                # 猴子补丁：_fetch_list 只拿第一页 10 条
                def _limited_fetch(self, since_date, page_size):
                    import requests

                    s = requests.Session()
                    s.headers["User-Agent"] = CHROME_UA
                    resp = safe_request(
                        s,
                        "GET",
                        self._list_url,
                        self.site_name,
                        timeout=120,
                        params={
                            "pageNumber": 1,
                            "pageSize": 10,
                            "sortName": "NOTICE_DATE",
                            "sortOrder": "desc",
                        },
                    )
                    if resp is None:
                        return []
                    try:
                        data = resp.json()
                    except Exception:
                        return []
                    rows = data.get("rows", [])[:10]
                    return [
                        {
                            "pid": r.get("PID", ""),
                            "code": r.get("CODE", ""),
                            "title": r.get("C_TITLE", ""),
                            "notice_date": r.get("NOTICE_DATE", ""),
                            "std_count": r.get("STD_COUNT", ""),
                        }
                        for r in rows
                    ]

                adapter._fetch_list = _limited_fetch.__get__(adapter, type(adapter))  # type: ignore[method-assign]

                # 复用现有逻辑：fetch + parse + match
                items = adapter.fetch_announcements(
                    since_date="", ocr_provider=ocr_provider
                )
                if not items:
                    _log(f"    announce {atype}: 无公告/解析为空")
                    continue
                announce_total += len(items)
                result = matcher.match_and_update(
                    items, source_site=adapter.source_site
                )
                _log(
                    f"    announce {atype}: {len(items)} 条标准, "
                    f"matched={result.get('matched', 0)} "
                    f"updated={result.get('updated', 0)}"
                )
            except Exception as e:
                _log(f"    announce {atype}: 异常 {e}")
                announce_rc = 1
    except Exception as e:
        _log(f"    announce 初始化失败: {e}")
        announce_rc = 1
    results["checkpoints"]["announce"] = {
        "rc": announce_rc,
        "total_ann": announce_total,
        "elapsed_s": round(time.time() - t0, 1),
    }

    # task — 异常保护
    _log("  1.8 task...")
    t0 = time.time()
    try:
        r = subprocess.run(
            [
                python,
                "-m",
                cli_module,
                "--storage-root",
                output_dir,
                "task",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        results["checkpoints"]["task"] = {
            "rc": r.returncode,
            "elapsed_s": round(time.time() - t0, 1),
        }
        _log(f"    task: rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    task: 超时")
        results["checkpoints"]["task"] = {
            "error": "timeout",
            "elapsed_s": round(time.time() - t0, 1),
        }
    except Exception as e:
        _log(f"    task: 异常 {e}")
        results["checkpoints"]["task"] = {
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 1),
        }

    # recheck — 报告公告匹配结果（公告已在 announce 步骤完成验证）
    # 仅 1.1~1.8 全部成功时执行（文档 §2 决策表）
    _prior_ok = all(
        results["checkpoints"].get(s, {}).get("rc", 1) == 0
        for s in (
            "scan",
            "query",
            "download",
            "normalize",
            "organize",
            "expire",
            "announce",
            "task",
        )
    )
    if _prior_ok:
        _log("  1.9 recheck...")
        t0 = time.time()
        recheck_checked = 0
        recheck_updated = 0
        recheck_rc = 0
        try:
            import os as _os

            from pilotstd.core.config import get_data_dir
            from pilotstd.core.db import Database

            db_path = _os.path.join(get_data_dir(), "pilotstd.db")
            db = Database(db_path)
            _ann_rows = db.fetchall(
                "SELECT COUNT(DISTINCT standard_number) as c FROM announcement_cache"
            )
            recheck_checked = _ann_rows[0]["c"] if _ann_rows else 0
            recheck_updated = (
                results["checkpoints"].get("announce", {}).get("total_ann", 0)
            )
            _log(f"    recheck: checked={recheck_checked} updated={recheck_updated}")
        except Exception as e:
            _log(f"    recheck: 异常 {e}")
            recheck_rc = 1
    else:
        _log("  1.9 recheck: 跳过（前序步骤存在失败，数据不完整）")
        recheck_rc = 0
        recheck_checked = 0
        recheck_updated = 0
    results["checkpoints"]["recheck"] = {
        "rc": recheck_rc,
        "checked": recheck_checked,
        "updated": recheck_updated,
        "elapsed_s": round(time.time() - t0, 1),
    }

    # 汇总 + 写入
    announce_info = results["checkpoints"].get("announce", {})
    results["summary"] = {
        "scan_count": scan_count,
        "query_download": dl_count,
        "query_expire": ex_count,
        "query_pending": pe_count,
        "query_exact": exact_count,
        "download_success": dl_success,
        "organize_moved": org_moved,
        "announce_rc": announce_info.get("rc", 1),
        "announce_total": announce_info.get("total_ann", 0),
    }
    step1_path = os.path.join(RESULT_DIR, "step1.json")
    with open(step1_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    _log(f"第一步完成: {step1_path}")
    return results


# ── 第二步：WinUI 热启 ────────────────────────────────────────


def _step2_winui_hot(
    source_dir: str, output_dir: str, step1_path: str, timeout_auto: int
):
    """pytest 调用 WinUI 测试，热启 auto + 交叉对比。"""
    _log("=" * 50)
    _log("第二步：WinUI 热启（交叉对比）")

    step2_path = os.path.join(RESULT_DIR, "step2.json")

    try:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                os.path.join(ROOT, "tests", "stress_winui.py"),
                "-v",
                "-s",
                "--source",
                source_dir,
                "--output",
                output_dir,
                "--step1",
                step1_path,
                "--step2",
                step2_path,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_auto or 1800,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
        )
        _log(f"WinUI pytest: rc={r.returncode}")
        if r.stdout:
            # 只打印 pytest 结果行
            for line in r.stdout.splitlines():
                if "PASSED" in line or "FAILED" in line or "ERROR" in line:
                    _log(f"  {line.strip()}")
        if r.returncode != 0 and r.stderr:
            _log(f"  stderr: {r.stderr[-500:]}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        _log("WinUI pytest: 超时")
        return False
    except Exception as e:
        _log(f"WinUI pytest: 异常 {e}")
        return False


# ── 第三步：Docker Web API ────────────────────────────────────


def _step3_docker(docker_url: str, docker_user: str, docker_pass: str):
    """Docker 部署态验证。凭证由 load_docker_credentials 保证非空。"""
    _log("=" * 50)
    _log(f"第三步：Docker Web API → {docker_url}")

    env = os.environ.copy()
    env["PILOTSTD_BASE_URL"] = docker_url
    env["PILOTSTD_USERNAME"] = docker_user
    env["PILOTSTD_PASSWORD"] = docker_pass
    env["STRESS_STEP3_PATH"] = os.path.join(RESULT_DIR, "step3.json")

    try:
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tests", "stress_web.py")],
            capture_output=True,
            text=True,
            timeout=360,
            cwd=ROOT,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        _log(f"Docker test: rc={r.returncode}")
        if r.stdout:
            for line in r.stdout.splitlines():
                if "PASS" in line or "FAIL" in line or "SKIP" in line:
                    _log(f"  {line.strip()}")
        # 读取 step3.json 汇总
        _step3_path = os.path.join(RESULT_DIR, "step3.json")
        if os.path.exists(_step3_path):
            try:
                with open(_step3_path, "r", encoding="utf-8") as _f:
                    _s3 = json.load(_f)
                _log(
                    f"Docker 统计: total={_s3.get('total', 0)} "
                    f"passed={_s3.get('passed', 0)} failed={_s3.get('failed', 0)} "
                    f"skipped={_s3.get('skipped', 0)}"
                )
                for _fitem in _s3.get("failures", []):
                    _log(f"  FAIL {_fitem['name']}: {_fitem['detail']}")
            except Exception:
                pass
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        _log("Docker test: 超时")
        return False
    except Exception as e:
        _log(f"Docker test: 异常 {e}")
        return False


# ── 第四步：汇总判定 ──────────────────────────────────────────


def _step4_verdict(
    step1_ok: bool,
    step2_ok: bool,
    step3_ok: bool,
    skip_winui: bool,
    skip_docker: bool,
    step1_data: dict | None = None,
    adapter_report_ok: bool = True,
    credential_ok: bool = True,
    credential_detail: str = "",
    flow_status: str = "",
):
    """汇总判定，写入方案执行记录。"""
    _log("=" * 50)
    _log("汇总判定")

    verdict = "PASS"
    lines = []
    if flow_status:
        lines.append(f"流程状态: {flow_status}")
        if "TERMINATED" in flow_status:
            verdict = "FAIL"
    if skip_docker:
        lines.append("凭证预检: SKIP — Docker 步骤已跳过")
    else:
        lines.append(
            f"凭证预检: {'PASS' if credential_ok else 'FAIL'} — {credential_detail}"
        )
        if not credential_ok:
            verdict = "FAIL"
    lines.append(f"第一步 CLI 冷启: {'PASS' if step1_ok else 'FAIL'}")
    if skip_winui:
        lines.append("第二步 WinUI 热启: SKIP")
    else:
        lines.append(f"第二步 WinUI 热启: {'PASS' if step2_ok else 'FAIL'}")
        if not step2_ok:
            verdict = "FAIL"
    if skip_docker:
        lines.append("第三步 Docker: SKIP")
    else:
        lines.append(f"第三步 Docker: {'PASS' if step3_ok else 'FAIL'}")
        if not step3_ok:
            verdict = "FAIL"
    lines.append(f"适配器统计报告: {'PASS' if adapter_report_ok else 'FAIL'}")
    if not adapter_report_ok:
        verdict = "FAIL"
    if not step1_ok:
        verdict = "FAIL"

    for line in lines:
        _log(line)

    # 逐桶指标对比基线
    if step1_data:
        q = step1_data.get("checkpoints", {}).get("query", {})
        funnel = q.get("funnel", {})
        cooldown = q.get("cooldown_count", -1)
        cooldown_details = q.get("cooldown_details", {})
        elapsed = q.get("funnel_elapsed_s", 0)
        csres = q.get("csres", {})
        csres_intervals = q.get("csres_intervals", [])
        water = q.get("water_level", {})
        milestones = q.get("rotator_milestones", [])
        parse_failures = q.get("parse_failures", 0)
        _log(
            f"逐桶指标: pending={funnel.get('pending', '?')} "
            f"overflow={funnel.get('overflow', '?')} "
            f"cooldown={cooldown} elapsed={elapsed:.0f}s "
            f"parse_failures={parse_failures}"
        )
        if cooldown_details:
            for site, actions in sorted(cooldown_details.items()):
                enter = actions.get("enter", 0)
                exit_ = actions.get("exit", 0)
                status = actions.get("status", 0)
                overflow = actions.get("overflow_skip", 0)
                _log(
                    f"  冷却详情 site={site} enter={enter} exit={exit_} status={status} overflow_skip={overflow}"
                )
        if milestones:
            _log(f"  ROTATOR里程碑: {len(milestones)} 条")
            for m in milestones:
                _log(
                    f"    {m['site']} {m['request_count']}/{m['max_requests']} ({m['pct']}%) daily={m['daily_count']}/{m['daily_limit']}"
                )
        if csres:
            _log(
                f"csres: processed={csres.get('processed', '?')} failures={csres.get('failures', '?')}"
            )
        if csres_intervals:
            actuals = [x["actual"] for x in csres_intervals]
            _log(
                f"csres间隔: min={min(actuals):.1f}s max={max(actuals):.1f}s avg={sum(actuals) / len(actuals):.1f}s count={len(actuals)}"
            )
        if water:
            _log(
                f"water: ahbz_remain={water.get('ahbz_remain', '?')} njbz_remain={water.get('njbz_remain', '?')}"
            )
        _log("基线(0617逐轮): pending=206 elapsed=1440s cooled=1348")
        if funnel.get("pending", 999) <= 206 and cooldown == 0:
            _log("逐桶对比: 优于基线 ✓")
        else:
            _log("逐桶对比: 未达基线，需分析 ✗")

    _log(f"判定: {verdict}")

    verdict_path = os.path.join(RESULT_DIR, "verdict.json")
    with open(verdict_path, "w", encoding="utf-8") as f:
        json.dump(
            {"verdict": verdict, "steps": lines, "ts": TS},
            f,
            ensure_ascii=False,
            indent=2,
        )
    _log(f"结果: {RESULT_DIR}")
    return verdict


# ── main ──────────────────────────────────────────────────────


def _yes(args):
    """--yes 模式下跳过所有交互确认。"""
    return getattr(args, "yes", False)


def main():
    global RESULT_DIR, TS
    args = _parse_args()

    # 加载本地压测配置（JSON，不上传 git），命令行参数优先
    from _stress_utils import load_docker_credentials  # type: ignore[import-not-found]

    cfg = _load_test_config(getattr(args, "config", None))  # type: ignore[arg-type]
    ocr_cfg = cfg.get("ocr", {})
    # Docker 凭证通过统一加载器读取（--config JSON > 环境变量）
    _creds = {}
    if not args.skip_docker:
        _creds = load_docker_credentials(getattr(args, "config", None))
    docker_url = args.docker_url or _creds.get("base_url", "")
    docker_user = args.docker_user or _creds.get("username", "")
    docker_pass = args.docker_pass or _creds.get("password", "")
    TS = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULT_DIR = args.result_dir or os.path.join(ROOT, "logs", f"stress_{TS}")
    os.makedirs(RESULT_DIR, exist_ok=True)

    # 冷却状态清理：每次压测启动时重置 rotator_state，确保冷启动
    try:
        import sqlite3 as _sqlite3

        from pilotstd.core.config import get_data_dir as _gcd

        _db_path = args.db_path or os.path.join(_gcd(), "pilotstd.db")
        if os.path.exists(_db_path):
            _conn = _sqlite3.connect(_db_path)
            _conn.execute("DELETE FROM rotator_state")
            _conn.commit()
            _conn.close()
            _log("[CLEANUP] rotator_state 已清空，冷却状态重置")
    except Exception as _e:
        _log(f"[WARN] rotator_state 清理失败，跳过: {_e}")

    _log(f"PilotStd 全量压力测试驱动器 v4.2 | {TS}")
    _log(f"源: {args.source}  输出: {args.output}")
    _log(f"结果目录: {RESULT_DIR}")

    # Python 环境自检：确保 cryptography 等依赖可用
    _log(f"Python: {sys.executable}")
    try:
        import cryptography  # noqa: F401
    except ModuleNotFoundError:
        _log(
            f"错误: cryptography 未安装，当前 Python 可能不是虚拟环境。\n"
            f"  sys.executable = {sys.executable}\n"
            f"  请使用虚拟环境 Python 运行压测:\n"
            f"  D:\\PilotStd\\pilotstd_env\\Scripts\\python.exe tests/stress_driver.py ..."
        )
        sys.exit(1)

    # winui-only 模式：跳过 CLI 冷启，直接跑 WinUI
    if getattr(args, "winui_only", False):
        _log("winui-only 模式：跳过 CLI 冷启")
        step1 = args.step1 or os.path.join(RESULT_DIR, "step1.json")
        if not os.path.exists(step1):
            _log(f"错误: step1.json 不存在 ({step1})")
            return 1
        step2_ok = _step2_winui_hot(args.source, args.output, step1, args.timeout_auto)
        step3_ok = True
        if not args.skip_docker:
            step3_ok = _step3_docker(docker_url, docker_user, docker_pass)
        verdict = _step4_verdict(
            True, step2_ok, step3_ok, False, args.skip_docker, None
        )
        return 0 if verdict == "PASS" else 1

    # 第〇步：环境自检
    _log("=" * 50)
    _log("第〇步：环境自检")
    _step0_check_preconditions(args.source, args.output, args.skip_docker, docker_url)
    _log("-" * 40)
    if not _yes(args):
        ans = input("是否开始测试？(y/n): ").strip().lower()
        if ans not in ("y", "yes"):
            _log("已取消。")
            return 0

    # 第〇步：复位 + 清 DB（仅当需要执行 CLI 或 WinUI 时才做）
    # --stop-after=cli 时跳过复位和清DB，保留数据供后续热启使用
    _stop_after_cli = getattr(args, "stop_after", None) == "cli"
    _skip_reset = (
        getattr(args, "skip_cli", False) and getattr(args, "skip_winui", False)
    ) or _stop_after_cli
    if _skip_reset:
        _log("第〇步：跳过复位源目录 + 清 DB（--skip-cli --skip-winui）")
    else:
        _log("第〇步：复位源目录 + 清 DB")
        if os.path.isdir(args.output):
            _step0_reset_source(args.source, args.output)
        if getattr(args, "keep_db", False) or _stop_after_cli:
            _log("--keep-db：跳过清 DB，保留缓存和索引")
        else:
            _step0_clear_db(args.db_path)

    # 第〇步：自检（纯逻辑秒级验证，零网络依赖）
    _log("第〇步：自检（stress_selfcheck）")
    sc_rc = subprocess.run(
        [
            sys.executable,
            os.path.join(ROOT, "tests", "stress_selfcheck.py"),
            "--output",
            args.output,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if sc_rc.returncode != 0:
        _log("自检失败，终止后续步骤")
        _log(sc_rc.stderr[-500:] if sc_rc.stderr else "")
        sys.exit(1)
    _log("自检通过")

    # 凭证预检（Docker 不可达时不影响后续，但凭证无效则提前退出）
    credential_ok = True
    credential_detail = ""
    if not args.skip_docker and docker_url:
        _log("凭证预检...")
        credential_ok, credential_detail = _step0_verify_credentials(
            docker_url, docker_user, docker_pass
        )
        _log(f"凭证预检: {'PASS' if credential_ok else 'FAIL'} — {credential_detail}")
        if not credential_ok:
            _log("凭证无效，终止后续步骤")
            sys.exit(1)
    elif args.skip_docker:
        credential_detail = "Docker 步骤已跳过"

    # 第一步：CLI 冷启
    if getattr(args, "skip_cli", False):
        _log("第一步：跳过（--skip-cli）")
        flow_status = "SKIPPED"
        _step1_path = getattr(args, "step1", None)
        if _step1_path and os.path.exists(_step1_path):
            with open(_step1_path, "r", encoding="utf-8") as _f:
                step1 = json.load(_f)
            _log(f"从 {_step1_path} 加载 step1 数据")
            step1_ok = all(
                step1["checkpoints"].get(c, {}).get("rc", 1) == 0
                for c in [
                    "scan",
                    "query",
                    "download",
                    "normalize",
                    "organize",
                    "expire",
                    "announce",
                    "task",
                ]
                if c in step1.get("checkpoints", {})
            )
        else:
            step1: dict = {"checkpoints": {}, "summary": {}}
            step1_ok = True
    else:
        step1 = _step1_cli_cold(args.source, args.output, args.timeout_query, ocr_cfg)

        # ── 决策表：按子步骤失败类型决定是否终止后续步骤（与 docs/压力测试方案.md §2 一致）──
        _CRITICAL = {"scan", "query", "normalize", "organize"}
        _NON_CRITICAL = {"download", "expire", "announce", "task", "recheck"}
        _terminated_early = False
        _terminated_step = ""

        # scan: 扫描文件数=0 或 rc≠0 → 终止
        _scan_rc = step1["checkpoints"].get("scan", {}).get("rc", 1)
        _scan_count = step1["checkpoints"].get("scan", {}).get("count", 0)
        if _scan_rc != 0 or _scan_count == 0:
            _terminated_early = True
            _terminated_step = "scan"
            _log(f"压测终止 — scan 失败 (rc={_scan_rc}, count={_scan_count})")

        # query: rc≠0 或 (成功数<10%扫描数 且 成功数<50) → 终止
        _q_rc = step1["checkpoints"].get("query", {}).get("rc", 1)
        _q_total = step1["checkpoints"].get("query", {}).get("total", 0)
        if not _terminated_early and _q_rc != 0:
            _terminated_early = True
            _terminated_step = "query"
            _log(f"压测终止 — query 失败 (rc={_q_rc})")
        elif not _terminated_early and _scan_count > 0:
            _q_rate = _q_total / _scan_count
            if _q_rate < 0.1 and _q_total < 50:
                _terminated_early = True
                _terminated_step = "query"
                _log(
                    f"压测终止 — query 结果不足 (found={_q_total}, scan={_scan_count}, rate={_q_rate:.1%}, 需≥10% 或 ≥50)"
                )

        # normalize: rc≠0 → 终止
        _n_rc = step1["checkpoints"].get("normalize", {}).get("rc", 1)
        if not _terminated_early and _n_rc != 0:
            _terminated_early = True
            _terminated_step = "normalize"
            _log(f"压测终止 — normalize 失败 (rc={_n_rc})")

        # organize: rc≠0 → 终止
        _o_rc = step1["checkpoints"].get("organize", {}).get("rc", 1)
        if not _terminated_early and _o_rc != 0:
            _terminated_early = True
            _terminated_step = "organize"
            _log(f"压测终止 — organize 失败 (rc={_o_rc})")

        step1_ok = not _terminated_early and all(
            step1["checkpoints"].get(c, {}).get("rc", 1) == 0
            for c in list(_CRITICAL) + list(_NON_CRITICAL)
            if c in step1.get("checkpoints", {})
        )

        # flow_status 判定
        if _terminated_early:
            flow_status = f"TERMINATED_EARLY ({_terminated_step})"
        elif not step1_ok:
            flow_status = "PARTIAL_FAIL"
        else:
            flow_status = "FULL_PASS"

        # --stop-after=cli：第一步完成后退出，不执行后续步骤
        if _stop_after_cli:
            _log("=" * 50)
            _log("--stop-after=cli：第一步完成，退出")
            _log(f"  step1.json: {os.path.join(RESULT_DIR, 'step1.json')}")
            _log(f"  数据库: {_db_path}")
            _log(f"  日志目录: {RESULT_DIR}")
            _log("  源目录状态: 已处理（CLI 冷启完成），未复位")
            _log(
                "  下一步: 检查数据后，如需继续第二/三步，执行: "
                f"python tests/stress_driver.py --source {args.source} --output {args.output} "
                f"--skip-cli --step1 {os.path.join(RESULT_DIR, 'step1.json')} --keep-db"
            )
            _log("=" * 50)
            return 0

        # 第一步后：如果未跳过 WinUI，等用户手动复位源目录
        # （方案规定：复位由用户操作，AI 不得越权）
        if not args.skip_winui:
            s = step1.get("summary", {})
            org_moved = s.get("organize_moved", 0)
            _log(
                f"第一步完成: scan={s.get('scan_count', 0)} query_dl={s.get('query_download', 0)} "
                f"query_ex={s.get('query_expire', 0)} query_pe={s.get('query_pending', 0)} "
                f"dl_ok={s.get('download_success', 0)} org_moved={org_moved} "
                f"ann_total={s.get('announce_total', 0)} ann_rc={s.get('announce_rc', -1)}"
            )
            if org_moved > 0:
                _log(
                    f"=== organize 已移动 {org_moved} 个文件到 {args.output}，请手动迁回 {args.source} ==="
                )
            else:
                _log("=== organize 未移动文件，源目录未变动 ===")
            if _yes(args) or org_moved == 0:
                if org_moved > 0:
                    _log("=== --yes 模式：自动复位源目录 ===")
                    _step0_reset_source(args.source, args.output)
                else:
                    _log("=== organize 未移动文件，自动继续 ===")
        else:
            _log("=== 用户复位源目录完成后，输入 y 继续 ===")
            ans = input("复位完成，是否继续 WinUI 测试？(y/n): ").strip().lower()
            if ans not in ("y", "yes"):
                _log("已取消，测试停止。")
                return 0
        if args.skip_winui:
            s = step1.get("summary", {})
            _log(
                f"第一步完成: scan={s.get('scan_count', 0)} query_dl={s.get('query_download', 0)} "
                f"query_ex={s.get('query_expire', 0)} query_pe={s.get('query_pending', 0)} "
                f"dl_ok={s.get('download_success', 0)} org_moved={s.get('organize_moved', 0)} "
                f"ann_total={s.get('announce_total', 0)} ann_rc={s.get('announce_rc', -1)}"
            )

    # 第二步：WinUI 热启
    step2_ok = True
    if _terminated_early:
        _log("第二步：跳过 — 关键步骤失败，无有效数据对比")
    elif not args.skip_winui:
        _step1_json = (
            getattr(args, "step1", None)
            if getattr(args, "skip_cli", False) and getattr(args, "step1", None)
            else os.path.join(RESULT_DIR, "step1.json")
        )
        step2_ok = _step2_winui_hot(
            args.source,
            args.output,
            _step1_json,  # type: ignore[arg-type]
            args.timeout_auto,
        )
        # 展示交叉对比结果
        try:
            with open(
                os.path.join(RESULT_DIR, "step2.json"), "r", encoding="utf-8"
            ) as f:
                step2_data = json.load(f)
            _log(
                f"WinUI 完成: 判定={step2_data.get('verdict', '?')} "
                f"耗时={step2_data.get('elapsed_s', 0)}s"
            )
            for c in step2_data.get("comparisons", []):
                _log(
                    f"  交叉对比 {c.get('item', '')}: CLI={c.get('cli_expected', '')} "
                    f"WinUI={c.get('winui_actual', '')} → {'PASS' if c.get('pass') else 'FAIL'}"
                )
        except Exception:
            pass
    else:
        _log("第二步：跳过（--skip-winui）")

    # 第三步：Docker
    step3_ok = True
    if not args.skip_docker:
        _log("-" * 40)
        _log("即将开始 Docker Web API 验证。")
        if not _yes(args):
            ans = input("是否继续 Docker 测试？(y/n): ").strip().lower()
            if ans not in ("y", "yes"):
                _log("已取消，测试停止。")
                return 0
        step3_ok = _step3_docker(docker_url, docker_user, docker_pass)
    else:
        _log("第三步：跳过（--skip-docker）")

    # 第四步：判定
    # 适配器统计报告验证（补充点1：数据收集链路完整性）
    adapter_report_ok = True
    try:
        from pilotstd.core.config import get_data_dir as _get_data_dir
        from pilotstd.core.db import Database as _Database

        _db_path = args.db_path or os.path.join(_get_data_dir(), "pilotstd.db")
        if os.path.exists(_db_path):
            _db = _Database(_db_path)
            _report = _db.get_adapter_stats_all()
            if not _report:
                _log("适配器统计: FAIL — 返回空列表，数据收集链路未打通")
                adapter_report_ok = False
            else:
                _total_q = sum(r.get("total_queries", 0) for r in _report)
                if _total_q == 0:
                    _log("适配器统计: FAIL — 总查询数为 0，record_query_result 未生效")
                    adapter_report_ok = False
                else:
                    _log(
                        f"适配器统计: PASS — {len(_report)} 个适配器, 总查询={_total_q}"
                    )
                    for _r in _report:
                        _log(
                            f"  {_r['adapter_name']}: queries={_r['total_queries']} "
                            f"success={_r['success_rate']:.1%} "
                            f"avg={_r['avg_response_time']:.2f}s "
                            f"cooldown={_r['cooldown_count']}"
                        )
        else:
            _log(f"适配器统计: SKIP — DB 不存在 ({_db_path})")
    except Exception as _e:
        _log(f"适配器统计: FAIL — 异常 {_e}")
        adapter_report_ok = False

    verdict = _step4_verdict(
        step1_ok,
        step2_ok,
        step3_ok,
        args.skip_winui,
        args.skip_docker,
        step1,
        adapter_report_ok,
        credential_ok,
        credential_detail,
        flow_status,
    )

    # 返回码
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
