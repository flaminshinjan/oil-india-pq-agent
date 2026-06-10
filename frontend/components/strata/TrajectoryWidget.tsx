'use client';
/**
 * Strategic targets surface — 4 MMT crude, 5 BCM gas, 100 wells.
 * Reads /api/os/targets, which derives everything from the canonical
 * Excels — nothing here is hardcoded.
 */
import { useEffect, useState } from 'react';

export interface Target {
  id: string;
  label: string;
  unit: string;
  actual: number;
  target: number;
  pct: number;          // 0..1+
  fy: string;
  note: string;
  amber?: boolean;
  in_progress?: number;
  fy_target?: number;
  trend?: { fy: string; value: number | null }[];
}

export function TrajectoryWidget() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/os/targets')
      .then(r => r.json())
      .then(d => {
        if (Array.isArray(d.targets)) setTargets(d.targets);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading || targets.length === 0) return null;

  return (
    <section className="targets anim" style={{ animationDelay: '.08s' }}>
      <div className="targets-rule">
        <span className="eyebrow">Strategic targets</span>
        <span className="targets-count">{targets.length} goals on horizon</span>
      </div>
      <div className="targets-grid">
        {targets.map(t => <TargetCard key={t.id} t={t} />)}
      </div>
    </section>
  );
}

function TargetCard({ t }: { t: Target }) {
  const pct = Math.max(0, Math.min(1, t.pct));
  const pctLabel = Math.round(t.pct * 100);
  const gap = t.target - t.actual;
  return (
    <article className={'target-card' + (t.amber ? ' is-amber' : '')}>
      <div className="target-head">
        <span className="target-label">{t.label}</span>
        <span className="target-fy num">{t.fy}</span>
      </div>
      <div className="target-num">
        <span className="serif target-actual num">
          {typeof t.actual === 'number' && t.actual >= 100
            ? t.actual.toLocaleString()
            : t.actual}
        </span>
        <span className="target-of">of</span>
        <span className="serif target-target num">{t.target}</span>
        <span className="target-unit">{t.unit}</span>
      </div>
      <div className="target-bar" aria-hidden>
        <span className="target-bar-fill" style={{ width: `${pct * 100}%` }} />
        <span className="target-bar-tick" style={{ left: '100%' }} />
      </div>
      <div className="target-foot">
        <span className="target-pct num">{pctLabel}% of goal</span>
        <span className="target-gap">
          {gap > 0 ? `${gap.toFixed(t.unit === 'wells' ? 0 : 2)} ${t.unit} to go` : 'Goal met'}
        </span>
      </div>
      <p className="target-note">{t.note}</p>
    </article>
  );
}
