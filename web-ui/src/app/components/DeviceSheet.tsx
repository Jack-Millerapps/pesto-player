import { useState } from 'react';
import { Headphones, Leaf, RefreshCw, Smartphone } from 'lucide-react';
import { usePlayer } from '../player/PlayerProvider';
import { Sheet } from './Modal';

export function DeviceSheet({ onClose }: { onClose: () => void }) {
  const { connection, playbackSource, battery, currentTrack, volume, reconnect } = usePlayer();
  const [checking, setChecking] = useState(false);
  const online = connection === 'online';
  return <Sheet title="Your Pesto Player" subtitle="A little player. A lot of soul." onClose={onClose}>
    <div className={`device-card ${online ? 'connected' : ''}`}><span className="device-icon"><Smartphone size={34} /></span><div><h3>{online ? 'Player connected' : connection === 'connecting' ? 'Finding your player…' : 'Play right here'}</h3><p>{online ? 'Your Pesto Player is available for device songs.' : 'Six included songs play directly on this device. Press play and turn it up.'}</p></div></div>
    <dl className="device-details"><div><dt>Listening through</dt><dd>{playbackSource === 'device' ? 'Pesto Player' : 'This device'}</dd></div>{battery && online && <div><dt>Battery</dt><dd>{Math.round(battery.percentage)}% · {battery.status}</dd></div>}<div><dt>Volume</dt><dd>{volume}%</dd></div><div><dt>Current song</dt><dd>{currentTrack?.title || 'Nothing selected yet'}</dd></div></dl>
    {!online && <div className="connection-guide"><h3><Headphones size={18} />Connect your Pesto Player</h3><ol><li>Start Pesto Player on your device.</li><li>Connect this phone to the same Wi-Fi.</li><li>Open your player’s web address in the browser.</li></ol></div>}
    <button className="action-primary reconnect-button" disabled={checking} onClick={async () => { setChecking(true); await reconnect(); setChecking(false); }}><RefreshCw size={17} />{checking ? 'Checking…' : online ? 'Check connection' : 'Try connecting again'}</button>
    <p className="storage-note"><Leaf size={14} />Your personal playlists, likes, and recent activity are saved in this browser.</p><p className="music-credit"><a href="/music/credits.html" target="_blank" rel="noreferrer">Included music &amp; credits ↗</a></p>
  </Sheet>;
}
