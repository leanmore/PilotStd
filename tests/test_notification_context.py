"""A-21 第三步 3a：NotificationContext 语义。"""

import pytest

from pilotstd.core.notification.context import NotificationContext


def test_user_requires_user_id():
    with pytest.raises(ValueError):
        NotificationContext(scope="user")
    assert NotificationContext(scope="user", user_id=2).log_user_id == 2


def test_admin_requires_real_user_id():
    with pytest.raises(ValueError):
        NotificationContext(scope="admin")
    assert NotificationContext(scope="admin", user_id=1).log_user_id == 1


def test_system_logs_zero():
    assert NotificationContext(scope="system").log_user_id == 0


def test_system_rejects_user_id():
    with pytest.raises(ValueError):
        NotificationContext(scope="system", user_id=1)
