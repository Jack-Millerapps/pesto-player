import { launch, mock, URL } from './lib.mjs';
import { ui } from './helpers.mjs';
const { browser, page } = await launch(); const u = ui(page);
await mock('/__mock/up', {}); await mock('/__mock/config', { tracks: 24, latencyMs: 0, failRate: 0, longNames: false });
await page.goto(URL); await page.waitForTimeout(1500);
await mock('/__mock/down', {}); await page.waitForTimeout(2000);
console.log('down', await u.conn());
await mock('/__mock/up', {});
for (let i = 1; i <= 8; i++) { await page.waitForTimeout(4000); console.log(i * 4 + 's after up:', await u.conn()); }
process.exit(0);
