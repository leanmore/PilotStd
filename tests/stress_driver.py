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
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── CLI 参数 ──────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description="PilotStd 全量压力测试驱动器")
    p.add_argument("--source", required=True, help="源目录，如 D:\\标准")
    p.add_argument("--output", required=True, help="输出目录，如 E:\\标准")
    p.add_argument("--timeout-query", type=int, default=None, help="查询超时秒数（默认不限）")
    p.add_argument("--timeout-auto", type=int, default=None, help="auto 超时秒数（默认不限）")
    p.add_argument("--skip-winui", action="store_true", help="跳过 WinUI 步骤")
    p.add_argument("--skip-docker", action="store_true", help="跳过 Docker 步骤")
    p.add_argument("--docker-url", default=os.environ.get("PILOTSTD_BASE_URL", ""),
                   help="Docker API 地址（需设置环境变量 PILOTSTD_BASE_URL）")
    p.add_argument("--docker-user", default=os.environ.get("PILOTSTD_USERNAME", ""),
                   help="Docker 管理员用户名（需设置环境变量 PILOTSTD_USERNAME）")
    p.add_argument("--docker-pass", default=os.environ.get("PILOTSTD_PASSWORD", ""),
                   help="Docker 管理员密码（需设置环境变量 PILOTSTD_PASSWORD）")
    p.add_argument("--db-path", default=None, help="数据库路径（默认 data/pilotstd.db）")
    p.add_argument("--yes", action="store_true", help="跳过所有交互确认（CI/自动模式）")
    p.add_argument("--winui-only", action="store_true", help="仅执行 WinUI 步骤（跳过CLI冷启）")
    p.add_argument("--step1", default=None, help="step1.json 路径（winui-only 模式时由总入口传入）")
    p.add_argument("--result-dir", default=None, help="结果目录（由 stress_all 传入，统一输出位置）")
    p.add_argument("--config", default=None, help="压测配置文件路径（JSON，含 Docker/OCR 凭证）")
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

def _step0_check_preconditions(source_dir: str, output_dir: str,
                                skip_docker: bool, docker_url: str):
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


def _step0_clear_db(db_path: str = None):
    """清空四表，保留 schema 和用户设置。"""
    from pilotstd.core.config import get_data_dir
    from pilotstd.core.db import Database

    if db_path is None:
        db_path = os.path.join(get_data_dir(), "pilotstd.db")
    if not os.path.exists(db_path):
        _log(f"DB 不存在，跳过清表: {db_path}")
        return
    db = Database(db_path)
    tables = ["standard_info_cache", "announcement_cache",
              "pending_lookup", "file_index"]
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
        if rel.startswith("logs") or rel.startswith("downloads") or rel.startswith("_stress"):
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
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=ROOT, encoding="utf-8", errors="replace", env=env)

        stdout_lines = []
        stderr_lines = []

        # 同时读取 stdout 和 stderr，避免管道缓冲区写满导致死锁
        def read_stream(stream, lines_list, prefix):
            for line in stream:
                line = line.rstrip()
                if line:
                    _log(f"  {line}")
                lines_list.append(line)

        t_stdout = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines, "  "), daemon=True)
        t_stderr = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines, "  "), daemon=True)
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
            "stdout": proc.stdout.read(),
            "stderr": "\n".join(stderr_lines),
            "returncode": proc.returncode
        }
    except Exception as e:
        _log(f"    {step_name}: 异常 {e}")
        return {"error": str(e)}


# ── 第一步：CLI 冷启 ─────────────────────────────────────────

