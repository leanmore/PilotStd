// web/src/api/quality.ts — 数据质量检查
import http from './http'

// 纯 click 触发，无需 routeTag（走 globalPool）
export function runQualityCheck(payload?: unknown) {
  return http.post('/quality/run', payload)
}
