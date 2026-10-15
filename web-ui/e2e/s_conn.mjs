import { launch, audit, mock, URL } from './lib.mjs';
import { ui } from './helpers.mjs';
const out = m => console.log(m);
// 1. long names + audit
{ const { browser, page } = await launch();
  await mock('/__mock/up', {}); await mock('/__mock/config', { tracks: 30, longNames: true, empty: false, latencyMs: 0, failRate: 0 });
  await page.goto(URL); await page.waitForTimeout(1500);
  out('long names home audit ' + JSON.stringify(await audit(page)));
  await page.getByRole('button', { name: /^Play An Extraordinarily/ }).first().tap(); await page.waitForTimeout(800);
  await page.locator('.mini-player [aria-label^="Open player"]').tap(); await page.waitForTimeout(400);
  out('long names full player audit ' + JSON.stringify(await audit(page)));
  await page.screenshot({ path: 'shots/long-full.png' });
  await browser.close(); }
// 2. empty library
{ const { browser, page } = await launch();
  await mock('/__mock/config', { empty: true, longNames: false });
  await page.goto(URL); await page.waitForTimeout(1500);
  out('empty home text: ' + (await page.locator('.home-content').innerText()).replace(/\n+/g, ' | ').slice(0, 300));
  await page.screenshot({ path: 'shots/empty-home.png' });
  await browser.close(); }
// 3. slow command -> does one slow response flip to offline?
{ const { browser, page, logs } = await launch(); const u = ui(page);
  await mock('/__mock/config', { empty: false, tracks: 24, latencyMs: 0 });
  await page.goto(URL); await page.waitForTimeout(1500);
  await page.getByRole('button', { name: /^Play Track 1 by/ }).first().tap(); await page.waitForTimeout(1200);
  out('before slow: ' + await u.conn() + ' ' + await u.playLabel());
  await mock('/__mock/config', { latencyMs: 7000 });
  await page.locator('.mini-player [aria-label="Pause"]').tap(); await page.waitForTimeout(6500);
  out('after slow(7s) pause: conn=' + await u.conn() + ' toast=' + await u.toast() + ' label=' + await u.playLabel());
  await mock('/__mock/config', { latencyMs: 0 }); await page.waitForTimeout(3000);
  out('after latency cleared: conn=' + await u.conn() + ' label=' + await u.playLabel());
  // 4. disconnect mid-playback and recover
  await mock('/__mock/down', {}); await page.waitForTimeout(1500);
  out('down: conn=' + await u.conn() + ' label=' + await u.playLabel());
  await page.locator('.mini-player [aria-label="Play"], .mini-player [aria-label="Pause"]').first().tap().catch(()=>{}); await page.waitForTimeout(400);
  out('tap while down: toast=' + await u.toast());
  await mock('/__mock/up', {}); await page.waitForTimeout(12000);
  out('up again: conn=' + await u.conn() + ' label=' + await u.playLabel());
  out('logs ' + logs.slice(0,4).join(' | '));
  await browser.close(); }
// 5. persistence
{ const { browser, page } = await launch();
  await mock('/__mock/config', { tracks: 24 });
  await page.goto(URL); await page.waitForTimeout(1200);
  await page.getByRole('button', { name: 'Library', exact: true }).last().tap();
  await page.getByRole('button', { name: 'Create playlist' }).tap();
  await page.getByLabel('Playlist name').fill('Stress mix');
  await page.locator('.selectable-track').nth(0).tap(); await page.locator('.selectable-track').nth(1).tap();
  await page.getByRole('button', { name: 'Create playlist' }).last().tap(); await page.waitForTimeout(500);
  await page.reload(); await page.waitForTimeout(1200);
  await page.getByRole('button', { name: 'Library', exact: true }).last().tap();
  out('after reload playlists include Stress mix: ' + (await page.locator('.library-list').innerText()).includes('Stress mix'));
  await browser.close(); }
process.exit(0);
