// Records the README demo in the demo organisation and prints phase timings (seconds from start).
const { chromium } = require('playwright');
const tok = require(process.env.DEMO_TOKEN_FILE || './demo_tok.json')   // {a: access, r: refresh} for the demo organisation;
const OUT = process.argv[2];
const Q = 'How much sales and use tax revenue did California collect in fiscal year 2023-24, how did it compare with 2022-23, and how much went to the General Fund?';

(async () => {
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
  const t0 = Date.now(); const t = () => ((Date.now() - t0) / 1000).toFixed(1);
  const marks = {};

  await page.goto('http://localhost:4200/documents-hub', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  marks.docs = t();
  await page.waitForTimeout(3000);

  await page.goto('http://localhost:4200/research', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  marks.research = t();
  await page.click('textarea.question-input');
  await page.keyboard.type(Q, { delay: 28 });
  await page.waitForTimeout(500);
  await page.keyboard.press('Enter');
  marks.submit = t();
  await page.waitForSelector('.answer-body', { timeout: 300000 });
  await page.waitForFunction(() => !document.querySelector('.thinking-area'), null, { timeout: 300000 });
  marks.answer = t();
  await page.waitForTimeout(5000);
  marks.end = t();

  await ctx.close(); await browser.close();
  console.log(JSON.stringify(marks));
})().catch(e => { console.error(e); process.exit(1); });
