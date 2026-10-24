// Analytics demo: spreadsheet question → table → Visualize → chart. Prints phase times from video start.
const { chromium } = require('playwright');
const tok = require(process.env.DEMO_TOKEN_FILE || './demo_tok.json')   // {a: access, r: refresh} for the demo organisation;
const OUT = process.argv[2];
const Q = 'Show total sales by region for 2024';

(async () => {
  const t0 = Date.now(); const t = () => +((Date.now() - t0) / 1000).toFixed(1);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: 'light',
    recordVideo: { dir: OUT, size: { width: 1280, height: 800 } } });
  await ctx.addInitScript(([a, r]) => {
    localStorage.setItem('udv_access_token', a);
    localStorage.setItem('udv_refresh_token', r);
    localStorage.setItem('udv_user', JSON.stringify({ id: 2, username: 'demo_reviewer', full_name: 'Demo Reviewer', role: 'admin', avatar_color: '#1570ef', language: 'en' }));
    localStorage.setItem('udv_vision_tip', '1');
    localStorage.setItem('udv.research.web', '0');
  }, [tok.a, tok.r]);
  const page = await ctx.newPage();
  const m = { start: t() };
  await page.goto('http://localhost:4200/research', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  m.ready = t();
  await page.click('textarea.question-input');
  await page.keyboard.type(Q, { delay: 45 });
  await page.waitForTimeout(400);
  await page.keyboard.press('Enter');
  m.submit = t();
  await page.waitForSelector('.answer-body', { timeout: 300000 });
  await page.waitForFunction(() => !document.querySelector('.thinking-area'), null, { timeout: 300000 });
  m.answer = t();
  await page.waitForTimeout(3500);
  m.hasViz = await page.locator('.viz-cta-btn').count();
  if (m.hasViz) {
    await page.locator('.viz-cta-btn').click();
  } else {
    await page.locator('.viz-action-btn').click({ trial: false }).catch(() => {});
  }
  m.click = t();
  await page.waitForTimeout(6000);
  m.url = page.url();
  m.end = t();
  await ctx.close(); await browser.close();
  console.log(JSON.stringify(m));
})().catch(e => { console.error(e); process.exit(1); });
