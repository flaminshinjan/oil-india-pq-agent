'use client';
/**
 * Dashboard switcher — a compact dropdown that swaps the analytics pane
 * between domain-specific views (Production, Exploration, HSE, etc.).
 *
 * Lives in the top bar between the brand and the live-ticker block.
 */
import { useEffect, useRef, useState } from 'react';

import { Icon } from './Icon';

export type DomainKey =
  | 'brief'
  | 'production'
  | 'exploration'
  | 'hse'
  | 'hr'
  | 'procurement';

export interface DomainOption {
  key: DomainKey;
  label: string;
  hint: string;
}

export const DOMAIN_OPTIONS: DomainOption[] = [
  { key: 'brief',        label: 'Executive Brief', hint: 'Today’s headline + cross-domain signals' },
  { key: 'production',   label: 'Production',      hint: 'Crude & gas — plan vs achievement' },
  { key: 'exploration',  label: 'Exploration',     hint: 'Drilling, wells, reserves & discoveries' },
  { key: 'hse',          label: 'HSE · Safety', hint: 'LTIFR trend + live PPE event log' },
  { key: 'hr',           label: 'HR · Workforce', hint: 'Headcount, diversity, BRSR labour' },
  { key: 'procurement',  label: 'Procurement',     hint: 'Vendor spend, contracts, payable cycle' },
];

interface Props {
  value: DomainKey;
  onChange: (next: DomainKey) => void;
}

export function DomainSelector({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (popRef.current?.contains(t)) return;
      if (btnRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const active = DOMAIN_OPTIONS.find(o => o.key === value) ?? DOMAIN_OPTIONS[0];

  return (
    <div className="domain-sel">
      <button
        ref={btnRef}
        className={'domain-sel-btn' + (open ? ' is-open' : '')}
        onClick={() => setOpen(v => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Switch dashboard"
      >
        <span className="domain-sel-eyebrow">Dashboard</span>
        <span className="domain-sel-label">{active.label}</span>
        <span className="domain-sel-chev" aria-hidden>
          <Icon name="arrow" size={13} />
        </span>
      </button>
      {open && (
        <div
          ref={popRef}
          className="domain-sel-pop"
          role="listbox"
          aria-label="Choose dashboard"
        >
          {DOMAIN_OPTIONS.map(opt => (
            <button
              key={opt.key}
              className={'domain-sel-opt' + (opt.key === value ? ' is-active' : '')}
              onClick={() => {
                onChange(opt.key);
                setOpen(false);
              }}
              role="option"
              aria-selected={opt.key === value}
            >
              <span className="domain-sel-opt-label">{opt.label}</span>
              <span className="domain-sel-opt-hint">{opt.hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
