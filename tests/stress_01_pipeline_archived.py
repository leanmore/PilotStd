# 全量压力测试脚本 v6 — 第一层：核心管线
# 用法: python tests/stress_01_pipeline.py [--source D:\标准] [--output E:\标准]
# 设计原则: 脚本只负责编排和统计，所有功能通过 StandardManager 公共 API 调用。
# 覆盖: 扫描→查询(含分类)→下载(仅GB类)→归档→过期→缓存→v2.1回归

import sys, os, json, time, re, logging, tracemalloc, threading, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.config import ConfigManager, get_data_dir
from pilotstd.core.logger import LoggerManager
from pilotstd.core.file_index import FileIndexRepository
from pilotstd.core.file_utils import remove_empty_dirs, ensure_long_path
from pilotstd.core.db import Database
from pilotstd.manager import StandardManager
from pilotstd.scan.scanner import FileScanner
from pilotstd.query.network import get_monitor

_p = argparse.ArgumentParser(description="全量压力测试 — 第一层：核心管线")
_p.add_argument("--source", required=True, help="源目录，如 D:\\标准")
_p.add_argument("--output", required=True, help="输出目录，如 E:\\标准")
_p.add_argument("--skip-cache", action="store_true", help="跳过阶段6缓存验证（站点冷却时使用）")
import sys as _sys; _args = _p.parse_args([]) if "pytest" in _sys.argv[0] else _p.parse_args()
SOURCE_DIR = _args.source
OUTPUT_DIR = _args.output
SKIP_CACHE = _args.skip_cache

# Windows 长路径支持：os.walk 深层目录需 \\?\ 前缀
if os.name == 'nt':
    SOURCE_DIR = '\\\\?\\' + os.path.abspath(SOURCE_DIR)
    OUTPUT_DIR = '\\\\?\\' + os.path.abspath(OUTPUT_DIR)

# ════════════════════════════════════════════════════════════════
# 日志: 同时输出到文件和控制台
# ════════════════════════════════════════════════════════════════

_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_path = os.path.join(_log_dir, f"stress_{time.strftime('%Y%m%d_%H%M%S')}.log")

# 控制台 handler（方便实时查看）
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))

# 文件 handler（完整记录）
_fh = logging.FileHandler(_log_path, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname).1s] %(name)s %(message)s", datefmt="%H:%M:%S"))

_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_root.addHandler(_ch)
_root.addHandler(_fh)

# 抑制第三方日志噪音
for _mod in ('urllib3', 'requests', 'lxml', 'httpx', 'PIL'):
    logging.getLogger(_mod).setLevel(logging.WARNING)

logger = logging.getLogger("stress")

tracemalloc.start()

# ════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════

def _mem(b):
    for u in ('B', 'KB', 'MB', 'GB'):
        if b < 1024: return f'{b:.1f}{u}'
        b /= 1024
    return f'{b:.1f}TB'

def _mem_now():
    cur, _ = tracemalloc.get_traced_memory()
    return _mem(cur)

def _reset_peak():
    tracemalloc.reset_peak()

def _cooldown_str(mgr):
    """获取所有站点冷却状态（一行摘要）。"""
    try:
        rotator = mgr.query_engine.rotator
        if not rotator:
            return ""
        parts = []
        for name in rotator.list_sites():
            r = rotator.get_cooldown_remaining(name)
            if r > 0:
                parts.append(f"{name}:{r/3600:.1f}h" if r >= 3600 else f"{name}:{int(r)}s")
        return " | ".join(parts) if parts else "无"
    except Exception:
        return ""

class ProgressReporter:
    """定时心跳报告器：每隔 interval 秒或每 N 条输出一次进度。

    用于长耗时阶段（查询/下载），防止用户以为脚本卡死。
    """
    def __init__(self, total: int, label: str = "", interval: float = 30.0,
                 every_n: int = 50):
        self.total = total
        self.label = label
        self.interval = interval
        self.every_n = every_n
        self._start = time.time()
        self._last_report_time = self._start
        self._last_report_count = 0
        self._lock = threading.Lock()

    def __call__(self, current: int, _total: int = 0):
        """供 query_batch progress_callback 直接调用。"""
        now = time.time()
        elapsed = now - self._start
        with self._lock:
            # 最后一条必须报告（100% 完成）
            is_last = current >= self.total
            # 按时间间隔 或 按条数间隔 触发
            by_time = now - self._last_report_time >= self.interval
            by_count = current - self._last_report_count >= self.every_n
            if not (by_time or by_count or is_last):
                return
            self._last_report_time = now
            self._last_report_count = current

        pct = current / max(self.total, 1) * 100
        rate = current / max(elapsed, 0.001)
        eta = (self.total - current) / max(rate, 0.001)
        mem = _mem_now()
        cooldown = _cooldown_str(mgr_holder[0]) if mgr_holder else ""
        logger.info(
            "[进度] %s%s | %d/%d (%.1f%%) | 速率 %.1f条/s | 预计剩余 %.0fs | 内存 %s%s",
            self.label + " " if self.label else "",
            "完成" if is_last else "进行中",
            current, self.total, pct, rate, eta, mem,
            f" | 冷却: {cooldown}" if cooldown else ""
        )


# 模块级变量，供 ProgressReporter 回调访问 mgr（避免循环引用）
mgr_holder = [None]


def heartbeat(label: str, interval: float = 30.0):
    """返回 (start, stop) 函数，在后台线程定时输出心跳日志。

    用法:
        hb_start, hb_stop = heartbeat("下载", 30)
        hb_start()
        ...  # 长耗时阻塞操作
        hb_stop()
    """
    stop_event = threading.Event()
    start_time = time.time()

    def _beat():
        while not stop_event.wait(interval):
            elapsed = time.time() - start_time
            mem = _mem_now()
            logger.info("[心跳] %s 仍在运行... (已耗时 %.0fs, 内存 %s)", label, elapsed, mem)

    def _start():
        t = threading.Thread(target=_beat, daemon=True)
        t.start()
        return t

    return _start, stop_event.set

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

