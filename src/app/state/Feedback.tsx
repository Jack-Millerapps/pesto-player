import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react';
import { Info, X } from 'lucide-react';

type Notice = { message: string; id: number };
const FeedbackContext = createContext<{ notice: Notice | null; notify: (message: string) => void; dismiss: () => void } | null>(null);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState<Notice | null>(null);
  const notify = useCallback((message: string) => setNotice({ message, id: Date.now() }), []);
  const dismiss = useCallback(() => setNotice(null), []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(dismiss, 4500);
    return () => window.clearTimeout(timer);
  }, [notice, dismiss]);
  return <FeedbackContext.Provider value={{ notice, notify, dismiss }}>{children}<FeedbackNotice /></FeedbackContext.Provider>;
}

export function useFeedback() {
  const context = useContext(FeedbackContext);
  if (!context) throw new Error('FeedbackProvider is required');
  return context;
}

export function FeedbackNotice() {
  const { notice, dismiss } = useFeedback();
  return <div className="feedback-region" role="status" aria-live="polite" aria-atomic="true">
    {notice && <div className="feedback-notice"><Info size={18} aria-hidden /><span>{notice.message}</span><button onClick={dismiss} aria-label="Dismiss message"><X size={16} /></button></div>}
  </div>;
}
