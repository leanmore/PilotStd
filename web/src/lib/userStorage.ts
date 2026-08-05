// web/src/lib/userStorage.ts
// 用户隔离 localStorage — key 格式 user_{userId}_{preferenceKey}

const USER_KEY_PREFIX = "user_"

/** 旧 key 列表（无用户隔离前缀），迁移时依次检查 */
const LEGACY_KEYS = [
  "dashboard_layout",
  "pilotstd_dashboard_layout",
  "theme",
  "pilotstd_theme",
  "locale",
  "pilotstd_locale",
]

/** 生成带用户隔离的 localStorage key */
export function getUserKey(userId: number, key: string): string {
  return `${USER_KEY_PREFIX}${userId}_${key}`
}

/** 从 userId key 中解析 userId（失败返回 null） */
export function parseUserIdFromKey(storageKey: string): number | null {
  if (!storageKey.startsWith(USER_KEY_PREFIX)) return null
  const rest = storageKey.slice(USER_KEY_PREFIX.length)
  const underscoreIdx = rest.indexOf("_")
  if (underscoreIdx < 1) return null
  const id = parseInt(rest.substring(0, underscoreIdx), 10)
  return Number.isNaN(id) ? null : id
}

/** 读取带用户隔离的值 */
export function getUserItem(userId: number, key: string): string | null {
  return localStorage.getItem(getUserKey(userId, key))
}

/** 写入带用户隔离的值 */
export function setUserItem(userId: number, key: string, value: string): void {
  localStorage.setItem(getUserKey(userId, key), value)
}

/** 删除带用户隔离的值 */
export function removeUserItem(userId: number, key: string): void {
  localStorage.removeItem(getUserKey(userId, key))
}

/**
 * 迁移旧 localStorage key 到用户隔离格式。
 * 执行顺序：检查新 key → 读旧 key → 写新 key → 删旧 key。
 * 幂等：新 key 已存在时跳过。
 */
export function migrateLegacyPreferences(userId: number): void {
  for (const legacyKey of LEGACY_KEYS) {
    const newKey = getUserKey(userId, legacyKey.replace(/^pilotstd_/, ""))
    if (localStorage.getItem(newKey) !== null) continue // 新 key 已存在，跳过

    const oldValue = localStorage.getItem(legacyKey)
    if (oldValue === null) continue // 旧 key 不存在，跳过

    localStorage.setItem(newKey, oldValue)
    localStorage.removeItem(legacyKey)
  }
}