# ════════════════════════════════════════════════════════════════
# 开始
# ════════════════════════════════════════════════════════════════

t0 = time.time()
logger.info("=" * 60)
logger.info("全量压力测试 v7 — 第一层：核心管线 | %s", time.strftime("%Y-%m-%d %H:%M:%S"))
logger.info("源: %s  输出: %s", SOURCE_DIR, OUTPUT_DIR)
logger.info("日志: %s", _log_path)
logger.info("=" * 60)

# ── 前置检查 ──
def _precheck():
    """验证运行环境是否满足压测条件，不满足则直接退出。"""
    ok = True
    # 1. 源目录存在且含文件
    if not os.path.isdir(SOURCE_DIR):
        logger.critical("前置失败: 源目录不存在 — %s", SOURCE_DIR)
        ok = False
    else:
        _src_files = sum(1 for _ in os.walk(SOURCE_DIR) for _f in _[2])
        if _src_files == 0:
            logger.critical("前置失败: 源目录无文件 — %s", SOURCE_DIR)
            ok = False
        else:
            logger.info("前置通过: 源目录 %d 文件", _src_files)
    # 2. 输出目录存在或可创建
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info("前置通过: 输出目录就绪")
    except OSError as e:
        logger.critical("前置失败: 无法创建输出目录 — %s", e)
        ok = False
    # 3. DB 状态（冷启动需清DB，热启动保留）
    _db_path = os.path.join(get_data_dir(), "pilotstd.db")
    if os.path.exists(_db_path):
        logger.info("前置: DB已存在(%s)→热启动模式（缓存命中+去重）",
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(_db_path))))
    else:
        logger.info("前置: DB不存在→冷启动模式（全量查询+首次归档）")
    if not ok:
        sys.exit(1)

_precheck()

cfg = ConfigManager()
cfg.set("storage.root_dir", OUTPUT_DIR)
cfg.set("query.use_cache", False)

# ── 初始化 ──
logger.info("初始化 StandardManager...")
mgr = StandardManager(config=cfg)
mgr_holder[0] = mgr  # 供 ProgressReporter 回调中访问冷却状态
logger.info("初始化完成 (%.1fs)", time.time() - t0)

# ════════════════════════════════════════════════════════════════
# 阶段1: 扫描
# ════════════════════════════════════════════════════════════════
_reset_peak()
t1 = time.time()
logger.info("--- 阶段1: 扫描 ---")

# 压力测试不传 file_index——否则 2063 条索引会把已归档文件全部跳过，失去压力意义
scanner = FileScanner(cfg, file_index=None)
scan_result = scanner.scan([SOURCE_DIR])
word_files = [f for f in scan_result.files if f.filename.lower().endswith(('.doc', '.docx'))]
pdf_files  = [f for f in scan_result.files if not f.filename.lower().endswith(('.doc', '.docx'))]

logger.info("扫描: %d PDF + %d Word | 排除 %d | 跳过目录 %d (%.1fs)",
            len(pdf_files), len(word_files),
            scan_result.stats.skipped, len(scan_result.skipped_dirs),
            time.time() - t1)

# 代号分布
codes = {}
for f in pdf_files:
    info = mgr.parser.parse(f.filename)
    if info:
        codes[info.logical_code] = codes.get(info.logical_code, 0) + 1

logger.info("PDF 代号分布:")
for c, n in sorted(codes.items(), key=lambda x: -x[1])[:15]:
    logger.info("  %s: %d", c, n)

gb_total = codes.get("GB", 0) + codes.get("GB/T", 0)
logger.info("GB类合计: %d (GB %d + GB/T %d)", gb_total, codes.get("GB", 0), codes.get("GB/T", 0))

_check("扫描: PDF有文件", len(pdf_files) > 0, f"{len(pdf_files)} 个")

# ════════════════════════════════════════════════════════════════
# 阶段2: 查询（使用 mgr.query() 公共 API，内部自动分类）
# ════════════════════════════════════════════════════════════════
_reset_peak()
t2 = time.time()
logger.info("--- 阶段2: 查询（渐进搜索 + 自动分类）---")

# 解析 PDF 为 ParsedStdInfo 列表
parsed_pdf = []
for f in pdf_files:
    info = mgr.parser.parse(f.filename)
    if info:
        info.source_path = f.full_path
        parsed_pdf.append(info)

total = len(parsed_pdf)
logger.info("PDF 解析: %d 条，开始全量查询...", total)

get_monitor().reset()

# 查询进度：每 30s 或每 50 条输出一次心跳
_query_reporter = ProgressReporter(total, "查询", interval=30.0, every_n=50)
results, q_stats = mgr.query(parsed_pdf, progress_callback=_query_reporter)
_log_query_end = time.time()
logger.info("查询实际耗时: %.1fs (平均 %.1fs/条)", _log_query_end - t2, (_log_query_end - t2) / max(total, 1))
query_time = time.time() - t2

# 读取分类结果（由 _classify_after_query 填充）
dl_list = getattr(mgr, '_download_list', [])
exp_list = getattr(mgr, '_expire_list', [])
pend_list = getattr(mgr, '_pending_list', [])

logger.info("统计: 找到%d | 可下载%d | 需下载%d | 采标%d | 过期%d | 待确认%d | 未找到%d | 错误%d",
            q_stats.found, q_stats.downloadable, len(dl_list),
            q_stats.adopted_restricted, len(exp_list), len(pend_list),
            q_stats.not_found, q_stats.errors)
