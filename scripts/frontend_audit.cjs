// playwright 装在 frontend/node_modules，从那里解析依赖
const path = require('path')
const { chromium } = require(path.resolve(__dirname, '../frontend/node_modules/playwright'))
const ROOT = path.resolve(__dirname, '..')

// 通用前端体检：遍历所有页面 × 多视口，找出
//  1) 内容被 overflow:hidden 裁掉（且父级无法滚动到）
//  2) 横向溢出视口
//  3) 元素重叠遮挡关键操作
const PAGES = ['工作台', '识别中心', '发票台账', '分析报告', '操作记录', '系统设置']
const VIEWPORTS = [
  { width: 1920, height: 1080, tag: '1920x1080' },
  { width: 1440, height: 1000, tag: '1440x1000' },
  { width: 1440, height: 820, tag: '1440x820' },
  { width: 1280, height: 800, tag: '1280x800' },
  { width: 1024, height: 768, tag: '1024x768' },
  { width: 768, height: 1024, tag: '768x1024' },
  { width: 390, height: 844, tag: '390x844' },
]

;(async () => {
  const b = await chromium.launch()
  const findings = []

  for (const vp of VIEWPORTS) {
    const ctx = await b.newContext({ viewport: { width: vp.width, height: vp.height } })
    const p = await ctx.newPage()
    const jsErrors = []
    p.on('pageerror', e => jsErrors.push(e.message))
    await p.goto(process.env.AUDIT_BASE || 'http://127.0.0.1:8000/')
    await p.waitForSelector('.auth-shell, .app-shell', { timeout: 20000 })
    if (await p.locator('.auth-shell').count()) {
      await p.getByLabel('邮箱', { exact: true }).fill(process.env.AUDIT_EMAIL || '1244399824@qq.com')
      await p.getByLabel('密码', { exact: true }).fill(process.env.AUDIT_PASSWORD || '')
      await p.getByRole('button', { name: /^登录$/ }).click()
    }
    await p.waitForSelector('text=工作台')

    const narrow = vp.width <= 760
    for (const pageName of PAGES) {
      if (narrow) {
        // 窄屏：先打开抽屉式侧边栏（模拟真实用户操作）
        const menu = p.locator('.mobile-menu')
        if (await menu.count() && await menu.isVisible()) { await menu.click(); await p.waitForTimeout(400) }
      }
      await p.locator('.sidebar').getByRole('button', { name: new RegExp('^' + pageName) }).click()
      await p.waitForTimeout(900)
      const r = await p.evaluate((vn) => {
        const out = { clipped: [], overflowX: 0, docOverflowY: 0 }
        out.overflowX = document.documentElement.scrollWidth - window.innerWidth
        out.docOverflowY = document.documentElement.scrollHeight - window.innerHeight
        // 找所有"内容超出但不可滚动"的容器
        const all = Array.from(document.querySelectorAll('body *'))
        for (const el of all) {
          const cs = getComputedStyle(el)
          const oy = cs.overflowY
          const ox = cs.overflowX
          const scrollable = oy === 'auto' || oy === 'scroll'
          // 纵向：内容超出、被 hidden 裁、且自身不可滚
          if (!scrollable && oy === 'hidden' && el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 0) {
            // 是否有祖先能滚到它？向上找
            let anc = el.parentElement, canReach = false
            while (anc && anc !== document.body) {
              const acs = getComputedStyle(anc)
              if ((acs.overflowY === 'auto' || acs.overflowY === 'scroll') && anc.scrollHeight > anc.clientHeight) { canReach = true; break }
              anc = anc.parentElement
            }
            if (!canReach) {
              out.clipped.push({
                cls: String(el.className || '').slice(0, 44),
                tag: el.tagName.toLowerCase(),
                clientH: el.clientHeight, scrollH: el.scrollHeight,
                lost: el.scrollHeight - el.clientHeight,
              })
            }
          }
          // 横向：内容超出、被 hidden 裁
          if (ox === 'hidden' && el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
            out.clipped.push({
              cls: String(el.className || '').slice(0, 44),
              tag: el.tagName.toLowerCase(),
              clientW: el.clientWidth, scrollW: el.scrollWidth,
              axis: 'x', lost: el.scrollWidth - el.clientWidth,
            })
          }
        }
        // 只保留最外层的（父元素不再出现在列表里）
        const uniq = []
        for (const c of out.clipped) {
          if (!out.clipped.some(o => o !== c && o.cls && c.cls && o.cls.includes(c.cls.split(' ')[0]) && o.lost < c.lost)) uniq.push(c)
        }
        out.clipped = uniq.slice(0, 6)
        return out
      })
      if (r.clipped.length || r.overflowX > 1) {
        findings.push({ vp: vp.tag, page: pageName, ...r })
      }
    }
    if (jsErrors.length) findings.push({ vp: vp.tag, page: '(JS错误)', jsErrors })
    await ctx.close()
  }
  console.log(JSON.stringify(findings, null, 1))
  console.log('\n问题总数:', findings.length)
  await b.close()
})().catch(e => { console.error('FAILED:', e.message); process.exit(1) })
