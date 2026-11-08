"""tests/test_c2_log_levels.py — U34-C2 的日志级别契约（6 处升 warning + 3 处保留 debug）。

对应 `docs/.local/U34-C-decisions.md`：
- D1/D4/D7/R5/R6/R7：失败已对用户可见（或让用户被误导），必须 WARNING；
- D2/D5/D6：可选增强降级，保留 DEBUG —— 本文件反向断言"不得冒出 WARNING"，防止后续被
  无脑升级成噪声；
- E1：`_njbz365_session_manager._do_request` 的三个 `except` 级别统一（原 error/error/无日志）；
- E4：`energy._fetch_candidates` 的不可达 debug 分支已删除（源码级断言 + 既有能量测试兜底行为）。
"""

import logging
import types

import requests


def _msgs(caplog, level: int) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def _has(caplog, level: int, needle: str) -> bool:
    return any(needle in m for m in _msgs(caplog, level))


# ── D1：docker debug 端点采集失败 ────────────────────────────────────────


def test_query_debug_collect_failure_is_warning(caplog, monkeypatch) -> None:
    import pilotstd.manager.facade as facade
    from docker.api import query_debug as mod

    def _boom():
        raise RuntimeError("mgmt down")

    monkeypatch.setattr(facade, "get_manager", _boom, raising=False)
    with caplog.at_level(logging.DEBUG):
        assert mod._collect_real_runtime_state() == {}

    assert _has(caplog, logging.WARNING, "debug 端点收集运行时状态失败")


# ── D4：公告任务 result_data 脏 JSON（行为不变：success + 空数据）─────────


def test_announce_task_bad_json_is_warning_and_behaviour_unchanged(caplog) -> None:
    from pilotstd.manager.announce_service import AnnounceService

    class _DB:
        def fetchone(self, *_a, **_k):
            return {"status": "success", "result_data": "{not json", "id": "t1"}

    svc = object.__new__(AnnounceService)
    svc._get_db = lambda: _DB()

    with caplog.at_level(logging.DEBUG):
        out = svc.get_task_results("t1")

    # 控制流不变：仍返回 success + 空 data
    assert out["status"] == "success"
    assert out["data"] == {}
    assert "结果数据损坏" in out["message"]
    assert _has(caplog, logging.WARNING, "公告任务结果 JSON 解析失败")


# ── D7：待确认查询的配置读取失败被当成"未开启" ───────────────────────────


def test_pending_dialog_config_failure_is_warning(caplog, monkeypatch) -> None:
    import pilotstd.core.config as config_mod
    from pilotstd.ui import pending_query_dialog as mod

    def _boom():
        raise RuntimeError("config broken")

    monkeypatch.setattr(config_mod, "ConfigManager", _boom)
    with caplog.at_level(logging.DEBUG):
        result = mod.PendingQueryDialog._check_local_db_available(types.SimpleNamespace())

    assert result is False  # 行为不变：仍按"未开启"处理
    assert _has(caplog, logging.WARNING, "待确认查询公告配置读取失败")


# ── R5：公告抓取锁写入失败被当成"锁被占用" ───────────────────────────────


def test_announce_lock_write_failure_is_warning(caplog) -> None:
    from pilotstd.manager.announce_service import AnnounceService

    class _BadDB:
        def execute(self, *_a, **_k):
            raise RuntimeError("db locked")

    svc = object.__new__(AnnounceService)
    svc._file_index = types.SimpleNamespace(_db=_BadDB())

    with caplog.at_level(logging.DEBUG):
        assert svc._acquire_manual_lock() is False

    assert _has(caplog, logging.WARNING, "公告抓取锁写入失败")


# ── R6：发布日期解析失败 → 静默跳过等待队列 ──────────────────────────────


def test_pending_enqueue_bad_date_is_warning(caplog) -> None:
    from pilotstd.manager.pending_service import PendingService

    parsed = types.SimpleNamespace(
        found_number="GB 1-2020",
        found_name="x",
        std_name="x",
        found_publish_date="not-a-date",
    )
    svc = object.__new__(PendingService)

    with caplog.at_level(logging.DEBUG):
        PendingService.enqueue_download_wait(svc, parsed)

    assert _has(caplog, logging.WARNING, "发布日期解析失败")


# ── R7 / E1：_njbz365 三个 except 统一 WARNING ───────────────────────────