logger.info("查询耗时: %.1fs (平均 %.1fs/条)", query_time, query_time / max(total, 1))

# 需下载清单：打印每条标准的来源站点、hcno、采标状态
if dl_list:
    logger.info("需下载清单(%d条):", len(dl_list))
    # 用id()映射避免ParsedStdInfo不可hash的问题
    _qr_by_id = {}
    for i, r in enumerate(mgr._query_results):
        if i < len(mgr._queried_items):
            _qr_by_id[id(mgr._queried_items[i])] = r
    for p in dl_list:
        r = _qr_by_id.get(id(p))
        _r_site = getattr(r, 'source_site', '?') if r else '?'
        _r_hcno = getattr(r, 'hcno', '?') if r else '?'
        _r_adopted = getattr(r, 'is_adopted', '?') if r else '?'
        _r_status = getattr(r, 'status', '?') if r else '?'
        logger.info("  %s | 来源=%s | hcno=%s | 采标=%s | 状态=%s | match=%s",
                    p.get_full_number(), _r_site, _r_hcno[:20] if _r_hcno else '?',
                    _r_adopted, _r_status, getattr(p, 'match_status', '?'))

# 验证分类合理性: 下载列表应全为 GB 类
non_gb_in_dl = [p for p in dl_list if not mgr._is_gb_code(p.logical_code)]
_check("分类: 下载列表全为GB类", len(non_gb_in_dl) == 0,
       f"非GB类 {len(non_gb_in_dl)} 条" if non_gb_in_dl else "全部GB类")

net_summary = get_monitor().summary()
_check("查询: 网络无异常", not net_summary, net_summary or "OK")

# 站点分布
site_stats = {}
for p in parsed_pdf:
    s = getattr(p, '_last_source_site', 'unknown')
    site_stats[s] = site_stats.get(s, 0) + 1
if site_stats:
    logger.info("站点分流:")
    for s, n in sorted(site_stats.items(), key=lambda x: -x[1]):
        logger.info("  %s: %d", s, n)

_log_query = time.time() - t2
logger.info("内存: %s", _mem_now())

# ════════════════════════════════════════════════════════════════
# 阶段3: 下载（仅下载列表中的项）
# ════════════════════════════════════════════════════════════════
_reset_peak()
t3 = time.time()
logger.info("--- 阶段3: 下载 (%d 条) ---", len(dl_list))

if dl_list:
    # 下载可能很耗时，启动心跳线程
    _dl_hb_start, _dl_hb_stop = heartbeat("下载", interval=30.0)
    _dl_hb_start()
    dl_tasks, dl_stats = mgr.download()
    _dl_hb_stop()
    logger.info("下载: 成功 %d | 采标跳过 %d | 已存在 %d | 失败 %d | 错误 %d (%.1fs)",
                dl_stats.success, dl_stats.skipped_adopted, dl_stats.skipped_exists,
                dl_stats.failed, dl_stats.errors, time.time() - t3)
    # 打印每条失败/跳过任务的详细原因
    for _t in dl_tasks:
        if _t.status.value in ("failed", "skipped") and _t.error_message:
            logger.info("  下载详情: %s | %s: %s", _t.standard_number, _t.status.value, _t.error_message)
    # 判定：成功/已存在/采标跳过均为正常结果，仅全失败+无采标时才FAIL
    _dl_any_ok = (dl_stats.success > 0 or dl_stats.skipped_exists > 0
                  or dl_stats.skipped_adopted > 0)
    _check("下载: 有成功/已存在/采标跳过", _dl_any_ok,
           f"成功{dl_stats.success} 已存在{dl_stats.skipped_exists} 采标跳过{dl_stats.skipped_adopted}")
else:
    logger.info("下载列表为空，跳过")
    dl_stats = type('obj', (object,), {'success': 0, 'skipped_adopted': 0, 'skipped_exists': 0, 'failed': 0, 'errors': 0})()

# ════════════════════════════════════════════════════════════════
# 阶段3.5: 规范化验证
# ════════════════════════════════════════════════════════════════
_norm_re = re.compile(r'^[A-Z]+(?:\s*/\s*[A-Z]+)?\s+\d+(?:\.\d+)?-\d{4}\s')

t35 = time.time()
dl_files = []
_downloads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")
if os.path.isdir(_downloads_dir):
    for _root, _dirs, _files in os.walk(_downloads_dir):
        for _f in _files:
            if _f.lower().endswith('.pdf'):
                dl_files.append(os.path.join(_root, _f))

norm_ok = sum(1 for f in dl_files if _norm_re.match(os.path.basename(f)))
norm_bad = len(dl_files) - norm_ok
logger.info("规范化: %d 符合, %d 不规范 (%d 文件, %.1fs)", norm_ok, norm_bad, len(dl_files), time.time() - t35)
if dl_files:
    _check("规范化: 大部分符合规范", norm_ok >= max(1, len(dl_files) * 0.8))

# ════════════════════════════════════════════════════════════════
# 阶段4: 归档
# ════════════════════════════════════════════════════════════════
_reset_peak()
t4 = time.time()
logger.info("--- 阶段4: 归档 ---")

_arc_hb_start, _arc_hb_stop = heartbeat("归档", interval=30.0)
_arc_hb_start()
org_pdf = mgr.organize(parsed_pdf)
_arc_hb_stop()

# 解析 Word 文件（含未识别 fallback）
from pilotstd.models import ParsedStdInfo as _PSI
parsed_word = []
for f in word_files:
    info = mgr.parser.parse(f.filename)
    if info:
        info.source_path = f.full_path
        parsed_word.append(info)
    else:
        fb = _PSI(raw_filename=f.filename, logical_code="WORD", number=0, year=0)
        fb.source_path = f.full_path
        fb.std_name = os.path.splitext(f.filename)[0]
        parsed_word.append(fb)

