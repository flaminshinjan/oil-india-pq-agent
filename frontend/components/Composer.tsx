'use client';
import { useEffect, useRef, useState } from 'react';

type Props = {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
};

const MIN_ROWS = 1;
const MAX_HEIGHT_PX = 200;

export function Composer({ busy, onSend, onStop }: Props) {
  const [value, setValue] = useState('');
  const ref = useRef<HTMLTextAreaElement | null>(null);

  // Auto-grow textarea up to MAX_HEIGHT_PX.
  useEffect(() => {
    const ta = ref.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const next = Math.min(ta.scrollHeight, MAX_HEIGHT_PX);
    ta.style.height = `${next}px`;
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue('');
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <textarea
          ref={ref}
          placeholder="Ask about Oil India operations, past PQs, or data…"
          value={value}
          rows={MIN_ROWS}
          disabled={busy}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {busy ? (
          <button className="composer-btn composer-btn-stop" onClick={onStop} title="Stop generating">
            <span className="stop-square" />
          </button>
        ) : (
          <button
            className="composer-btn"
            onClick={submit}
            disabled={!value.trim()}
            title="Send (Enter)"
          >
            <ArrowUp />
          </button>
        )}
      </div>
      <div className="footer-hint">
        Answers are grounded in OIL's archive &amp; cite their sources. Press
        <kbd>Enter</kbd> to send, <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line.
      </div>
    </div>
  );
}

function ArrowUp() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  );
}
