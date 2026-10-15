import { Home, Library, Search } from 'lucide-react';

export type Tab = 'home' | 'search' | 'library';

const tabs = [
  { id: 'home' as const, label: 'Home', Icon: Home },
  { id: 'search' as const, label: 'Search', Icon: Search },
  { id: 'library' as const, label: 'Library', Icon: Library },
];

interface BottomNavProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export function BottomNav({ activeTab, onTabChange }: BottomNavProps) {
  return (
    <nav aria-label="Mobile navigation" className="bottom-nav absolute bottom-0 left-0 right-0 z-30 border-t border-cream/10 bg-basil-950/90 pb-safe backdrop-blur-xl">
      <div className="flex h-[68px] items-stretch justify-around">
        {tabs.map(({ id, label, Icon }) => {
          const active = activeTab === id;
          return (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              aria-current={active ? 'page' : undefined}
              className="flex flex-1 flex-col items-center justify-center gap-1"
            >
              <Icon
                size={22}
                className={active ? 'text-pesto' : 'text-sage'}
                strokeWidth={active ? 2.4 : 2}
              />
              <span
                className={`text-[11px] ${active ? 'font-semibold text-pesto' : 'text-sage'}`}
              >
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
