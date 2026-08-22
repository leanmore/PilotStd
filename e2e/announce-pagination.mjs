// e2e/announce-pagination.mjs — 公告记录分页化 E2E 验证（Phase 3）
// 用法：
//   node e2e/announce-pagination.mjs <paginated|legacy> [baseUrl]
// 依赖：本地 dev server 已按对应模式启动（VITE_USE_PAGINATED_RECORDS_API=true|false）
// 账密从 config/docker_creds.json 读取（凭证落盘文件）
import { chromium } from 'file:///D:/PilotStd/web/node_modules/.pnpm/playwright@1.62.0/node_modules/playwright/index.mjs'
import fs from 'node:fs'

const mode = process.argv[2] || 'paginated'
const BASE = process.argv[3] || 'http://localhost:5173'
const creds = JSON.parse(fs.readFileSync('D:/PilotStd/config/docker_creds.json', 'utf8'))
const { username, password } = creds.docker

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

// Network 捕获：分页请求 / 全量请求
const paginatedRequests = []
const liteRequests = []
page.on('request', (req) => {
  const url = req.url()
  if (url.includes('/records?') || url.includes('/records?')) paginatedRequests.push(url)
  else if (url.includes('/lite')) liteRequests.push(url)
})

const errors = []
page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 200)))
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)) })

// ── 登录（经 vite 代理到远程 API）──
await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
await page.fill('input[name=username]', username)
await page.fill('input[name=password]', password)
await page.click('button[type=submit]')
await page.waitForTimeout(2500)
console.log(`[${mode}] 登录后 URL =`, page.url())

// ── 详情页：2026年第33号（330 条）──
await page.goto(BASE + '/announce/announcement_gb/' + encodeURIComponent('2026年第33号'), { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.p-datatable-tbody tr', { timeout: 30000 })
await page.waitForTimeout(3000)

const count = async () => page.locator('.p-datatable-tbody tr').count()
const footer = async () => ((await page.locator('.table-load-footer').textContent()) || '').replace(/\s+/g, ' ').trim()

console.log(`[${mode}] 首屏行数 =`, await count(), '| footer =', await footer())
const paginatedCalls = paginatedRequests.length
const liteCalls = liteRequests.length
console.log(`[${mode}] 首屏后 Network：/records 请求 =`, paginatedCalls, '| /lite 请求 =', liteCalls)
if (mode === 'paginated') {
  console.log('[分页模式] 首屏应已请求 page=1 →', paginatedCalls >= 1 ? '✅' : '❌')
} else {
  console.log('[降级模式] 首屏应只请求 /lite 且无 /records →', paginatedCalls === 0 && liteCalls >= 1 ? '✅' : '❌')
}

// ── 滚动到页面底部（真实滚动容器为 window/body）──
let sawButton = false
for (let i = 0; i < 10; i++) {
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight)
    document.documentElement.scrollTop = document.documentElement.scrollHeight
  })
  await page.waitForTimeout(1000)
  const rows = await count()
  const f = await footer()
  console.log(`[${mode}] 滚动 ${i + 1}：行数 =`, rows, '| footer =', f)
  if ((await page.locator('.load-all-btn').count()) > 0) {
    sawButton = true
    console.log(`[${mode}] → 出现"加载剩余"按钮`)
    break
  }
  if (rows >= 330) break
}

// ── 点击"加载剩余" → 全量 ──
const btn = page.locator('.load-all-btn')
if ((await btn.count()) > 0) {
  await btn.click()
  await page.waitForTimeout(1500)
  console.log(`[${mode}] 加载剩余后：行数 =`, await count(), '| footer =', await footer())
}

// ── 汇总断言 ──
const finalRows = await count()
const finalFooter = await footer()
const pass = finalRows >= 330 && finalFooter.includes('已显示全部 330 条标准')
console.log(`[${mode}] 最终行数 =`, finalRows)
console.log(`[${mode}] 最终 footer =`, finalFooter)
console.log(`[${mode}] 分页请求总数 =`, paginatedRequests.length)
console.log(`[${mode}] 页面错误 =`, JSON.stringify(errors.slice(0, 3)))
console.log(`[${mode}] RESULT:`, pass ? 'PASS ✅' : 'FAIL ❌')

await page.screenshot({ path: `e2e/announce-pagination-${mode}.png` })
await browser.close()
process.exit(pass ? 0 : 1)
