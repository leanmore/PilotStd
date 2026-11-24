"""缺口覆盖：为 6 个此前无测试引用的后端模块补契约测试（顺序同任务清单）。

断言基于对源码的只读探测（Python 3.14 / pydantic 2.13），不依赖真实网络、数据库或 Qt 事件循环。
UI 相关用例经 `ui_env` fixture 惰性导入（后端 import 守卫要求模块级不出现 pilotstd.ui）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import docker.api._announce_detail_parse as announce_parse
import pilotstd.announcement.parser as announcement_parser
from docker.api._announce_detail_models import (
    AnnouncementDetailResponse,
    AnnouncementHeaderItem,
    AnnouncementParseResponse,
    AnnouncementRecordItem,
    AnnouncementRecordLiteItem,
    AnnouncementRecordPageItem,
    AnnouncementRecordsPageResponse,
)
from pilotstd.core.notification._builders_system_security import (
    _build_notification_credential_changed_message,
    _build_security_login_failed_message,
    _build_security_password_changed_message,
    _build_security_token_refreshed_message,
)
from pilotstd.core.notification.blocks import KeyValueBlock, TextBlock
from pilotstd.i18n import t
from pilotstd.query.site_config._profiles import ADAPTER_DEFAULT_PROFILES

_CRED_NS = "notification.system.notification_credential_changed"
_PWD_NS = "notification.system.security_password_changed"
_TOKEN_NS = "notification.system.security_token_refreshed"
_LOGIN_NS = "notification.system.security_login_failed"


@pytest.fixture
def ui_env():
    """惰性加载 UI 适配器与 Handler 协议；PyQt6 缺失时跳过依赖它们的用例。"""
    pytest.importorskip("PyQt6.QtWidgets")
    import pilotstd.ui.core._core_adapters as adapters
    from pilotstd.ui.core.handlers import protocols

    return SimpleNamespace(adapters=adapters, protocols=protocols)


# ── 1. 公告详情响应模型 ───────────────────────────────────────────────────────
_PAGE_ITEM = {
    "id": 1, "row_index": None, "standard_number": "GB/T 1-2024", "std_name": None,
    "publish_date": None, "implement_date": None, "expiry_date": None, "superseded_by": None,
    "status": None, "language": None, "foreign_name": None, "source_site": "std_gov",
}


class TestAnnounceDetailModels:
    def test_page_item_nullable_columns_and_pagination_wire_contract(self):
        item = AnnouncementRecordPageItem(**_PAGE_ITEM)
        assert item.model_dump()["row_index"] is None and item.model_dump()["superseded_by"] is None
        page = AnnouncementRecordsPageResponse(items=[item], total=1, page=2, pageSize=50, hasMore=True)
        dumped = page.model_dump()
        assert list(AnnouncementRecordsPageResponse.model_fields) == ["items", "total", "page", "pageSize", "hasMore"]
        assert dumped["pageSize"] == 50 and dumped["hasMore"] is True

    def test_required_fields_and_int_type_validation(self):
        with pytest.raises(ValidationError) as excinfo:
            AnnouncementRecordItem(id=1, row_index=1, standard_number="GB")
        assert len(excinfo.value.errors()) == 10
        assert {error["type"] for error in excinfo.value.errors()} == {"missing"}
        with pytest.raises(ValidationError) as excinfo:
            AnnouncementRecordPageItem(**{**_PAGE_ITEM, "id": "not-an-int"})
        assert excinfo.value.errors()[0]["type"] == "int_parsing"

    def test_nested_detail_coerces_confidence_and_aux_responses(self):
        header = AnnouncementHeaderItem(
            id=1, announce_no="A-1", title="公告", publish_date="2024-01-01", source_url="http://x/d",
            attachment_url="http://x/a.wps", site_name="站点", content="正文", source="src", source_type="attachment",
        )
        record = AnnouncementRecordItem(
            id=7, row_index=2, standard_number="GB/T 1-2024", std_name="标题", publish_date="2024-01-01",
            implement_date="2024-06-01", expiry_date="", superseded_by="", status="current", confidence=1,
            source_type="attachment", created_at="c", updated_at="u",
        )
        detail = AnnouncementDetailResponse(announcement=header, records=[record], parse_status="completed")
        assert detail.records[0].confidence == 1.0 and isinstance(detail.records[0].confidence, float)
        assert detail.model_dump()["announcement"]["announce_no"] == "A-1"
        with pytest.raises(ValidationError):
            AnnouncementDetailResponse(records=[], parse_status="completed")
        lite_fields = list(AnnouncementRecordLiteItem.model_fields)
        assert lite_fields[0] == "id" and "confidence" not in lite_fields and len(lite_fields) == 9
        assert AnnouncementParseResponse(status="parsing").model_dump() == {
            "status": "parsing", "record_count": None, "announce_no": None,
        }


# ── 2. 公告附件后台解析 ───────────────────────────────────────────────────────
_SAMPLE_ITEMS = [
    {
        "std_code": "GB/T 1-2024", "std_name": "标题", "publish_date": "2024-01-01",
        "implementation_date": "2024-06-01", "replaces_code": "GB/T 0-2020", "confidence": 0.9, "raw_text": "raw",
    },
    {"std_code": "GB/T 2-2024"},
]


@pytest.fixture
def parse_env(monkeypatch):
    """隔离 manager.db 与 parser 依赖，只观察后台解析写下的 SQL 语句序列。"""
    db = MagicMock()
    monkeypatch.setattr(announce_parse, "_get_mgr", lambda: SimpleNamespace(db=db))
    download = MagicMock(return_value=b"%PDF-fake")
    parse = MagicMock(return_value=(list(_SAMPLE_ITEMS), {}))
    monkeypatch.setattr(announcement_parser, "download_attachment", download)
    monkeypatch.setattr(announcement_parser, "parse_announcement_detail", parse)
    return SimpleNamespace(db=db, download=download, parse=parse)


def test_now_iso_is_utc_aware():
    raw = announce_parse._now_iso()
    parsed = datetime.fromisoformat(raw)
    assert raw.endswith("+00:00") and parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(None)
    assert datetime.fromisoformat(announce_parse._now_iso()) >= parsed


@pytest.mark.parametrize("failure", ["download_none", "download_empty", "parse_empty", "raise"])
def test_failure_paths_never_write_db(parse_env, failure):
    if failure == "parse_empty":
        parse_env.parse.return_value = ([], {})
    elif failure == "raise":
        parse_env.download.side_effect = RuntimeError("network down")
    else:
        parse_env.download.return_value = None if failure == "download_none" else b""
    announce_parse._parse_attachment_bg(11, "ANN-1", "http://x/a.wps")  # 异常不向 BackgroundTasks 传播
    assert parse_env.db.method_calls == []


def test_success_writes_rows_then_header(parse_env):
    announce_parse._parse_attachment_bg(
        11, "ANN-1", "http://x/files/doc.wps", source_site="std_gov", pid="p-1", source_url="http://x/detail",
    )
    calls = parse_env.db.method_calls
    assert [call[0] for call in calls] == ["execute", "executemany", "execute"]
    assert "DELETE FROM announcement_record" in calls[0].args[0] and calls[0].args[1] == ("ANN-1",)
    first, second = calls[1].args[1]
    assert first[:6] == (11, "ANN-1", 1, "GB/T 1-2024", "标题", "2024-01-01")
    assert second[:6] == (11, "ANN-1", 2, "GB/T 2-2024", "", "")
    assert (first[7], first[8], first[9], second[9]) == (None, "GB/T 0-2020", 0.9, 0.0)
    assert (first[11], first[12]) == ("attachment", "附件解析")  # meta.source 缺省 / 固定来源类型
    assert first[13] == second[13] and datetime.fromisoformat(first[13]).tzinfo is not None
    sql, params = calls[2].args
    assert "INSERT OR REPLACE INTO announcements" in sql and "'completed'" in sql
    assert params[:7] == ("std_gov", "p-1", "ANN-1", "", "", "http://x/detail", "http://x/files/doc.wps")
    assert params[7] == "" and datetime.fromisoformat(params[8]).tzinfo is not None
    assert parse_env.parse.call_args.kwargs["attachment_filename"] == "doc.wps"
    for url in ("http://x/files/", ""):  # 无文件名时回退
        announce_parse._parse_attachment_bg(11, "ANN-1", url)
        assert parse_env.parse.call_args.kwargs["attachment_filename"] == "attachment.wps"


def test_header_explicit_values_win_over_parser_meta(parse_env):
    parse_env.parse.return_value = (
        list(_SAMPLE_ITEMS), {"title": "meta-title", "publish_date": "2024-02-02", "source": "ocr"},
    )
    announce_parse._parse_attachment_bg(11, "ANN-1", "http://x/a.wps", ann_title="显式标题", publish_date="2023-12-31")
    params = parse_env.db.method_calls[-1].args[1]
    assert params[3:5] == ("显式标题", "2023-12-31")
    assert parse_env.db.method_calls[1].args[1][0][11] == "ocr"


# ── 3. 系统安全类事件构建器 ───────────────────────────────────────────────────
def _kvs(message):
    return [(block.key, block.value) for block in message.blocks if isinstance(block, KeyValueBlock)]


def _texts(message):
    return [block.text for block in message.blocks if isinstance(block, TextBlock)]


class TestSystemSecurityBuilders:
    def test_credential_changed_minimal_rules_and_surface_details(self):
        minimal = _build_notification_credential_changed_message({})
        assert (minimal.level, minimal.event_type, minimal.icon) == (
            "warning", "notification_credential_changed", "pi pi-shield")
        assert minimal.blocks == [TextBlock(text=t(f"{_CRED_NS}.body.hint"))]
        rules_only = _build_notification_credential_changed_message({"rules_changed": True, "changed_keys": ["r"]})
        assert _texts(rules_only) == [t(f"{_CRED_NS}.body.rules"), t(f"{_CRED_NS}.body.hint")]
        detailed = _build_notification_credential_changed_message({
            "services": ["wechat", "telegram"], "changed_keys": ["token", "url"],
            "rules_changed": True, "from_ip": "10.0.0.1",
        })
        assert _kvs(detailed) == [
            (t(f"{_CRED_NS}.body.services"), "wechat, telegram"),
            (t(f"{_CRED_NS}.body.keys"), "token, url"),
            (t(f"{_CRED_NS}.body.from_ip"), "10.0.0.1"),
        ]
        assert t(f"{_CRED_NS}.body.rules") not in _texts(detailed)
        assert _texts(detailed)[-1] == t(f"{_CRED_NS}.body.hint")

    @pytest.mark.parametrize(("sessions_revoked", "expect_kept"), [
        (None, True), (False, True), (0, True), ("", True), (True, False),
    ])
    def test_password_changed_session_hint(self, sessions_revoked, expect_kept):
        payload = {"user_id": "u-1", "from_ip": "1.2.3.4"}
        if sessions_revoked is not None:
            payload["sessions_revoked"] = sessions_revoked
        message = _build_security_password_changed_message(payload)
        assert (message.level, message.event_type, message.icon) == (
            "warning", "security_password_changed", "pi pi-key")
        assert _kvs(message) == [(t(f"{_PWD_NS}.body.account"), "u-1"), (t(f"{_PWD_NS}.body.from_ip"), "1.2.3.4")]
        assert (t(f"{_PWD_NS}.body.sessions_kept") in _texts(message)) is expect_kept
        assert _texts(message)[-1] == t(f"{_PWD_NS}.body.hint")

    @pytest.mark.parametrize(("payload", "expected_kvs", "expect_unsynced"), [
        ({"rotated_at": "t", "from_ip": "8.8.8.8"},
         [(t(f"{_TOKEN_NS}.body.time"), "t"), (t(f"{_TOKEN_NS}.body.from_ip"), "8.8.8.8")], False),
        ({"db_synced": False}, [], True),
    ])
    def test_token_refreshed_db_sync_alert(self, payload, expected_kvs, expect_unsynced):
        message = _build_security_token_refreshed_message(payload)
        assert (message.level, message.event_type, message.title) == (
            "warning", "security_token_refreshed", t(f"{_TOKEN_NS}.title"))
        assert _kvs(message) == expected_kvs
        assert (t(f"{_TOKEN_NS}.body.db_unsynced") in _texts(message)) is expect_unsynced
        assert _texts(message)[-1] == t(f"{_TOKEN_NS}.body.hint")

    @pytest.mark.parametrize(("payload", "expected_minutes"), [
        ({"failures": 5, "window_seconds": 900, "username": "alice", "from_ip": "2.2.2.2"}, 15),
        ({"window_seconds": 30}, 1), ({"window_seconds": 0}, 1),
        ({"window_seconds": -120}, 1), ({"window_seconds": "invalid"}, 0), ({}, 1),
    ])
    def test_login_failed_formats_window_and_survives_bad_input(self, payload, expected_minutes):
        message = _build_security_login_failed_message(payload)
        assert (message.level, message.event_type, message.icon) == (
            "warning", "security_login_failed", "pi pi-lock")
        count = t(f"{_LOGIN_NS}.body.count").format(n=payload.get("failures", 0), minutes=expected_minutes)
        assert _texts(message)[0] == count
        pairs = (("username", "account"), ("from_ip", "from_ip"))
        assert _kvs(message) == [(t(f"{_LOGIN_NS}.body.{field}"), payload[key])
                                 for key, field in pairs if payload.get(key)]


# ── 4. 站点适配器默认画像 ─────────────────────────────────────────────────────
class TestAdapterDefaultProfiles:
    _FIELDS = {
        "label", "industries", "std_prefixes", "is_general", "reliability", "default_weight",
        "rate_limit", "cooling_threshold", "cooling_duration", "role",
    }

    def test_every_profile_has_complete_typed_schema(self):
        for name, profile in ADAPTER_DEFAULT_PROFILES.items():
            assert set(profile) == self._FIELDS, name
            assert isinstance(profile["label"], str) and profile["label"].strip(), name
            assert isinstance(profile["is_general"], bool), name
            assert profile["reliability"] in {"high", "medium", "low"}, name
            assert profile["role"] in {"primary", "background"}, name
            assert isinstance(profile["default_weight"], int) and 0 < profile["default_weight"] <= 100, name
            for key in ("industries", "std_prefixes"):
                assert isinstance(profile[key], list), (name, key)
                assert all(isinstance(value, str) and value for value in profile[key]), (name, key)
            for key in ("cooling_threshold", "cooling_duration"):
                assert isinstance(profile[key], int) and profile[key] > 0, (name, key)
            rate = profile["rate_limit"]
            assert set(rate) == {"request_interval", "batch_limit", "batch_cooldown"}, name
            assert rate["request_interval"] > 0 and rate["batch_cooldown"] > 0, name
            assert isinstance(rate["batch_limit"], int) and rate["batch_limit"] >= 1, name

    def test_known_anchors_route_roles_and_container_isolation(self):
        std_gov = ADAPTER_DEFAULT_PROFILES["std_gov"]
        assert (std_gov["std_prefixes"], std_gov["default_weight"]) == (["GB", "GB/T", "GB/Z"], 70)
        assert ADAPTER_DEFAULT_PROFILES["jjg"]["industries"] == ["计量"]
        assert {n for n, p in ADAPTER_DEFAULT_PROFILES.items() if p["role"] == "background"} == {"csres"}
        assert ADAPTER_DEFAULT_PROFILES["csres"]["cooling_duration"] == 86400
        assert all(not p["industries"] for p in ADAPTER_DEFAULT_PROFILES.values() if p["is_general"])
        rate_limits = [id(p["rate_limit"]) for p in ADAPTER_DEFAULT_PROFILES.values()]
        assert len(set(rate_limits)) == len(rate_limits) == len(ADAPTER_DEFAULT_PROFILES)

    def test_adapter_keys_are_stable_identifiers(self):
        assert all(name.isidentifier() and name.islower() for name in ADAPTER_DEFAULT_PROFILES)


# ── 5. Qt 核心适配器 ─────────────────────────────────────────────────────────
class TestCoreAdapters:
    def test_table_ops_delegate_and_add_row_builds_update(self, ui_env):
        core = MagicMock()
        core._find_row_by_seq.return_value = "7"
        core._get_selected_path_cb = None
        adapter = ui_env.adapters._TableOpsAdapter(core)
        assert adapter.find_row_by_seq(3) == 7
        assert adapter.get_selected_path() == ""
        assert adapter.get_table_as_list() == []
        assert adapter.remove_selected_rows() is None and adapter.get_selected_seq() is None
        assert adapter.get_work_table() is core._work_table
        adapter.clear_table()
        core._clear_table.assert_called_once_with()
        core._get_selected_path_cb = MagicMock(return_value="C:/work")
        assert ui_env.adapters._TableOpsAdapter(core).get_selected_path() == "C:/work"
        assert adapter.add_table_row({"seq": 5, "parsed": {"code": "GB"}, "work_status": "ok", "total": 9}) == 0
        update = core._add_table_row.call_args.args[0]
        assert type(update).__name__ == "RowUpdate"
        assert (update.seq, update.parsed, update.work_status, update.total) == (5, {"code": "GB"}, "ok", 9)
        assert adapter.add_table_row({}) == 0
        empty = core._add_table_row.call_args.args[0]
        assert (empty.seq, empty.parsed, empty.work_status, empty.total) == (0, None, "", 0)

    @pytest.mark.parametrize(("raw_value", "expected"), [
        ("stage-2", "stage-2"), (None, None), (123, None), (["x"], None),
    ])
    def test_stage_dialog_ops_normalize_and_delegate(self, ui_env, raw_value, expected):
        core = MagicMock()
        core._stage_prereq_dialog.return_value = raw_value
        adapter = ui_env.adapters._DialogOpsAdapter(core)
        assert adapter.stage_prereq_dialog("T", "M", "task") == expected
        core._stage_prereq_dialog.assert_called_once_with("T", "M", "task")
        action = MagicMock()
        adapter.show_stage_dialog("T", "C", action)
        core._show_stage_dialog.assert_called_once_with("T", "C", action)

    def test_question_dlg_and_message_boxes_delegate(self, ui_env, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox

        core = MagicMock()
        adapter = ui_env.adapters._DialogOpsAdapter(core)
        core._question_dlg.return_value = QMessageBox.StandardButton.Yes
        assert adapter.question_dlg("T", "M") is True
        for button in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Cancel):
            core._question_dlg.return_value = button
            assert adapter.question_dlg("T", "M") is False
        fake_box = MagicMock()
        monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox", fake_box)
        parent = object()
        core._parent = parent
        adapter.info_dlg("T", "M")
        adapter.warning_dlg("W", "M2")
        fake_box.information.assert_called_once_with(parent, "T", "M")
        fake_box.warning.assert_called_once_with(parent, "W", "M2")

    def test_task_and_worker_factory_adapters_delegate(self, ui_env, monkeypatch):
        core = MagicMock()
        task = ui_env.adapters._TaskOpsAdapter(core)
        assert task.register_task("scan", 100) == ""
        core._register_task.assert_called_once_with("scan", 100)
        assert (task.update_task_status("t-1", 50, "half"), task.task_completed("t-1"),
                task.get_task_status("t-1")) == (None, None, None)
        factory_adapter = ui_env.adapters._QueryWorkerFactoryAdapter(core)
        factory_adapter._factory = factory = MagicMock()
        factory_adapter.create_query_worker([{"seq": 1}], "callbacks")
        factory.create_query_worker.assert_called_once_with([{"seq": 1}], "callbacks")
        fake_dialog = MagicMock(return_value="dialog")
        monkeypatch.setattr("pilotstd.ui.pending_query_dialog.PendingQueryDialog", fake_dialog)
        assert factory_adapter.create_pending_query_dialog([{"seq": 1}], "parent") == "dialog"
        fake_dialog.assert_called_once_with(core._mgr, [{"seq": 1}], "parent")


# ── 6. Handler 依赖协议 ─────────────────────────────────────────────────────
class TestHandlerProtocols:
    def test_query_callbacks_requires_all_five_callables(self, ui_env):
        callbacks_cls = ui_env.protocols.QueryCallbacks
        with pytest.raises(TypeError):
            callbacks_cls()
        callbacks = callbacks_cls(
            on_result_ready=MagicMock(), on_batch_ready=MagicMock(), on_progress=MagicMock(),
            on_finished=MagicMock(), on_error=MagicMock(),
        )
        assert tuple(callbacks_cls.__dataclass_fields__) == (
            "on_result_ready", "on_batch_ready", "on_progress", "on_finished", "on_error")
        callbacks.on_progress(42)
        callbacks.on_progress.assert_called_once_with(42)

    def test_protocol_member_sets_are_locked_and_structural_only(self, ui_env):
        expected = {
            "ITableOps": {"add_table_row", "find_row_by_seq", "clear_table", "get_table_as_list",
                          "remove_selected_rows", "get_selected_path", "get_selected_seq", "get_work_table"},
            "IDialogOps": {"question_dlg", "stage_prereq_dialog", "show_stage_dialog", "info_dlg", "warning_dlg"},
            "ITaskOps": {"register_task", "update_task_status", "task_completed", "get_task_status"},
            "IQueryWorkerFactory": {"create_query_worker", "create_pending_query_dialog"},
        }
        for name, members in expected.items():
            protocol = getattr(ui_env.protocols, name)
            assert protocol.__protocol_attrs__ == frozenset(members), name
            assert protocol._is_protocol is True, name
            with pytest.raises(TypeError, match="runtime_checkable"):
                isinstance(object(), protocol)

    def test_adapters_satisfy_protocols_and_dependencies_map(self, ui_env):
        adapters, protocols = ui_env.adapters, ui_env.protocols
        pairs = [
            (adapters._TableOpsAdapter, protocols.ITableOps),
            (adapters._DialogOpsAdapter, protocols.IDialogOps),
            (adapters._TaskOpsAdapter, protocols.ITaskOps),
            (adapters._QueryWorkerFactoryAdapter, protocols.IQueryWorkerFactory),
        ]
        for adapter_cls, protocol in pairs:
            for member in protocol.__protocol_attrs__:
                assert callable(getattr(adapter_cls, member, None)), (adapter_cls.__name__, member)
        hints = get_type_hints(protocols.IQueryDependencies)
        expected = (protocols.ITableOps, protocols.IDialogOps, protocols.ITaskOps, protocols.IQueryWorkerFactory)
        assert tuple(hints[name] for name in ("table", "dialog", "task", "worker_factory")) == expected