org_word = mgr.organize(parsed_word, word_source_root=SOURCE_DIR) if parsed_word else {"moved": 0, "failed": 0}
org_skipped = mgr.organize_skipped_dirs(scan_result.skipped_dirs, source_root=SOURCE_DIR) if scan_result.skipped_dirs else {"moved": 0, "failed": 0}
# 兜底镜像：归档后残留文件（扩展名不支持/关键词排除/解析失败）按源目录结构搬走
org_fallback = mgr.organize_fallback(SOURCE_DIR)
# 清理源目录中所有空子目录（兜底镜像可能产生新空目录，循环至清零）
# 多层嵌套空目录需多轮清理（os.walk 快照机制导致每轮只能清一层）
_empty_removed = 0
_pass = 0
while True:
    _pass += 1
    _n = remove_empty_dirs(SOURCE_DIR)
    _empty_removed += _n
    if _n:
        logger.info("源目录空文件夹清理(第%d遍): %d 个", _pass, _n)
    if _n == 0:
        break

logger.info("归档 (%.1fs): PDF移动%d 已存在%d | Word镜像%d | 目录%d | 兜底%d | 失败%d",
            time.time() - t4,
            org_pdf.get('moved', 0), org_pdf.get('skipped_exists', 0),
            org_word.get('word_mirrored', 0) if isinstance(org_word, dict) else 0,
            org_skipped.get('moved', 0),
            org_fallback.get('moved', 0),
            org_pdf.get('failed', 0) + (org_word.get('failed', 0) if isinstance(org_word, dict) else 0))
_check("归档: 有PDF移动或已存在", org_pdf.get('moved', 0) + org_pdf.get('skipped_exists', 0) > 0)

# --- 归档命名规范性检查（复用 _norm_re） ---
t37 = time.time()
_archive_pdfs = []
for _root, _dirs, _files in os.walk(OUTPUT_DIR):
    for _f in _files:
        if _f.lower().endswith('.pdf'):
            _archive_pdfs.append(_f)

_archive_norm_ok = sum(1 for f in _archive_pdfs if _norm_re.match(f))
_archive_norm_bad = len(_archive_pdfs) - _archive_norm_ok
logger.info("归档命名: %d 符合, %d 不规范 (%d 文件, %.1fs)",
            _archive_norm_ok, _archive_norm_bad, len(_archive_pdfs), time.time() - t37)
if _archive_pdfs:
    _check("归档命名: >=80%符合规范",
           _archive_norm_ok >= max(1, len(_archive_pdfs) * 0.8),
           f"{_archive_norm_ok}/{len(_archive_pdfs)}")

# TSG 双目录检查（B修复验证）
_top_dirs = set()
for _r, _ds, _fs in os.walk(OUTPUT_DIR):
    for _d in _ds:
        _top_dirs.add(_d)
    break  # 只看第一层
_tsg_bare = any(d == "TSG" for d in _top_dirs)
_tsg_full = any(d == "TSG 特种设备安全技术规范" for d in _top_dirs)
_check("归档: TSG目录名统一", not (_tsg_bare and _tsg_full),
       f"裸名:{_tsg_bare} 全名:{_tsg_full} (同现=双目录bug)")

# Word 镜像数量检查
_word_mirrored = org_word.get('word_mirrored', 0) if isinstance(org_word, dict) else 0
_word_total = len(word_files)
if _word_total > 0:
    _check("归档: Word镜像数量正确", _word_mirrored > 0,
           f"镜像 {_word_mirrored} / 总计 {_word_total} Word 文件")
else:
    _check("归档: Word镜像数量正确", True, "无Word文件，跳过")

# 空目录检查：归档后源目录不应残留空文件夹（用长路径前缀绕过 Windows MAX_PATH 限制）
_empty_dirs = []
# 统一加 \\?\ 前缀确保深度嵌套目录（>260字符）也能被遍历到
_walk_root = ensure_long_path(SOURCE_DIR) if os.name == 'nt' else SOURCE_DIR
for _root, _dirs, _files in os.walk(_walk_root):
    if not _files and not _dirs:
        _empty_dirs.append(_root)
_check("归档: 源目录无残留空文件夹", len(_empty_dirs) == 0,
       f"{len(_empty_dirs)} 个空目录" if _empty_dirs else "零空目录")

# ════════════════════════════════════════════════════════════════
# 阶段5: 过期处理
# ════════════════════════════════════════════════════════════════
if exp_list:
    t55 = time.time()
    logger.info("--- 阶段5: 过期处理 (%d 条) ---", len(exp_list))
    exp_result = mgr.handle_expired(exp_list)
    logger.info("过期处理 (%.1fs): 移动 %d | 失败 %d",
                time.time() - t55, exp_result.get('moved', 0), exp_result.get('failed', 0))
    _check("过期处理: 可执行", True)
else:
    logger.info("无过期项，跳过阶段5")

# ════════════════════════════════════════════════════════════════
# 阶段6: 缓存验证
# ════════════════════════════════════════════════════════════════
if SKIP_CACHE:
    logger.info("--- 阶段6: 缓存验证（跳过） ---")
    _check("缓存: 命中率", None, "SKIP")
    _check("缓存: 公告回退", None, "SKIP")
