import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { transform } from 'esbuild';
const source = await readFile(new URL('../src/app/player/BrowserAudio.ts', import.meta.url), 'utf8');
const { code } = await transform(source, { loader: 'ts', format: 'esm' });
const { BrowserAudio } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
class FakeAudio extends EventTarget {
  src = ''; currentTime = 0; duration = NaN; volume = 1; paused = true; ended = false; readyState = 0;
  load() { this.currentTime = 0; this.duration = NaN; this.ended = false; }
  play() { this.paused = false; this.dispatchEvent(new Event('play')); return Promise.resolve(); }
  pause() { this.paused = true; this.dispatchEvent(new Event('pause')); }
  emit(name) { this.dispatchEvent(new Event(name)); }
}
const track = { id: 'song', audioUrl: '/music/carefree.mp3' };
function setup() {
  const media = new FakeAudio(), states = [], errors = [], ended = [];
  const engine = new BrowserAudio(media, s => states.push(s), () => ended.push(true), e => errors.push(e));
  return { media, states, errors, ended, engine };
}
test('loading a queued song does not autoplay; play and pause use the media element', () => {
  const { engine, media, states } = setup();
  engine.load(track); assert.equal(media.src, track.audioUrl); assert.equal(media.paused, true);
  engine.play(); assert.equal(media.paused, false); assert.equal(states.at(-1).playing, true);
  engine.pause(); assert.equal(media.paused, true); assert.equal(states.at(-1).playing, false);
});
test('duration and progress reflect decoded media events, not a simulated timer', () => {
  const { engine, media, states } = setup();
  engine.play(track); media.duration = 205.14; media.currentTime = 12.4; media.emit('timeupdate');
  assert.equal(states.at(-1).duration, 205.14); assert.equal(states.at(-1).position, 12.4);
  media.emit('waiting'); assert.equal(states.at(-1).loading, true);
  media.emit('playing'); assert.equal(states.at(-1).loading, false);
});
test('seeking waits for valid metadata and clamps to the recording boundaries', () => {
  const { engine, media } = setup(); engine.load(track);
  engine.seek(30); assert.equal(media.currentTime, 0);
  media.duration = 50; engine.seek(100); assert.equal(media.currentTime, 50);
  engine.seek(-1); assert.equal(media.currentTime, 0);
  engine.seek(20); assert.equal(media.currentTime, 20);
});
test('volume changes actual audio volume and stays in bounds', () => {
  const { engine, media } = setup(); engine.volume(42); assert.equal(media.volume, .42);
  engine.volume(200); assert.equal(media.volume, 1); engine.volume(-2); assert.equal(media.volume, 0);
});
test('a real ended event advances once; cleanup stops playback and removes callbacks', () => {
  const { engine, media, ended, states } = setup(); engine.play(track);
  media.ended = true; media.emit('ended'); assert.equal(ended.length, 1); assert.equal(states.at(-1).playing, false);
  const count = states.length; engine.dispose(); media.emit('ended'); media.emit('timeupdate');
  assert.equal(media.paused, true); assert.equal(media.src, ''); assert.equal(ended.length, 1); assert.equal(states.length, count);
});
test('blocked autoplay produces an actionable error rather than pretending to play', async () => {
  const { engine, media, errors, states } = setup();
  media.play = () => Promise.reject(Object.assign(new Error(), { name: 'NotAllowedError' }));
  engine.play(track); await Promise.resolve();
  assert.match(errors[0], /Tap Play/); assert.equal(states.at(-1).playing, false);
});
test('a superseded play rejection cannot report an error for the next song', async () => {
  const { engine, media, errors } = setup(); let reject;
  media.play = () => new Promise((_, fail) => { reject = fail; }); engine.play(track);
  engine.load({ id: 'next', audioUrl: '/music/cipher.mp3' }); reject(new Error('old request'));
  await Promise.resolve(); assert.deepEqual(errors, []); assert.equal(media.src, '/music/cipher.mp3');
});
test('a failed file pauses playback and reports the loading error', () => {
  const { engine, media, errors, states } = setup(); engine.play(track); media.emit('error');
  assert.equal(media.paused, true); assert.match(errors[0], /couldn’t load/); assert.equal(states.at(-1).loading, false);
});
