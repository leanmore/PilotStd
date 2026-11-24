"""API 依赖 / 公告查询 / 主题索引 的补测（NEW-43，2026-11-24）。

补 3 个后端模块（清单记录的 16 个无测试模块之一部分）：

| 模块 | 职责 | 错了会怎样 |
|---|---|---|
| `docker/api/notification_deps.py` | 通知接口公共依赖（用户校验 + mgr 获取） | **已删用户的 token 仍能读通知** |
| `docker/api/announce_lookup.py` | 按标准号查公告缓存 | 命中/未命中字段混用，前端渲染错 |
| `pilotstd/core/_topic_index.py` | 主题索引**数据字典**加载 | 数据缺失静默退化 → 主题分组全落兜底 |

断言基于**实测数据**（先看 `topic_index_data.json` 实际条数再断言范围）。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════════
# 1. notification_deps：公共依赖注入
# ════════════════════════════════════════════════════════════════


class TestNotificationDeps:
    """通知接口公共依赖。"""

    def test_get_user_id_returns_when_user_exists(self):
        """用户存在时原样返回 user_id（不触发 401）。

        `_get_user_id` 的默认参数是 `Depends(...)`，但直接传入实参可绕过注入
        （位置参数覆盖默认值），故可直接单测。
        """
        from docker.api.notification_deps import _get_user_id

        mgr = MagicMock()
        mgr.user_service.get_user_by_id.return_value = {"id": 7}

        assert _get_user_id(7, mgr) == 7
        mgr.user_service.get_user_by_id.assert_called_once_with(7)

    def test_get_user_id_raises_401_when_missing(self):
        """**已删除用户的 token 必须被拒**（401，不能继续读通知）。"""
        from fastapi import HTTPException

        from docker.api.notification_deps import _get_user_id

        mgr = MagicMock()
        mgr.user_service.get_user_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            _get_user_id(7, mgr)
        assert exc.value.status_code == 401

    def test_get_notification_mgr_returns_manager(self):
        from docker.api.notification_deps import _get_notification_mgr

        mgr = MagicMock()
        mgr.notification_mgr = "NMGR"

        assert _get_notification_mgr(mgr) == "NMGR"


# ════════════════════════════════════════════════════════════════
# 2. announce_lookup：按标准号查公告缓存
# ════════════════════════════════════════════════════════════════


def _lookup_mgr(row):
    mgr = MagicMock()
    mgr._announce_svc.lookup_announcement.return_value = row
    return mgr


class TestAnnounceLookup:
    """公告缓存精确查询。"""

    def test_not_found_payload(self):
        """未命中：`found=False`，带提示文案，不带 `data`。"""
        from docker.api.announce_lookup import lookup_announcement

        result = lookup_announcement(number="GB 1-2020", mgr=_lookup_mgr(None))

        assert result["found"] is False
        assert result["data"] is None
        assert result["message"]

    def test_found_payload(self):
        """命中：`found=True`，`data` 含名称与抓取时间，`source` 标明来源。"""
        from docker.api.announce_lookup import lookup_announcement

        row = {"std_name": "标准名", "fetched_at": "2026-01-01T00:00:00"}
        result = lookup_announcement(number="GB 1-2020", mgr=_lookup_mgr(row))

        assert result["found"] is True
        assert result["data"] == {"standard_name": "标准名", "fetched_at": "2026-01-01T00:00:00"}
        assert result["cached_at"] == "2026-01-01T00:00:00"
        assert result["source"] == "announcement_record"

    def test_passes_number_to_service(self):
        """标准号必须原样透传给 service（不做二次清洗）。"""
        from docker.api.announce_lookup import lookup_announcement

        mgr = _lookup_mgr(None)
        lookup_announcement(number="GB/T 50011-2010", mgr=mgr)

        mgr._announce_svc.lookup_announcement.assert_called_once_with("GB/T 50011-2010")

    def test_response_model_declared(self):
        """路由必须声明 `response_model`（CI 的 B 步骤要求）。"""
        from fastapi.routing import APIRoute

        from docker.api.announce_lookup import router

        route = next(
            (r for r in router.routes if isinstance(r, APIRoute) and r.path == "/api/announce/lookup"),
            None,
        )
        assert route is not None
        assert route.response_model is not None


# ════════════════════════════════════════════════════════════════
# 3. _topic_index：主题索引数据字典
# ════════════════════════════════════════════════════════════════


class TestTopicIndex:
    """主题索引数据（聚合器专用，非文案）。"""

    def test_data_loaded_at_import(self):
        """模块导入即加载数据（缺文件会在导入时炸，不静默退化）。"""
        from pilotstd.core import _topic_index as ti

        assert isinstance(ti._TOPIC_BY_EVENT, dict)
        assert isinstance(ti._LEGACY_TOPIC_KEYWORDS, tuple)

    def test_event_topics_non_empty(self):
        """事件 → 主题映射必须非空（空表会让主题分组全落兜底）。"""
        from pilotstd.core import _topic_index as ti

        assert len(ti._TOPIC_BY_EVENT) >= 40
        # 抽样断言已知事件
        assert ti._TOPIC_BY_EVENT["scan_complete"] == "done"
        assert ti._TOPIC_BY_EVENT["archive_complete"] == "done"

    def test_legacy_keywords_shape(self):
        """兜底关键词结构：`(topic, (word, ...))`，每个 topic 至少一个词。"""
        from pilotstd.core import _topic_index as ti

        assert len(ti._LEGACY_TOPIC_KEYWORDS) >= 5
        for topic, words in ti._LEGACY_TOPIC_KEYWORDS:
            assert isinstance(topic, str) and topic
            assert isinstance(words, tuple) and words
            assert all(isinstance(w, str) and w for w in words)

    def test_legacy_covers_error_and_done(self):
        """兜底词表必须覆盖 `done`/`error` 两个最常用主题（否则英文标题归不了组）。"""
        from pilotstd.core import _topic_index as ti

        topics = {t for t, _ in ti._LEGACY_TOPIC_KEYWORDS}
        assert "done" in topics
        assert "error" in topics

    def test_all_topics_are_strings(self):
        """所有主题串必须非空字符串（空串会让分组键退化）。"""
        from pilotstd.core import _topic_index as ti

        assert all(isinstance(v, str) and v for v in ti._TOPIC_BY_EVENT.values())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
