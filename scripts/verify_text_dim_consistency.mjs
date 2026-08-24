// 批次5-E组 步骤2：CSS / themes.ts / aura-token-map.ts 三源一致性校验（Node.js）
// 运行：node scripts/verify_text_dim_consistency.mjs
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

// 1. 解析 style.css 的 :root --text-dim（初始默认值 = light 主题）
const css = readFileSync(path.join(root, 'web/src/style.css'), 'utf8')
const cssRootMatch = css.match(/--text-dim:\s*(#[0-9a-fA-F]{6})/)
if (!cssRootMatch) throw new Error('style.css 未找到 --text-dim')
const cssLight = cssRootMatch[1].toLowerCase()

// 2. 解析 themes.ts 四主题 textDim
const ts = readFileSync(path.join(root, 'web/src/config/themes.ts'), 'utf8')
function tsThemeValue(themeId, field) {
  const block = ts.match(new RegExp(`${themeId}:\\s*{[\\s\\S]*?colors:\\s*{[\\s\\S]*?}`))
  if (!block) throw new Error(`themes.ts 未找到主题 ${themeId}`)
  const m = block[0].match(new RegExp(`${field}:\\s*'([^']+)'`))
  return m ? m[1].toLowerCase() : null
}
const tsLight = tsThemeValue('light', 'textDim')
const tsGreen = tsThemeValue('green', 'textDim')
const tsDark = tsThemeValue('dark', 'textDim')
const tsBlue = tsThemeValue('blue', 'textDim')

// 3. 解析 aura-token-map.ts AURA_TEXT_DIM_MAP
const aura = readFileSync(path.join(root, 'web/src/theme/aura-token-map.ts'), 'utf8')
const auraBlock = aura.match(/AURA_TEXT_DIM_MAP[\s\S]*?\{[\s\S]*?\}/)
if (!auraBlock) throw new Error('aura-token-map.ts 未找到 AURA_TEXT_DIM_MAP')
const auraMap = {}
for (const t of ['light', 'dark', 'green', 'blue']) {
  const m = auraBlock[0].match(new RegExp(`${t}:\\s*'([^']+)'`))
  auraMap[t] = m ? m[1].toLowerCase() : null
}

let fail = 0
function check(label, a, b) {
  const ok = a === b
  console.log(`${ok ? '✅' : '❌'} ${label}: ${a} vs ${b}`)
  if (!ok) fail++
}

console.log('== style.css :root（初始默认 = light） ==')
console.log(`   --text-dim: ${cssLight}\n`)
console.log('== themes.ts 四主题 textDim ==')
console.log(`   light: ${tsLight}  green: ${tsGreen}  dark: ${tsDark}  blue: ${tsBlue}\n`)
console.log('== aura-token-map.ts AURA_TEXT_DIM_MAP ==')
console.log(`   light: ${auraMap.light}  green: ${auraMap.green}  dark: ${auraMap.dark}  blue: ${auraMap.blue}\n`)

console.log('== 一致性断言 ==')
check('style.css(:root=light) == themes.light', cssLight, tsLight)
check('themes.light == aura.light', tsLight, auraMap.light)
check('themes.green == aura.green', tsGreen, auraMap.green)
check('themes.dark == aura.dark', tsDark, auraMap.dark)
check('themes.blue == aura.blue', tsBlue, auraMap.blue)
// blue/dark 保持原值 #a3afc2（排除项）
check('dark 保持 #a3afc2', tsDark, '#a3afc2')
check('blue 保持 #a3afc2', tsBlue, '#a3afc2')
// light/green 新值 #445264
check('light 新值 #445264', tsLight, '#445264')
check('green 新值 #445264', tsGreen, '#445264')

console.log(fail === 0 ? '\n✅ ALL CONSISTENT' : `\n❌ ${fail} 处不一致`)
process.exit(fail === 0 ? 0 : 1)
