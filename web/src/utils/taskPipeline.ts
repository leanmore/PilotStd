// web/src/utils/taskPipeline.ts — 归档项构建（从 TaskView 抽出，控制组件有效行）
import { parseStandardNumber } from './standardParser'

export interface ArchiveItem {
  source_path: string
  new_filename: string
  logical_code: string
  number: number
  year: number
  std_name: string
  num_prefix: string
  ext: string
}

/**
 * 扫描件字段解析：后端已解析字段优先，缺失时才回落前端正则。
 *
 * 批次10（P1-7.1 B-13）：旧实现把 `f.year` 当真值门（`f.logical_code && f.number && f.year`），
 * 后端 B 通道合法的 `year=0`（`API STD 610` / `ASME B16.5` / BPVC 无年份）会被打回前端正则 → null
 * → 不进入 normalizeResults → buildArchiveItems 的 archiveMap 缺键 → 文件静默不归档。
 */
export function resolveScanFields(
  f: any,
): { logical_code: string; number: number; year: number } | null {
  if (f && f.logical_code && f.number) {
    return {
      logical_code: String(f.logical_code),
      number: Number(f.number),
      year: Number(f.year) || 0,
    }
  }
  return parseStandardNumber(f?.standard_number || '')
}

/** 扫描件 + 下载成功件合并为归档项；按 source_path 去重。 */
export function buildArchiveItems(
  scanFiles: any[],
  normalizeResults: any[],
  downloadResults: any[],
): ArchiveItem[] {
  const archiveMap = new Map((normalizeResults || []).map((r: any) => [r.source_path, r.new_filename]))
  const items: ArchiveItem[] = (scanFiles || [])
    .filter((f: any) => archiveMap.has(f.full_path))
    .map((f: any) => ({
      source_path: f.full_path,
      new_filename: archiveMap.get(f.full_path) || f.name || '',
      logical_code: f.logical_code || '',
      number: f.number || 0,
      year: f.year || 0,
      std_name: f.std_name || f.name || '',
      num_prefix: f.num_prefix || '',
      ext: (f.name || '').toLowerCase().endsWith('.pdf') ? 'pdf' : 'doc',
    }))
  // 下载成功的文件也要进入归档；否则 Web 五段式的下载件会留在 /standards 根目录。
  const archivedPaths = new Set(items.map((i) => i.source_path))
  for (const dl of downloadResults || []) {
    if (dl.status !== 'success' || !dl.saved_path || !dl.standard_number) continue
    if (archivedPaths.has(dl.saved_path)) continue
    // 优先用**后端解析结果**（唯一口径：`parse_std_number`，已覆盖 API/ASME/BPVC）；
    // 后端字段缺失（旧版接口/解析失败）时才回落前端正则。
    // 2026-11-24 修：此前只用前端正则，对 API/ASME 等编号 38/40 全盲 → 解析失败即静默跳过归档，
    // 下载件会滞留在 /standards 根目录（数据丢失）。
    const parsed =
      dl.logical_code && dl.number
        ? {
            logical_code: String(dl.logical_code),
            number: Number(dl.number),
            year: Number(dl.year) || 0,
          }
        : parseStandardNumber(dl.standard_number)
    if (!parsed) {
      console.warn('[Archive] 跳过无法解析的下载件:', dl.standard_number, dl.saved_path) // i18n-allow: 开发者日志
      continue
    }
    const filename = String(dl.saved_path).split(/[\\/]/).pop() || dl.standard_name || dl.standard_number
    items.push({
      source_path: dl.saved_path,
      new_filename: filename,
      logical_code: parsed.logical_code,
      number: parsed.number,
      year: parsed.year,
      std_name: dl.standard_name || filename,
      num_prefix: dl.num_prefix || '',
      ext: filename.toLowerCase().endsWith('.pdf') ? 'pdf' : 'doc',
    })
    archivedPaths.add(dl.saved_path)
  }
  return items
}
