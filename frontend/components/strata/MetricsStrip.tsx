'use client';
import { useState } from 'react';
import { Icon } from './Icon';

export interface Metric {
  id: string;
  label: string;
  value: string;
  unit: string;
  note: string;
  amber?: boolean;
}

interface Props {
  metrics: Metric[];
  peek: string;          // "Crude, gas, reserves & safety — all current"
}

export function MetricsStrip({ metrics, peek }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <section className="metrics anim" style={{ animationDelay: '.05s' }}>
      <button className="metrics-bar" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <span className="eyebrow">Key metrics</span>
        <span className="metrics-peek">
          {open ? 'Tap any metric to open its source' : peek}
        </span>
        <div className={'metrics-chev' + (open ? ' is-open' : '')}>
          <Icon name="chevron" size={16} />
        </div>
      </button>
      {open && (
        <div className="metrics-panel">
          <div className="metrics-grid">
            {metrics.map(m => (
              <div className={'metric' + (m.amber ? ' metric-amber' : '')} key={m.id}>
                <span className="metric-label">{m.label}</span>
                <span className="metric-val serif num">
                  {m.value}
                  <span className="metric-unit">{m.unit}</span>
                </span>
                <span className="metric-note">
                  {m.amber && <span className="amber-dot" />}
                  {m.note}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
