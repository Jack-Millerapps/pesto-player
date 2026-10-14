import { io } from '../node_modules/socket.io-client/build/esm/index.js';
const s = io(process.argv[2] || 'http://127.0.0.1:5050', { transports: ['websocket','polling'], reconnection: true, reconnectionDelay: 1000, reconnectionDelayMax: 10000, reconnectionAttempts: Infinity });
const t0 = Date.now(); const log = m => console.log(String(Date.now()-t0).padStart(6), m);
s.on('connect', () => log('connect')); s.on('disconnect', r => log('disconnect ' + r)); s.on('connect_error', e => log('connect_error ' + e.message));
setTimeout(() => fetch('http://127.0.0.1:5050/__mock/kick', {method:'POST', body:'{}'}).then(()=>log('kicked')), 1500);
setTimeout(() => process.exit(), 9000);
