/** Keep duplicate occurrences and earlier unplayed shuffle entries visible. */
export function visibleQueue<T>(queue: T[], index: number, played: Set<number>, shuffle: boolean): T[] {
  if (!queue[index]) return [];
  if (!shuffle) return queue.slice(index);
  return [queue[index], ...queue.filter((_, i) => i !== index && !played.has(i))];
}
