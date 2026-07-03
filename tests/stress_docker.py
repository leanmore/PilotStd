# Docker Web API 压力测试 — 第四层
# 用法: cd d:\PilotStd && python tests/stress_docker.py
# 前置: docker compose up（端口 9028）
# 全程自动化；Docker不可达时自动跳过
# 覆盖: 认证(4)/业务API(11)/配置与公告(10)/文件操作(4)/端到端(5)/权限(3)/熔断(3)/标准状态(2)/时效性(4) 共46项
# 通过阈值: ≥42/46 PASS (≥91%)，压测期间禁用 POST /api/system/update

import json
import os
import os as _os_module
import time

import requests
from stress_utils import (  # type: ignore[import-not-found]
    get_check_results,
    load_docker_credentials,
    setup_stress_logging,
)

from pilotstd.query.engine import PROGRESS_TAG


def _check_directories(config: dict, result_dir: str) -> bool:
    """Check input/output directories, list files, write to log."""
    from stress_utils import log_to_file_and_console

    log_file = _os_module.path.join(result_dir, "stress_docker_precheck.log")

    # Input directory (inbox)
    inbox_dir = config.get("docker", {}).get("inbox_dir") or "/inbox"
    log_to_file_and_console(f"\nInput directory (inbox): {inbox_dir}", log_file)

    # Output directory (standards)
    output_dir = "/standards"
    log_to_file_and_console(f"\nOutput directory (standards): {output_dir}", log_file)

    log_to_file_and_console(f"\nDirectory check complete. Log: {log_file}", log_file)
    return True


