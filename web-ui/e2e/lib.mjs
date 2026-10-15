import { chromium } from 'playwright-core';
export const URL = process.env.URL || 'http://127.0.0.1:5173';
export const MOCK = 'http://127.0.0.1:5050';
export async function launch({ w = 320, h = 480, offline = false } = {}) {
  const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--autoplay-policy=no-user-gesture-required', '--disable-audio-output'] });
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, hasTouch: true, isMobile: w < 768, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const logs = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(`${m.type()}: ${m.text()}`); });
  page.on('pageerror', e => logs.push('pageerror: ' + e.message));
  return { browser, ctx, page, logs };
}
export const mock = (path, body) => fetch(MOCK + path, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }).then(r => r.json());
export async function audit(page) {
  return page.evaluate(() => {
    const out = { vw: innerWidth, vh: innerHeight, overflowX: document.documentElement.scrollWidth > innerWidth, small: [], offscreen: [], hscroll: [] };
    const top = [...document.querySelectorAll('dialog[open]')].pop() || document;
    top.querySelectorAll('button, a[href], input, select, textarea, [role=button]').forEach(el => {
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden') return;
      if (el.closest('.pesto-main, .bottom-nav, .mini-player, .app-header') && document.querySelector('dialog[open]') && !el.closest('dialog')) return;
      const name = (el.getAttribute('aria-label') || el.textContent || el.placeholder || '').trim().slice(0, 28);
      if (r.width < 44 || r.height < 44) out.small.push(`${el.tagName.toLowerCase()}[${name}] ${Math.round(r.width)}x${Math.round(r.height)}`);
      if (r.right > innerWidth + 1 || r.left < -1) out.offscreen.push(`${name} L${Math.round(r.left)} R${Math.round(r.right)}`);
    });
    document.querySelectorAll('*').forEach(el => { if (el.scrollWidth > el.clientWidth + 2 && ['visible'].includes(getComputedStyle(el).overflowX) === false && getComputedStyle(el).overflowX === 'hidden' && el.clientWidth > 0 && el.tagName !== 'BODY') { /* clipped text candidates */ } });
    return out;
  });
}
