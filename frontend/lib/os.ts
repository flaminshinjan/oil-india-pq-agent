/* Wire types + a fetch helper for the Atlas OS endpoints. */

export type Severity = 'info' | 'low' | 'med' | 'high' | 'critical';

export interface Ref {
  filename?: string;
  source?: string;
  section?: string;
}

export interface Signal {
  id: number;
  agent: string;
  severity: Severity;
  title: string;
  body: string;
  refs: Ref[];
  metric: Record<string, unknown> | null;
  ts: number;
  status: 'open' | 'acked' | 'resolved';
}

export interface Headline {
  title: string;
  body: string;
  refs: Ref[];
  metric: Record<string, unknown> | null;
  linked_signal_ids?: (number | null)[];
}

export interface Brief {
  headline: Headline;
  signals: Signal[];
  refreshed_at: number;
}

export async function getBrief(refresh = false): Promise<Brief> {
  const r = await fetch(`/api/os/brief${refresh ? '?refresh=true' : ''}`);
  if (!r.ok) throw new Error(`brief: HTTP ${r.status}`);
  return r.json();
}

export async function refreshSignals(): Promise<{ ok: boolean; count: number }> {
  const r = await fetch('/api/os/refresh', { method: 'POST' });
  if (!r.ok) throw new Error(`refresh: HTTP ${r.status}`);
  return r.json();
}

export async function listSignals(agent?: string): Promise<{ signals: Signal[]; count: number }> {
  const r = await fetch(`/api/os/signals${agent ? `?agent=${encodeURIComponent(agent)}` : ''}`);
  if (!r.ok) throw new Error(`signals: HTTP ${r.status}`);
  return r.json();
}

export const AGENT_LABELS: Record<string, string> = {
  production: 'Production & Reserves',
  drilling: 'Drilling & Project',
  hse: 'HSE / Safety',
  procurement: 'Procurement',
  workforce: 'Workforce',
  pq: 'PQ Drafting',
};

export const AGENT_HUES: Record<string, string> = {
  production: '#5fd1a7',     // teal-green
  drilling:   '#f5a85a',     // amber
  hse:        '#ef6f6f',     // red
  procurement:'#7faaff',     // blue
  workforce:  '#c39df5',     // violet
  pq:         '#9ce8a8',     // light green
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'CRITICAL',
  high: 'HIGH',
  med: 'MED',
  low: 'LOW',
  info: 'INFO',
};
