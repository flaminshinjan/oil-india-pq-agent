'use client';
/**
 * Rich HSE/PPE block injected into the Drilldown overlay.
 *
 * Pulls /api/os/hse/events on mount and renders:
 *   - 4-up stats grid (total / last 24h / sites / avg confidence)
 *   - "By site" horizontal bar list
 *   - "By type" horizontal bar list
 *   - Full event log table (time / site / asset / type / confidence / shift)
 *
 * The component is self-contained — Drilldown.tsx just embeds it when the
 * incoming signal's agent === 'hse'.
 */
import { useEffect, useState } from 'react';

interface PpeEvent {
  site: string;
  asset: string;
  type: string;
  confidence: number;
  crew_lead: string;
  shift: string;
  minutes_ago: number;
  relative_time: string;
}

interface Stats {
  total: number;
  last_24h: number;
  last_week_at_top_site: number;
  sites_involved: number;
  by_site: Record<string, number>;
  by_type: Record<string, number>;
  by_shift: Record<string, number>;
  avg_confidence: number | null;
  min_confidence: number | null;
  max_confidence: number | null;
  top_site: string | null;
  top_type: string | null;
  site_notes: Record<string, string>;
}

interface Payload {
  events: PpeEvent[];
  stats: Stats;
  as_of: string;
}

const TYPE_LABELS: Record<string, string> = {
  no_hardhat: 'No hard-hat',
  no_hi_vis: 'No hi-vis',
  no_gloves: 'No gloves',
  no_goggles: 'No goggles',
};

export function HseDrilldownBlock() {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/os/hse/events')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="hse-rich-loading">Loading event log…</div>;
  if (!data || data.events.length === 0) return null;

  const { events, stats } = data;
  const maxSite = Math.max(...Object.values(stats.by_site || {}), 1);
  const maxType = Math.max(...Object.values(stats.by_type || {}), 1);

  return (
    <div className="hse-rich">
      {/* Stats grid */}
      <div className="hse-stats">
        <Stat label="Open events" value={stats.total.toString()} sub="all sites · all shifts" />
        <Stat label="Last 24 hours" value={stats.last_24h.toString()} sub="rolling window" amber={stats.last_24h >= 3} />
        <Stat label="Sites involved" value={stats.sites_involved.toString()} sub={stats.top_site ? `top: ${stats.top_site}` : '—'} />
        <Stat
          label="Detection confidence"
          value={stats.avg_confidence !== null ? `${Math.round((stats.avg_confidence) * 100)}%` : '—'}
          sub={
            stats.min_confidence !== null && stats.max_confidence !== null
              ? `range ${Math.round(stats.min_confidence * 100)}–${Math.round(stats.max_confidence * 100)}%`
              : 'CV pipeline avg'
          }
        />
      </div>

      {/* By-site + by-type bars */}
      <div className="hse-bars">
        <div className="hse-bar-block">
          <div className="hse-bar-title eyebrow">Events by site</div>
          {Object.entries(stats.by_site).map(([site, n]) => (
            <div className="hse-bar-row" key={site}>
              <div className="hse-bar-label" title={stats.site_notes?.[site]}>{site}</div>
              <div className="hse-bar-track">
                <div className="hse-bar-fill" style={{ width: `${(n / maxSite) * 100}%` }} />
              </div>
              <div className="hse-bar-count num">{n}</div>
            </div>
          ))}
          {Object.entries(stats.site_notes || {}).map(([site, note]) => (
            <p key={`note-${site}`} className="hse-site-note">
              <span className="hse-site-note-dot" />
              <strong>{site}:</strong> {note}
            </p>
          ))}
        </div>

        <div className="hse-bar-block">
          <div className="hse-bar-title eyebrow">Events by type</div>
          {Object.entries(stats.by_type).map(([type, n]) => (
            <div className="hse-bar-row" key={type}>
              <div className="hse-bar-label">{TYPE_LABELS[type] ?? type}</div>
              <div className="hse-bar-track">
                <div className="hse-bar-fill hse-bar-fill-amber" style={{ width: `${(n / maxType) * 100}%` }} />
              </div>
              <div className="hse-bar-count num">{n}</div>
            </div>
          ))}

          <div className="hse-bar-title eyebrow" style={{ marginTop: 22 }}>By shift</div>
          {Object.entries(stats.by_shift || {}).map(([shift, n]) => (
            <div className="hse-bar-row" key={`s-${shift}`}>
              <div className="hse-bar-label">Shift {shift}</div>
              <div className="hse-bar-track">
                <div className="hse-bar-fill" style={{ width: `${(n / stats.total) * 100}%` }} />
              </div>
              <div className="hse-bar-count num">{n}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Event log */}
      <div className="hse-events">
        <div className="hse-bar-title eyebrow">Full event log</div>
        <table className="hse-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Site</th>
              <th>Asset</th>
              <th>Type</th>
              <th>Conf.</th>
              <th>Shift</th>
              <th>Crew lead</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i} className={e.minutes_ago < 30 ? 'is-recent' : ''}>
                <td className="num hse-table-when">{e.relative_time}</td>
                <td>{e.site}</td>
                <td>{e.asset}</td>
                <td>
                  <span className="hse-type-pill">
                    {TYPE_LABELS[e.type] ?? e.type}
                  </span>
                </td>
                <td className="num">{Math.round(e.confidence * 100)}%</td>
                <td>{e.shift}</td>
                <td>{e.crew_lead}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({
  label, value, sub, amber,
}: { label: string; value: string; sub: string; amber?: boolean }) {
  return (
    <div className={'hse-stat' + (amber ? ' is-amber' : '')}>
      <div className="hse-stat-label">{label}</div>
      <div className="hse-stat-value serif num">{value}</div>
      <div className="hse-stat-sub">{sub}</div>
    </div>
  );
}
