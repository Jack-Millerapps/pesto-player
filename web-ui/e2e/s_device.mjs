import { launch, mock, URL } from './lib.mjs';
import { ui } from './helpers.mjs';
const { browser, page, logs } = await launch();
await mock('/__mock/down', {});
await page.goto(URL); await page.waitForTimeout(2500);
const u = ui(page);
console.log('conn:', await u.conn());
await page.getByRole('button', { name: /^Play Carefree by/ }).first().tap(); await page.waitForTimeout(800);
console.log('after tap play:', await u.title(), await u.playLabel(), JSON.stringify(await u.audio()));
// wait for end -> auto advance (12s tracks)
await page.waitForTimeout(12500);
console.log('after track end:', await u.title(), await u.playLabel(), JSON.stringify(await u.audio()));
// rapid next x8
for (let i = 0; i < 8; i++) await page.locator('.mini-player [aria-label="Next track"]').tap({ noWaitAfter: true, timeout: 3000 }).catch(e => console.log('tap fail', e.message.split('\n')[0]));
await page.waitForTimeout(700);
console.log('after 8 nexts:', await u.title(), await u.playLabel(), JSON.stringify(await u.audio()));
// open full, seek, repeat one, wait end
await page.locator('.mini-player [aria-label^="Open player"]').tap();
await page.locator('input[aria-label=Seek]').fill('10'); await page.waitForTimeout(800);
console.log('after seek 10:', JSON.stringify(await u.audio()));
const rep = page.getByRole('button', { name: /^Repeat/ });
await rep.tap(); await rep.tap(); console.log('repeat label:', await rep.getAttribute('aria-label'));
await page.waitForTimeout(3500);
console.log('after end w/ repeat one:', JSON.stringify(await u.audio()), 'title', await page.locator('.player-song-title').textContent());
await rep.tap(); console.log('repeat label:', await rep.getAttribute('aria-label'));
// pause/play spam
const pp = page.locator('.player-transport button.rounded-full, .player-transport [aria-label=Pause], .player-transport [aria-label=Play]').first();
for (let i = 0; i < 11; i++) await page.locator('.player-transport button').nth(2).tap({ timeout: 2000 }).catch(() => {});
await page.waitForTimeout(500);
console.log('after 11 play/pause taps (expect paused):', JSON.stringify(await u.audio()), await page.locator('.player-transport button').nth(2).getAttribute('aria-label'));
// volume
await page.locator('input[aria-label=Volume]').fill('20'); await page.waitForTimeout(600);
console.log('volume el:', await page.evaluate(() => document.querySelector('audio').volume));
console.log('LOGS', logs.join(' | '));
await browser.close(); process.exit(0);
