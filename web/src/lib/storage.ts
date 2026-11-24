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
  if (localStorage.getItem(newKey) !== null) {
    // 新 key 已存在（更新）：**不得**返回旧值 —— 否则 getItem 会把过期数据交给调用方，
    // 同时旧 key 已被删除，更新数据永远读不到（2026-11-25 修复，见 storage.test.ts 回归用例）。
    localStorage.removeItem(key)
    return ""
  }
  localStorage.setItem(newKey, oldVal)
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
