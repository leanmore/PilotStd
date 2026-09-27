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