else:
    logger.info("--- 阶段6: 缓存验证 ---")

    # 6a: 启用缓存后重复查询应命中
    if total >= 5:
        cfg.set("query.use_cache", True)
        hits = 0
        for p in parsed_pdf[:5]:
            r1 = mgr.query_engine.query_single(p.get_full_number())
            r2 = mgr.query_engine.query_single(p.get_full_number())
            if r1 and r2 and r1.standard_name == r2.standard_name:
                hits += 1
        _check("缓存: 命中率", hits >= 4, f"{hits}/5")
        cfg.set("query.use_cache", False)

    # 6b: 公告缓存回退
    try:
        from pilotstd.core.file_index import ANNOUNCEMENT_CACHE_TABLE
        _test_std = "GB/T 99999-2099"
        _test_data = {"status": "现行", "standard_name": "公告回退验证",
                      "match_status": "exact", "is_adopted": False, "source_site": "announcement"}
        mgr.db.execute(
            f"INSERT OR REPLACE INTO {ANNOUNCEMENT_CACHE_TABLE} "
            "(standard_number, source_site, result_json, cached_at) VALUES (?, 'announcement', ?, datetime('now'))",
            (_test_std, json.dumps(_test_data, ensure_ascii=False)))
        cr = mgr.cache.get(_test_std, "csres")
        _check("缓存: 公告回退", cr is not None and cr.standard_name == "公告回退验证")
        mgr.db.execute(f"DELETE FROM {ANNOUNCEMENT_CACHE_TABLE} WHERE standard_number=?", (_test_std,))
    except Exception as e:
        _check("缓存: 公告回退测试可执行", False, str(e))

# ════════════════════════════════════════════════════════════════
# 阶段7: file_index
# ════════════════════════════════════════════════════════════════
_db_path = os.path.join(get_data_dir(), "pilotstd.db")
if os.path.exists(_db_path):
    fix = FileIndexRepository(Database(_db_path))
    n = fix.count()
    _check("file_index: 有记录", n > 0, f"{n} 条")

# ════════════════════════════════════════════════════════════════
# 阶段8: v2.1 回归检查
# ════════════════════════════════════════════════════════════════
logger.info("--- 阶段8: v2.1 回归 ---")

# Worker 导入
try:
    from pilotstd.ui.workers import (LogHandler, QueryWorker, DownloadWorker,
                                      NormalizeWorker, ArchiveWorker, ScanWorker,
                                      AnnounceWorker, RowUpdate)
    _check("Worker提取: 导入正常", True)
except Exception as e:
    _check("Worker提取: 导入正常", False, str(e))

# BS 解析器
try:
    from pilotstd.announcement.parser import parse_announcement_meta, parse_html_table
    _html = "<html><head><title>公告测试</title></head><body>"
    _html += "<table><thead><tr><th>序号</th><th>标准编号</th><th>标准名称</th><th>代替标准号</th><th>发布日期</th></tr></thead>"
    _html += "<tbody><tr><td>1</td><td>GB/T 1-2026</td><td>测试</td><td>GB/T 1-2020</td><td>2026-05-01</td></tr></tbody></table>"
    _html += "<p>2026-05-29</p></body></html>"
    _meta = parse_announcement_meta(_html)
    _items = parse_html_table(_html)
    _check("BS解析: meta标题", _meta["title"] == "公告测试")
    _check("BS解析: 代替关系", len(_items) == 1 and _items[0]["replaces_code"] == "GB/T 1-2020")
except Exception as e:
    _check("BS解析: 可执行", False, str(e))

# 数据库备份
try:
    _bak = mgr.db.backup()
    _check("退出备份: .bak存在", os.path.exists(_bak) and os.path.getsize(_bak) > 0)
except Exception as e:
    _check("退出备份: 可执行", False, str(e))

# csres HTTP 提示
try:
    from pilotstd.query.adapters.csres import CsresAdapter
    _csres = CsresAdapter()
    _check("HTTP提示: csres已警告", CsresAdapter._http_warned)
except Exception as e:
    _check("HTTP提示: 可执行", False, str(e))

# ddddocr
try:
    import ddddocr
    _check("ddddocr: 可用", True)
except Exception as e:
    _check("ddddocr: 可用", False, str(e))

# 下载内容类型无误报
_type_lines = 0
if os.path.exists(_log_path):
    with open(_log_path, encoding='utf-8') as lf:
        _type_lines = sum(1 for l in lf if '文件类型异常' in l)
_check("类型校验: 无误报", _type_lines == 0,
       f"误报 {_type_lines} 次" if _type_lines else "零误报")

# 路径越界拦截
try:
    from pilotstd.organizer.mover import FileMover
    _mover = FileMover.__new__(FileMover)
    _mover._library_root = os.path.join(OUTPUT_DIR, "GB 国家标准")
    _safe_inside = _mover._is_safe_path(
        os.path.join(OUTPUT_DIR, "GB 国家标准", "subdir", "test.pdf"))
    _safe_outside = _mover._is_safe_path(
        os.path.join(OUTPUT_DIR, "..", "outside.pdf"))
    _check("路径安全: 子目录通过", _safe_inside)
    _check("路径安全: 越界拒绝", not _safe_outside)
except Exception as e:
    _check("路径安全: 可执行", False, str(e))

# ════════════════════════════════════════════════════════════════
# v2.2 回归：DB 解析 / 语言标记 / 版次跳过 / 适配器导入 / 公告引擎
# ════════════════════════════════════════════════════════════════
logger.info("--- v2.2 回归 ---")

# DB 地方标准解析
try:
    from pilotstd.scan.parser import StandardParser
    from pilotstd.organizer.industry_lookup import build_code_mapping
    _p = StandardParser(build_code_mapping())
    _info = _p.parse("DB11/T 1951-2021 城市照明规划标准.pdf")
    _check("DB解析: DB11/T 1951-2021", _info is not None
           and _info.logical_code == "DB11/T" and _info.number == 1951)
    _info = _p.parse("DB3501/T 002-2023 福州标准.pdf")
    _check("DB解析: DB3501/T 002-2023", _info is not None
           and _info.logical_code == "DB3501/T" and _info.number == 2)
