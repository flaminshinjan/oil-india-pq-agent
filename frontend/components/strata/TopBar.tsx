'use client';
/**
 * Two-block bar.
 *
 *   [ brand ]                                [ selector · ticker · FY · date ]
 *
 * Brand sits on the left. Everything live or actionable — the dashboard
 * selector dropdown, the rotating live ticker, the FY, and today's date —
 * is bunched into a single right-aligned block.
 */
import { useEffect, useMemo, useState } from 'react';

import { Icon } from './Icon';

interface Props {
  dateStr: string;
  onCustomise?: () => void;
  customiseOpen?: boolean;
  /** Click handler for the "share / export" icon. */
  onShare?: () => void;
  /** Mobile-only: opens the chat as a full-screen sheet. */
  onOpenChat?: () => void;
}

interface Signal {
  id: number;
  agent: string;
  severity: 'info' | 'low' | 'med' | 'high' | 'critical';
  title: string;
  ts: number;
}

const AGENT_LABEL: Record<string, string> = {
  production: 'Reserves',
  drilling: 'Drilling',
  hse: 'HSE',
  procurement: 'Procurement',
  workforce: 'Workforce',
  pq: 'Parliamentary',
};

const SEVERITY_RANK: Record<Signal['severity'], number> = {
  critical: 4, high: 3, med: 2, low: 1, info: 0,
};

export function TopBar({
  dateStr, onCustomise, customiseOpen = false, onShare, onOpenChat,
}: Props) {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [tickerIdx, setTickerIdx] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch('/api/os/signals?limit=8')
        .then(r => r.json())
        .then(s => {
          if (cancelled) return;
          if (s && Array.isArray(s.signals)) {
            const sorted = (s.signals as Signal[]).slice().sort(
              (a, b) =>
                (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0) ||
                b.ts - a.ts,
            );
            setSignals(sorted);
          }
        })
        .catch(() => {/* ignore */});
    };
    load();
    const t = setInterval(load, 30_000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  useEffect(() => {
    if (signals.length <= 1) return;
    const t = setInterval(
      () => setTickerIdx(i => (i + 1) % signals.length),
      4_500,
    );
    return () => clearInterval(t);
  }, [signals.length]);

  const active = signals[tickerIdx] ?? null;

  const fyLabel = useMemo(() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    const start = m >= 4 ? y : y - 1;
    return `FY ${start}-${String((start + 1) % 100).padStart(2, '0')}`;
  }, []);

  return (
    <header className="topbar topbar-v3">
      <div className="topbar-v3-in">
        {/* Brand — left */}
        <div className="topbar-brand">
          <div className="brand-mark-v2" aria-hidden>
            <img src="/oil-logo.png" alt="Oil India" className="brand-logo-img" />
          </div>
          <div className="brand-text-v2">
            <div className="brand-name-v2">DIGBY</div>
            <div className="brand-sub-v2">intelligence OS · Oil India</div>
          </div>
        </div>

        {/* Centered live ticker */}
        <div className="topbar-center">
          <div className="topbar-ticker" aria-live="polite">
            <div className="ticker-blip">
              <span className="ticker-blip-dot" />
              <span className="ticker-blip-ring" />
            </div>
            <span className="ticker-label">LIVE</span>
            {active ? (
              <span key={active.id} className="ticker-text">
                <span className={`ticker-sev ticker-sev-${active.severity}`}>
                  {active.severity.toUpperCase()}
                </span>
                <span className="ticker-agent">{AGENT_LABEL[active.agent] ?? active.agent}</span>
                <span className="ticker-sep">·</span>
                <span className="ticker-title">{active.title}</span>
              </span>
            ) : (
              <span className="ticker-text ticker-text-empty">streaming signals…</span>
            )}
          </div>
        </div>

        {/* Right cluster — FY + date + icons */}
        <div className="topbar-right">
          <div className="topbar-fy">
            <span className="topbar-fy-label">FY</span>
            <span className="topbar-fy-val">{fyLabel.replace('FY ', '')}</span>
          </div>

          <div className="topbar-date-v2">
            <span className="date-day">{dateStr.split(',')[0]}</span>
            <span className="date-rest">{dateStr.split(',').slice(1).join(',').trim()}</span>
          </div>

          {onOpenChat && (
            <button
              className="icon-btn icon-btn-chat"
              onClick={onOpenChat}
              aria-label="Open chat"
              title="Open Ask Digby"
            >
              <Icon name="spark" size={16} />
            </button>
          )}

          <button
            className="icon-btn icon-btn-share"
            onClick={onShare ?? (() => window.print())}
            aria-label="Share / export"
            title="Share / export this view (Cmd-P)"
          >
            <Icon name="copy" size={16} />
          </button>

          {onCustomise && (
            <button
              className={'icon-btn' + (customiseOpen ? ' is-on' : '')}
              onClick={onCustomise}
              aria-label="Customise"
              title="Customise"
            >
              <Icon name="sliders" size={17} />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

