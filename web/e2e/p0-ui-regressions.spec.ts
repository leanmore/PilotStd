// P0 前端视觉回归（2026-11-24）—— 锁定 4 项修复中 3 项**样式契约**
//
// 为什么用 e2e 而不用 vitest：这 3 项都是 scoped CSS 的**计算样式**，
// jsdom 不应用样式表，只有真实浏览器能断言。
//
// 断言全部**数据无关**（CI 的后端是空库也能跑）：
//   1) 日期控件：外层一层边框，下拉按钮不再自画边框/底色，× 与日历图标同色同尺寸
//   2) Select：中文文字墨迹垂直居中（容器中心 ±2px）
//   3) 侧栏：sticky 固定、高度=视口、滚到底仍可见
//
// 账号：CI 由 workflow 种 `admin`/`Admin@123`；本地可用 E2E_USERNAME/E2E_PASSWORD 覆盖。
import { test, expect, type Page } from '@playwright/test'

const USERNAME = process.env.E2E_USERNAME || 'admin'
const PASSWORD = process.env.E2E_PASSWORD || 'Admin@123'

async function login(page: Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input[name="username"]', { timeout: 20000 })
  await page.fill('input[name="username"]', USERNAME)
  await page.fill('input[name="password"]', PASSWORD)
  await page.click('button[type="submit"]')
  await page.waitForTimeout(2500)
}

test.describe('P0 UI 视觉回归', () => {
  test('日期控件：单层边框，清除/日历图标同色同尺寸', async ({ page }) => {
    await login(page)
    await page.goto('/announce', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)

    const dp = page.locator('.p-datepicker').first()
    await expect(dp).toBeVisible()

    const m = await dp.evaluate((root) => {
      const clear = root.querySelector('.p-datepicker-clear-icon')
      const drop = root.querySelector('.p-datepicker-dropdown')
      const dropSvg = drop?.querySelector('svg')
      const rect = (el: Element | null | undefined) =>
        el ? el.getBoundingClientRect() : null
      const cs = (el: Element | null | undefined) => (el ? getComputedStyle(el) : null)
      return {
        rootBorderWidth: cs(root)!.borderTopWidth,
        clearColor: cs(clear)!.color,
        clearRect: rect(clear),
        dropBorderWidth: cs(drop)!.borderTopWidth,
        dropBackground: cs(drop)!.backgroundColor,
        dropColor: cs(drop)!.color,
        dropSvgRect: rect(dropSvg),
      }
    })

    // 外层承担唯一一层边框
    expect(m.rootBorderWidth).toBe('1px')
    // 下拉按钮不再自画边框/底色（原缺陷：与 input 边框叠加成"胶囊"）
    expect(m.dropBorderWidth).toBe('0px')
    expect(m.dropBackground).toBe('rgba(0, 0, 0, 0)')
    // 两枚图标同色
    expect(m.clearColor).toBe(m.dropColor)
    // 两枚图标同尺寸
    expect(m.clearRect!.width).toBeCloseTo(m.dropSvgRect!.width, 0)
    expect(m.clearRect!.height).toBeCloseTo(m.dropSvgRect!.height, 0)
  })

  test('Select：中文文字垂直居中（墨迹中心与容器中心偏差 ≤2px）', async ({ page }) => {
    await login(page)
    await page.goto('/settings', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2500)

    const selects = page.locator('.p-select')
    const count = await selects.count()
    test.skip(count === 0, '当前环境设置页没有 Select（数据/权限差异）')

    for (let i = 0; i < Math.min(count, 3); i++) {
      const offset = await selects.nth(i).evaluate((sel) => {
        const label = sel.querySelector('.p-select-label')
        if (!label) return null
        const selRect = sel.getBoundingClientRect()
        const range = document.createRange()
        range.selectNodeContents(label)
        const inkRect = range.getBoundingClientRect()
        if (!inkRect.height) return null
        return inkRect.top + inkRect.height / 2 - (selRect.top + selRect.height / 2)
      })
      if (offset === null) continue
      // 原缺陷约 -10px（文字贴顶）；修复后应接近 0
      expect(Math.abs(offset), `第 ${i} 个 Select 文字垂直偏移`).toBeLessThanOrEqual(2)
    }
  })

  test('侧栏：sticky 固定且滚到底仍可见', async ({ page }) => {
    await login(page)
    await page.goto('/settings', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2500)

    const sidebar = page.locator('.sidebar').first()
    test.skip((await sidebar.count()) === 0, '当前视口为移动端布局（侧栏不渲染）')

    const before = await sidebar.evaluate((el) => {
      const cs = getComputedStyle(el)
      return { position: cs.position, height: el.getBoundingClientRect().height }
    })
    expect(before.position).toBe('sticky')
    // 原缺陷：被 flex stretch 拉成整页高（可达数千 px）
    const viewportH = page.viewportSize()!.height
    expect(before.height).toBeLessThanOrEqual(viewportH + 1)

    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await page.waitForTimeout(800)

    const visible = await sidebar.evaluate((el) => {
      const r = el.getBoundingClientRect()
      return r.top >= -1 && r.top < window.innerHeight
    })
    expect(visible, '滚动到底后侧栏应仍在视口内').toBe(true)
  })
})
