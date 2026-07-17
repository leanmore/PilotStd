// web/src/constants/sourceMapping.ts
// source_site 数据库值与 URL 标识符的双向映射

export const SOURCE_TO_URL: Record<string, string> = {
  announcement_gb: 'annc_gb',
  announcement_hb: 'annc_hb',
  announcement_db: 'annc_db',
}

export const URL_TO_SOURCE: Record<string, string> = {
  annc_gb: 'announcement_gb',
  annc_hb: 'announcement_hb',
  annc_db: 'announcement_db',
}

export const SOURCE_LABEL: Record<string, string> = {
  announcement_gb: '国家标准',
  announcement_hb: '行业标准',
  announcement_db: '地方标准',
}
