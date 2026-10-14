import { BatteryFull, BatteryLow, BatteryMedium, Leaf } from 'lucide-react';
import { useState } from 'react';
import { DeviceSheet } from './DeviceSheet';
import { usePlayer } from '../player/PlayerProvider';

function BatteryBadge() {
  const { battery } = usePlayer();
  if (!battery) return null;

  const pct = Math.round(battery.percentage);
  const Icon = pct > 60 ? BatteryFull : pct > 25 ? BatteryMedium : BatteryLow;
  const tone = pct > 25 ? 'text-pine' : 'text-red-400';

  return (
    <span className={`flex items-center gap-1 ${tone}`} title={battery.status}>
      <Icon size={16} aria-hidden />
      <span className="text-xs font-medium tabular-nums">{pct}%</span>
    </span>
  );
}

/**
 * Wordmark plus device status: connection dot, and battery when a
 * physical player is connected.
 */
export function AppHeader() {
  const [deviceOpen, setDeviceOpen] = useState(false);
  const { connection } = usePlayer();

  const dot =
    connection === 'online'
      ? 'bg-pesto'
      : connection === 'connecting'
        ? 'bg-pine animate-pulse'
        : 'bg-sage';
  const label =
    connection === 'online' ? 'Player connected' : connection === 'connecting' ? 'Connecting' : 'This device';

  return (
    <div className="app-header">
      <div className="mobile-brand flex items-center gap-1.5">
        <Leaf size={18} className="text-pesto" aria-hidden />
        <span className="font-display text-lg font-bold tracking-tight text-cream">pesto.</span>
      </div>

      <span className="header-caption">YOUR DAILY DOSE OF GOOD SOUND</span>
      <button onClick={() => setDeviceOpen(true)} aria-label="Player connection details" className="device-status-button flex items-center gap-3 rounded-full border border-cream/10 bg-basil-900/80 px-3 py-1.5">
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
          <span className="text-xs font-medium text-sage">{label}</span>
        </span>
        {connection === 'online' && <BatteryBadge />}
      </button>
      {deviceOpen && <DeviceSheet onClose={() => setDeviceOpen(false)} />}
    </div>
  );
}
