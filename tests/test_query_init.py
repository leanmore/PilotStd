"""query 包顶层导出契约（A-33 后仅保留 __all__ 检查）。

原文件测的是 20 个 `_get_*_adapter` 懒加载函数——生产 0 调用、唯一消费者就是这些测试，
属"自我维系的导出面"；2026-11-14 已连同函数一起删除（见
`docs/records/2026-11-14-a33-lazy-getters-audit.md`）。适配器统一走
`pilotstd/query/adapters/registry.py`。
"""


class TestTopLevelExports:
    def test_top_level_exports(self):
        import pilotstd.query as q

        assert q.QueryResult is not None
        assert q.QueryEngine is not None
        assert q.SiteRotator is not None
        assert q.BaseAdapter is not None
        assert q.CacheRepository is not None
