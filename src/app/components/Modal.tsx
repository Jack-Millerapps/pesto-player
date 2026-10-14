import { ReactNode, useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { FeedbackNotice } from '../state/Feedback';

/** Native dialogs contain keyboard focus, make the background inert, and support Escape. */
export function Modal({ children, onClose, label, className = '' }: { children: ReactNode; onClose: () => void; label: string; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    dialog?.querySelector<HTMLButtonElement>('button:not([tabindex="-1"])')?.focus();
    return () => { dialog?.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog ref={ref} className={`pesto-dialog ${className}`} aria-label={label} onCancel={event => { event.preventDefault(); onClose(); }}>
    {children}<FeedbackNotice />
  </dialog>;
}
export function Sheet({ children, title, subtitle, onClose, className = '' }: { children: ReactNode; title: string; subtitle?: string; onClose: () => void; className?: string }) {
  return <Modal label={title} onClose={onClose} className={`utility-modal ${className}`}>
    <div className="sheet-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="round-control" onClick={onClose} aria-label="Close"><X size={20} /></button></div>
    {children}
  </Modal>;
}
