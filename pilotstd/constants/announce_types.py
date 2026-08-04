# 模块：项目/常量/_脚本
# 公告类型映射常量 — 单一真实来源
# 分隔
# 用途：脚本和_脚本共用此映射，
# 新增公告适配器时只需在此处追加条目，无需双处同步。

# _→_（供///使用）
SOURCE_SITE_TO_TYPE = {
    "announcement_gb": "gb",
    "announcement_hb": "hb",
    "announcement_db": "db",
}

# _→_内部标识（供_脚本使用）
SOURCE_SITE_TO_ANNC = {
    "announcement_gb": "annc_gb",
    "announcement_hb": "annc_hb",
    "announcement_db": "annc_db",
}
