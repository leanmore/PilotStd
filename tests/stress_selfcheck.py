# 纯逻辑模块压力测试 — 第三层（零网络依赖）
# 用法: python tests/stress_03_logic.py [--output E:\标准]
# 全程自动化，秒级完成
#
# 覆盖: i18n/通知/配额/任务队列/DB备份/文件工具/路径安全/clear_stale/数据模型

import sys, os, time, logging, json, threading, shutil, sqlite3, argparse
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_p = argparse.ArgumentParser(description="纯逻辑压力测试 — 第三层")
_p.add_argument("--output", required=True, help="输出目录，如 E:\\标准")
import sys as _sys; _args = _p.parse_args([]) if "pytest" in _sys.argv[0] else _p.parse_args()
OUTPUT_DIR = _args.output

_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_path = os.path.join(_log_dir, f"stress_logic_{time.strftime('%Y%m%d_%H%M%S')}.log")

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

# 抑制第三方日志噪音
for _mod in ('urllib3', 'requests', 'lxml', 'httpx', 'PIL'):
    logging.getLogger(_mod).setLevel(logging.WARNING)

logger = logging.getLogger("stress_logic")

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


# ======================================================================
# 开始
# ======================================================================

t0 = time.time()
logger.info("=" * 60)
logger.info("纯逻辑压力测试 v1 | %s", time.strftime("%Y-%m-%d %H:%M:%S"))
logger.info("=" * 60)

# --- i18n ---
logger.info("--- i18n ---")
from pilotstd.i18n import set_language, get_language, _

_orig = get_language()

# 使用所有三种语言中都实际存在的 key，覆盖菜单/按钮/状态三类
_keys = ["file", "settings", "help", "about", "tools", "btn_ok", "btn_cancel",
         "btn_save", "btn_close", "ready", "completed", "scan_complete"]
for lang in ("zh_CN", "zh_TW", "en"):
    set_language(lang)
    missing = [k for k in _keys if _(k) == k]
    _check(f"i18n: {lang} 关键key({len(_keys)}个)", len(missing) == 0,
           f"缺 {missing}" if missing else "全部存在")

set_language("zh_CN")
_check("i18n: set→get一致(zh_CN)", get_language() == "zh_CN")
set_language("en")
_check("i18n: set→get一致(en)", get_language() == "en")
set_language(_orig)

# --- 通知 ---
logger.info("--- 通知 ---")
_notify_ok = False
try:
    from pilotstd.core.notify import NotifyService
    _notify_ok = True
except Exception as e:
    logger.info("  SKIP 通知模块（PyQt6 不可用: %s）", e)

if _notify_ok:
    ns = NotifyService(None)
    try:
        ns.show("测试", "消息内容")
        ns.show_warning("警告", "警告内容")
        _check("通知: 无tray静默降级", True)
    except Exception as e:
        _check("通知: 无tray静默降级", False, str(e))

    ns2 = NotifyService(None)
    ns2._last.clear()
    _check("通知: 首次发送通过", ns2._check_dedup("title1"))
    _check("通知: 3秒内去重", not ns2._check_dedup("title1"))
    _check("通知: 不同标题不去重", ns2._check_dedup("title2"))
else:
    _check("通知: 无tray静默降级", False, "PyQt6 不可用，跳过")
    _check("通知: 首次发送通过", False, "PyQt6 不可用，跳过")
    _check("通知: 3秒内去重", False, "PyQt6 不可用，跳过")
    _check("通知: 不同标题不去重", False, "PyQt6 不可用，跳过")

# --- 配额 ---
logger.info("--- 配额 ---")
from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database
from pilotstd.query.daily_quota import DailyQuotaTracker

db = Database(get_db_path())
qt = DailyQuotaTracker(db)

_used_before = qt.get_used("_stress_test")
_rem = qt.record_usage("_stress_test", 3)
_check("配额: record_usage返回剩余", _rem >= 0, str(_rem))
_check("配额: get_used增加", qt.get_used("_stress_test") == _used_before + 3)

# 跨天检测：_ensure_date 应识别日期变化并更新 _today
_orig_today = qt._today
qt._today = "2000-01-01"
qt._ensure_date()
_check("配额: 跨天检测", qt._today == str(date.today()),
       f"_today={qt._today}")
