export const ui = page => ({
  title: () => page.evaluate(() => document.querySelector('.mini-player [aria-label^="Open player"]')?.getAttribute('aria-label') || null),
  playLabel: () => page.evaluate(() => [...document.querySelectorAll('.mini-player button')].map(b => b.getAttribute('aria-label')).find(l => l === 'Play' || l === 'Pause') || null),
  toast: () => page.evaluate(() => document.querySelector('.feedback-notice span')?.textContent || null),
  conn: () => page.evaluate(() => document.querySelector('.device-status-button')?.innerText.replace(/\n/g, ' ') || null),
  audio: () => page.evaluate(() => { const a = document.querySelector('audio'); return a ? { paused: a.paused, t: +a.currentTime.toFixed(1), d: +(a.duration || 0).toFixed(1), src: a.src.split('/').pop(), ended: a.ended } : null; }),
});