def _step1_cli_cold(source_dir: str, output_dir: str, timeout_query: int,
                   ocr_config: dict = None):
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
        env["OCR_ALIYUN_ACCESS_KEY_SECRET"] = ocr_config.get("aliyun_access_key_secret", "")

    results = {"step": 1, "ts": TS, "checkpoints": {}}

    # scan — 快速扫描，保持 subprocess.run + 异常保护
    _log("  1.1 scan...")
    t0 = time.time()
    scan_count = 0
    scan_stdout = ""
    try:
        r = subprocess.run(
            [python, "-m", cli_module, "--storage-root", output_dir,
             "scan", source_dir, "--format", "json"],
            capture_output=True, text=True, timeout=120,
            cwd=ROOT, encoding="utf-8", errors="replace", env=env)
        scan_stdout = r.stdout if r.stdout else ""
        if r.returncode == 0:
            try:
                scan_data = json.loads(r.stdout if r.stdout else "[]")
                scan_count = len(scan_data)
            except json.JSONDecodeError:
                scan_count = len([l for l in (r.stdout or "").splitlines() if l.strip()])
        results["checkpoints"]["scan"] = {"count": scan_count, "rc": r.returncode, "elapsed_s": round(time.time() - t0, 1)}
        _log(f"    scan: {scan_count} 条, rc={r.returncode}, {results['checkpoints']['scan']['elapsed_s']}s")
    except subprocess.TimeoutExpired:
        _log(f"    scan: 超时")
        results["checkpoints"]["scan"] = {"count": 0, "error": "timeout", "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        _log(f"    scan: 异常 {e}")
        results["checkpoints"]["scan"] = {"count": 0, "error": str(e), "elapsed_s": round(time.time() - t0, 1)}

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
        [python, "-m", cli_module, "--storage-root", output_dir,
         "query", "--file", nums_file, "--no-cache"],
        timeout=timeout_query or 3600, step_name="query", env=env)
    # 从 query 输出解析分类计数 + 逐桶统计
    dl_count = ex_count = pe_count = exact_count = 0
    bucket_stats = {}  # {key: total}
    funnel = {}        # {total, ok, overflow, pending}
    timeline_elapsed = 0
    cooldown_count = 0
    csres_info = {}     # {processed, failures}
    overflow_count = 0
    water_level = {}    # {ahbz_remain, njbz_remain}
    if "error" not in r:
        for line in (r.get("stdout", "") + r.get("stderr", "")).splitlines():
            if "download=" in line and "expire=" in line:
                m = re.search(r"download=(\d+).*?expire=(\d+).*?pending=(\d+)", line)
                if m:
                    dl_count, ex_count, pe_count = int(m.group(1)), int(m.group(2)), int(m.group(3))
            m2 = re.search(r"(\d+)\s+精确", line)
            if m2:
                exact_count = int(m2.group(1))
            # 逐桶日志解析
            m3 = re.match(r".*\[BUCKET\]\s+(\S+)\s+total=(\d+)\s+done=(\d+)\s+overflow=(\d+)\s+elapsed=([\d.]+)", line)
            if m3:
                bucket_stats[m3.group(1)] = {"total": int(m3.group(2)),
                    "done": int(m3.group(3)), "overflow": int(m3.group(4)),
                    "elapsed_s": float(m3.group(5))}
            m4 = re.match(r".*\[FUNNEL\]\s+total=(\d+)\s+ok=(\d+)\s+overflow=(\d+)\s+pending=(\d+)", line)
            if m4:
                funnel = {"total": int(m4.group(1)), "ok": int(m4.group(2)),
                         "overflow": int(m4.group(3)), "pending": int(m4.group(4))}
            m5 = re.match(r".*\[TIMELINE\]\s+query_bucketed_done\s+total=(\d+)\s+elapsed=([\d.]+)", line)
            if m5:
                timeline_elapsed = float(m5.group(2))
            if "[COOLDOWN]" in line:
                cooldown_count += 1
            m6 = re.match(r".*\[CSRES\]\s+processed=(\d+)\s+failures=(\d+)", line)
            if m6:
                csres_info = {"processed": int(m6.group(1)), "failures": int(m6.group(2))}
            m7 = re.match(r".*\[OVERFLOW\]\s+events=(\d+)", line)
            if m7:
                overflow_count = int(m7.group(1))
            m8 = re.match(r".*\[WATER\]\s+ahbz_overflow_remain=(\d+)\s+njbz365_remain=(\d+)", line)
            if m8:
                water_level = {"ahbz_remain": int(m8.group(1)), "njbz_remain": int(m8.group(2))}
        results["checkpoints"]["query"] = {
            "download": dl_count, "expire": ex_count, "pending": pe_count,
            "exact": exact_count,
            "total": dl_count + ex_count + pe_count,
            "rc": r.get("returncode", 0), "elapsed_s": round(time.time() - t0, 1)}
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
        _log(f"    query: download={dl_count} expire={ex_count} pending={pe_count} exact={exact_count}, rc={r.get('returncode', 0)}")
        if bucket_stats:
            _log(f"    bucket_stats: {bucket_stats}")
        if funnel:
            _log(f"    funnel: total={funnel['total']} ok={funnel['ok']} overflow={funnel['overflow']} pending={funnel['pending']} elapsed={timeline_elapsed}s")
        if csres_info:
            _log(f"    csres: processed={csres_info['processed']} failures={csres_info['failures']}")
        if overflow_count:
            _log(f"    overflow_events: {overflow_count}")
        if water_level:
            _log(f"    water: ahbz_remain={water_level['ahbz_remain']} njbz_remain={water_level['njbz_remain']}")
    else:
        query_failed = True
        results["checkpoints"]["query"] = {"error": r["error"], "elapsed_s": round(time.time() - t0, 1)}
        _log(f"    query 失败: {r['error']}，跳过后续下载步骤")

    # download（如果有可下载的） — 流式读取 + 异常保护
    dl_success = 0
    if dl_count > 0 and not query_failed:
        _log(f"  1.3 download ({dl_count} 条)...")
        t0 = time.time()
        r = _safe_run(
            [python, "-m", cli_module, "--storage-root", output_dir, "download"],
            timeout=timeout_query or 3600, step_name="download", env=env)
        if "error" not in r:
            dl_success = (r.get("stdout", "") + r.get("stderr", "")).count("成功") + (r.get("stdout", "") + r.get("stderr", "")).count("跳过")
            results["checkpoints"]["download"] = {"success": dl_success, "rc": r.get("returncode", 0), "elapsed_s": round(time.time() - t0, 1)}
            _log(f"    download: {dl_success} 成功/跳过, rc={r.get('returncode', 0)}")
        else:
            results["checkpoints"]["download"] = {"success": 0, "error": r["error"], "elapsed_s": round(time.time() - t0, 1)}
            _log(f"    download 失败: {r['error']}")
    elif query_failed:
        results["checkpoints"]["download"] = {"success": 0, "rc": 0, "elapsed_s": 0, "skipped": "query_failed"}
        _log("    download: query 失败，跳过")
    else:
        results["checkpoints"]["download"] = {"success": 0, "rc": 0, "elapsed_s": 0}
        _log("    download: 队列为空，跳过")

    # normalize — 异常保护
    _log("  1.4 normalize...")
    t0 = time.time()
    try:
        r = subprocess.run(
            [python, "-m", cli_module, "--storage-root", output_dir, "normalize", source_dir],
            capture_output=True, text=True, timeout=120,
            cwd=ROOT, encoding="utf-8", errors="replace", env=env)
        results["checkpoints"]["normalize"] = {"rc": r.returncode, "elapsed_s": round(time.time() - t0, 1)}
        _log(f"    normalize: rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    normalize: 超时")
        results["checkpoints"]["normalize"] = {"error": "timeout", "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        _log(f"    normalize: 异常 {e}")
        results["checkpoints"]["normalize"] = {"error": str(e), "elapsed_s": round(time.time() - t0, 1)}

    # organize — 异常保护
    _log("  1.5 organize...")
    t0 = time.time()
    org_moved = 0
    try:
        r = subprocess.run(
            [python, "-m", cli_module, "--storage-root", output_dir,
             "organize", "--format", "json", "--source", source_dir],
            capture_output=True, text=True, timeout=300,
            cwd=ROOT, encoding="utf-8", errors="replace", env=env)
        try:
            org_data = json.loads(r.stdout.splitlines()[-1] if r.stdout else "{}")
            org_moved = org_data.get("moved", 0)
        except json.JSONDecodeError:
            pass
        results["checkpoints"]["organize"] = {"moved": org_moved, "rc": r.returncode, "elapsed_s": round(time.time() - t0, 1)}
        _log(f"    organize: moved={org_moved}, rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    organize: 超时")
        results["checkpoints"]["organize"] = {"moved": 0, "error": "timeout", "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        _log(f"    organize: 异常 {e}")
        results["checkpoints"]["organize"] = {"moved": 0, "error": str(e), "elapsed_s": round(time.time() - t0, 1)}

    # expire — 异常保护
    _log("  1.6 expire...")
    t0 = time.time()
    try:
        r = subprocess.run(
            [python, "-m", cli_module, "--storage-root", output_dir, "expire", output_dir],
            capture_output=True, text=True, timeout=60,
            cwd=ROOT, encoding="utf-8", errors="replace", env=env)
        results["checkpoints"]["expire"] = {"rc": r.returncode, "elapsed_s": round(time.time() - t0, 1)}
        _log(f"    expire: rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    expire: 超时")
        results["checkpoints"]["expire"] = {"error": "timeout", "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        _log(f"    expire: 异常 {e}")
        results["checkpoints"]["expire"] = {"error": str(e), "elapsed_s": round(time.time() - t0, 1)}

    # announce（公告闭环 + 三表写完）— 各类型限制 10 条
    _log("  1.7 announce gb/hb/db (各10条)...")
    t0 = time.time()
    announce_rc = 0
    announce_total = 0
    try:
        from pilotstd.announcement.adapters.samr_gb import SamrGbAdapter
        from pilotstd.announcement.adapters.samr_hb import SamrHbAdapter
        from pilotstd.announcement.adapters.samr_db import SamrDbAdapter
        from pilotstd.announcement.ocr import create_ocr_provider
        from pilotstd.announcement.matcher import AnnouncementMatcher
        from pilotstd.core.config import ConfigManager, get_data_dir
        from pilotstd.core.db import Database
        from pilotstd.query.network import safe_request, CHROME_UA
        import os as _os

        cfg = ConfigManager(_os.path.join(get_data_dir(), "config.json"))
        db_path = _os.path.join(get_data_dir(), "pilotstd.db")
        db = Database(db_path)
        matcher = AnnouncementMatcher(db)

        ocr_config = {
            "baidu_api_key": cfg.get("ocr.baidu_api_key", ""),
            "baidu_secret_key": cfg.get("ocr.baidu_secret_key", ""),
            "tencent_secret_id": cfg.get("ocr.tencent_secret_id", ""),
            "tencent_secret_key": cfg.get("ocr.tencent_secret_key", ""),
            "aliyun_access_key_id": cfg.get("ocr.aliyun_access_key_id", ""),
            "aliyun_access_key_secret": cfg.get("ocr.aliyun_access_key_secret", ""),
        }
        ocr_provider = create_ocr_provider(ocr_config) if any(ocr_config.values()) else None
        _log(f"    OCR provider: {ocr_provider.name if ocr_provider else 'None'}")

        for atype, AdapterCls in [("gb", SamrGbAdapter), ("hb", SamrHbAdapter), ("db", SamrDbAdapter)]:
            try:
                adapter = AdapterCls()
                # 猴子补丁：_fetch_list 只拿第一页 10 条
                def _limited_fetch(self, since_date, page_size):
                    import requests
                    s = requests.Session()
                    s.headers["User-Agent"] = CHROME_UA
                    resp = safe_request(s, "GET", self._list_url, self.site_name,
                                      timeout=120, params={
                                          "pageNumber": 1, "pageSize": 10,
                                          "sortName": "NOTICE_DATE", "sortOrder": "desc",
                                      })
                    if resp is None:
                        return []
                    try:
                        data = resp.json()
                    except Exception:
                        return []
                    rows = data.get("rows", [])[:10]
                    return [{"pid": r.get("PID", ""), "code": r.get("CODE", ""),
                             "title": r.get("C_TITLE", ""),
                             "notice_date": r.get("NOTICE_DATE", ""),
                             "std_count": r.get("STD_COUNT", "")} for r in rows]
                adapter._fetch_list = _limited_fetch.__get__(adapter, type(adapter))

                # 复用现有逻辑：fetch + parse + match
                items = adapter.fetch_announcements(since_date="",
                                                   ocr_provider=ocr_provider)
                if not items:
                    _log(f"    announce {atype}: 无公告/解析为空")
                    continue
                announce_total += len(items)
                result = matcher.match_and_update(
                    items, source_site=adapter.source_site)
                _log(f"    announce {atype}: {len(items)} 条标准, "
                     f"matched={result.get('matched', 0)} "
                     f"updated={result.get('updated', 0)}")
            except Exception as e:
                _log(f"    announce {atype}: 异常 {e}")
                announce_rc = 1
    except Exception as e:
        _log(f"    announce 初始化失败: {e}")
        announce_rc = 1
    results["checkpoints"]["announce"] = {"rc": announce_rc, "total_ann": announce_total,
                                          "elapsed_s": round(time.time() - t0, 1)}

    # task — 异常保护
    _log("  1.8 task...")
    t0 = time.time()
    try:
        r = subprocess.run(
            [python, "-m", cli_module, "--storage-root", output_dir, "task", "--format", "json"],
            capture_output=True, text=True, timeout=30,
            cwd=ROOT, encoding="utf-8", errors="replace", env=env)
        results["checkpoints"]["task"] = {"rc": r.returncode, "elapsed_s": round(time.time() - t0, 1)}
        _log(f"    task: rc={r.returncode}")
    except subprocess.TimeoutExpired:
        _log("    task: 超时")
        results["checkpoints"]["task"] = {"error": "timeout", "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        _log(f"    task: 异常 {e}")
        results["checkpoints"]["task"] = {"error": str(e), "elapsed_s": round(time.time() - t0, 1)}

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

def _step2_winui_hot(source_dir: str, output_dir: str, step1_path: str, timeout_auto: int):
    """pytest 调用 WinUI 测试，热启 auto + 交叉对比。"""
    _log("=" * 50)
    _log("第二步：WinUI 热启（交叉对比）")

    step2_path = os.path.join(RESULT_DIR, "step2.json")

    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest",
             os.path.join(ROOT, "tests", "stress_winui.py"),
             "-v", "-s",
             "--source", source_dir,
             "--output", output_dir,
             "--step1", step1_path,
             "--step2", step2_path],
            capture_output=True, text=True,
            timeout=timeout_auto,
            cwd=ROOT, encoding="utf-8", errors="replace")
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
    """Docker 部署态验证。Docker 不可达时返回 SKIP。"""
    _log("=" * 50)
    _log(f"第三步：Docker Web API → {docker_url}")

    env = os.environ.copy()
    env["PILOTSTD_BASE_URL"] = docker_url
    env["PILOTSTD_USERNAME"] = docker_user
    env["PILOTSTD_PASSWORD"] = docker_pass

    try:
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tests", "stress_web.py")],
            capture_output=True, text=True,
            timeout=360,  # announce/check 内部有 180s 超时请求
            cwd=ROOT, encoding="utf-8", errors="replace", env=env)
        _log(f"Docker test: rc={r.returncode}")
        if r.stdout:
            for line in r.stdout.splitlines():
                if "PASS" in line or "FAIL" in line or "SKIP" in line:
                    _log(f"  {line.strip()}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        _log("Docker test: 超时")
        return False
    except Exception as e:
        _log(f"Docker test: 异常 {e}")
        return False


# ── 第四步：汇总判定 ──────────────────────────────────────────

def _step4_verdict(step1_ok: bool, step2_ok: bool, step3_ok: bool,
                   skip_winui: bool, skip_docker: bool, step1_data: dict = None):
    """汇总判定，写入方案执行记录。"""
    _log("=" * 50)
    _log("汇总判定")

    verdict = "PASS"
    lines = []
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
    if not step1_ok:
        verdict = "FAIL"

    for line in lines:
        _log(line)

    # 逐桶指标对比基线
    if step1_data:
        q = step1_data.get("checkpoints", {}).get("query", {})
        funnel = q.get("funnel", {})
        cooldown = q.get("cooldown_count", -1)
        elapsed = q.get("funnel_elapsed_s", 0)
        csres = q.get("csres", {})
        water = q.get("water_level", {})
        _log(f"逐桶指标: pending={funnel.get('pending','?')} "
             f"overflow={funnel.get('overflow','?')} "
             f"cooldown={cooldown} elapsed={elapsed:.0f}s")
        if csres:
            _log(f"csres: processed={csres.get('processed','?')} failures={csres.get('failures','?')}")
        if water:
            _log(f"water: ahbz_remain={water.get('ahbz_remain','?')} njbz_remain={water.get('njbz_remain','?')}")
        _log("基线(0617逐轮): pending=206 elapsed=1440s cooled=1348")
        if funnel.get("pending", 999) <= 206 and cooldown == 0:
            _log("逐桶对比: 优于基线 ✓")
        else:
            _log("逐桶对比: 未达基线，需分析 ✗")

    _log(f"判定: {verdict}")

    verdict_path = os.path.join(RESULT_DIR, "verdict.json")
    with open(verdict_path, "w", encoding="utf-8") as f:
        json.dump({"verdict": verdict, "steps": lines, "ts": TS}, f, ensure_ascii=False, indent=2)
    _log(f"结果: {RESULT_DIR}")
    return verdict


# ── main ──────────────────────────────────────────────────────

def _yes(args):
    """--yes 模式下跳过所有交互确认。"""
    return getattr(args, 'yes', False)

def main():
    global RESULT_DIR, TS
    args = _parse_args()

    # 加载本地压测配置（JSON，不上传 git），命令行参数优先
    cfg = _load_test_config(getattr(args, 'config', None))
    docker_cfg = cfg.get("docker", {})
    ocr_cfg = cfg.get("ocr", {})
    docker_url = args.docker_url or docker_cfg.get("url", "")
    docker_user = args.docker_user or docker_cfg.get("username", "")
    docker_pass = args.docker_pass or docker_cfg.get("password", "")
    TS = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULT_DIR = args.result_dir or os.path.join(ROOT, "logs", f"stress_{TS}")
    os.makedirs(RESULT_DIR, exist_ok=True)
    _log(f"PilotStd 全量压力测试驱动器 v4.2 | {TS}")
    _log(f"源: {args.source}  输出: {args.output}")
    _log(f"结果目录: {RESULT_DIR}")

    # winui-only 模式：跳过 CLI 冷启，直接跑 WinUI
    if getattr(args, 'winui_only', False):
        _log("winui-only 模式：跳过 CLI 冷启")
        step1 = args.step1 or os.path.join(RESULT_DIR, "step1.json")
        if not os.path.exists(step1):
            _log(f"错误: step1.json 不存在 ({step1})")
            return 1
        step2_ok = _step2_winui_hot(
            args.source, args.output,
            step1,
            args.timeout_auto)
        step3_ok = True
        if not args.skip_docker:
            step3_ok = _step3_docker(docker_url, docker_user, docker_pass)
        verdict = _step4_verdict(True, step2_ok, step3_ok,
                                 False, args.skip_docker, None)
        return 0 if verdict == "PASS" else 1

    # 第〇步：环境自检
    _log("=" * 50)
    _log("第〇步：环境自检")
    _step0_check_preconditions(args.source, args.output,
                               args.skip_docker, docker_url)
    _log("-" * 40)
    if not _yes(args):
        ans = input("是否开始测试？(y/n): ").strip().lower()
        if ans not in ("y", "yes"):
            _log("已取消。")
            return 0

    # 第〇步：复位 + 清 DB
    _log("第〇步：复位源目录 + 清 DB")
    if os.path.isdir(args.output):
        _step0_reset_source(args.source, args.output)
    _step0_clear_db(args.db_path)

    # 第〇步：自检（纯逻辑秒级验证，零网络依赖）
    _log("第〇步：自检（stress_selfcheck）")
    sc_rc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tests", "stress_selfcheck.py"),
         "--output", args.output],
        capture_output=True, text=True, timeout=120)
    if sc_rc.returncode != 0:
        _log("自检失败，终止后续步骤")
        _log(sc_rc.stderr[-500:] if sc_rc.stderr else "")
        sys.exit(1)
    _log("自检通过")

    # 第一步：CLI 冷启
    step1 = _step1_cli_cold(args.source, args.output, args.timeout_query, ocr_cfg)
    step1_ok = all(
        step1["checkpoints"].get(c, {}).get("rc", 1) == 0
        for c in ["scan", "query", "download", "normalize", "organize", "expire", "announce", "task"]
    )

    # 第一步后：如果未跳过 WinUI，等用户手动复位源目录
    # （方案规定：复位由用户操作，AI 不得越权）
    if not args.skip_winui:
        s = step1.get("summary", {})
        org_moved = s.get("organize_moved", 0)
        _log(f"第一步完成: scan={s.get('scan_count',0)} query_dl={s.get('query_download',0)} "
             f"query_ex={s.get('query_expire',0)} query_pe={s.get('query_pending',0)} "
             f"dl_ok={s.get('download_success',0)} org_moved={org_moved} "
             f"ann_total={s.get('announce_total',0)} ann_rc={s.get('announce_rc',-1)}")
        if org_moved > 0:
            _log(f"=== organize 已移动 {org_moved} 个文件到 {args.output}，请手动迁回 {args.source} ===")
        else:
            _log("=== organize 未移动文件，源目录未变动 ===")
        if _yes(args) or org_moved == 0:
            _log("=== --yes 或 organize 未移动文件，自动继续 ===")
        else:
            _log("=== 用户复位源目录完成后，输入 y 继续 ===")
            ans = input("复位完成，是否继续 WinUI 测试？(y/n): ").strip().lower()
            if ans not in ("y", "yes"):
                _log("已取消，测试停止。")
                return 0
    else:
        s = step1.get("summary", {})
        _log(f"第一步完成: scan={s.get('scan_count',0)} query_dl={s.get('query_download',0)} "
             f"query_ex={s.get('query_expire',0)} query_pe={s.get('query_pending',0)} "
             f"dl_ok={s.get('download_success',0)} org_moved={s.get('organize_moved',0)} "
             f"ann_total={s.get('announce_total',0)} ann_rc={s.get('announce_rc',-1)}")

    # 第二步：WinUI 热启
    step2_ok = True
    if not args.skip_winui:
        step2_ok = _step2_winui_hot(
            args.source, args.output,
            os.path.join(RESULT_DIR, "step1.json"),
            args.timeout_auto)
        # 展示交叉对比结果
        try:
            with open(os.path.join(RESULT_DIR, "step2.json"), "r", encoding="utf-8") as f:
                step2_data = json.load(f)
            _log(f"WinUI 完成: 判定={step2_data.get('verdict','?')} "
                 f"耗时={step2_data.get('elapsed_s',0)}s")
            for c in step2_data.get("comparisons", []):
                _log(f"  交叉对比 {c.get('item','')}: CLI={c.get('cli_expected','')} "
                     f"WinUI={c.get('winui_actual','')} → {'PASS' if c.get('pass') else 'FAIL'}")
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
    verdict = _step4_verdict(step1_ok, step2_ok, step3_ok,
                             args.skip_winui, args.skip_docker, step1)

    # 返回码
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
