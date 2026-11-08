"""通知菜单模型/客户端契约测试（不访问真实渠道）。"""

from __future__ import annotations

import pytest

from pilotstd.core.notification.menu.clients import (
    DingtalkMenuClient,
    FeishuMenuClient,
    MenuResult,
    TelegramCommandClient,
    WecomMenuClient,
)
from pilotstd.core.notification.menu.config import menu_from_config
from pilotstd.core.notification.menu.model import (
    Menu,
    MenuItem,
    MenuValidationError,
    validate,
)
from pilotstd.core.notification.menu.service import sync_channel


def _wecom_menu() -> Menu:
    return Menu(
        "wechat",
        (
            MenuItem("task", "notification.menu.task", "view", 1, url="/task"),
            MenuItem("logs", "notification.menu.logs", "view", 2, url="/notification-logs"),
            MenuItem("more", "notification.menu.more", "click", 3, key="menu:more"),
        ),
    )


def test_wecom_menu_payload_and_limits() -> None:
    menu = _wecom_menu()
    validate(menu)
    calls: list[tuple] = []

    def transport(method, url, payload, headers):
        calls.append((method, url, payload, headers))
        if "gettoken" in url:
            return {"errcode": 0, "access_token": "tok"}
        return {"errcode": 0}

    client = WecomMenuClient("corp", "secret", "1000001", transport=transport)
    result = client.create_menu(menu)

    assert result.ok is True
    assert calls[-1][0] == "POST"
    assert "/menu/create" in calls[-1][1]
    assert "agentid=1000001" in calls[-1][1]
    assert calls[-1][2]["button"][0]["type"] == "view"
    assert calls[-1][2]["button"][2]["type"] == "click"
    assert calls[-1][2]["button"][2]["key"] == "menu:more"


def test_wecom_menu_error_mapping() -> None:
    def transport(method, url, payload, headers):
        if "gettoken" in url:
            return {"errcode": 0, "access_token": "tok"}
        return {"errcode": 48001, "errmsg": "unauthorized"}

    result = WecomMenuClient("c", "s", "1", transport=transport).get_menu()
    assert result.ok is False
    assert result.code == "48001"
    assert "unauthorized" in result.message


def test_feishu_group_menu_payload() -> None:
    menu = Menu(
        "feishu",
        (
            MenuItem("task", "notification.menu.task", "view", 1, url="https://example.com/task"),
            MenuItem("logs", "notification.menu.logs", "view", 2, url="https://example.com/logs"),
        ),
    )
    calls: list[tuple] = []

    def transport(method, url, payload, headers):
        calls.append((method, url, payload, headers))
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "t"}
        return {"code": 0, "data": {"menu_tree": {"chat_menu_top_levels": []}}}

    client = FeishuMenuClient("app", "secret", "chat-1", transport=transport)
    result = client.create_menu(menu)

    assert result.ok is True
    assert calls[-1][0] == "POST"
    assert calls[-1][1].endswith("/chats/chat-1/menu_tree")
    assert calls[-1][3]["Authorization"] == "Bearer t"
    top = calls[-1][2]["menu_tree"]["chat_menu_top_levels"][0]
    assert top["chat_menu_item"]["action_type"] == "REDIRECT_LINK"
    assert top["chat_menu_item"]["redirect_link"]["web_url"].endswith("/task")


def test_telegram_command_payload() -> None:
    menu = Menu(
        "telegram",
        (
            MenuItem("task", "notification.menu.task", "command", 1, command="/task"),
            MenuItem("logs", "notification.menu.logs", "command", 2, command="/logs"),
        ),
    )
    calls: list[tuple] = []

    def transport(method, url, payload, headers):
        calls.append((method, url, payload, headers))
        return {"ok": True, "result": True}

    result = TelegramCommandClient("bot-token", transport=transport).create_menu(menu)
    assert result.ok is True
    assert calls[-1][1].endswith("/setMyCommands")
    assert calls[-1][2]["commands"][0] == {"command": "task", "description": "notification.menu.task"}


def test_dingtalk_explicitly_unsupported() -> None:
    client = DingtalkMenuClient()
    assert client.supports_menu() is False
    assert client.create_menu(Menu("dingtalk", ())).ok is False


@pytest.mark.parametrize(
    "bad",
    [
        Menu("wechat", tuple(MenuItem(f"i{i}", "k", "view", i + 1, url="/x") for i in range(4))),
        Menu("wechat", (MenuItem("a", "k", "view", 1, url="/x"), MenuItem("a", "k2", "view", 2, url="/y"))),
        Menu("wechat", (MenuItem("a", "k", "view", 1, url="javascript:alert(1)"),)),
        Menu("wechat", (MenuItem("a", "k", "view", 2, url="/x"),)),
        Menu("telegram", (MenuItem("a", "k", "command", 1, command="task"),)),
    ],
)
def test_menu_validation_rejects_bad_config(bad: Menu) -> None:
    with pytest.raises(MenuValidationError):
        validate(bad)


def test_sync_is_idempotent(monkeypatch) -> None:
    class _Cfg:
        def __init__(self) -> None:
            self.data = {
                "notification": {
                    "menus": {
                        "wechat": {
                            "enabled": True,
                            "items": [
                                {
                                    "id": "task",
                                    "label_key": "notification.menu.task",
                                    "type": "view",
                                    "order": 1,
                                    "url": "/task",
                                }
                            ],
                        }
                    }
                }
            }

        def get(self, key, default=None):
            node = self.data
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

        def set(self, key, value):
            parts = key.split(".")
            node = self.data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value

        def save(self):
            pass

    class _Client:
        def __init__(self):
            self.created = 0

        def supports_menu(self):
            return True

        def get_menu(self):
            return MenuResult(True, data={})

        def create_menu(self, menu):
            self.created += 1
            return MenuResult(True)

        def supports_type(self, item_type):
            return item_type in {"view", "group"}

    cfg = _Cfg()
    client = _Client()
    monkeypatch.setattr("pilotstd.core.notification.menu.service.build_client", lambda *a, **k: client)

    assert sync_channel("wechat", cfg)["changed"] is True
    assert sync_channel("wechat", cfg)["changed"] is False
    assert client.created == 1


def test_menu_from_config_nested_children() -> None:
    menu = menu_from_config(
        "wechat",
        {
            "enabled": True,
            "items": [
                {
                    "id": "task",
                    "label_key": "notification.menu.task",
                    "type": "group",
                    "order": 1,
                    "children": [
                        {
                            "id": "task_all",
                            "label_key": "notification.menu.task_all",
                            "type": "view",
                            "order": 1,
                            "url": "/task/all",
                        }
                    ],
                }
            ],
        },
    )
    assert menu.items[0].children[0].id == "task_all"
