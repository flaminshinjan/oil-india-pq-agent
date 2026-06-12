'use client';
/**
 * Per-domain dashboard — KPI cards, breakdown bars, and a trend chart,
 * all driven by /api/os/domain/{key}.
 *
 * Numbers come straight from OIL's data files (10-yr Excel, FY perf
 * annexures, synthetic JSON feeds). No filenames are shown — the user
 * sees metrics, not provenance.
 *
 * HSE keeps the live PPE block underneath because the camera-vision
 * stream is genuinely useful alongside the rolling stats.
 */
import { useEffect, useState } from 'react';

import { Drilldown, type DrilldownData } from './Drilldown';
import { Chart, LogicMap, ClaimsTable, type ChartSpec } from './Charts';
import type { DomainKey } from './DomainSelector';

interface Kpi {
  label: string;
  value: string;
  unit?: string;
  trend?: string;
  amber?: boolean;
  note?: string;
}

interface BreakdownItem {
  label: string;
  value: number;
  share: number;
  amber?: boolean;
}

interface Breakdown {
  title: string;
  unit?: string;
  items: BreakdownItem[];
}

interface TrendSeries {
  name: string;
  values: (number | null)[];
}

interface Trend {
  label: string;
  unit?: string;
  labels: string[];
  series: TrendSeries[];
}

interface Predictive {
  label?: string;
  method?: string;
  output?: string;
  metrics?: Record<string, unknown>;
}

interface Insight {
  id: string;
  title: string;
  summary: string;
  drilldown?: { l1_title?: string; l1?: string; l2_title?: string; l2?: string };
  predictive?: Predictive;
  links?: string[];
}

interface Milestone {
  title: string;
  body: string;
  source: string;
  tags: string[];
  status?: string;
}

interface ScenarioLens {
  lens: string;
  output: string;
  table?: { pool_bcm: number; uplift_2p_gas_pct?: number; added_reserve_life_yrs?: number }[] | null;
  hypothetical?: boolean;
}

interface ScenarioTimeline { stage: string; when: string; done: boolean; }

interface Scenario {
  label: string;
  subtitle?: string;
  guardrail: string;
  facts?: Record<string, unknown>;
  lenses: ScenarioLens[];
  timeline?: ScenarioTimeline[];
  scrape_status?: string;
  live_sources?: { title: string; url: string; published?: string; snippet?: string }[];
  live_source_method?: string;
  system_of_record?: string;
}

interface Payload {
  key: string;
  title: string;
  lead: string;
  kpis: Kpi[];
  breakdowns: Breakdown[];
  trend: Trend | null;
  highlights: string[];
  insights?: Insight[];
  milestones?: Milestone[];
  scenario?: Scenario | null;
  charts?: Record<string, ChartSpec>;
  as_of?: string;
}

/* Ordered chart panels per page — title + the charts.{key}s to render in
 * that group (side-by-side when more than one). Mirrors the SME pack. */
const CHART_PANELS: Record<string, { title: string; sub?: string; keys: string[] }[]> = {
  production: [
    { title: '10-year production trend', sub: 'Crude (MMT) vs natural gas (MMSCM), FY16–FY26', keys: ['crude_gas_trend'] },
    { title: 'State-wise FY26 achievement', sub: 'Crude and gas cumulative actuals vs annual BE target', keys: ['state_crude', 'state_gas'] },
    { title: 'Reserves analysis — RRR & 2P divergence', sub: 'RRR vs the 1.0 threshold; 2P oil falling while 2P gas rises', keys: ['rrr_bars', 'twop_divergence'] },
    { title: 'Production forecast fan — FY27–28', sub: 'Decline-curve + intervention regression', keys: ['production_forecast'] },
    { title: 'RRR scenario fan — FY26–28', sub: 'Accretion scenarios + arithmetic verification', keys: ['rrr_scenario', 'rrr_verification'] },
    { title: 'Gasification crossover projection', sub: 'Gas share of MMToE output crossing 50%', keys: ['gasification'] },
  ],
  finance: [
    { title: 'Earnings & margins (5-yr)', sub: 'Income, EBITDA, PAT and the margin trend — standalone, ₹ crore', keys: ['finance_earnings', 'finance_margins'] },
    { title: 'Drivers & cash (5-yr)', sub: 'Price realizations vs the cash-flow / capex / exchequer picture', keys: ['finance_realizations', 'finance_cashflow'] },
  ],
  exploration: [
    { title: 'Drilling intensity vs production', sub: 'Wells + workovers vs crude, FY21–FY26 + forecast', keys: ['wells_workovers'] },
    { title: 'FY26 drilling breakdown', sub: 'Nominated vs other regimes — verified against the grand-total row', keys: ['drilling_breakdown'] },
    { title: 'Exploratory meterage by regime — FY26', sub: 'Per-regime achievement vs the 100% BE target', keys: ['regime_achievement'] },
    { title: 'Exploration effectiveness & required-wells inversion', sub: 'Accretion per exploratory well, inverted to an FY27 requirement', keys: ['effectiveness', 'required_wells'] },
  ],
};

