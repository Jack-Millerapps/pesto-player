import { ReactNode, useEffect, useRef, useState } from 'react';

/**
 * Renders a long list a page at a time: the first `step` items immediately, more as the user
 * scrolls near the end. A 1,500-song list as 1,500 mounted rows cost ~1.1 s to open at 6x CPU
 * slowdown and ~25k DOM nodes; this keeps the DOM to a few dozen rows.
 */
export function Incremental<T>({ items, render, step = 50 }: { items: readonly T[]; render: (item: T, index: number) => ReactNode; step?: number }) {
  const [count, setCount] = useState(step);
  const sentinel = useRef<HTMLDivElement>(null);
  // A different list (new search, another collection) starts from the top again.
  const first = items[0];
  useEffect(() => setCount(step), [items.length, first, step]);
  const more = count < items.length;
  useEffect(() => {
    const node = sentinel.current;
    if (!more || !node) return;
    if (typeof IntersectionObserver === 'undefined') { setCount(items.length); return; }
    // Re-created after every page so a sentinel that is still on screen fires again.
    const observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) setCount(c => c + step); }, { rootMargin: '400px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [more, count, items.length, step]);
  return <>{items.slice(0, count).map(render)}{more && <div ref={sentinel} aria-hidden="true" style={{ height: 1 }} />}</>;
}
