"""channel.py 接口可用性验证。"""

from pilotstd.core.notification.channel import NotificationMessage
from tests.fixtures.engine_mock_tree import ChannelStub


class TestNotificationMessage:
    def test_defaults(self):
        msg = NotificationMessage(title="Test")
        assert msg.title == "Test"
        assert msg.body == ""
        assert msg.level == "info"
        assert msg.blocks == []

    def test_custom_fields(self):
        msg = NotificationMessage(
            title="T", body="B", level="warning",
            event_type="test", standard_number="GB/T 1",
            aggregated_count=5, status="success"
        )
        assert msg.event_type == "test"
        assert msg.aggregated_count == 5


class TestChannelStubInterface:
    def test_send_returns_true(self):
        ch = ChannelStub("test", should_succeed=True)
        msg = NotificationMessage(title="T")
        assert ch.send(msg) is True
        assert len(ch.sent) == 1

    def test_send_returns_false(self):
        ch = ChannelStub("test", should_succeed=False)
        assert ch.send(NotificationMessage(title="T")) is False

    def test_validate_config(self):
        assert ChannelStub.validate_config({"k": "v"}) is True