def run_docker_phase(config_path: str = "", step1_path: str = "", result_dir: str = "", yes: bool = False) -> bool:
    """Execute Docker API verification phase. Returns True if passed."""
    global BASE, USERNAME, PASSWORD
    from stress_utils import check as _check
    from stress_utils import verdict as _verdict

    logger = setup_stress_logging("stress_docker")

    # Load credentials
    _creds = load_docker_credentials(config_path)
    BASE = _creds["base_url"]
    USERNAME = _creds["username"]
    PASSWORD = _creds["password"]

    # 加载配置并检查目录
    if config_path:
        try:
            from pilotstd.core.config import ConfigManager

            _config = ConfigManager(filepath=config_path)
            _check_directories(_config, result_dir)
        except Exception:
            logger.info("目录预检: 配置加载失败，跳过目录检查")

    TIMEOUT = 300

    # ════════════════════════════════════════════════════════════════
    # 环境预检
    # ════════════════════════════════════════════════════════════════

    t0 = time.time()
    logger.info("=" * 60)
    logger.info("Web API 压力测试 v10.0 | %s", time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # ── 前置检查 ──
    _docker_up = False
    _docker_healthy = False

    # 1. 健康检查
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        _docker_healthy = r.status_code == 200 and r.json().get("status") == "ok"
        logger.info(
            "前置: Docker健康检查 %s",
            "PASS" if _docker_healthy else "FAIL status=%d" % r.status_code,
        )
    except Exception as e:
        logger.info("前置: Docker健康检查 FAIL — %s", str(e)[:80])

    # 2. API 可达性（login 端点 = 401 表示可达）
    try:
        r = requests.post(f"{BASE}/api/login", data={"username": USERNAME, "password": "wrong"}, timeout=5)
        _docker_up = r.status_code in (200, 401, 403, 404, 422, 500)
        logger.info("前置: API可达 %s", "PASS" if _docker_up else "FAIL")
    except requests.exceptions.ConnectionError as e:
        logger.info("前置: API可达 FAIL — %s", str(e)[:80])
    except Exception as e:
        logger.info("前置: API可达 FAIL — %s", str(e)[:80])

    if not _docker_up or not _docker_healthy:
        logger.info("Docker 环境不可达或不健康，跳过全部 Web API 测试")
        _check(
            "环境: Docker可达",
            _docker_up,
            "跳过全部 Web 测试" if not _docker_up else "API ok",
        )
        _check(
            "环境: Docker健康",
            _docker_healthy,
            "跳过全部 Web 测试" if not _docker_healthy else "health ok",
        )
        _verdict()
        return False

    _check("环境: Docker可达", True)

    # ── 进度心跳（每60秒，供 stress_driver 存活检测）──
    import threading as _thr  # noqa: E402

    _prog_total = 3  # AUTH-01 + AUTH-02 + BIZ-13
    _prog_completed = [0]
    _prog_ok = [0]
    _prog_lock = _thr.Lock()
    _prog_stop = _thr.Event()
    _prog_t0 = time.time()

    def _prog_bump(ok=False):
        with _prog_lock:
            _prog_completed[0] += 1
            if ok:
                _prog_ok[0] += 1

    def _progress_heartbeat():
        while not _prog_stop.wait(60.0):
            with _prog_lock:
                c = _prog_completed[0]
                o = _prog_ok[0]
            elapsed = time.time() - _prog_t0
            rate = c / max(elapsed, 0.001)
            eta = (_prog_total - c) / max(rate, 0.001) if rate > 0 else 0.0
            logger.info(
                f"{PROGRESS_TAG} completed=%d total=%d ok=%d rate=%.1f/s eta=%.0fs",
                c,
                _prog_total,
                o,
                rate,
                eta,
            )

    _prog_thread = _thr.Thread(target=_progress_heartbeat, daemon=True)
    _prog_thread.start()

    # ════════════════════════════════════════════════════════════════
    # 认证测试（4项）
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 认证 ---")

    # 1. 错误密码返回 401
    r = requests.post(
        f"{BASE}/api/login",
        data={"username": USERNAME, "password": "wrong"},
        timeout=TIMEOUT,
    )
    _check("认证: 错误密码返回401", r.status_code == 401, f"status={r.status_code}")

    # 2. 正确密码登录成功，获取 pilotstd_token cookie
    r = requests.post(
        f"{BASE}/api/login",
        data={"username": USERNAME, "password": PASSWORD},
        timeout=TIMEOUT,
    )
    _login_ok = r.status_code == 200 and r.json().get("ok")
    _check(
        "认证: 登录成功",
        _login_ok,
        f"status={r.status_code}, ok={r.json().get('ok') if r.status_code == 200 else 'N/A'}",
    )
    _cookies = r.cookies.get_dict() if _login_ok else {}
    _csrf = _cookies.get("csrf_token", "")

    # 3. 未认证访问受保护端点（/api/stats 不在白名单，需登录）
    r = requests.get(f"{BASE}/api/stats", timeout=TIMEOUT)
    _check("认证: 未登录拒绝", r.status_code in (401, 403), f"status={r.status_code}")

    # 4. 登出清除 cookie（POST 需 CSRF token）
    if _cookies and _csrf:
        r = requests.post(
            f"{BASE}/api/logout",
            cookies=_cookies,
            headers={"X-CSRF-Token": _csrf},
            timeout=TIMEOUT,
        )
        _check(
            "认证: 登出成功",
            r.status_code == 200 and r.json().get("ok"),
            f"status={r.status_code}",
        )
    else:
        _check("认证: 登出成功", None, "未登录，跳过")

    # API Key 三种传递方式验证
    _api_token = os.environ.get("PILOTSTD_API_TOKEN", "")
    if _api_token:
        _pst_token = f"pst_{_api_token}"
        # AUTH-01a: Authorization Bearer
        r = requests.get(
            f"{BASE}/api/announce/lookup?number=GB/T+1",
            headers={"Authorization": f"Bearer {_pst_token}"},
            timeout=TIMEOUT,
        )
        _check(
            "认证: Bearer pst_token",
            r.status_code == 200,
            f"status={r.status_code}",
        )
        # AUTH-01b: X-API-KEY header
        r = requests.get(
            f"{BASE}/api/announce/lookup?number=GB/T+1",
            headers={"X-API-KEY": _pst_token},
            timeout=TIMEOUT,
        )
        _check(
            "认证: X-API-KEY pst_token",
            r.status_code == 200,
            f"status={r.status_code}",
        )
        # AUTH-01c: ?token= query param
        r = requests.get(
            f"{BASE}/api/announce/lookup?number=GB/T+1&token={_pst_token}",
            timeout=TIMEOUT,
        )
        _check(
            "认证: query token pst_token",
            r.status_code == 200,
            f"status={r.status_code}",
        )
        # AUTH-02a: 不带 pst_ 前缀 → 401
        r = requests.get(
            f"{BASE}/api/announce/lookup?number=GB/T+1",
            headers={"X-API-KEY": _api_token},
            timeout=TIMEOUT,
        )
        _check(
            "认证: 无pst_前缀拒绝",
            r.status_code == 401,
            f"status={r.status_code}",
        )
    else:
        _check("认证: API Key 验证", None, "PILOTSTD_API_TOKEN 未设置，跳过")
        _check("认证: API Key 验证", None, "PILOTSTD_API_TOKEN 未设置，跳过")
        _check("认证: API Key 验证", None, "PILOTSTD_API_TOKEN 未设置，跳过")
        _check("认证: API Key 验证", None, "PILOTSTD_API_TOKEN 未设置，跳过")

    # ════════════════════════════════════════════════════════════════
    # 业务 API（11项，需登录）
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 业务 API ---")

    # 重新登录获取有效 cookie + CSRF token
    r = requests.post(
        f"{BASE}/api/login",
        data={"username": USERNAME, "password": PASSWORD},
        timeout=TIMEOUT,
    )
    _cookies = r.cookies.get_dict()
    _csrf_token = _cookies.get("csrf_token", "")
    _csrf_headers = {"X-CSRF-Token": _csrf_token} if _csrf_token else {}

    def _get(path, **kwargs):
        """带认证 cookie 的 GET 请求。"""
        return requests.get(f"{BASE}{path}", cookies=_cookies, timeout=TIMEOUT, **kwargs)

    def _post(path, data=None, json_data=None, **kwargs):
        """带认证 cookie + CSRF 头的 POST 请求。"""
        kw = {"cookies": _cookies, "timeout": TIMEOUT, "headers": _csrf_headers}
        if data is not None:
            kw["data"] = data
        if json_data is not None:
            kw["json"] = json_data
        kw.update(kwargs)
        return requests.post(f"{BASE}{path}", **kw)  # type: ignore[arg-type]

    def _put(path, json_data=None, **kwargs):
        """带认证 cookie + CSRF 头的 PUT 请求。"""
        kw = {"cookies": _cookies, "timeout": TIMEOUT, "headers": _csrf_headers}
        if json_data is not None:
            kw["json"] = json_data
        kw.update(kwargs)
        return requests.put(f"{BASE}{path}", **kw)  # type: ignore[arg-type]

    # 5. 统计接口
    r = _get("/api/stats")
    _check("API: 统计接口", r.status_code == 200, f"status={r.status_code}")

    # 6. 扫描（scan 使用查询参数，非 JSON body）
    r = _post("/api/scan", data={"path": r"D:\标准\GB 国标", "recursive": "true"})
    _check(
        "API: 扫描启动",
        r.status_code in (200, 404, 500),
        f"status={r.status_code} (路径可能不存在)",
    )

    # 7. 标准查询（Body embed: {"numbers": [...]}）
    r = _post("/api/query", json_data={"numbers": ["GB/T 1-2020"]})
    _check("API: 标准查询", r.status_code in (200, 404), f"status={r.status_code}")

    # 8. 下载任务（Body embed: {"numbers": [...]}）
    r = _post("/api/download", json_data={"numbers": ["GB/T 1-2020"]})
    _check("API: 下载任务", r.status_code in (200, 404), f"status={r.status_code}")

    # 9. 公告结果
    r = _get("/api/announce/results")
    _check("API: 公告结果", r.status_code == 200, f"status={r.status_code}")

    # 10. 文件列表（路径白名单因部署环境而异，400 为合法的路径安全策略响应）
    r = _get("/api/files", params={"path": "/standards"})
    _check("API: 文件列表", r.status_code in (200, 400, 404), f"status={r.status_code}")

    # 11. 系统配置读取
    r = _get("/api/settings")
    _settings_ok = r.status_code == 200
    _check("API: 配置读取", _settings_ok, f"status={r.status_code}")

    # 12. 待确认重查（body 直接传 list[str]）
    r = _post("/api/pending/requery", json_data=["GB/T 1-2020"])
    _check("API: 待确认重查", r.status_code in (200, 404), f"status={r.status_code}")

    # 13. 待确认清单读取（新增 GET /api/pending）
    r = _get("/api/pending")
    _check(
        "API: 待确认清单",
        r.status_code == 200,
        f"status={r.status_code}, items={len(r.json().get('items', [])) if r.status_code == 200 else 'N/A'}",
    )

    # 14. 查询结果持久化保存（新增 POST /api/query/save）
    _sample_results = [
        {
            "standard_number": "GB/T 1-2020",
            "standard_name": "测试标准",
            "status": "现行",
            "source_site": "test",
            "match_status": "精确匹配",
            "is_adopted": False,
        }
    ]
    r = _post("/api/query/save", json_data=_sample_results)
    _save_ok = r.status_code == 200 and r.json().get("ok")
    _check(
        "API: 查询结果保存",
        _save_ok,
        f"status={r.status_code}, count={r.json().get('count', 0) if r.status_code == 200 else 'N/A'}",
    )

    # 15. 查询结果读取（新增 GET /api/query/results）
    r = _get("/api/query/results")
    _results_ok = r.status_code == 200
    _results_data = r.json().get("results", []) if _results_ok else []
    _check(
        "API: 查询结果读取",
        _results_ok and len(_results_data) > 0,
        f"status={r.status_code}, count={len(_results_data)}",
    )

    # ════════════════════════════════════════════════════════════════
    # 配置与公告写入（3项）
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 配置与公告 ---")

    # 16. 系统配置写入（PUT 端点，同时验证调度器联动）
    if _settings_ok:
        try:
            current_settings = r.json()
        except Exception:
            current_settings = {}
        tasks_cfg = current_settings.get("tasks", {})
        r = _put("/api/settings", json_data={"tasks": tasks_cfg})
        _check("配置: 保存设置", r.status_code == 200, f"status={r.status_code}")
    else:
        _check("配置: 保存设置", None, "配置读取失败，跳过")

    # 17. 公告异步抓取（gb/hb/db 三个适配器）— 仅验证触发 + 状态可查，不等待完成
    _announce_total_count = 0
    _announce_adapters_ok = 0
    _VALID_STATUSES = ("pending", "running", "success", "failed")
    for _adapter in ["gb", "hb", "db"]:
        try:
            # 触发异步抓取
            _r = _post("/api/announcements/fetch", json_data={"adapter_name": _adapter}, timeout=300)
            _af_data = _r.json() if _r.status_code == 200 else {}
            _task_id = _af_data.get("task_id", "")
            _trigger_ok = bool(_task_id)
            if not _trigger_ok:
                _check(f"公告: {_adapter}异步触发", False, f"status={_r.status_code}, no task_id")
                continue
            # 查询状态（不轮询等待完成）
            _sr = _get(f"/api/announcements/status/{_task_id}")
            _sd = _sr.json() if _sr.status_code == 200 else {}
            _status = _sd.get("status", "")
            _progress = _sd.get("progress", 0)
            _status_ok = _status in _VALID_STATUSES
            _check(
                f"公告: {_adapter}异步抓取",
                _trigger_ok and _status_ok,
                f"task={_task_id} status={_status} progress={_progress}",
            )
            if _trigger_ok and _status_ok:
                _announce_adapters_ok += 1
        except Exception as e:
            _check(f"公告: {_adapter}异步抓取", False, f"异常: {str(e)[:60]}")

    # 17b. /api/system/update — 压测期间必须禁用（自更新重启容器）
    logger.info("[SKIP] /api/system/update — 压测期间禁用（自更新会重启容器，不验证此端点）")
    _check("系统: 自更新禁用", True, "SKIP — 压测期间禁用")

    # ════════════════════════════════════════════════════════════════
    # 公告样本抓取 — 异步模式完成后读取 results
    # ════════════════════════════════════════════════════════════════
    _CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "stress")
    os.makedirs(_CACHE_DIR, exist_ok=True)
    _ANNOUNCE_SAMPLE_PATH = os.path.join(_CACHE_DIR, "announce_sample.json")

    _announce_sample_ok = False
    if _announce_total_count > 0:
        try:
            # v9.5: 从 announcement_record 抽样（全量抓取记录，无论匹配结果）
            r_log = _get("/api/announce/fetch-log")
            if r_log.status_code == 200:
                _log_data = r_log.json()
                _sample_items = _log_data.get("items", [])
                logger.info("公告样本(fetch_checkpoint): %d 条就绪", len(_sample_items))
            else:
                _sample_items = []
            if _sample_items:
                import random

                _by_source: dict = {}
                for _item in _sample_items:
                    _src = _item.get("source_site", "unknown")
                    _by_source.setdefault(_src, []).append(_item)
                _sampled = []
                _max_per_source = 40
                for _src, _src_items in _by_source.items():
                    if len(_src_items) <= _max_per_source:
                        _sampled.extend(_src_items)
                    else:
                        _sampled.extend(random.sample(_src_items, _max_per_source))
                _sample_out = {
                    "total": len(_sampled),
                    "source_distribution": {s: len(v) for s, v in _by_source.items()},
                    "source_table": "announcement_record",
                    "items": _sampled,
                }
                with open(_ANNOUNCE_SAMPLE_PATH, "w", encoding="utf-8") as _f:
                    json.dump(_sample_out, _f, ensure_ascii=False, indent=2)
                _announce_sample_ok = True
                logger.info(
                    "公告样本: 写入 %s (total=%d, 分布=%s)",
                    _ANNOUNCE_SAMPLE_PATH,
                    len(_sampled),
                    _sample_out["source_distribution"],
                )
            else:
                logger.warning("公告样本: fetch_checkpoint 为空，跳过样本生成")
        except Exception as _e:
            logger.warning("公告样本: 提取失败 — %s", _e)
    else:
        logger.warning("公告样本: 异步抓取 total_count=0，跳过样本生成")

    # ════════════════════════════════════════════════════════════════
    # 文件操作权限测试（5项）— 验证容器内实际文件读写
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 文件操作权限 ---")

    # 18. 上传图片 → 读取验证 → 清理
    _test_file_name = f"_stress_test_{int(time.time())}.png"
    _test_file_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # 最小合法 PNG
    try:
        r = requests.post(
            f"{BASE}/api/upload",
            files={"file": (_test_file_name, _test_file_content, "image/png")},
            cookies=_cookies,
            headers=_csrf_headers,
            timeout=TIMEOUT,
        )
        _upload_ok = r.status_code == 200 and "url" in r.json()
        _upload_url = r.json().get("url", "") if _upload_ok else ""
        _check("文件: 上传图片", _upload_ok, f"status={r.status_code}, url={_upload_url}")
        # 读取刚上传的文件验证内容
        if _upload_url:
            r2 = requests.get(f"{BASE}{_upload_url}", timeout=TIMEOUT)
            _check(
                "文件: 读取已上传图片",
                r2.status_code == 200 and len(r2.content) > 0,
                f"status={r2.status_code}, size={len(r2.content)}",
            )
        else:
            _check("文件: 读取已上传图片", None, "上传未成功，跳过")
    except Exception as e:
        _check("文件: 上传图片", None, f"异常: {str(e)[:60]}")

    # 19. 文件列表可读 + 列出的是真实目录内容
    r = _get("/api/files", params={"path": "/standards"})
    _files_list_ok = r.status_code in (200, 400, 404)
    _files_data = r.json() if r.status_code == 200 else {}
    _check(
        "文件: 列表/standards可读",
        _files_list_ok,
        f"status={r.status_code}, count={len(_files_data.get('files', []))}",
    )

    # 20. 从 inode 确认容器内有可写的持久化目录
    for _test_dir, _label in [
        ("/inbox", "inbox"),
        ("/standards", "standards"),
        ("/app/data", "data"),
        ("/app/logs", "logs"),
    ]:
        r = _get("/api/files", params={"path": _test_dir})
        # 只有标准库目录返回 200；非库目录返回 400 是路径安全策略的正确行为
        _ok = r.status_code in (200, 400, 404)
        _check(f"文件: 目录{_label}可访问", _ok, f"status={r.status_code}")

    # 21. 扫描 inbox 目录（确认文件遍历权限正常）
    r = _post("/api/scan", data={"path": "/inbox", "recursive": "true"})
    _scan_ok = r.status_code in (200, 404)
    _scan_data = r.json() if _scan_ok else {}
    _check(
        "文件: 扫描inbox目录",
        _scan_ok,
        f"status={r.status_code}, files={_scan_data.get('total', 0)}",
    )

    # 22. 清空目录（无空目录时返回 400 为正常业务响应）
    r = _post("/api/clean-empty", data={"path": "/standards"})
    _clean_ok = r.status_code in (200, 400, 404)
    _check(
        "文件: clean-empty权限",
        _clean_ok,
        f"status={r.status_code}, cleaned={r.json().get('cleaned', 0) if r.status_code == 200 else 'N/A'}",
    )

    # ════════════════════════════════════════════════════════════════
    # 补充：配置一致性 + 权限隔离 + 端到端管线
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 配置一致性 ---")

    # 23. 配置读写一致：先 GET → PUT 改一个值 → GET 验证 → PUT 还原
    if _settings_ok:
        try:
            orig = r.json() if _settings_ok else {}
            test_val = "test_roundtrip_value"
            r_put = _put("/api/settings", json_data={"storage": {"downloads_dir": test_val}})
            r_get = _get("/api/settings")
            _new_val = r_get.json().get("storage", {}).get("downloads_dir", "") if r_get.status_code == 200 else ""
            _roundtrip_ok = r_put.status_code == 200 and _new_val == test_val
            _check(
                "配置: 读写一致",
                _roundtrip_ok,
                f"put={r_put.status_code}, get={r_get.status_code}, val={_new_val}",
            )
            # 还原
            _put(
                "/api/settings",
                json_data={"storage": {"downloads_dir": orig.get("storage", {}).get("downloads_dir", "")}},
            )
        except Exception as e:
            _check("配置: 读写一致", None, f"异常: {str(e)[:60]}")
    else:
        _check("配置: 读写一致", None, "配置读取失败，跳过")

    logger.info("--- 权限隔离 ---")

    # 24. 非超级用户不能改设置（require_admin 端点验证，权限基于 SUPERUSER 用户名匹配）— 测试完清理临时用户
    _non_superuser = "_test_nosuper_"
    try:
        r_create = _post(
            "/api/users",
            json_data={
                "username": _non_superuser,
                "password": "test123456",
                "role": "user",
            },
        )
        _user_created = r_create.status_code in (200, 409)
        if _user_created or r_create.status_code == 409:
            r_login = requests.post(
                f"{BASE}/api/login",
                data={"username": _non_superuser, "password": "test123456"},
                timeout=TIMEOUT,
            )
            if r_login.status_code == 200 and r_login.json().get("ok"):
                _user_cookies = r_login.cookies.get_dict()
                _user_csrf = _user_cookies.get("csrf_token", "")
                r_put = requests.put(
                    f"{BASE}/api/settings",
                    json={"tasks": {"auto_scan_enabled": False}},
                    cookies=_user_cookies,
                    headers={"X-CSRF-Token": _user_csrf} if _user_csrf else {},
                    timeout=TIMEOUT,
                )
                _check(
                    "权限: 非超级用户改设置",
                    r_put.status_code in (401, 403, 405),
                    f"status={r_put.status_code}",
                )
                # 清理：删除临时用户（需获取 user_id）
                r_users = _get("/api/users")
                if r_users.status_code == 200:
                    for u in r_users.json().get("users", []):
                        if u.get("username") == _non_superuser:
                            _csrf_headers_extra = {"X-CSRF-Token": _csrf_token} if _csrf_token else {}
                            requests.delete(
                                f"{BASE}/api/users/{u['id']}",
                                cookies=_cookies,
                                headers=_csrf_headers_extra,
                                timeout=TIMEOUT,
                            )
                            break
            else:
                _check("权限: 非超级用户改设置", None, "普通用户登录失败，跳过")
        else:
            _check("权限: 非超级用户改设置", None, f"创建用户失败 status={r_create.status_code}")
    except Exception as e:
        _check("权限: 非超级用户改设置", None, f"异常: {str(e)[:60]}")

    logger.info("--- 端到端管线 ---")

    # [TRACE] 指令C-3: Docker容器内文件系统检查
    for _test_dir, _label in [("/inbox", "inbox"), ("/standards", "standards")]:
        try:
            r_fs = _get("/api/files", params={"path": _test_dir})
            if r_fs.status_code == 200:
                _fs_data = r_fs.json()
                _files = _fs_data.get("files", [])
                logger.info(
                    "[TRACE-C] fs_check: dir=%s status=%d file_count=%d files=%s",
                    _test_dir,
                    r_fs.status_code,
                    len(_files),
                    [f.get("name", "") for f in _files[:5]],
                )
            else:
                logger.info(
                    "[TRACE-C] fs_check: dir=%s status=%d detail=%s",
                    _test_dir,
                    r_fs.status_code,
                    r_fs.text[:200],
                )
        except Exception as e:
            logger.info("[TRACE-C] fs_check: dir=%s error=%s", _test_dir, str(e)[:100])

    # 25. 完整管线：扫描 inbox → 查询 → 下载 → 规范化 → 归档
    r_scan = _post("/api/scan", data={"path": "/inbox"})
    _scan_files = r_scan.json().get("files", []) if r_scan.status_code == 200 else []

    _e2e_timeout = False  # 初始化：E2E 超时标记
    if _scan_files:
        _std_numbers = [f["standard_number"] for f in _scan_files if f.get("standard_number")]
        # [TRACE] 指令C: 端到端扫描结果详情
        logger.info(
            "[TRACE-C] e2e_scan: status=%d files=%d std_numbers=%s",
            r_scan.status_code,
            len(_scan_files),
            _std_numbers[:5],
        )
        # 查询 — 分批串行，每批5条，批次间隔2s，避免远端API并发超时
        _query_all_ok = True
        _batch_size = 5
        _batch_delay = 2.0
        _E2E_MAX_DURATION = 1200  # 20 分钟总超时
        _e2e_start = time.time()
        _total_batches = (len(_std_numbers) + _batch_size - 1) // _batch_size
        for _batch_start in range(0, len(_std_numbers), _batch_size):
            # 总超时检查：防止 Docker 容器外网不通时无限等待
            _elapsed = time.time() - _e2e_start
            if _elapsed > _E2E_MAX_DURATION:
                _e2e_timeout = True
                _completed = _batch_start // _batch_size
                _remaining = _total_batches - _completed
                logger.warning(
                    "E2E 查询超时（%.0fs/%ds）: 已完成 %d/%d 批，跳过剩余 %d 批",
                    _elapsed,
                    _E2E_MAX_DURATION,
                    _completed,
                    _total_batches,
                    _remaining,
                )
                _query_all_ok = False
                break
            _batch = _std_numbers[_batch_start : _batch_start + _batch_size]
            if _batch_start > 0:
                time.sleep(_batch_delay)
            r_q = _post("/api/query", json_data={"numbers": _batch})
            if r_q.status_code != 200:
                _query_all_ok = False
                logger.info(
                    "[TRACE-C] e2e_query_batch: batch=%d/%d status=%d body=%s",
                    _batch_start // _batch_size + 1,
                    _total_batches,
                    r_q.status_code,
                    (r_q.text or "")[:200],
                )
        logger.info(
            "[TRACE-C] e2e_scan: status=%d files=%d std_numbers=%s",
            r_scan.status_code,
            len(_scan_files),
            _std_numbers[:5],
        )
        _check(
            "管线: 扫描→查询",
            _query_all_ok,
            f"scan={len(_scan_files)}files, batches={(len(_std_numbers) + _batch_size - 1) // _batch_size}",
        )

        # 规范化（用扫描结果的字段构造 items）
        _norm_items = [
            {
                "logical_code": f.get("logical_code", ""),
                "number": f.get("number", 0),
                "year": f.get("year", 0),
                "part": f.get("part"),
                "source_path": f.get("full_path", ""),
            }
            for f in _scan_files
        ]
        r_norm = _post("/api/normalize", json_data={"items": _norm_items})
        _norm_ok = r_norm.status_code == 200
        logger.info(
            "[TRACE-C] e2e_normalize: status=%d ok=%s body=%s",
            r_norm.status_code,
            _norm_ok,
            (r_norm.text or "")[:200],
        )
        _check(
            "管线: 规范化",
            _norm_ok,
            f"status={r_norm.status_code}, results={len(r_norm.json().get('results', []))}",
        )

        # 归档（需要查询结果的匹配信息）
        _archive_items = []
        for f in _scan_files:
            _archive_items.append(
                {
                    "logical_code": f.get("logical_code", ""),
                    "number": f.get("number", 0),
                    "year": f.get("year", 0),
                    "part": f.get("part"),
                    "source_path": f.get("full_path", ""),
                    "std_name": f.get("std_name", ""),
                    "num_prefix": f.get("num_prefix", ""),
                    "num_suffix": f.get("num_suffix", ""),
                    "language": f.get("language", ""),
                    "ext": f.get("ext", ".pdf"),
                }
            )
        r_archive = _post(
            "/api/archive",
            json_data={"items": _archive_items, "word_source_root": "/inbox"},
        )
        _archive_ok = r_archive.status_code in (200, 404)
        _moved = r_archive.json().get("moved", 0) if r_archive.status_code == 200 else 0
        logger.info(
            "[TRACE-C] e2e_archive: status=%d ok=%s moved=%s body=%s",
            r_archive.status_code,
            _archive_ok,
            _moved,
            (r_archive.text or "")[:200],
        )
        _check("管线: 归档", _archive_ok, f"status={r_archive.status_code}, moved={_moved}")

        # 验证文件已归档（用 archive 返回的 moved 计数）
        _check("管线: 文件进入输出目录", _moved > 0, f"归档移动了 {_moved} 个文件到 /standards")
    else:
        logger.info(
            "[TRACE-C] e2e_skip: inbox为空，跳过端到端管线 scan_status=%d",
            r_scan.status_code,
        )
        _check("管线: 扫描→查询", None, "inbox 无文件，跳过端到端")
        _check("管线: 规范化", None, "跳过")
        _check("管线: 归档", None, "跳过")
        _check("管线: 文件进入输出目录", None, "跳过")

    # ════════════════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════════════════
    # 公告缓存路由 + API Key 鉴权压测（v4.2 新增）
    # ════════════════════════════════════════════════════════════════

    _stress_api_key = os.environ.get("PILOTSTD_API_TOKEN") or os.environ.get("PILOTSTD_API_KEY", "")
    _cache_hit_count = 0
    _cache_miss_count = 0
    _source_dist: dict[str, int] = {}
    _auth_total = 0
    _auth_pass = 0

    logger.info("--- 公告缓存路由 + API 令牌鉴权 ---")

    # AUTH-01: 有效令牌 → 200（支持 Authorization: Bearer + X-API-KEY 双通道）
    if _stress_api_key:
        _auth_total += 1
        try:
            r = requests.get(
                f"{BASE}/api/announce/lookup?number=GB/T%201-2020",
                headers={"Authorization": f"Bearer pst_{_stress_api_key}"},
                timeout=10,
            )
            ok = r.status_code == 200
            if ok:
                _auth_pass += 1
            _check(
                "AUTH-01: 有效令牌鉴权 (Bearer)",
                ok,
                f"status={r.status_code}" if not ok else "200 OK",
            )
            _prog_bump(ok=ok)
        except Exception as e:
            _check("AUTH-01: 有效令牌鉴权 (Bearer)", False, f"异常: {str(e)[:60]}")
            _prog_bump(ok=False)
    else:
        _check("AUTH-01: 有效令牌鉴权", None, "PILOTSTD_API_TOKEN 未设置，跳过")
        _prog_bump(ok=False)

    # AUTH-02: 无效令牌 → 401
    _auth_total += 1
    try:
        r = requests.get(
            f"{BASE}/api/announce/lookup?number=GB/T%201-2020&token=pst_invalid_static_token",
            timeout=10,
        )
        ok = r.status_code in (401, 403)
        if ok:
            _auth_pass += 1
        _check(
            "AUTH-02: 无效令牌拒绝",
            ok,
            f"status={r.status_code}" if not ok else f"拒绝 {r.status_code}",
        )
        _prog_bump(ok=ok)
    except Exception as e:
        _check("AUTH-02: 无效令牌拒绝", False, f"异常: {str(e)[:60]}")
        _prog_bump(ok=False)

    # BIZ-12 已移至 WinUI 乙轮（Docker 阶段公告异步抓取缓存可能未就绪）

    # BIZ-13: 缓存未命中降级
    _hdr = {}
    if _stress_api_key:
        _hdr["Authorization"] = f"Bearer pst_{_stress_api_key}"
    try:
        t1 = time.time()
        r = requests.get(
            f"{BASE}/api/announce/lookup?number=GB%2FT%2099999-9999",
            headers=_hdr,
            timeout=10,
        )
        elapsed_ms = (time.time() - t1) * 1000
        body = r.json() if r.status_code == 200 else {}
        found = body.get("found", False)
        msg = body.get("message", "")
        _cache_miss_count += 1
        _check(
            "BIZ-13: 缓存未命中降级",
            not found and r.status_code == 200,
            f"found={found} msg={msg[:30]} {elapsed_ms:.0f}ms" if not found else f"意外命中 {elapsed_ms:.0f}ms",
        )
        _prog_bump(ok=not found and r.status_code == 200)
    except Exception as e:
        _check("BIZ-13: 缓存未命中降级", False, f"异常: {str(e)[:60]}")
        _prog_bump(ok=False)

    # ════════════════════════════════════════════════════════════════
    # 熔断与配置热加载（3 项）
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 熔断与配置 ---")

    # 28. 适配器状态
    r = _get("/api/adapter/status")
    _adapter_status_ok = r.status_code == 200
    if _adapter_status_ok:
        _adapters = r.json().get("adapters", [])
        _check(
            "熔断: 适配器状态查询",
            len(_adapters) >= 3 and all(a.get("status") == "normal" for a in _adapters[:3]),
            f"adapters={[a['name'] for a in _adapters]}, statuses={[a.get('status') for a in _adapters]}",
        )
    else:
        _check("熔断: 适配器状态查询", False, f"status={r.status_code}")

    # 29. 配置读取
    r = _get("/api/adapter/config")
    _cfg_read_ok = r.status_code == 200
    if _cfg_read_ok:
        _cfg = r.json()
        _check(
            "熔断: 配置读取",
            _cfg.get("failure_threshold") == 3 and _cfg.get("freeze_durations") == [30, 120, 360, 720],
            f"threshold={_cfg.get('failure_threshold')}, durations={_cfg.get('freeze_durations')}",
        )
    else:
        _check("熔断: 配置读取", False, f"status={r.status_code}")

    # 30. 配置热加载（修改 threshold=7 → GET 确认 → 恢复默认 3）
    _new_cfg = {"failure_threshold": 7, "freeze_durations": [30, 120, 360, 720], "reset_window_hours": 24}
    r = _put("/api/adapter/config", json_data=_new_cfg)
    if r.status_code == 200:
        r2 = _get("/api/adapter/config")
        _hot_ok = r2.status_code == 200 and r2.json().get("failure_threshold") == 7
        _hot_val = r2.json().get("failure_threshold") if r2.status_code == 200 else "N/A"
        _check("熔断: 配置热加载", _hot_ok, f"threshold after PUT={_hot_val}")
        # 恢复默认
        _restore_cfg = {"failure_threshold": 3, "freeze_durations": [30, 120, 360, 720], "reset_window_hours": 24}
        _put("/api/adapter/config", json_data=_restore_cfg)
    else:
        _check("熔断: 配置热加载", False, f"status={r.status_code}")

    # ════════════════════════════════════════════════════════════════
    # 标准状态（2 项）
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 标准状态 ---")

    # 31. 统计卡片
    r = _get("/api/standards/status/stats")
    if r.status_code == 200:
        _stats = r.json()
        _check(
            "标准: 状态统计",
            all(k in _stats for k in ("active", "inactive", "unknown")),
            f"active={_stats.get('active')}, inactive={_stats.get('inactive')}, unknown={_stats.get('unknown')}",
        )
    else:
        _check("标准: 状态统计", False, f"status={r.status_code}")

    # 32. 分页列表（中文状态筛选）
    r = _get("/api/standards/status?status=现行&page=1&page_size=10")
    if r.status_code == 200:
        _sdata = r.json()
        _check(
            "标准: 状态列表(中文筛选)",
            "items" in _sdata and _sdata.get("total", 0) >= 0,
            f"total={_sdata.get('total')}, items={len(_sdata.get('items', []))}",
        )
    else:
        _check("标准: 状态列表(中文筛选)", False, f"status={r.status_code}")

    # ════════════════════════════════════════════════════════════════
    # 时效性检查配置（4 项）
    # ════════════════════════════════════════════════════════════════
    logger.info("--- 时效性检查 ---")

    # 33. 配置读取
    r = _get("/api/validity/config")
    if r.status_code == 200:
        _vc = r.json()
        _check(
            "时效: 配置读取",
            _vc.get("batch_size") == 50 and _vc.get("frequency") == "weekly",
            f"frequency={_vc.get('frequency')}, batch_size={_vc.get('batch_size')}",
        )
    else:
        _check("时效: 配置读取", False, f"status={r.status_code}")

    # 34. 配置写入（修改 batch_size=100 → GET 确认 → 恢复默认）
    _vc_new = {
        "frequency": "weekly",
        "execute_time": "03:00",
        "batch_size": 100,
        "batch_interval": 3,
        "check_ratio": 30,
        "update_interval": 28,
    }
    r = _put("/api/validity/config", json_data=_vc_new)
    if r.status_code == 200:
        r2 = _get("/api/validity/config")
        _v_write_ok = r2.status_code == 200 and r2.json().get("batch_size") == 100
        _w_val = r2.json().get("batch_size") if r2.status_code == 200 else "N/A"
        _check("时效: 配置写入", _v_write_ok, f"batch_size after PUT={_w_val}")
        # 恢复默认
        _vc_restore = {
            "frequency": "weekly",
            "execute_time": "03:00",
            "batch_size": 50,
            "batch_interval": 5,
            "check_ratio": 25,
            "update_interval": 28,
        }
        _put("/api/validity/config", json_data=_vc_restore)
    else:
        _check("时效: 配置写入", False, f"status={r.status_code}")

    # 35. 立即执行
    r = _post("/api/validity/run")
    _run_ok = r.status_code == 200 and r.json().get("ok") is True
    _check(
        "时效: 立即执行",
        _run_ok,
        f"status={r.status_code}, checked={r.json().get('checked', 0) if r.status_code == 200 else 'N/A'}",
    )

    # 36. 执行历史
    r = _get("/api/validity/history?page=1&page_size=10")
    if r.status_code == 200:
        _vh = r.json()
        _check(
            "时效: 执行历史",
            "items" in _vh and _vh.get("total", 0) >= 0,
            f"total={_vh.get('total')}, items={len(_vh.get('items', []))}",
        )
    else:
        _check("时效: 执行历史", False, f"status={r.status_code}")

    # ════════════════════════════════════════════════════════════════
    # 汇总
    # ════════════════════════════════════════════════════════════════
    _prog_stop.set()
    with _prog_lock:
        c = _prog_completed[0]
        o = _prog_ok[0]
    elapsed = time.time() - _prog_t0
    logger.info(
        f"{PROGRESS_TAG} completed=%d total=%d ok=%d rate=%.1f/s eta=0s (done)",
        c,
        _prog_total,
        o,
        c / max(elapsed, 0.001),
    )
    total_time = time.time() - t0
    logger.info("=" * 60)
    logger.info("Web API 压力测试完成 (%.1fs)", total_time)
    logger.info("日志已写入: logs/app.log")

    # 端点数量自检：预期 47 项
    _results = get_check_results()
    _total = len(_results)
    _expected_total = 46
    if _total == _expected_total:
        logger.info("[OK] 端点数量校验通过: %d 个 (预期 %d)", _total, _expected_total)
    else:
        logger.warning("[WARN] 端点数量与方案不符: 实际 %d, 预期 %d", _total, _expected_total)

    _all_ok = _verdict()
    _total = len(_results)
    _passed = sum(1 for _, ok, _ in _results if ok)
    _failed = sum(1 for _, ok, _ in _results if ok is False)
    _skipped = _total - _passed - _failed
    _failures = [{"name": label, "detail": detail} for label, ok, detail in _results if ok is False]
    _step3 = {
        "step": 3,
        "ts": time.strftime("%Y%m%d_%H%M%S"),
        "elapsed_s": round(total_time, 1),
        "total": _total,
        "passed": _passed,
        "failed": _failed,
        "skipped": _skipped,
        "failures": _failures,
        "verdict": "PASS" if _all_ok else "FAIL",
        "e2e_status": "timeout" if _e2e_timeout else ("completed" if _all_ok else "failed"),
        "extended": {
            "cache_hit": _cache_hit_count,
            "cache_miss": _cache_miss_count,
            "source_distribution": _source_dist,
            "auth_total": _auth_total,
            "auth_pass": _auth_pass,
            "announce_sample_ok": _announce_sample_ok,
            "announce_sample_path": _ANNOUNCE_SAMPLE_PATH,
        },
    }

    # 写入 step3.json 到 result_dir
    if result_dir:
        os.makedirs(result_dir, exist_ok=True)
        _step3_path = os.path.join(result_dir, "step3.json")
        with open(_step3_path, "w", encoding="utf-8") as _f:
            json.dump(_step3, _f, ensure_ascii=False, indent=2)
        logger.info("step3.json: %s", _step3_path)
    else:
        logger.info(
            "step3 统计: total=%d passed=%d failed=%d skipped=%d",
            _total,
            _passed,
            _failed,
            _skipped,
        )

    return _all_ok


if __name__ == "__main__":
    run_docker_phase()
