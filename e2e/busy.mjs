import { launch, mock, URL } from './lib.mjs';
const slow = +process.env.SLOW || 6;
const { browser, ctx, page } = await launch();
await mock('/__mock/config', { tracks: +process.env.N || 1500 });
const cdp = await ctx.newCDPSession(page);
await cdp.send('Performance.enable'); await cdp.send('Emulation.setCPUThrottlingRate', { rate: slow });
await page.goto(URL); await page.getByRole('button', { name: /All \d+ songs/ }).tap();
await page.locator('.collection-tracks .track-row > button').first().tap(); await page.waitForTimeout(1500);
const run = async (label) => { const a = await cdp.send('Performance.getMetrics'); await page.waitForTimeout(4000); const b = await cdp.send('Performance.getMetrics'); const d = k => (b.metrics.find(x=>x.name===k).value - a.metrics.find(x=>x.name===k).value).toFixed(2); console.log(label, 'busy', d('TaskDuration'), 'script', d('ScriptDuration'), 'layout', d('LayoutDuration'), 'style', d('RecalcStyleDuration'), 'layouts', d('LayoutCount')); };
await run('baseline playing');
if (process.env.CSS) { await page.addStyleTag({ content: process.env.CSS }); await run('with css: ' + process.env.CSS); }
await browser.close();
