import { launch, audit, mock, URL } from './lib.mjs';
const { browser, page } = await launch();
await mock('/__mock/config', { tracks: 30, longNames: true });
await page.goto(URL); await page.waitForTimeout(1500);
const a = await audit(page); console.log('offscreen', a.offscreen.length, JSON.stringify(a.offscreen.slice(0,3)), 'small', JSON.stringify(a.small));
await mock('/__mock/config', { longNames: false });
process.exit(0);
