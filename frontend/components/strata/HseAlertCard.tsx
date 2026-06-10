'use client';
/**
 * HSE / PPE emergency card — sits prominently above The Brief.
 *
 * Pulls the latest HIGH-severity HSE signal from /api/os/signals?agent=hse.
 * If no live event exists, shows the "all clear" empty state. Click anywhere
 * to drill into the HSE signal detail (uses the same Drilldown overlay).
 */
import { useEffect, useState } from 'react';

import { Icon } from './Icon';

interface Signal {
  id: number;
  agent: string;
  severity: 'info' | 'low' | 'med' | 'high' | 'critical';
  title: string;
  body: string;
  ts: number;
  metric: Record<string, unknown> | null;
}

interface Props {
  /** Open the drilldown for this signal (the page passes the same handler
   *  used by the brief cards). */
  onOpen?: (signalId: number) => void;
  /** Days since last lost-time injury, for the "all clear" stat row. */
  ltiDays?: number;
}

const SEVERITY_RANK: Record<Signal['severity'], number> = {
  critical: 4, high: 3, med: 2, low: 1, info: 0,
};

export function HseAlertCard({ onOpen, ltiDays }: Props) {
  const [topSignal, setTopSignal] = useState<Signal | null>(null);
  const [allSignals, setAllSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/os/signals?agent=hse&limit=10')
      .then(r => r.json())
      .then(d => {
        if (cancelled) return;
        const sigs: Signal[] = Array.isArray(d.signals) ? d.signals : [];
        sigs.sort(
          (a, b) =>
            (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0) ||
            b.ts - a.ts,
        );
        setAllSignals(sigs);
        setTopSignal(sigs[0] ?? null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
    return () => { cancelled = true; };
  }, []);

  if (loading) return null;

  // No incidents → "all clear" stat strip.
  if (!topSignal) {
    return (
      <section className="hse-card hse-card-clear anim" style={{ animationDelay: '.08s' }}>
        <span className="hse-icon">
          <Icon name="check" size={18} />
        </span>
        <div className="hse-card-body">
          <div className="hse-card-eyebrow">HSE · Safety</div>
          <div className="hse-card-title">
            No active safety flags. {ltiDays ? `${ltiDays} days since the last LTI.` : ''}
          </div>
        </div>
      </section>
    );
  }

  // Visual treatment by severity — high/critical render the "amber alert"
  // card; med/low are quieter but still visible.
  const sev = topSignal.severity;
  const isAlert = sev === 'high' || sev === 'critical';

  // Pull site / event-type from the structured metric if present.
  const metric = (topSignal.metric ?? {}) as Record<string, unknown>;
  const site = typeof metric.site === 'string' ? metric.site : null;
  const eventType = typeof metric.type === 'string' ? metric.type : null;
  const minsAgo = typeof metric.minutes_ago === 'number' ? metric.minutes_ago : null;

  return (
    <section
      className={'hse-card anim' + (isAlert ? ' hse-card-alert' : '')}
      style={{ animationDelay: '.08s' }}
      onClick={() => onOpen?.(topSignal.id)}
      role="button"
      tabIndex={0}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen?.(topSignal.id);
        }
      }}
    >
      <span className="hse-icon">
        <span className="hse-pulse" />
        <span className="hse-icon-glyph">!</span>
      </span>

      <div className="hse-card-body">
        <div className="hse-card-eyebrow">
          HSE · Safety alert
          {site && <span className="hse-card-sep">·</span>}
          {site && <span className="hse-card-site">{site}</span>}
          {minsAgo !== null && minsAgo < 60 * 12 && (
            <>
              <span className="hse-card-sep">·</span>
              <span className="hse-card-time">
                {minsAgo < 60 ? `${minsAgo} min ago` : `${Math.floor(minsAgo / 60)}h ago`}
              </span>
            </>
          )}
        </div>
        <div className="hse-card-title">{topSignal.title}</div>
        <div className="hse-card-meta">
          {allSignals.length > 1 && (
            <span>{allSignals.length} open signals from the HSE agent today</span>
          )}
          {ltiDays && (
            <span className="hse-card-lti">{ltiDays} days since last LTI</span>
          )}
        </div>
      </div>

      <div className="hse-card-arr" aria-hidden>
        <Icon name="arrow" size={16} />
      </div>
    </section>
  );
}
