import { chromium } from 'playwright-core';
for (const args of [[], ['--mute-audio'], ['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'], ['--disable-features=AudioServiceOutOfProcess'], ['--autoplay-policy=no-user-gesture-required','--disable-audio-output']]) {
  const b = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args });
  const p = await b.newPage(); await p.goto('http://127.0.0.1:5173/');
  const r = await p.evaluate(async () => { const a = new Audio('/music/carefree.mp3'); await a.play().catch(e => 'err ' + e.message); await new Promise(r => setTimeout(r, 2000)); return a.currentTime; });
  console.log(JSON.stringify(args), '->', r); await b.close();
}
process.exit(0);
