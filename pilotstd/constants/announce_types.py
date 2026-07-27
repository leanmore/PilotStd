# pilotstd/constants/announce_types.py
# 公告类型映射常量 — 单一真实来源
#
# 用途：announce.py 和 announce_detail.py 共用此映射，
# 新增公告适配器时只需在此处追加条目，无需双处同步。

# source_site → standard_type（供 /api/announce/results 使用）
SOURCE_SITE_TO_TYPE = {
    "announcement_gb": "gb",
    "announcement_hb": "hb",
    "announcement_db": "db",
}

# source_site → announce_detail 内部标识（供 announce_detail.py 使用）
SOURCE_SITE_TO_ANNC = {
    "announcement_gb": "annc_gb",
    "announcement_hb": "annc_hb",
    "announcement_db": "annc_db",
}