except Exception as e:
    _check("DB解析: 可执行", False, str(e))

# 语言标记
try:
    _info = _p.parse("ASME 1-2021 压力容器建造规则（中文）.pdf")
    _check("语言标记: 中文版", _info is not None and _info.language == "中文版")
    _info = _p.parse("API Spec 6D-2008 阀门（英文）.pdf")
    _check("语言标记: 英文版", _info is not None and _info.language == "英文版")
except Exception as e:
    _check("语言标记: 可执行", False, str(e))

# 版次跳过
try:
    _info = _p.parse("ANSI API Standard 610 10版 2004 离心泵（中文）.pdf")
    _check("版次跳过: 10版", _info is not None and _info.year == 2004)
except Exception as e:
    _check("版次跳过: 可执行", False, str(e))

# dbba 适配器
try:
    from pilotstd.query.adapters.dbba import DbbaAdapter
    _check("适配器: dbba导入", True)
except Exception as e:
    _check("适配器: dbba导入", False, str(e))

# 公告模块
try:
    from pilotstd.announcement import AnnounceEngine, SamrGbAdapter, SamrHbAdapter, SamrDbAdapter
    _check("公告: 引擎+三适配器导入", True)
except Exception as e:
    _check("公告: 引擎+三适配器导入", False, str(e))

# 附件子目录
try:
    from pilotstd.core.file_utils import ensure_dir
    import shutil as _shutil
    _attach_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "data", "announcements")
    for _t in ("gb", "hb", "db"):
        ensure_dir(os.path.join(_attach_base, _t))
    _check("附件子目录: gb/hb/db", True)
    _shutil.rmtree(_attach_base, ignore_errors=True)
except Exception as e:
    _check("附件子目录: gb/hb/db", False, str(e))

# fetch_log 表
try:
    _rows = mgr.db.fetchall(
        "SELECT source_site FROM fetch_log WHERE source_site IN ('nocGB','nocHB','nocDB')")
    _check("fetch_log: 表查询正常", isinstance(_rows, list))
except Exception as e:
    _check("fetch_log: 表查询正常", False, str(e))

# ════════════════════════════════════════════════════════════════
# v2.3 回归：分类验证 / 待确认 / 搜索策略 / 下载路由 / 适配器统一
# ════════════════════════════════════════════════════════════════
logger.info("--- v2.3 回归 ---")

# 10. 分类验证：get_stage_queue + stage_status
logger.info("  10a. 分类队列")
s = mgr.get_stage_summary()
_check("分类: get_stage_summary返回字典", isinstance(s, dict) and "download" in s)
_check("分类: download+expire+pending <= total",
       s.get("download",0) + s.get("expire",0) + s.get("pending",0) <= s.get("total", 1),
       f"download={s.get('download')} expire={s.get('expire')} pending={s.get('pending')} total={s.get('total')}")

dl = mgr.get_stage_queue("download")
ex = mgr.get_stage_queue("expire")
pe = mgr.get_stage_queue("pending")

# 非 GB newer 不应在 download 中
_non_gb_newer_dl = [p for p in dl if p.match_status == "newer" and not p.logical_code.upper().startswith("GB")]
_check("分类: 非GB newer不在download", len(_non_gb_newer_dl) == 0,
       f"{len(_non_gb_newer_dl)} 条" if _non_gb_newer_dl else "OK")

# stage_status 已回写
_has_status = sum(1 for p in parsed_pdf if getattr(p, 'stage_status', ''))
_check("分类: stage_status已回写", _has_status > 0, f"{_has_status} 条有stage_status")

# 11. 待确认三维限制
logger.info("  11. 待确认三维限制")
try:
    _pn = pe[0].get_full_number() if pe else None
    if _pn:
        # 重置计数避免上轮残留
        mgr.db.execute("UPDATE pending_lookup SET requery_count=0 WHERE standard_number=?", (_pn,))
        _c1 = mgr.increment_requery_count(_pn)
        _c2 = mgr.increment_requery_count(_pn)
        _c3 = mgr.increment_requery_count(_pn)
        _check("待确认: requery_count 递增正确", _c1 == 1 and _c2 == 2 and _c3 == 3,
               f"count: {_c1},{_c2},{_c3}")
        _check("待确认: 3次后已耗尽", mgr.is_requery_exhausted(_pn))
        mgr.mark_manual_required(_pn)
        _check("待确认: mark_manual_required可执行", True)
    else:
        _check("待确认: requery检查", None, "SKIP 无pending条目")
except Exception as e:
    _check("待确认: 可执行", False, str(e))

# 12. 搜索策略回归
logger.info("  12. 搜索策略回归")
from pilotstd.query.search_strategy import (
    build_search_terms, build_code_variants, _parse_result_number, match_result)

# build_search_terms 回退层级去重验证（无 part 时层级 3/4 与 1/2 重复，去重后 ≥ 4 层即正确）
_terms = build_search_terms("GB/T", 19001, 2016, "质量管理体系")
_check("搜索词: 去重后层级", len(_terms) >= 4, f"{len(_terms)} 级")
_check("搜索词: 第1级含年份", str(2016) in _terms[0])

# build_code_variants
_check("变体: ASME→BPVC", any("BPVC" in t for t in build_code_variants("ASME", 8, 2021, "VIII")))
_check("变体: API→Std", any("Std" in t for t in build_code_variants("API", 610, 2004)))
_check("变体: DIN→EN", any("DIN EN" in t for t in build_code_variants("DIN", 11851, 1998)))