interface Props {
  domain: DomainKey;
  onOpenSource?: (filename: string) => void;
}

export function DomainDashboard({ domain, onOpenSource }: Props) {
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drill, setDrill] = useState<DrilldownData | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setLoading(true);
    setError(null);
    fetch(`/api/os/domain/${domain}`)
      .then(r => r.json())
      .then(d => {
        if (cancelled) return;
        if (d?.error) setError(d.error);
        else setData(d);
        setLoading(false);
      })
      .catch(e => {
        if (cancelled) return;
        setError(String(e?.message ?? e));
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [domain]);

  if (loading) return <DomainSkeleton />;

  if (error || !data) {
    return (
      <div className="domain-view">
        <div className="domain-empty">
          <h2 className="serif domain-title">Unable to load this dashboard</h2>
          <p className="domain-empty-sub">{error ?? 'No data returned.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="domain-view">
      <header className="domain-head">
        <span className="eyebrow">{data.title}</span>
        <h1 className="serif domain-title">{data.title}</h1>
        <p className="domain-lead">{data.lead}</p>
      </header>

      {data.kpis && data.kpis.length > 0 && (
        <section className="domain-kpis">
          {data.kpis.map((k, i) => (
            <KpiCard
              key={i}
              kpi={k}
              onOpen={() => setDrill(buildKpiDrill(data, k))}
            />
          ))}
        </section>
      )}

      {drill && (
        <Drilldown
          data={drill}
          onClose={() => setDrill(null)}
          onOpenSource={onOpenSource}
        />
      )}

      {data.charts && (CHART_PANELS[data.key] || []).map((panel, pi) => {
        const present = panel.keys.filter(k => data.charts?.[k]);
        if (present.length === 0) return null;
        return (
          <section className="domain-block" key={`panel-${pi}`}>
            <h2 className="serif domain-section-title">{panel.title}</h2>
            {panel.sub && <p className="domain-section-sub">{panel.sub}</p>}
            <div className={'chart-panel-grid' + (present.length > 1 ? ' is-split' : '')}>
              {present.map(k => <Chart key={k} chart={data.charts![k]} />)}
            </div>
          </section>
        );
      })}

      {data.milestones && data.milestones.length > 0 && (
        <section className="domain-block">
          <h2 className="serif domain-section-title">Live milestones</h2>
          <div className="milestone-strip">
            {data.milestones.map((m, i) => (
              <div
                key={i}
                className={'milestone-card' + (m.status === 'unbooked' ? ' is-unbooked' : '')}
              >
                <div className="milestone-tags">
                  {m.tags.map(t => <span key={t} className="milestone-tag">{t}</span>)}
                  {m.status === 'unbooked' && (
                    <span className="milestone-status">unbooked</span>
                  )}
                </div>
                <div className="milestone-title">{m.title}</div>
                <div className="milestone-body">{m.body}</div>
                <div className="milestone-source">{m.source}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.insights && data.insights.length > 0 && (
        <section className="domain-block">
          <h2 className="serif domain-section-title">Analysis</h2>
          <p className="domain-section-sub">
            Deep-dive insights — each backed by a model computed on OIL&rsquo;s own data.
          </p>
          <div className="insight-grid">
            {data.insights.map(ins => (
              <button
                key={ins.id}
                type="button"
                className="insight-card is-clickable"
                onClick={() => setDrill(buildInsightDrill(data, ins))}
              >
                {ins.predictive?.output && (
                  <span className="insight-badge">Predictive</span>
                )}
                <h3 className="insight-title serif">{ins.title}</h3>
                <p className="insight-summary">{ins.summary}</p>
                {ins.predictive?.output && (
                  <p className="insight-predictive">
                    <span className="insight-predictive-label">
                      {ins.predictive.label ?? 'Model'}
                    </span>
                    {ins.predictive.output}
                  </p>
                )}
                <span className="insight-more">Open analysis →</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {data.scenario && (
        <ScenarioModule scenario={data.scenario} bayesian={data.charts?.bayesian} />
      )}

      {(!data.insights || data.insights.length === 0) &&
        data.highlights && data.highlights.length > 0 && (
        <section className="domain-highlights">
          {data.highlights.map((h, i) => (
            <p key={i} className="domain-highlight">
              <span className="domain-highlight-dot" />
              <span>{h}</span>
            </p>
          ))}
        </section>
      )}

      {!data.charts && data.trend && data.trend.labels.length > 0 && (
        <section className="domain-block">
          <h2 className="serif domain-section-title">Trend</h2>
          <p className="domain-section-sub">{data.trend.label}</p>
          <TrendChart trend={data.trend} />
        </section>
      )}

      {data.breakdowns && data.breakdowns.length > 0 && (
        <section className="domain-block">
          <h2 className="serif domain-section-title">Breakdown</h2>
          <div className="domain-breakdowns">
            {data.breakdowns.map((b, i) => (
              <BreakdownBlock key={i} block={b} />
            ))}
          </div>
        </section>
      )}

      {data.charts && (
        <section className="domain-block">
          <h2 className="serif domain-section-title">Cross-page predictive logic</h2>
          <p className="domain-section-sub">
            How the models join up — and where the booked/hypothetical line sits.
          </p>
          <LogicMap />
          <h3 className="serif domain-section-title" style={{ marginTop: 24 }}>
            Predictive claims inventory
          </h3>
          <ClaimsTable />
        </section>
      )}

    </div>
  );
}

/* ---------------- subcomponents ---------------- */

function KpiCard({ kpi, onOpen }: { kpi: Kpi; onOpen?: () => void }) {
  return (
    <button
      type="button"
      className={'kpi-card' + (kpi.amber ? ' is-amber' : '') + (onOpen ? ' is-clickable' : '')}
      onClick={onOpen}
    >
      <div className="kpi-card-label">{kpi.label}</div>
      <div className="kpi-card-value-row">
        <span className="kpi-card-value serif num">{kpi.value}</span>
        {kpi.unit && <span className="kpi-card-unit">{kpi.unit}</span>}
      </div>
      {kpi.trend && <div className="kpi-card-trend">{kpi.trend}</div>}
      {kpi.note && <div className="kpi-card-note">{kpi.note}</div>}
    </button>
  );
}

/** Build a Drilldown payload for a KPI card click. We re-use the same
 *  shape the brief-card drilldown uses, packing the dashboard's
 *  breakdowns + highlights + trend as sections. */
function buildKpiDrill(payload: Payload, kpi: Kpi): DrilldownData {
  const sections = [];
  if (payload.highlights && payload.highlights.length > 0) {
    sections.push({
      eyebrow: 'What this means',
      body: payload.highlights.map(h => `- ${h}`).join('\n'),
    });
  }
  if (payload.breakdowns && payload.breakdowns.length > 0) {
    payload.breakdowns.forEach(b => {
      const tbl = ['| Item | Value |', '|---|---:|'];
      b.items.forEach(it => tbl.push(`| ${it.label} | ${fmtVal(it.value)} ${b.unit ?? ''} |`));
      sections.push({
        eyebrow: 'Breakdown',
        title: b.title,
        body: tbl.join('\n'),
      });
    });
  }
  const lead = `${kpi.label}: **${kpi.value}${kpi.unit ? ' ' + kpi.unit : ''}**` +
    (kpi.trend ? ` — ${kpi.trend}` : '') +
    (kpi.note ? `\n\n${kpi.note}` : '');
  return {
    tag: payload.title,
    eyebrow: 'KPI detail',
    title: kpi.label,
    lead,
    sections,
    sources: [],
    agent: undefined,
  };
}

/** Build a Drilldown payload for an insight card — packs L1, L2 and the
 *  computed predictive block as sections. */
function buildInsightDrill(payload: Payload, ins: Insight): DrilldownData {
  const sections = [];
  const dd = ins.drilldown ?? {};
  if (dd.l1) {
    sections.push({ eyebrow: 'Drill-down · L1', title: dd.l1_title, body: dd.l1 });
  }
  if (dd.l2) {
    sections.push({ eyebrow: 'Drill-down · L2', title: dd.l2_title, body: dd.l2 });
  }
  const p = ins.predictive;
  if (p?.output) {
    const body = [
      p.method ? `_${p.method}_` : '',
      '',
      p.output,
    ].filter(Boolean).join('\n');
    sections.push({
      eyebrow: 'Predictive · computed model',
      title: p.label ?? 'Model output',
      body,
    });
  }
  return {
    tag: payload.title,
    eyebrow: 'Insight',
    title: ins.title,
    lead: ins.summary,
    sections,
    sources: [],
    agent: undefined,
  };
}

function ScenarioModule({ scenario, bayesian }:
  { scenario: Scenario; bayesian?: ChartSpec }) {
  const wells = (scenario.facts?.wells as any[]) || [];
  return (
    <section className="scenario-module">
      <div className="scenario-head">
        <span className="scenario-eyebrow">Possible upside · scenario</span>
        <h2 className="serif scenario-title">{scenario.label}</h2>
        {scenario.subtitle && <p className="scenario-subtitle">{scenario.subtitle}</p>}
      </div>

      <div className="scenario-guardrail">{scenario.guardrail}</div>

      {wells.length > 0 && (
        <div className="scenario-wells">
          {wells.map((w: any, i: number) => (
            <div className={'scenario-well' + (w.gas_bearing ? ' is-gas' : '')} key={i}>
              <div className="scenario-well-name">{w.well}</div>
              <div className="scenario-well-meta">
                {w.result}{w.water_depth_m ? ` · ${w.water_depth_m} m WD` : ''}
                {w.methane_pct ? ` · ${w.methane_pct}% methane` : ''}
              </div>
            </div>
          ))}
        </div>
      )}

      {bayesian && (
        <div className="scenario-chart">
          <div className="scenario-chart-title">
            Bayesian basin-probability tracker — prior updated on each well result
          </div>
          <Chart chart={bayesian} />
        </div>
      )}

      <div className="scenario-lenses">
        {scenario.lenses.map((l, i) => (
          <div className="scenario-lens" key={i}>
            <div className="scenario-lens-head">
              <span className="scenario-lens-name">{l.lens}</span>
              {l.hypothetical && <span className="scenario-hyp">illustrative</span>}
            </div>
            <p className="scenario-lens-output">{l.output}</p>
            {l.table && l.table.length > 0 && (
              <table className="scenario-table">
                <thead>
                  <tr><th>Pool</th><th>2P gas uplift</th><th>+ reserve life</th></tr>
                </thead>
                <tbody>
                  {l.table.map((row, j) => (
                    <tr key={j}>
                      <td>{row.pool_bcm} BCM</td>
                      <td>+{row.uplift_2p_gas_pct}%</td>
                      <td>+{row.added_reserve_life_yrs} yrs</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      {scenario.timeline && scenario.timeline.length > 0 && (
        <div className="scenario-timeline">
          {scenario.timeline.map((t, i) => (
            <div className={'scenario-step' + (t.done ? ' is-done' : '')} key={i}>
              <span className="scenario-step-dot" />
              <span className="scenario-step-stage">{t.stage}</span>
              <span className="scenario-step-when">{t.when}</span>
            </div>
          ))}
        </div>
      )}

      {scenario.scrape_status && (
        <div className="scenario-foot">
          <span className="scenario-foot-label">Source</span>
          {scenario.system_of_record} · {scenario.scrape_status}
        </div>
      )}
      {scenario.live_sources && scenario.live_sources.length > 0 && (
        <ul className="scenario-sources">
          {scenario.live_sources.slice(0, 5).map((s, i) => (
            <li key={i}>
              <a href={s.url} target="_blank" rel="noopener noreferrer"
                 className="scenario-source-link" title={s.snippet || s.url}>
                {s.title || s.url}
              </a>
              {s.published && <span className="scenario-source-date">{s.published}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function BreakdownBlock({ block }: { block: Breakdown }) {
  const maxVal = Math.max(...block.items.map(i => i.value), 1);
  return (
    <div className="breakdown-block">
      <div className="breakdown-title eyebrow">{block.title}</div>
      {block.items.map((it, i) => (
        <div className={'breakdown-row' + (it.amber ? ' is-amber' : '')} key={i}>
          <div className="breakdown-label" title={it.label}>{it.label}</div>
          <div className="breakdown-track">
            <div
              className="breakdown-fill"
              style={{ width: `${Math.max(2, (it.value / maxVal) * 100)}%` }}
            />
          </div>
          <div className="breakdown-val num">
            {fmtVal(it.value)}{block.unit ? ' ' : ''}
            {block.unit && <span className="breakdown-unit">{block.unit}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function fmtVal(v: number): string {
  if (Math.abs(v) >= 1000) return v.toLocaleString();
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(2);
}

function TrendChart({ trend }: { trend: Trend }) {
  // Simple SVG line chart — one path per series, normalised together so
  // they're comparable on the same y-axis. Skips null values.
  const W = 700;
  const H = 200;
  const PAD = { top: 16, right: 16, bottom: 28, left: 36 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const n = trend.labels.length;

  const allVals = trend.series.flatMap(s => s.values.filter((v): v is number => v != null));
  if (allVals.length === 0) return null;
  const min = Math.min(...allVals);
  const max = Math.max(...allVals);
  const span = max - min || 1;

  function x(i: number) {
    if (n <= 1) return PAD.left + innerW / 2;
    return PAD.left + (i / (n - 1)) * innerW;
  }
  function y(v: number) {
    return PAD.top + innerH - ((v - min) / span) * innerH;
  }

  const colors = ['var(--accent)', 'var(--amber-ink)'];

  return (
    <div className="trend-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="trend-svg" role="img"
           aria-label={trend.label}>
        {/* horizontal grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((t, idx) => {
          const yy = PAD.top + innerH * t;
          return (
            <line key={idx} x1={PAD.left} x2={W - PAD.right}
                  y1={yy} y2={yy} stroke="var(--line)" strokeDasharray="2 4" />
          );
        })}
        {/* x labels */}
        {trend.labels.map((lbl, i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle"
                fontSize="10" fill="var(--ink-4)"
                style={{ fontFeatureSettings: '"tnum" 1' }}>
            {lbl}
          </text>
        ))}
        {/* series */}
        {trend.series.map((s, si) => {
          const pts = s.values
            .map((v, i) => (v == null ? null : `${x(i)},${y(v)}`))
            .filter(Boolean) as string[];
          if (pts.length === 0) return null;
          return (
            <g key={si}>
              <polyline
                points={pts.join(' ')}
                fill="none"
                stroke={colors[si % colors.length]}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {s.values.map((v, i) => v == null ? null : (
                <circle key={i} cx={x(i)} cy={y(v)} r="2.6"
                        fill={colors[si % colors.length]} />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="trend-legend">
        {trend.series.map((s, i) => (
          <span key={i} className="trend-legend-item">
            <span className="trend-legend-dot"
                  style={{ background: colors[i % colors.length] }} />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------------- loading skeleton ---------------- */

function DomainSkeleton() {
  return (
    <div className="domain-view">
      <header className="domain-head">
        <div className="sk-line sk-eyebrow" />
        <div className="sk-line sk-title" />
        <div className="sk-line sk-lead" />
        <div className="sk-line sk-lead-2" />
      </header>
      <section className="domain-kpis">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="kpi-card sk-kpi">
            <div className="sk-line sk-kpi-label" />
            <div className="sk-line sk-kpi-value" />
            <div className="sk-line sk-kpi-trend" />
          </div>
        ))}
      </section>
      <section className="domain-block">
        <div className="sk-line sk-section-title" />
        <div className="sk-block" />
      </section>
    </div>
  );
}