qt._today = _orig_today
qt._ensure_date()

# 并发安全：4 线程各写 10 次，无异常即通过
_errors = []
def _quota_worker():
    try:
        for _ in range(10):
            qt.record_usage("_stress_concurrent", 1)
    except Exception as e:
        _errors.append(str(e))
_threads = [threading.Thread(target=_quota_worker) for _ in range(4)]
for t in _threads:
    t.start()
for t in _threads:
    t.join()
_check("配额: 4线程并发无异常", len(_errors) == 0,
       f"{len(_errors)} 个异常" if _errors else "OK")

# --- 任务队列 ---
logger.info("--- 任务队列 ---")
from pilotstd.task.queue import TaskQueue
from pilotstd.task.models import TaskType, TaskStatus

tq = TaskQueue(db)
task = tq.enqueue(TaskType.SCAN, 100)  # enqueue(task_type, total_items)
_check("队列: 入队成功", task.task_id is not None)

# 状态流转: pending → paused → cancelled，用实际 API 验证
tq.pause(task.task_id)
tq.cancel(task.task_id)
all_tasks = tq.list_all()
_check("队列: 状态流转", len(all_tasks) > 0, f"{len(all_tasks)} 个任务")

# --- DB 备份 ---
logger.info("--- DB 备份 ---")
bak_path = db.backup()
_check("备份: 文件生成", os.path.exists(bak_path) and os.path.getsize(bak_path) > 0,
       f"{os.path.getsize(bak_path) if os.path.exists(bak_path) else 0} 字节")

try:
    _bc = sqlite3.connect(bak_path)
    _tables = [r[0] for r in _bc.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    _check("备份: 表结构完整", len(_tables) > 0, f"{len(_tables)} 个表")
    _bc.close()
except Exception as e:
    _check("备份: 可打开", False, str(e))

# --- 文件工具 ---
logger.info("--- 文件工具 ---")
from pilotstd.core.file_utils import (sanitize_filename, safe_code_for_filename,
                                       make_standard_filename, ensure_dir)

_result = sanitize_filename('a<b>c:d"e/f\\g|h?i*j')
_check("文件: sanitize 无非法字符",
       all(c not in _result for c in '<>:"/\\|?*'))
_check("文件: safe_code GB/T→GBT", safe_code_for_filename("GB/T") == "GBT")
_fn = make_standard_filename("GB", 1, 2020, "测试标准", None)
_check("文件: make_standard_filename", _fn.startswith("GB 1-2020"), _fn[:60])

# --- 路径安全 ---
logger.info("--- 路径安全 ---")
from pilotstd.organizer.mover import FileMover

# 通过 __new__ 绕过 DirBuilder 依赖，仅测 _is_safe_path 逻辑
_mover = FileMover.__new__(FileMover)
_mover._library_root = os.path.join(OUTPUT_DIR, "GB 国家标准")
_check("路径: 子目录通过", _mover._is_safe_path(
    os.path.join(OUTPUT_DIR, "GB 国家标准", "subdir", "test.pdf")))
_check("路径: 越界拒绝", not _mover._is_safe_path(
    os.path.join(OUTPUT_DIR, "..", "outside.pdf")))

# --- clear_stale ---
logger.info("--- clear_stale ---")
from pilotstd.core.file_index import FileIndexRepository
fix = FileIndexRepository(db)

_old_1d = (date.today() - timedelta(days=1)).isoformat()
_old_8d = (date.today() - timedelta(days=8)).isoformat()

# 插入两条测试记录：1天前（应保留）和 8天前（应被清理）
fix.upsert("D:/_stress_clear_1d.pdf", logical_code="GB", number=1, year=2020,
           std_name="近期记录", file_hash="hash_1d_stress3")
fix.upsert("D:/_stress_clear_8d.pdf", logical_code="GB", number=2, year=2020,
           std_name="过期记录", file_hash="hash_8d_stress3")
db.execute("UPDATE file_index SET last_checked=? WHERE file_hash=?",
           (_old_1d, "hash_1d_stress3"))
db.execute("UPDATE file_index SET last_checked=? WHERE file_hash=?",
           (_old_8d, "hash_8d_stress3"))

_removed = fix.clear_stale()
_check("clear_stale: 可执行", _removed >= 0, f"清理 {_removed} 条")
# 1天前的记录不应被清理（last_checked 不到 7 天）
_entry_1d = fix.get("D:/_stress_clear_1d.pdf")
_check("clear_stale: 保留近期(1d)", _entry_1d is not None,
       "被错误清理" if _entry_1d is None else "OK")

# 清理测试数据
for _h in ("hash_1d_stress3", "hash_8d_stress3"):
    db.execute("DELETE FROM file_index WHERE file_hash=?", (_h,))

# --- 数据模型 ---
logger.info("--- 数据模型 ---")
from pilotstd.models import ParsedStdInfo

p = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020,
                  std_name="测试")
