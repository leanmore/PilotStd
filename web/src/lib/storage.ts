// web/src/lib/storage.ts
// localStorage 工具 — 统一 pilotstd_ 命名空间前缀 + 旧 key 平滑迁移

const PREFIX = "pilotstd_"

/** 旧 key → 新 key 映射（迁移后旧 key 会被删除） */
const MIGRATIONS: Record<string, string> = {
  theme: "theme",
  locale: "locale",
  announce_tab: "announce_tab",
  dashboard_layout: "dashboard_layout",
}

function migrate(key: string): string {
  const oldVal = localStorage.getItem(key)
  if (oldVal === null) return "" // 无旧数据，跳过
  const newKey = `${PREFIX}${MIGRATIONS[key]}`
  // 只有新 key 不存在时才覆盖（避免覆盖更新的数据）
  if (localStorage.getItem(newKey) === null) {
    localStorage.setItem(newKey, oldVal)
  }
  localStorage.removeItem(key)
  return oldVal
}

export function getItem(key: string): string | null {
  // 检查是否需要迁移
  if (key in MIGRATIONS && localStorage.getItem(key) !== null) {
    const migrated = migrate(key)
    if (migrated) return migrated
  }
  return localStorage.getItem(`${PREFIX}${key}`)
}

export function setItem(key: string, value: string): void {
  localStorage.setItem(`${PREFIX}${key}`, value)
}

export function removeItem(key: string): void {
  localStorage.removeItem(`${PREFIX}${key}`)
  // 同时清理遗留旧 key
  if (key in MIGRATIONS) localStorage.removeItem(key)
}