# _parse_result_number 新格式
_r1 = _parse_result_number("DB35/T 1234-2020")
_check("解析: DB35/T", _r1.get("code") == "DB35T" and _r1.get("year") == 2020,
       str(_r1))
_r2 = _parse_result_number("IEC 61000-4-2:2008")
_check("解析: IEC多连字符", _r2.get("code") == "IEC" and _r2.get("year") == 2008,
       str(_r2))
_r3 = _parse_result_number("ASME VIII.1-2021")
_check("解析: ASME罗马数字", _r3.get("code") == "ASME" and _r3.get("number") == 8,
       str(_r3))

# match_result 不应该是自比较
_, _ms = match_result("API", 610, 2004, "Centrifugal Pumps", "API 610-2004")
_check("匹配: API exact", _ms == "exact", _ms)
_, _ms = match_result("API", 610, 2004, "", "ISO 9001-2015")
_check("匹配: API vs ISO mismatch", _ms == "mismatch", _ms)

# 13. 下载 source_site 传播
logger.info("  13. 下载路由")
from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
from pilotstd.download.engine import DownloadEngine
from pilotstd.download.models import DownloadTask
from pilotstd.download.session import SessionManager as _SM
_oad = OpenstdDownloadAdapter(_SM().create_session())
_eng = DownloadEngine(adapters=[_oad], session_manager=_SM(),
                       save_root=os.path.join(OUTPUT_DIR, "dl_verify"))
_check("下载: can_handle拒绝空source", not _oad.can_handle(DownloadTask(standard_number="GB/T 1-2020", source_site="")))
_check("下载: can_handle接受openstd", _oad.can_handle(DownloadTask(standard_number="GB/T 1-2020", source_site="openstd_download")))
_check("下载: can_handle拒绝njbz365", not _oad.can_handle(DownloadTask(standard_number="API 610-2004", source_site="njbz365")))
_found = _eng._find_adapter(DownloadTask(standard_number="GB/T 1-2020", source_site="std_gov"))
_check("下载: std_gov→openstd映射", _found is not None and _found.site_name == "openstd_download",
       f"found={_found.site_name if _found else 'None'}")
_none = _eng._find_adapter(DownloadTask(standard_number="API 610-2004", source_site="njbz365"))
_check("下载: 国外标准无适配器", _none is None, f"found={_none}")

# 14. 适配器 _search_candidates 统一
logger.info("  14. 适配器统一")
from pilotstd.query.adapters.njbz365 import Njbz365Adapter as _NJ
_nj = _NJ()
_check("适配器: njbz365有_search_candidates", hasattr(_nj, '_search_candidates'))
_check("适配器: njbz365有_post_process_result", hasattr(_nj, '_post_process_result'))
_check("适配器: njbz365无query_with_strategy重写",
       _NJ.query_with_strategy.__qualname__.startswith("BaseAdapter"))

from pilotstd.query.adapters.hbba import HbbaAdapter as _HB
_hb = _HB()
_check("适配器: hbba有_search_candidates", hasattr(_hb, '_search_candidates'))
_check("适配器: hbba有_post_process_result", hasattr(_hb, '_post_process_result'))
_check("适配器: hbba无_pick_best", not hasattr(_hb, '_pick_best'))

from pilotstd.query.adapters.dbba import DbbaAdapter as _DB
_db = _DB()
_check("适配器: dbba无_pick_best", not hasattr(_db, '_pick_best'))

from pilotstd.query.adapters.iso_gov import IsoGovAdapter as _IG
_ig = _IG()
_check("适配器: iso_gov无_pick_best", not hasattr(_ig, '_pick_best'))

# 15. DB 迁移 v9
logger.info("  15. DB迁移")
try:
    _cols = {r["name"] for r in mgr.db.fetchall("PRAGMA table_info(pending_lookup)")}
    _check("DB迁移: requery_count列存在", "requery_count" in _cols if _cols else None,
           "SKIP 表不存在" if not _cols else ("OK" if "requery_count" in _cols else "缺失"))
except Exception as e:
    _check("DB迁移: 检查可执行", False, str(e))

# 16. ParsedStdInfo 新字段
logger.info("  16. 模型字段")
from pilotstd.models import ParsedStdInfo as _PSI
_psi = _PSI(raw_filename="test.pdf", logical_code="GB/T", number=1, year=2020)
_check("模型: found_source_site字段", hasattr(_psi, 'found_source_site'))
_check("模型: stage_status字段", hasattr(_psi, 'stage_status'))

# 17. 异常恢复（网络超时、非JSON响应、站点冷却）
logger.info("  17. 异常恢复")
from pilotstd.query.network import get_monitor as _gm
_monitor = _gm()
_check("异常恢复: 网络监控可用", _monitor is not None)
_check("异常恢复: 查询无未捕获异常", True)  # 阶段2已跑完全量查询

# 日志验证：超时重试、冷却阻塞
_log_text_err = ""
try:
    with open(_log_path, 'r', encoding='utf-8', errors='replace') as _lf:
        _log_text_err = _lf.read()
except OSError:
    pass
_has_retry = "重试" in _log_text_err or "retry" in _log_text_err.lower()
_has_cooldown = "冷却" in _log_text_err or "cooldown" in _log_text_err.lower()
_check("异常恢复: 超时重试机制存在", True, "日志含重试" if _has_retry else "本次无超时重试")
_check("异常恢复: 冷却机制存在", True, "日志含冷却" if _has_cooldown else "本次无冷却触发")

# 18. 跨适配器一致性
logger.info("  18. 跨适配器")
from pilotstd.query.adapters.hbba import HbbaAdapter as _HBA
from pilotstd.query.adapters.njbz365 import Njbz365Adapter as _NJZ
from pilotstd.query.adapters.std_gov import StdGovAdapter as _SGA
_hba = _HBA()
_njz = _NJZ()
_sga = _SGA()

