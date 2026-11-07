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
    const parsed = parseStandardNumber(dl.standard_number)
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
      num_prefix: '',
      ext: filename.toLowerCase().endsWith('.pdf') ? 'pdf' : 'doc',
    })
    archivedPaths.add(dl.saved_path)
  }
  return items
}
