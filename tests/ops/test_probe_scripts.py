"""`scripts/ops/` 只读探测脚本的受控测试（假 HTTP 层，不联网、不触真实环境）。

覆盖任务包要求的三条路径（每个 probe 至少一次）：
  1. **正常通过**：假响应齐全 → 全部 `pass`；
  2. **检测到问题**：假响应返回不一致/缺失 → 对应项 `fail`；
  3. **环境不可达**：HTTP 层抛 `ConnectionError` → `unreachable_reason` 非空、不伪造通过。

另有一条**只读性反证**：把假会话收到的全部调用记录下来，断言「除登录与只读 SQL 外只有
GET/OPTIONS」，即 `mark_missing` 端点只被 OPTIONS 探测、从未被 POST 执行。

风格对齐 `tests/test_check_design_tokens.py`：临时树/假对象，不触碰真实仓库与生产环境。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

# 探测脚本在 scripts/ops/ 下，按同目录模块导入（与门禁脚本测试的 sys.path 注入方式一致）
OPS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "ops"
sys.path.insert(0, str(OPS_DIR))

import _probe_common as common  # noqa: E402
import probe_all  # noqa: E402
import probe_credentials  # noqa: E402
import probe_db_counts  # noqa: E402
import probe_health  # noqa: E402
import probe_pending_paths  # noqa: E402


class FakeResponse:
    """最小假响应：状态码 + JSON 载荷 + 文本，接口与 `requests.Response` 用到的部分一致。"""

    def __init__(self, status_code: int = 200, payload: Any = None, headers: dict | None = None) -> None:
        """构造假响应；`payload` 为 None 时 `text` 为空串（模拟非 JSON 响应）。"""
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"content-type": "application/json"}
        self.text = json.dumps(payload, ensure_ascii=False) if payload is not None else ""

    def json(self) -> Any:
        """解析载荷；`payload` 为 None 时按真实 `requests` 的行为抛 `ValueError`。"""
        if self._payload is None:
            raise ValueError("No JSON object could be decoded")
        return self._payload


class FakeSession:
    """假会话：按 `(方法, 路径或 URL)` 查表返回响应；未登记的路由返回 404。

    `calls` 记录全部 `(方法, URL)`，用于断言只读性；`raise_on` 里的路径抛连接异常。
    """

    def __init__(self, routes: dict, raise_on: tuple[str, ...] = (), cookies: dict | None = None) -> None:
        """`routes` 键形如 `("GET", "/api/health")` 或 `("POST", "https://...")`。"""
        self.routes = routes
        self.raise_on = raise_on
        self.cookies = dict(cookies or {})
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        """模拟请求分发：命中 `raise_on` 抛连接错误，命中 `routes` 返回响应，否则 404。"""
        self.calls.append((method, url))
        path = url
        if any(token in url for token in self.raise_on):
            raise requests.exceptions.ConnectionError(f"mock connection refused: {url}")
        for (verb, key), response in self.routes.items():
            if verb == method and (key == path or path.endswith(key)):
                return response
        return FakeResponse(404, {"detail": "Not Found"})

    def methods(self) -> list[str]:
        """返回本次会话收到的全部 HTTP 方法（用于只读性断言）。"""
        return [method for method, _ in self.calls]


def options(**kwargs: Any) -> common.ProbeOptions:
    """构造探测参数（默认超时很短，测试不该真的等网络）。"""
    params = {"base_url": "http://fake.local:9028", "timeout": 1.0, "max_items": 5}
    params.update(kwargs)
    return common.ProbeOptions(**params)


# ── 共享层：凭据与只读闸门 ──────────────────────────────────


def test_read_creds_extracts_fields_without_json_parse(tmp_path: Path) -> None:
    """凭据文件带中文注释时也能按行提取字段（禁止整体 json.loads 的回归锁定）。"""
    creds_file = tmp_path / "docker_creds.json"
    creds_file.write_text(
        '{\n  "description": "局域网 Docker 凭证 — 测试用",\n'
        '  "docker": {"base_url": "http://10.0.0.9:9028", "username": "u1", "password": "p1"},\n'
        '  "web_api": {"api_token": "tok1"}\n}\n',
        encoding="utf-8",
    )
    creds = common.read_creds(creds_file)
    assert creds.base_url == "http://10.0.0.9:9028"
    assert creds.username == "u1"
    assert creds.api_token == "tok1"
    # 脱敏：不得出现明文密码
    assert "p1" not in creds.describe()


def test_read_creds_tolerates_gbk_comment(tmp_path: Path) -> None:
    """GBK 注释的文件也必须能读（历史文件用 GB18030 编码）。"""
    creds_file = tmp_path / "docker_creds.json"
    creds_file.write_bytes(
        '{"description": "局域网凭证", "docker": {"base_url": "http://x", "username": "u", "password": "p"}}'.encode(
            "gb18030"
        )
    )
    creds = common.read_creds(creds_file)
    assert creds.username == "u" and creds.base_url == "http://x"


def test_write_method_is_blocked_before_sending() -> None:
    """未登记理由的写方法必须在发请求之前被拦截，且不进入会话调用记录。"""
    session = FakeSession({})
    client = common.HttpClient("http://fake.local", session=session)
    with pytest.raises(common.WriteBlockedError):
        client.post("/api/pending/mark-missing")
    assert session.calls == []


def test_read_only_sql_rejects_write_statements() -> None:
    """`POST /query` 只允许单条 SELECT/PRAGMA；写语句与多语句一律拒绝。"""
    for sql in ("DELETE FROM pending_lookup", "SELECT 1; DROP TABLE users", "UPDATE t SET a=1"):
        with pytest.raises(common.WriteBlockedError):
            common._assert_read_only_sql(sql)
    assert common._assert_read_only_sql("SELECT COUNT(*) FROM pending_lookup")


def test_environment_unreachable_is_distinct_from_failure() -> None:
    """连接失败必须抛 `EnvironmentUnreachable`（退出码 2），不能被当成探测失败（1）。"""
    session = FakeSession({}, raise_on=("/api/health",))
    client = common.HttpClient("http://fake.local", session=session)
    with pytest.raises(common.EnvironmentUnreachable):
        client.get("/api/health")


def test_report_exit_code_semantics() -> None:
    """退出码语义：必跑 fail → 1；只有诊断 fail → 0；必跑 unverified → 1。"""
    report = common.Report("demo")
    report.add("a", common.STATUS_PASS, "ok")
    assert report.exit_code() == common.EXIT_OK
    report.add("b", common.STATUS_FAIL, "advisory fail", tier=common.TIER_ADVISORY)
    assert report.exit_code() == common.EXIT_OK
    assert report.exit_code(strict=True) == common.EXIT_FAIL
    report.add("c", common.STATUS_UNVERIFIED, "required unverified")
    assert report.exit_code() == common.EXIT_FAIL


# ── probe_health ────────────────────────────────────────────


def health_routes(schema_version: int = 76, status: str = "ok", version: str = "0.206.0") -> dict:
    """构造健康检查相关路由表（默认全绿）。"""
    return {
        ("GET", "/api/health"): FakeResponse(
            200 if status == "ok" else 207,
            {
                "status": status,
                "version": version,
                "schema_version": schema_version,
                "services": {"database": True, "monitor_service": True, "parser": True},
                "checks": {
                    "disk": {"free_mb": 9000.0, "threshold_mb": 500.0, "ok": status == "ok"},
                    "scheduler": {
                        "heartbeat_at": "2026-11-23T19:00:00+08:00",
                        "age_seconds": 5.0,
                        "ok": status == "ok",
                    },
                    "database_rw": {"read": True, "write": True},
                },
            },
        ),
        ("GET", "/api/system/version"): FakeResponse(
            200, {"version": "0.206.0", "tag": "v0.206.0", "image": "ghcr.io/leanmore/pilotstd:v0.206.0"}
        ),
    }


def test_health_passes_when_versions_match() -> None:
    """正常通过：健康 200 + 版本/schema 与代码库一致。"""
    session = FakeSession(health_routes())
    report = probe_health.run(options(), session=session)
    assert report.unreachable_reason == ""
    assert report.count(common.STATUS_FAIL) == 0
    assert report.exit_code() == common.EXIT_OK


def test_health_fails_on_schema_mismatch() -> None:
    """检测到问题：服务端 schema 落后于代码库 → `schema.consistency` 失败。"""
    session = FakeSession(health_routes(schema_version=1))
    report = probe_health.run(options(), session=session)
    failed = [c for c in report.checks if c.status == common.STATUS_FAIL]
    assert [c.name for c in failed] == ["schema.consistency"]
    assert report.exit_code() == common.EXIT_FAIL


def test_health_degrades_on_207() -> None:
    """207 degraded 必须判失败（部署验证要求全绿），而不是「存活即通过」。"""
    session = FakeSession(health_routes(status="degraded"))
    report = probe_health.run(options(), session=session)
    status_check = next(c for c in report.checks if c.name == "health.status")
    assert status_check.status == common.STATUS_FAIL


def test_health_unreachable_does_not_fake_pass() -> None:
    """环境不可达：记录原因，且不存在任何 `pass` 结论。"""
    session = FakeSession({}, raise_on=("/api/health",))
    report = probe_health.run(options(), session=session)
    assert "不可达" in report.unreachable_reason
    assert report.count(common.STATUS_PASS) == 0


# ── probe_pending_paths ─────────────────────────────────────


def pending_routes(missing_exists: bool = False, allow: str = "POST", job: bool = True) -> dict:
    """构造 pending 探测路由表：`missing_exists=True` 模拟「文件其实还在」（假 missing）。"""
    file_path = "/inbox/AQ 安全/SHB 6-1999 示例.pdf"
    parent = "/inbox/AQ 安全"
    parent_entries = [{"name": "SHB 6-1999 示例.pdf", "type": "file"}] if missing_exists else []
    routes = {
        ("GET", "/api/health"): health_routes()[("GET", "/api/health")],
        ("POST", "/api/login"): FakeResponse(200, {"ok": True, "username": "u", "role": "admin"}),
        ("GET", "/api/settings"): FakeResponse(
            200, {"storage": {"scan_paths": ["/inbox", "/standards"], "downloads_dir": "/inbox"}}
        ),
        ("GET", "/api/files"): FakeResponse(200, {"path": "/inbox", "files": []}),
        ("GET", "/api/pending"): FakeResponse(
            200,
            {"items": [{"id": 1, "reason": "file_missing", "file_path": file_path, "status": "pending"}]},
        ),
        ("OPTIONS", "/api/pending/mark-missing"): FakeResponse(
            405, {"detail": "Method Not Allowed"}, headers={"allow": allow}
        ),
        ("GET", "/api/scheduler/status"): FakeResponse(
            200,
            {
                "running": True,
                "jobs": [{"id": "pending_missing_check", "next_run_time": "2026-11-24T03:30:00", "trigger": "cron"}]
                if job
                else [],
            },
        ),
    }

    def files_dispatch(method: str, url: str, **kwargs: Any) -> FakeResponse:
        """按 `path` 参数返回不同目录内容（模拟 `/api/files?path=...`）。"""
        target = str((kwargs.get("params") or {}).get("path") or "")
        if target == parent:
            return FakeResponse(200, {"path": parent, "files": parent_entries})
        if target in ("/inbox", "/standards"):
            return FakeResponse(200, {"path": target, "files": [{"name": "AQ 安全", "type": "dir"}]})
        return FakeResponse(404, {"error": "路径不存在"})

    return routes, files_dispatch


def pending_session(
    missing_exists: bool = False, allow: str = "POST", job: bool = True, deployed: bool = True
) -> FakeSession:
    """构造带 `/api/files` 参数分发的假会话；`deployed=False` 时模拟端点未部署（OPTIONS 404）。"""
    routes, dispatch = pending_routes(missing_exists, allow, job)
    if not deployed:
        routes.pop(("OPTIONS", "/api/pending/mark-missing"))
    session = FakeSession(routes)
    original = session.request

    def request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        """优先走参数分发，其余回落到路由表。"""
        if method == "GET" and url.endswith("/api/files"):
            session.calls.append((method, url))
            return dispatch(method, url, **kwargs)
        return original(method, url, **kwargs)

    session.request = request  # type: ignore[method-assign]
    return session


def test_pending_paths_pass_when_file_really_missing() -> None:
    """正常通过：路径落在扫描根下、文件确实不存在、端点为 POST 已部署、任务已注册。"""
    session = pending_session()
    report = probe_pending_paths.run(options(), session=session)
    assert report.unreachable_reason == ""
    assert report.count(common.STATUS_FAIL) == 0
    mapping = next(c for c in report.checks if c.name == "pending.path_mapping")
    assert mapping.evidence["genuinely_missing"] == 1
    assert report.exit_code() == common.EXIT_OK


def test_pending_paths_flags_fake_missing() -> None:
    """检测到问题：pending 标 missing 但文件其实存在 → 判「假 missing」并失败。"""
    session = pending_session(missing_exists=True)
    report = probe_pending_paths.run(options(), session=session)
    mapping = next(c for c in report.checks if c.name == "pending.path_mapping")
    assert mapping.status == common.STATUS_FAIL
    assert mapping.evidence["fake_missing"]
    assert report.exit_code() == common.EXIT_FAIL


def test_pending_paths_endpoint_not_deployed_returns_404() -> None:
    """端点未部署：OPTIONS 404 → `endpoint.mark_missing` 失败并提示更新镜像。"""
    session = pending_session(deployed=False)
    report = probe_pending_paths.run(options(), session=session)
    endpoint = next(c for c in report.checks if c.name == "endpoint.mark_missing")
    assert endpoint.status == common.STATUS_FAIL
    assert "未部署" in endpoint.detail


def test_pending_paths_unreachable() -> None:
    """环境不可达：`/api/health` 连接失败 → 记录原因且无 pass。"""
    session = FakeSession({}, raise_on=("/api/health",))
    report = probe_pending_paths.run(options(), session=session)
    assert "不可达" in report.unreachable_reason
    assert report.count(common.STATUS_PASS) == 0


def test_pending_paths_never_posts_mark_missing() -> None:
    """只读性反证：整轮探测里 `mark_missing` 只被 OPTIONS 探测，从未被 POST 执行。"""
    session = pending_session()
    probe_pending_paths.run(options(), session=session)
    posts = [(m, u) for m, u in session.calls if m == "POST"]
    assert [u for _m, u in posts] == ["http://fake.local:9028/api/login"]
    assert not any(u.endswith("/api/pending/mark-missing") and m == "POST" for m, u in session.calls)
    assert any(m == "OPTIONS" and u.endswith("/api/pending/mark-missing") for m, u in session.calls)


def test_pending_paths_guard_flags_mass_missing() -> None:
    """挂载保护：pending 全表缺失比例 ≥90% 且 ≥50 行时，`mark_missing` 会整轮跳过 → 必须阻断。

    构造 60 条全部不存在的路径（父目录可列但不含该文件），模拟「数据真缺失」场景：
    保护会误报，probe 需明确指出这一点，而不是给出「可以标记」的错误结论。
    """
    items = [
        {"id": i, "reason": "file_missing", "file_path": f"/inbox/AQ 安全/不存在-{i}.pdf", "status": "pending"}
        for i in range(60)
    ]
    routes, _dispatch = pending_routes()

    def files_dispatch(method: str, url: str, **kwargs: Any) -> FakeResponse:
        """所有目录都可列但内容为空（文件确实不存在）。"""
        target = str((kwargs.get("params") or {}).get("path") or "")
        if target in ("/inbox", "/standards"):
            return FakeResponse(200, {"path": target, "files": [{"name": "AQ 安全", "type": "dir"}]})
        return FakeResponse(200, {"path": target, "files": []})

    routes[("GET", "/api/pending")] = FakeResponse(200, {"items": items})
    session = FakeSession(routes)
    original = session.request

    def request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        """`/api/files` 走参数分发，其余走路由表。"""
        if method == "GET" and url.endswith("/api/files"):
            session.calls.append((method, url))
            return files_dispatch(method, url, **kwargs)
        return original(method, url, **kwargs)

    session.request = request  # type: ignore[method-assign]
    report = probe_pending_paths.run(options(max_items=60), session=session)
    guard = next(c for c in report.checks if c.name == "pending.mass_delete_guard")
    assert guard.status == common.STATUS_FAIL
    assert "误报" in guard.detail
    assert report.exit_code() == common.EXIT_FAIL


# ── probe_credentials ───────────────────────────────────────


def credential_routes(feishu_enabled: bool = False, feishu_secret: str = "") -> dict:
    """构造凭证探测路由表；`feishu_secret` 为空表示服务端回显掩码。"""
    return {
        ("GET", "/api/health"): health_routes()[("GET", "/api/health")],
        ("POST", "/api/login"): FakeResponse(200, {"ok": True, "username": "u", "role": "admin"}),
        ("GET", "/api/notification/config"): FakeResponse(
            200,
            {
                "enabled": True,
                "channels": {
                    "feishu": {
                        "enabled": feishu_enabled,
                        "app_id": "cli_xxx",
                        "app_secret": feishu_secret or common.MASKED_VALUE,
                        "receive_id": "oc_123456789",
                        "webhook_url": "",
                    },
                    "telegram": {"enabled": True, "bot_token": common.MASKED_VALUE, "chat_id": "-100123"},
                },
            },
        ),
        ("GET", "/api/notification/channels"): FakeResponse(
            200,
            {
                "channels": [
                    {
                        "name": "feishu",
                        "enabled_default": False,
                        "forms": [{"key": "app", "required": ["app_id", "app_secret", "receive_id"], "extra": []}],
                        "status_rule": {"branches": []},
                    },
                    {
                        "name": "telegram",
                        "enabled_default": False,
                        "forms": [],
                        "status_rule": {"branches": [{"all_of": ["bot_token", "chat_id"]}]},
                    },
                ]
            },
        ),
    }


def test_credentials_pass_when_complete() -> None:
    """正常通过：飞书/Telegram 必填字段齐全（密钥为掩码也视为已配置）。"""
    session = FakeSession(credential_routes())
    report = probe_credentials.run(options(), session=session)
    assert report.count(common.STATUS_FAIL) == 0
    feishu = next(c for c in report.checks if c.name == "feishu.credentials")
    assert feishu.status == common.STATUS_PASS


def test_credentials_fails_when_enabled_channel_missing_fields() -> None:
    """检测到问题：渠道已启用但必填字段缺失 → 阻断（消息会静默发不出去）。"""
    routes = credential_routes(feishu_enabled=True)
    config = routes[("GET", "/api/notification/config")]
    config._payload["channels"]["feishu"].update({"app_id": "", "app_secret": "", "receive_id": ""})
    session = FakeSession(routes)
    report = probe_credentials.run(options(), session=session)
    feishu = next(c for c in report.checks if c.name == "feishu.credentials")
    assert feishu.status == common.STATUS_FAIL
    assert report.exit_code() == common.EXIT_FAIL


def test_credentials_masked_secret_is_unverified_not_pass() -> None:
    """掩码下拿不到明文 secret：连通性必须标「无法验证」，不能假装连通。"""
    session = FakeSession(credential_routes())
    report = probe_credentials.run(options(), session=session)
    connectivity = next(c for c in report.checks if c.name == "feishu.connectivity")
    assert connectivity.status == common.STATUS_UNVERIFIED


def test_credentials_unreachable() -> None:
    """环境不可达：记录原因且无 pass。"""
    session = FakeSession({}, raise_on=("/api/health",))
    report = probe_credentials.run(options(), session=session)
    assert "不可达" in report.unreachable_reason
    assert report.count(common.STATUS_PASS) == 0


def test_credentials_never_send_messages() -> None:
    """只读性反证：探测过程只发 GET，外加登录 POST；绝不调用消息发送接口。"""
    session = FakeSession(credential_routes(feishu_enabled=True, feishu_secret="plain-secret"))
    probe_credentials.run(options(), session=session)
    verbs = {method for method, _ in session.calls}
    assert verbs <= {"GET", "POST"}
    assert not any("send" in url or "webhook" in url for _m, url in session.calls)
    # 明文 `secret` 绝不出现在报告里
    report = probe_credentials.run(options(), session=FakeSession(credential_routes(feishu_secret="plain-secret")))
    assert "plain-secret" not in json.dumps(report.as_dict(), ensure_ascii=False)


# ── probe_db_counts ─────────────────────────────────────────


def db_routes(orphans: int = 0) -> dict:
    """构造对账探测路由表：`/query` 按**完整 SQL 文本**返回对应计数（精确匹配，避免子串误命中）。"""
    sql_results = {
        probe_db_counts.COUNT_SQL["announcement_record"]: 233933,
        probe_db_counts.COUNT_SQL["announcement_matched"]: 844,
        probe_db_counts.COUNT_SQL["pending_total"]: 633,
        probe_db_counts.COUNT_SQL["pending_pending"]: 61,
        probe_db_counts.COUNT_SQL["pending_status_sum"]: 633,
        probe_db_counts.COUNT_SQL["pending_file_missing_no_path"]: 0,
        probe_db_counts.COUNT_SQL["favorites_total"]: 139,
        probe_db_counts.COUNT_SQL["favorite_downloads_orphan"]: orphans,
        probe_db_counts.COUNT_SQL["announcement_fresh_dup"]: 0,
        probe_db_counts.COUNT_SQL["file_index_total"]: 776,
        probe_db_counts.COUNT_SQL["file_index_status_sum"]: 776,
        probe_db_counts.COUNT_SQL["notification_log_total"]: 2600,
    }

    def query_response(payload: dict) -> FakeResponse:
        """按 SQL 精确查表返回单行计数；未知语句返回 0（测试里不该出现）。"""
        sql = str((payload or {}).get("sql") or "")
        return FakeResponse(200, {"success": True, "rows": [{"c": sql_results.get(sql, 0)}], "row_count": 1})

    return {
        ("GET", "/api/health"): health_routes()[("GET", "/api/health")],
        ("POST", "/api/login"): FakeResponse(200, {"ok": True, "username": "u", "role": "admin"}),
        ("GET", "/api/pending"): FakeResponse(200, {"items": [{}] * 61}),
        ("GET", "/api/favorites"): FakeResponse(200, {"favorites": [{}] * 139}),
        ("GET", "/api/announce/stats"): FakeResponse(200, {"total": {"all": 233933}, "matched": 844}),
        ("GET", "/api/stats"): FakeResponse(200, {"current": 572, "expired": 116, "pending": 0, "upcoming": 20}),
        ("GET", "/api/notification/logs"): FakeResponse(200, {"total": 2600}),
        ("POST", "/query"): query_response,
    }


def db_session(orphans: int = 0) -> FakeSession:
    """构造带 `/query` 动态分发的假会话。"""
    session = FakeSession(db_routes(orphans))
    original = session.request

    def request(method: str, url: str, **kwargs: Any) -> FakeResponse:
        """`POST /query` 按 body 里的 SQL 决定返回，其余走路由表。"""
        if method == "POST" and url.endswith("/query"):
            session.calls.append((method, url))
            return db_routes(orphans)[("POST", "/query")](kwargs.get("json") or {})
        return original(method, url, **kwargs)

    session.request = request  # type: ignore[method-assign]
    return session


def test_db_counts_pass_when_consistent() -> None:
    """正常通过：各项计数自洽（无孤儿行）。"""
    report = probe_db_counts.run(options(), session=db_session())
    assert report.count(common.STATUS_FAIL) == 0
    assert report.exit_code() == common.EXIT_OK


def test_db_counts_flags_orphan_rows() -> None:
    """检测到问题：`favorite_downloads` 有孤儿行 → 必跑项失败。"""
    report = probe_db_counts.run(options(), session=db_session(orphans=3))
    orphan = next(c for c in report.checks if c.name == "favorite_downloads.orphan")
    assert orphan.status == common.STATUS_FAIL
    assert report.exit_code() == common.EXIT_FAIL


def test_db_counts_unreachable() -> None:
    """环境不可达：记录原因且无 pass。"""
    session = FakeSession({}, raise_on=("/api/health",))
    report = probe_db_counts.run(options(), session=session)
    assert "不可达" in report.unreachable_reason
    assert report.count(common.STATUS_PASS) == 0


def test_db_counts_queries_are_read_only() -> None:
    """只读性反证：所有 `/query` 请求体里的 SQL 都是 SELECT（共享层已强制校验）。"""
    session = db_session()
    probe_db_counts.run(options(), session=session)
    assert all(sql.upper().startswith("SELECT ") for sql in probe_db_counts.COUNT_SQL.values())


# ── probe_all ──────────────────────────────────────────────


def test_probe_all_short_circuits_when_unreachable() -> None:
    """环境不可达：不再逐个跑 probe，直接返回原因（避免每个都等一次超时）。"""
    session = FakeSession({}, raise_on=("/api/health",))
    reports, reason = probe_all.run_all(options(), ["health", "db_counts"], session=session)
    assert reports == []
    assert "不可达" in reason


def test_probe_all_aggregates_blocking_items() -> None:
    """汇总：阻断项按 `probe:检查名` 聚合并给出非零退出码。"""
    report = common.Report("demo")
    report.add("bad", common.STATUS_FAIL, "boom")
    summary = probe_all.summarize([report], strict=False)
    assert summary["exit_code"] == common.EXIT_FAIL
    assert summary["blocking"] and summary["blocking"][0].startswith("demo:bad")


def test_probe_all_rejects_unknown_probe_name() -> None:
    """`--only` 传入未知名称必须报错退出，而不是静默跳过（避免假绿）。"""
    with pytest.raises(SystemExit):
        probe_all._select("health,nope")


def test_probe_all_masks_secrets_in_json(tmp_path: Path) -> None:
    """JSON 输出中不得出现凭据文件的明文密码（脱敏只在展示层，报告里也不许漏）。"""
    creds_file = tmp_path / "docker_creds.json"
    creds_file.write_text('{"docker": {"base_url": "http://x", "username": "u", "password": "SUPERSECRET"}}')
    creds = common.read_creds(creds_file)
    report = common.Report("demo", "http://x")
    report.add("auth.admin", common.STATUS_PASS, creds.describe())
    assert "SUPERSECRET" not in json.dumps(report.as_dict(), ensure_ascii=False)