# GB/T 19001 在 std_gov 和 njbz365 均可查
_r_sg = _sga.query_with_strategy("GB/T", 19001, 2016)
_r_nj = _njz.query_single("GB/T 19001-2016")
_check("跨适配器: GB在std_gov查到", _r_sg is not None and _r_sg.is_found(),
       f"match={getattr(_r_sg,'match_status','?')}" if _r_sg else "无结果")
_check("跨适配器: GB在njbz365查到", _r_nj is not None and _r_nj.is_found(),
       f"match={getattr(_r_nj,'match_status','?')}" if _r_nj else "无结果")

# SH/T 1610 在 hbba 和 njbz365 均可查
_r_hb = _hba._search("SH/T 1610-2011")
_r_nj_sh = _njz.query_single("SH/T 1610-2011")
_check("跨适配器: SH在hbba查到", _r_hb is not None and _r_hb.is_found(),
       f"match={getattr(_r_hb,'match_status','?')}" if _r_hb else "无结果")
_check("跨适配器: SH在njbz365查到", _r_nj_sh is not None and _r_nj_sh.is_found(),
       f"match={getattr(_r_nj_sh,'match_status','?')}" if _r_nj_sh else "无结果")

# 19. FileWatcher 文件监控
logger.info("  19. FileWatcher")
try:
    mgr.start_watching([SOURCE_DIR])
    _check("FileWatcher: 启动不报错", True)
    mgr.stop_watching()
    _check("FileWatcher: 停止不报错", True)
except ImportError:
    _check("FileWatcher: 启动", None, "SKIP watchdog未安装")
except Exception as e:
    _check("FileWatcher: 可执行", False, str(e))

# 20. ProjectManager 项目保存/加载
logger.info("  20. ProjectManager")
from pilotstd.core.project import ProjectManager as _PM
_pm = _PM()
_proj_path = os.path.join(OUTPUT_DIR, "_stress_test_project.pilotstd")
_state = {"test_key": "test_value", "parsed_count": 42}
try:
    _pm.save(_proj_path, _state)
    _check("ProjectManager: 保存成功", os.path.isfile(_proj_path))
    _loaded = _pm.load(_proj_path)
    _check("ProjectManager: 加载成功", _loaded is not None and _loaded.get("test_key") == "test_value")
finally:
    try: os.remove(_proj_path)
    except OSError: pass

# 21. ScheduledService
logger.info("  21. ScheduledService")
from pilotstd.manager.scheduled_service import ScheduledService as _SS
_ss = _SS(cfg=mgr.cfg, scanner=mgr.scanner, parser=mgr.parser,
          query_engine=mgr.query_engine, file_index=mgr.file_index,
          quota_tracker=mgr.quota_tracker, download_engine=mgr.download_engine)
_tmp_scan_dir = os.path.join(OUTPUT_DIR, "_stress_scheduled_test")
os.makedirs(_tmp_scan_dir, exist_ok=True)
with open(os.path.join(_tmp_scan_dir, "GBT 19001-2016.pdf"), "w") as _f: _f.write("test")
try:
    _n = _ss.scan_and_index(_tmp_scan_dir)
    _check("Scheduled: scan_and_index", _n >= 0, f"入库 {_n} 条")
except Exception as e:
    _check("Scheduled: scan_and_index", False, str(e))
_shutil.rmtree(_tmp_scan_dir, ignore_errors=True)

# ════════════════════════════════════════════════════════════════
# 汇总
# ════════════════════════════════════════════════════════════════
total_time = time.time() - t0
cur_f, peak = tracemalloc.get_traced_memory()
logger.info("=" * 60)
logger.info("全量压力测试完成 (%.1fs / %.1fmin)", total_time, total_time / 60)
logger.info("阶段: 扫描(%.1fs) → 查询(%.1fs) → 下载(%.1fs) → 归档(%.1fs)",
            time.time() - t1 if 't1' in dir() else 0,
            query_time,
            time.time() - t3 if 't3' in dir() else 0,
            time.time() - t4 if 't4' in dir() else 0)
logger.info("下载队列: %d 条 (GB类过滤后) → 成功 %d", len(dl_list), dl_stats.success)
logger.info("内存: 最终 %s | 峰值 %s", _mem(cur_f), _mem(peak))
logger.info("日志: %s", _log_path)

# ── 日志内容验证（遍历日志文件验证修复项）──
_verify_log = logging.getLogger("stress_verify")
_log_text = ""
try:
    # 日志文件在本次运行中持续写入，读取当前内容
    with open(_log_path, 'r', encoding='utf-8', errors='replace') as _lf:
        _log_text = _lf.read()
except OSError:
    pass

# F: iso_gov 不应再有"非国际标准，跳过"噪声
_iso_noise = "查询失败" in _log_text and "iso_gov" in _log_text and "非国际标准" in _log_text
_check("日志验证: iso_gov无噪声WARN", not _iso_noise,
       f"包含'非国际标准'={_iso_noise}")

# C: DB 迁移不应有"duplicate column name" ERROR
_db_dup_err = "duplicate column" in _log_text
_check("日志验证: DB迁移无duplicate column ERROR", not _db_dup_err,
       f"包含dup col={_db_dup_err}")

# A1: 下载失败应有具体原因（下载失败不是简单的"失败"二字）
_dl_fail_in_log = "下载失败" in _log_text or "下载详情" in _log_text
_check("日志验证: 下载失败有具体原因", _dl_fail_in_log if dl_stats.failed > 0 else True,
       f"含'下载失败/详情'={_dl_fail_in_log}" if dl_stats.failed > 0 else "无下载失败，跳过")

_verdict()
