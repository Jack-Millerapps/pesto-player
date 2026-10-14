import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { transform } from 'esbuild';
const source = await readFile(new URL('../src/app/lib/queue.ts', import.meta.url), 'utf8');
const { code } = await transform(source, { loader: 'ts', format: 'esm' });
const { visibleQueue, advanceIndex } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
test('ordered queue keeps the current song and later duplicates', () => assert.deepEqual(visibleQueue(['a','b','a'], 0, new Set([0]), false), ['a','b','a']));
test('shuffling keeps earlier unplayed songs visible', () => assert.deepEqual(visibleQueue(['a','b','c','d'], 2, new Set([1,2]), true), ['c','a','d']));
test('played shuffle entries do not return as upcoming', () => assert.deepEqual(visibleQueue(['a','b','c'], 1, new Set([0,1,2]), true), ['b']));
test('an empty queue stays empty', () => assert.deepEqual(visibleQueue([], 0, new Set(), false), []));
test('a queue past its end has no current song', () => assert.deepEqual(visibleQueue(['a'], 1, new Set(), true), []));

const set = (...n) => new Set(n);
const first = () => 0; // deterministic "random": always the first candidate
test('advance: sequential play moves forward and records the song as played', () => assert.deepEqual(advanceIndex(3, 0, set(0), 1, false, 'off'), { type: 'play', index: 1, played: set(0, 1) }));
test('advance: the end of the queue stops unless repeat-all, which wraps', () => {
  assert.deepEqual(advanceIndex(3, 2, set(2), 1, false, 'off'), { type: 'stop' });
  assert.deepEqual(advanceIndex(3, 2, set(2), 1, false, 'all'), { type: 'play', index: 0, played: set(2, 0) });
});
test('advance: previous clamps at the first song instead of going negative', () => assert.deepEqual(advanceIndex(3, 0, set(0), -1, false, 'off'), { type: 'play', index: 0, played: set(0) }));
test('advance: an empty queue stops', () => assert.deepEqual(advanceIndex(0, 0, set(), 1, true, 'all'), { type: 'stop' }));
test('advance: shuffle only picks songs not yet played', () => assert.deepEqual(advanceIndex(4, 1, set(0, 1), 1, true, 'off', first), { type: 'play', index: 2, played: set(0, 1, 2) }));
test('advance: shuffle with every song played stops, or reshuffles under repeat-all without repeating the current song', () => {
  assert.deepEqual(advanceIndex(3, 2, set(0, 1, 2), 1, true, 'off', first), { type: 'stop' });
  assert.deepEqual(advanceIndex(3, 2, set(0, 1, 2), 1, true, 'all', first), { type: 'play', index: 0, played: set(2, 0) });
});
test('advance: a one-song queue under shuffle + repeat-all replays that song', () => assert.deepEqual(advanceIndex(1, 0, set(0), 1, true, 'all'), { type: 'play', index: 0, played: set(0) }));
test('advance: does not mutate the played set it was given', () => { const played = set(0); advanceIndex(3, 0, played, 1, false, 'off'); assert.deepEqual([...played], [0]); });
