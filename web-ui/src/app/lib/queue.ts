/** Keep duplicate occurrences and earlier unplayed shuffle entries visible. */
export function visibleQueue<T>(queue: T[], index: number, played: Set<number>, shuffle: boolean): T[] {
  if (!queue[index]) return [];
  if (!shuffle) return queue.slice(index);
  return [queue[index], ...queue.filter((_, i) => i !== index && !played.has(i))];
}

export type RepeatMode = 'off' | 'all' | 'one';
export type Advance = { type: 'play'; index: number; played: Set<number> } | { type: 'stop' };
/** Where the browser queue goes next. Pure so shuffle/repeat edge cases can be tested without a DOM. */
export function advanceIndex(length: number, index: number, played: ReadonlySet<number>, direction: 1 | -1, shuffle: boolean, repeat: RepeatMode, random: () => number = Math.random): Advance {
  if (length === 0) return { type: 'stop' };
  let next = index + direction;
  let seen = new Set(played);
  if (direction === 1 && shuffle && length > 1) {
    let available = Array.from({ length }, (_, i) => i).filter(i => !seen.has(i));
    if (!available.length && repeat === 'all') { seen = new Set([index]); available = Array.from({ length }, (_, i) => i).filter(i => i !== index); }
    next = available.length ? available[Math.floor(random() * available.length)] : length;
  }
  if (next >= length) {
    if (repeat !== 'all') return { type: 'stop' };
    next = 0;
  }
  if (next < 0) next = 0;
  seen.add(next);
  return { type: 'play', index: next, played: seen };
}
