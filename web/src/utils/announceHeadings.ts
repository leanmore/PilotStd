/**
 * 前端兜底修正：将后端误分类为 announce-body 的标题/文号行
 * 替换为 announce-heading，使其应用居中加粗样式。
 */
export function fixAnnounceHeadings(html: string): string {
  const fixedTitles = [
    '中华人民共和国国家标准',
    '行业标准公告',
    '行业标准备案公告',
    '地方标准公告',
  ]

  let result = html

  for (const title of fixedTitles) {
    const pattern = new RegExp(
      `<p class="announce-body">${title}</p>`,
      'g'
    )
    result = result.replace(pattern, `<p class="announce-heading">${title}</p>`)
  }

  // 动态文号：如 "2025年第8号"、"2024年第12号"
  result = result.replace(
    /<p class="announce-body">(\d{4}年第\d+号)<\/p>/g,
    '<p class="announce-heading">$1</p>'
  )

  return result
}
