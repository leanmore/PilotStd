// web/src/types/api.ts — 后端 API 返回值的 TypeScript 接口定义
// 与 docker/api/models.py 和 pilotstd/query/models.py 保持同步

// ── 查询 ──────────────────────────────────────────────

/** 单条标准查询结果，对应 pilotstd/query/models.py QueryResult */
export interface QueryResult {
  standard_number: string
  standard_name: string
  status: string // 现行 / 废止 / 即将实施 / 未知
  replaces: string
  implementation_date: string
  responsible_dept: string
  is_adopted: boolean
  match_status: string // exact / newer / older / code_only / mismatch
  source_site: string
  publish_date: string
  abolition_date: string
  hcno: string
  split_into: string
  is_downloadable: boolean
  error_message: string
}

/** 批量查询响应（实际 API 返回 shape） */
export interface QueryResponse {
  stats: {
    total?: number
    found: number
    downloadable: number
    not_found?: number
  }
  results: QueryResult[]
}

// ── 扫描 ──────────────────────────────────────────────

/** 扫描文件条目 */
export interface FileItem {
  name: string
  full_path: string
  size: number
  status: string
}

/** 扫描结果响应 */
export interface ScanResponse {
  run_id: string
  total: number
  pdf_count: number
  word_count: number
  dup_skipped: number
  skipped_dirs: number
  files: FileItem[]
}

// ── 文件浏览 ──────────────────────────────────────────

/** 文件/目录条目 */
export interface DirItem {
  name: string
  type: 'dir' | 'file'
  path: string
  size: number
}

/** 文件列表响应 */
export interface ListFilesResponse {
  path: string
  files: DirItem[]
}

// ── 下载 ──────────────────────────────────────────────

/** 单个下载结果 */
export interface DownloadResult {
  standard_number: string
  status: string
  saved_path: string
}

/** 批量下载统计 */
export interface DownloadStats {
  total: number
  success: number
  failed: number
  skipped: number
  skipped_exists: number
}

/** 批量下载响应 */
export interface DownloadResponse {
  stats: DownloadStats
  results: DownloadResult[]
}

// ── 用户 ──────────────────────────────────────────────

export interface User {
  id: number
  username: string
  role: string
}

export interface UserListResponse {
  users: User[]
}

// ── 公告 ──────────────────────────────────────────────

export interface AnnounceItem {
  announce_no: string
  announcement_title: string
  standard_count: number | null
  publish_date: string
  source_site: string
}

/** 公告响应包装 */
export interface AnnounceResponse {
  results: AnnounceItem[]
}

// ── 整理 ──────────────────────────────────────────────

export interface NormalizeResult {
  source_path: string
  new_filename: string
}

// ── 待确认 ────────────────────────────────────────────

export interface PendingItem {
  id: number
  standard_number: string
  standard_name: string
  status: string
  source_site: string
  file_path: string
}

// ── 统计 ──────────────────────────────────────────────

export interface StatusStats {
  current: number
  expired: number
  pending: number
  upcoming: number
  [key: string]: number
}

// ── 设置 ──────────────────────────────────────────────

export interface Settings {
  version: string
  storage: {
    scan_paths?: string[]
    [key: string]: unknown
  }
  organize: Record<string, unknown>
  scan: Record<string, unknown>
  query: Record<string, unknown>
  appearance: {
    login_bg?: string
    [key: string]: unknown
  }
  login_bg_url?: string
  [key: string]: unknown
}

// ── 清理 ──────────────────────────────────────────────

export interface CleanResponse {
  cleaned: number
  removed: number
}

// ── 上传 ──────────────────────────────────────────────

export interface UploadResponse {
  url: string
  filename?: string
}

// ── 通用 ──────────────────────────────────────────────

export interface SuccessResponse {
  ok?: boolean
  message?: string
  username?: string
  role?: string
  must_change_password?: boolean
}