class _BadPost:
    """`.post()` 直接抛 / 返回坏 JSON 的会话替身。"""

    def __init__(self, exc=None, bad_json=False) -> None:
        self._exc = exc
        self._bad_json = bad_json

    def post(self, *_a, **_k):
        if self._exc is not None:
            raise self._exc

        class _Resp:
            @staticmethod
            def json():
                raise ValueError("bad json")

        return _Resp()


def _manager(session):
    from pilotstd.query.adapters._njbz365_session_manager import Njz365SessionManager

    mgr = object.__new__(Njz365SessionManager)
    mgr._session = session
    mgr._ensure_session = lambda: None
    mgr._build_base_params = lambda _term: {}
    mgr._compute_sign = lambda _params: "sig"
    mgr._initialized = True
    return mgr


def test_njbz365_three_branches_all_error(caplog, monkeypatch) -> None:
    """R7/E1 修订：三个 except 统一 ERROR（超时最终失败/其他请求异常/JSON 解析失败）。"""
    from pilotstd.query.adapters import _njbz365_session_manager as mod

    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)

    with caplog.at_level(logging.DEBUG):
        # ① 超时/连接失败 → 重试耗尽
        assert _manager(_BadPost(exc=requests.ConnectionError("down")))._do_request("GB") is None
        # ② 其他请求异常
        assert _manager(_BadPost(exc=requests.HTTPError("500")))._do_request("GB") is None
        # ③ JSON 解析失败（原先完全无日志）
        assert _manager(_BadPost(bad_json=True))._do_request("GB") is None

    err = "\n".join(_msgs(caplog, logging.ERROR))
    assert "njbz365 会话请求最终失败" in err
    assert "njbz365 会话请求失败" in err
    assert "njbz365 会话响应 JSON 解析失败" in err

    # 三条失败不得再落回 warning（重试提示仍是 warning，故按消息精确断言）
    warn = "\n".join(_msgs(caplog, logging.WARNING))
    assert "会话请求最终失败" not in warn
    assert "会话请求失败" not in warn
    assert "会话响应 JSON 解析失败" not in warn


# ── D2 / D5 / D6：保留 DEBUG，且不得冒出 WARNING ────────────────────────


def test_std_name_lookup_failure_stays_debug(caplog) -> None:
    from pilotstd.core._validity_pipeline import _std_name

    class _DB:
        def fetchone(self, *_a, **_k):
            raise RuntimeError("db down")

    with caplog.at_level(logging.DEBUG):
        assert _std_name(_DB(), "GB 1-2020") == ""

    assert _has(caplog, logging.DEBUG, "std_name lookup failed")
    assert not _has(caplog, logging.WARNING, "std_name")


def test_router_failure_stays_debug(caplog, monkeypatch) -> None:
    from pilotstd.query.engine import _routing

    def _boom(*_a, **_k):
        raise RuntimeError("scorer crashed")

    monkeypatch.setattr(_routing, "get_priority_chain", _boom)
    handler = object.__new__(_routing.RoutingHandler)
    handler._core = types.SimpleNamespace(rotator=None, quota=None)

    with caplog.at_level(logging.DEBUG):
        handler._resolve_base_route("GB")

    assert _has(caplog, logging.DEBUG, "评分器路由失败，回退到硬编码路由")
    assert not _has(caplog, logging.WARNING, "评分器路由失败")


def test_scorer_config_override_failure_stays_debug(caplog, monkeypatch) -> None:
    from pilotstd.core.config import manager as config_manager_mod
    from pilotstd.query.routing import scorer

    def _boom():
        raise RuntimeError("config broken")

    monkeypatch.setattr(config_manager_mod, "get_shared_config", _boom)
    name = next(iter(scorer.ADAPTER_DEFAULT_PROFILES))

    with caplog.at_level(logging.DEBUG):
        profile = scorer.get_profile(name)

    assert isinstance(profile, dict)
    assert _has(caplog, logging.DEBUG, "读取站点配置覆盖失败")
    assert not _has(caplog, logging.WARNING, "读取站点配置覆盖失败")


# ── E4：energy 不可达 debug 分支已删除（源码级）───────────────────────────


def test_energy_dead_branch_removed() -> None:
    from pathlib import Path

    import pilotstd.query.adapters.energy as energy_mod

    src = Path(energy_mod.__file__).read_text(encoding="utf-8")
    assert "energy 第%d页请求失败: keyword=" not in src, "不可达的 debug 分支应已删除"