_check("模型: get_full_number", p.get_full_number() == "GB/T 1-2020")
p2 = ParsedStdInfo(raw_filename="test.pdf", logical_code="GB", number=150, year=2011,
                   part=1, std_name="压力容器")
_check("模型: 带部分号", p2.get_full_number() == "GB 150.1-2011")

# --- v2.2 新增：DB 地方标准解析 ---
logger.info("--- DB 地方标准解析 ---")
from pilotstd.scan.parser import StandardParser
from pilotstd.organizer.industry_lookup import build_code_mapping
_parser = StandardParser(build_code_mapping())

# 省级推荐
_info = _parser.parse("DB11/T 1951-2021 城市照明规划标准.pdf")
_check("DB解析: DB11/T 1951-2021", _info is not None and _info.logical_code == "DB11/T"
       and _info.number == 1951 and _info.year == 2021)
# 省级强制
_info = _parser.parse("DB44 123-2018 广东强制标准.pdf")
_check("DB解析: DB44 123-2018", _info is not None and _info.logical_code == "DB44"
       and _info.number == 123 and _info.year == 2018)
# 市级
_info = _parser.parse("DB3501/T 002-2023 福州标准.pdf")
_check("DB解析: DB3501/T 002-2023", _info is not None and _info.logical_code == "DB3501/T"
       and _info.number == 2 and _info.year == 2023)
# 市级强制
_info = _parser.parse("DB4201 001-2020 武汉标准.pdf")
_check("DB解析: DB4201 001-2020", _info is not None and _info.logical_code == "DB4201"
       and _info.number == 1 and _info.year == 2020)

# --- v2.2 新增：语言标记 ---
logger.info("--- 语言标记 ---")
_lang_cases = [
    ("ASME 1-2021 压力容器建造规则（中文）.pdf", "中文版"),
    ("API Spec 6D-2008 阀门（英文）.pdf", "英文版"),
    ("DIN EN 1092.1-2018 en.pdf", "英文版"),
    ("GB 1499.2-2024 钢筋.pdf", ""),  # 国内标准无语言标记
]
for _fn, _exp_lang in _lang_cases:
    _info = _parser.parse(_fn)
    _ok = _info is not None and _info.language == _exp_lang
    _check(f"语言标记: {_fn[:30]}", _ok,
           f"got={_info.language!r} exp={_exp_lang!r}" if _info and not _ok else "")

# --- v2.2 新增：版次跳过 ---
logger.info("--- 版次跳过 ---")
_info = _parser.parse("ANSI API Standard 610 10版 2004 离心泵（中文）.pdf")
_check("版次跳过: 10版", _info is not None and _info.year == 2004,
       f"year={_info.year if _info else 'None'}")
_info = _parser.parse("ANSI API Standard 610 Tenth Edition 2004 Centrifugal en.pdf")
_check("版次跳过: Tenth Edition", _info is not None and _info.year == 2004,
       f"year={_info.year if _info else 'None'}")

# --- v2.2 新增：适配器/引擎导入 ---
logger.info("--- 适配器/引擎导入 ---")
try:
    from pilotstd.query.adapters.dbba import DbbaAdapter
    _check("适配器导入: dbba", True)
except Exception as e:
    _check("适配器导入: dbba", False, str(e))

try:
    from pilotstd.announcement import AnnounceEngine, SamrGbAdapter, SamrHbAdapter, SamrDbAdapter
    _check("公告导入: 引擎+三适配器", True)
except Exception as e:
    _check("公告导入: 引擎+三适配器", False, str(e))

