import { launch, mock, URL } from './lib.mjs';
const { browser, page, logs } = await launch();
await mock('/__mock/config', { tracks: 24 });
await page.goto(URL); await page.waitForTimeout(1500);
const label = () => page.evaluate(() => (document.querySelector('.device-status-button')?.innerText || '').replace(/\n/g,' '));
const kind = () => page.evaluate(() => { const t = document.querySelector('.home-content')?.innerText || ''; return t.includes('Finding your next favorite') ? 'LOADING' : t.includes('Six real songs') ? 'DEMO' : 'DEVICE'; });
console.log('start', await label(), await kind(), JSON.stringify((await mock('/__mock/stats')).sockets));
const s0 = (await mock('/__mock/stats')).byPath;
await mock('/__mock/flap', { ms: 2500 });
const seq = [];
for (let i = 0; i < 40; i++) { await page.waitForTimeout(300); const k = await kind(); if (seq[seq.length-1] !== k) seq.push(k); }
await mock('/__mock/flap', { ms: 0 });
await page.waitForTimeout(2500);
const s1 = (await mock('/__mock/stats')).byPath;
console.log('home states during 12s flap (2.5s drop interval):', seq.join(' > '));
console.log('api requests during flap:', JSON.stringify(Object.fromEntries(Object.keys(s1).map(k => [k, s1[k] - (s0[k]||0)]).filter(([k,v]) => v))));
console.log('end', await label(), await kind());
console.log(logs.join('\n'));
await browser.close();