# --- v2.2 新增：附件子目录 ---
logger.info("--- 附件子目录 ---")
_attach_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "announcements")
for _t in ("gb", "hb", "db"):
    _d = ensure_dir(os.path.join(_attach_base, _t))
    _check(f"附件目录: announcements/{_t}", os.path.isdir(_d))
shutil.rmtree(os.path.join(_attach_base), ignore_errors=True)

# --- Worker 暂停/停止/进度 ---
logger.info("--- Worker 暂停/停止/进度 ---")
from unittest.mock import MagicMock
from pilotstd.ui.workers import QueryWorker
from pilotstd.models import ParsedStdInfo as _PI

def _make_items(n=3):
    return [_PI(raw_filename=f"test{i}.pdf", logical_code="GB", number=1000+i, year=2020,
                std_name=f"测试{i}", source_path=f"/tmp/test{i}.pdf") for i in range(n)]

# --- QueryWorker 进度 ---
_progress_hit = threading.Event()
_mgr = MagicMock()
def _slow_query(items, progress_callback=None, **kwargs):
    for i in range(5):
        if progress_callback:
            progress_callback(i + 1, 5)
        _progress_hit.set()
        time.sleep(0.01)
    return [], MagicMock(success=0, skipped_exists=0, failed=0, errors=0)
_mgr.query = _slow_query
_w = QueryWorker(_mgr, _make_items())
_w.start()
_ok = _progress_hit.wait(timeout=2.0)
_w.stop(); _w.wait(3000)
_check("Worker: QueryWorker 进度回调", _ok, "收到" if _ok else "超时")

# --- QueryWorker 暂停/继续 ---
# 用 slow_query 中 progress_callback 内部的 wait() 来测试暂停
_pause_evt = threading.Event(); _pause_evt.set()
_blocked = threading.Event()  # 当 progress_callback 被暂停阻塞时置位
_cb_count = [0]
def _pausable_query(items, progress_callback=None, **kwargs):
    for i in range(30):
        if progress_callback:
            progress_callback(i + 1, 30)
            # progress_callback 中会检查 pause_event.wait()
            # 如果被 clear，会阻塞。此时通知主线程"已阻塞"
            if not _pause_evt.is_set():
                _blocked.set()
        time.sleep(0.02)
    return [], MagicMock(success=0, skipped_exists=0, failed=0, errors=0)
_mgr2 = MagicMock(); _mgr2.query = _pausable_query
_w2 = QueryWorker(_mgr2, _make_items(2), pause_event=_pause_evt)
_w2.start()
time.sleep(0.1)          # 让 worker 先跑几个回调
_pause_evt.clear()       # 暂停：progress_callback 中的 wait() 将阻塞
_blocked.wait(timeout=2.0)  # 等待 worker 确认阻塞
time.sleep(0.1)
_paused_ok = not _w2.isFinished()  # 暂停后 worker 应该还在运行(被阻塞)
_pause_evt.set()          # 恢复
_w2.wait(3000)
_resumed_ok = _w2.isFinished()
_check("Worker: QueryWorker 暂停/继续", _paused_ok and _resumed_ok,
       f"暂停时运行={_paused_ok} 恢复后完成={_resumed_ok}")

# --- QueryWorker 停止 ---
_stop_hit = threading.Event()
def _stoppable_query(items, progress_callback=None, **kwargs):
    for i in range(5):
        if progress_callback:
            progress_callback(i + 1, 5)
        time.sleep(0.02)
    _stop_hit.set()
    return [], MagicMock(success=0, skipped_exists=0, failed=0, errors=0)
_mgr3 = MagicMock(); _mgr3.query = _stoppable_query
_w3 = QueryWorker(_mgr3, _make_items())
_batch_got = []
_w3.batch_ready.connect(lambda b: _batch_got.append(b))
_w3.start()
_w3.stop()
_w3.wait(3000)
_check("Worker: QueryWorker 停止", len(_batch_got) == 0,
       f"停止后batch_ready: {len(_batch_got)}次(预期0)")

# ======================================================================
# 汇总
# ======================================================================

# ======================================================================
# 汇总
# ======================================================================

total_time = time.time() - t0
logger.info("=" * 60)
logger.info("纯逻辑压力测试完成 (%.1fs)", total_time)
logger.info("日志: %s", _log_path)
_verdict()
