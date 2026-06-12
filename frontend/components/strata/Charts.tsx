'use client';
/**
 * Charts — hand-rolled SVG chart primitives for the Production &
 * Exploration dashboards. No chart library; every panel is driven by the
 * `charts` block in /api/os/domain/{key}, whose series are all computed
 * server-side from OIL's own files + fitted models.
 *
 * One dispatcher <Chart> picks the renderer by `chart.type`:
 *   dual_line · bar_threshold · forecast_line · forecast_fan ·
 *   grouped_bar_line · hbar_target · line · bar · prob_track
 */

/* ---- shared types ---- */
export interface ChartSpec {
  type: string;
  // common-ish fields (loosely typed — each renderer reads what it needs)
  [k: string]: any;
}

const C = {
  blue:   '#2f6db0',
  teal:   '#1f8a70',
  amber:  '#d68a2e',
  amberHi:'#b3641b',
  red:    '#c0492f',
  purple: '#6b5bd2',
  grid:   'var(--line)',
  axis:   'var(--ink-4)',
  ink:    'var(--ink-2)',
};

/* ---- scale helpers ---- */
function bounds(vals: number[], padFrac = 0.08): [number, number] {
  const clean = vals.filter(v => v != null && !Number.isNaN(v));
  if (!clean.length) return [0, 1];
  let lo = Math.min(...clean);
  let hi = Math.max(...clean);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * padFrac;
  return [lo - pad, hi + pad];
}
function fmtNum(v: number): string {
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString();
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(Math.abs(v) < 10 ? 2 : 1);
}

/* ============================================================ */

export function Chart({ chart }: { chart: ChartSpec }) {
  switch (chart.type) {
    case 'dual_line':       return <DualLine c={chart} />;
    case 'bar_threshold':   return <BarThreshold c={chart} />;
    case 'forecast_line':   return <Forecast c={chart} mode="line" />;
    case 'forecast_fan':    return <Forecast c={chart} mode="bars" />;
    case 'grouped_bar_line':return <GroupedBarLine c={chart} />;
    case 'hbar_target':     return <HBarTarget c={chart} />;
    case 'line':            return <SimpleLine c={chart} />;
    case 'bar':             return <SimpleBar c={chart} />;
    case 'prob_track':      return <ProbTrack c={chart} />;
    case 'table':           return <DataTable c={chart} />;
    default:                return null;
  }
}

/* ============================================================
   table — source-verified data table (drilling breakdown, RRR verify)
   ============================================================ */
function DataTable({ c }: { c: ChartSpec }) {
  return (
    <div className="chart-table-wrap">
      {c.title && <div className="chart-table-title">{c.title}</div>}
      <table className="chart-table">
        <thead>
          <tr>{c.columns.map((h: string, i: number) =>
            <th key={i} className={i === 0 ? 'tl' : 'tr'}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {c.rows.map((row: any[], ri: number) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} className={ci === 0 ? 'tl' : 'tr num'}>
                  {cell == null ? '—' : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {c.note && <p className="chart-note">{c.note}</p>}
    </div>
  );
}

/* ---- frame primitives ---- */
const W = 720, H = 280;
const P = { t: 18, r: 54, b: 34, l: 50 };
const IW = W - P.l - P.r;
const IH = H - P.t - P.b;
const xAt = (i: number, n: number) => n <= 1 ? P.l + IW / 2 : P.l + (i / (n - 1)) * IW;

function Grid({ ticks = 5 }: { ticks?: number }) {
  return (
    <>
      {Array.from({ length: ticks }, (_, i) => {
        const y = P.t + (IH * i) / (ticks - 1);
        return <line key={i} x1={P.l} x2={W - P.r} y1={y} y2={y}
                     stroke={C.grid} strokeDasharray="2 4" />;
      })}
    </>
  );
}
function XLabels({ labels }: { labels: string[] }) {
  const n = labels.length;
  const step = n > 12 ? Math.ceil(n / 12) : 1;
  return (
    <>
      {labels.map((l, i) => (i % step === 0 || i === n - 1) ? (
        <text key={i} x={xAt(i, n)} y={H - 12} textAnchor="middle"
              fontSize="9.5" fill={C.axis}
              style={{ fontFeatureSettings: '"tnum" 1' }}>{l}</text>
      ) : null)}
    </>
  );
}
function YLabels({ lo, hi, side = 'left', color = C.axis, fmt = fmtNum }:
  { lo: number; hi: number; side?: 'left' | 'right'; color?: string; fmt?: (v: number) => string }) {
  const ticks = 5;
  return (
    <>
      {Array.from({ length: ticks }, (_, i) => {
        const v = lo + ((hi - lo) * i) / (ticks - 1);
        const y = P.t + IH - (IH * i) / (ticks - 1);
        return (
          <text key={i} x={side === 'left' ? P.l - 8 : W - P.r + 8} y={y + 3}
                textAnchor={side === 'left' ? 'end' : 'start'}
                fontSize="9" fill={color}
                style={{ fontFeatureSettings: '"tnum" 1' }}>{fmt(v)}</text>
        );
      })}
    </>
  );
}
function polyline(values: (number | null)[], lo: number, hi: number, n: number) {
  const yAt = (v: number) => P.t + IH - ((v - lo) / (hi - lo || 1)) * IH;
  return values.map((v, i) => v == null ? null : `${xAt(i, n)},${yAt(v)}`)
               .filter(Boolean).join(' ');
}
const yScale = (lo: number, hi: number) => (v: number) =>
  P.t + IH - ((v - lo) / (hi - lo || 1)) * IH;

function Legend({ items }: { items: { name: string; color: string; dash?: boolean }[] }) {
  return (
    <div className="chart-legend">
      {items.map((it, i) => (
        <span key={i} className="chart-legend-item">
          <span className="chart-legend-dot"
                style={{ background: it.dash ? 'transparent' : it.color,
                         borderBottom: it.dash ? `2px dashed ${it.color}` : undefined,
                         width: it.dash ? 14 : 9, height: it.dash ? 0 : 9 }} />
          {it.name}
        </span>
      ))}
    </div>
  );
}

/* ============================================================
   dual_line — two y-axes, two line series
   ============================================================ */
function DualLine({ c }: { c: ChartSpec }) {
  const n = c.labels.length;
  const [llo, lhi] = bounds(c.left.values);
  const [rlo, rhi] = bounds(c.right.values);
  const yl = yScale(llo, lhi);
  const yr = yScale(rlo, rhi);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.left.name}>
        <Grid />
        <XLabels labels={c.labels} />
        <YLabels lo={llo} hi={lhi} side="left" color={C.blue} />
        <YLabels lo={rlo} hi={rhi} side="right" color={C.teal} />
        {/* left series */}
        <polyline points={polyline(c.left.values, llo, lhi, n)} fill="none"
                  stroke={C.blue} strokeWidth="2" strokeLinejoin="round" />
        {c.left.values.map((v: number | null, i: number) => v == null ? null :
          <circle key={`l${i}`} cx={xAt(i, n)} cy={yl(v)} r="2.6" fill={C.blue} />)}
        {/* right series (dashed) */}
        <polyline points={polyline(c.right.values, rlo, rhi, n)} fill="none"
                  stroke={C.teal} strokeWidth="2" strokeDasharray="5 4" strokeLinejoin="round" />
        {c.right.values.map((v: number | null, i: number) => v == null ? null :
          <rect key={`r${i}`} x={xAt(i, n) - 2.4} y={yr(v) - 2.4} width="4.8" height="4.8" fill={C.teal} />)}
        {/* annotations */}
        {(c.annotations || []).map((a: any, i: number) => {
          const idx = c.labels.indexOf(a.fy);
          if (idx < 0) return null;
          return <text key={i} x={xAt(idx, n)} y={P.t + 10} textAnchor="middle"
                       fontSize="8.5" fill={C.axis} fontStyle="italic">{a.label}</text>;
        })}
      </svg>
      <Legend items={[
        { name: c.left.name, color: C.blue },
        { name: c.right.name, color: C.teal, dash: true },
      ]} />
    </div>
  );
}

/* ============================================================
   bar_threshold — vertical bars + horizontal threshold line
   ============================================================ */
function BarThreshold({ c }: { c: ChartSpec }) {
  const n = c.labels.length;
  const allv = [...c.values, c.threshold];
  const [lo, hi] = bounds(allv, 0.12);
  const y = yScale(lo, hi);
  const bw = Math.min(54, (IW / n) * 0.55);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.unit}>
        <Grid />
        <XLabels labels={c.labels} />
        <YLabels lo={lo} hi={hi} side="left" />
        {c.values.map((v: number, i: number) => {
          const below = c.amber_below && c.threshold != null && v < c.threshold;
          const yy = y(v);
          const y0 = y(lo);
          return (
            <g key={i}>
              <rect x={xAt(i, n) - bw / 2} y={yy} width={bw} height={Math.max(0, y0 - yy)}
                    rx="2" fill={below ? C.amberHi : C.amber} opacity={0.92} />
              <text x={xAt(i, n)} y={yy - 5} textAnchor="middle" fontSize="9.5"
                    fill={C.ink} style={{ fontFeatureSettings: '"tnum" 1' }}>{fmtNum(v)}</text>
            </g>
          );
        })}
        {c.threshold != null && (
          <>
            <line x1={P.l} x2={W - P.r} y1={y(c.threshold)} y2={y(c.threshold)}
                  stroke={C.red} strokeWidth="1.2" strokeDasharray="5 3" />
            <text x={W - P.r} y={y(c.threshold) - 4} textAnchor="end" fontSize="8.5"
                  fill={C.red}>{c.threshold_label || `threshold ${c.threshold}`}</text>
          </>
        )}
      </svg>
    </div>
  );
}

/* ============================================================
   forecast_line / forecast_fan — actuals (line or bars) +
   dashed forecast paths + shaded forecast band + threshold
   ============================================================ */
const PATH_STYLE: Record<string, { color: string; dash: string; marker: 'sq' | 'tri' | 'dot' }> = {
  up:   { color: C.teal,   dash: '6 3', marker: 'sq' },
  down: { color: C.red,    dash: '2 3', marker: 'tri' },
  flat: { color: C.purple, dash: '5 4', marker: 'dot' },
  hyp:  { color: C.purple, dash: '2 3', marker: 'tri' },
};
function Forecast({ c, mode }: { c: ChartSpec; mode: 'line' | 'bars' }) {
  const n = c.labels.length;
  const seriesVals: number[] = [];
  if (mode === 'line') c.actual.values.forEach((v: number | null) => v != null && seriesVals.push(v));
  if (mode === 'bars') c.bars.values.forEach((v: number | null) => v != null && seriesVals.push(v));
  c.paths.forEach((p: any) => p.values.forEach((v: number | null) => v != null && seriesVals.push(v)));
  if (c.threshold != null) seriesVals.push(c.threshold);
  const [lo, hi] = bounds(seriesVals, 0.1);
  const y = yScale(lo, hi);
  const fx = c.forecast_from != null ? xAt(c.forecast_from - 0.5, n) : null;
  const bw = Math.min(40, (IW / n) * 0.5);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.y_label}>
        {/* forecast band */}
        {fx != null && (
          <rect x={fx} y={P.t} width={W - P.r - fx} height={IH}
                fill={C.amber} opacity="0.06" />
        )}
        {fx != null && (
          <text x={W - P.r - 4} y={P.t + 11} textAnchor="end" fontSize="8.5"
                fill={C.amberHi} fontWeight="600" letterSpacing="0.08em">FORECAST</text>
        )}
        <Grid />
        <XLabels labels={c.labels} />
        <YLabels lo={lo} hi={hi} side="left" />
        {/* actuals */}
        {mode === 'line' && (
          <>
            <polyline points={polyline(c.actual.values, lo, hi, n)} fill="none"
                      stroke={C.blue} strokeWidth="2" strokeLinejoin="round" />
            {c.actual.values.map((v: number | null, i: number) => v == null ? null :
              <circle key={i} cx={xAt(i, n)} cy={y(v)} r="2.6" fill={C.blue} />)}
          </>
        )}
        {mode === 'bars' && c.bars.values.map((v: number | null, i: number) => v == null ? null : (
          <rect key={i} x={xAt(i, n) - bw / 2} y={y(v)} width={bw}
                height={Math.max(0, y(lo) - y(v))} rx="2" fill={C.amber} opacity="0.85" />
        ))}
        {/* threshold */}
        {c.threshold != null && (
          <>
            <line x1={P.l} x2={W - P.r} y1={y(c.threshold)} y2={y(c.threshold)}
                  stroke={C.red} strokeWidth="1.1" strokeDasharray="5 3" />
            <text x={P.l + 4} y={y(c.threshold) - 4} fontSize="8.5"
                  fill={C.red}>{c.threshold_label || `${c.threshold}`}</text>
          </>
        )}
        {/* forecast paths */}
        {c.paths.map((p: any, pi: number) => {
          const st = PATH_STYLE[p.style] || PATH_STYLE.flat;
          return (
            <g key={pi}>
              <polyline points={polyline(p.values, lo, hi, n)} fill="none"
                        stroke={st.color} strokeWidth="2" strokeDasharray={st.dash}
                        strokeLinejoin="round" />
              {p.values.map((v: number | null, i: number) => v == null ? null :
                <circle key={i} cx={xAt(i, n)} cy={y(v)} r="2.4" fill={st.color} />)}
            </g>
          );
        })}
      </svg>
      <Legend items={[
        ...(mode === 'line' ? [{ name: c.actual.name, color: C.blue }] :
                              [{ name: c.bars.name, color: C.amber }]),
        ...c.paths.map((p: any) => ({
          name: p.name, color: (PATH_STYLE[p.style] || PATH_STYLE.flat).color, dash: true,
        })),
      ]} />
      {c.model_note && <p className="chart-note">{c.model_note}</p>}
    </div>
  );
}

/* ============================================================
   grouped_bar_line — grouped bars (left axis) + line (right axis)
   ============================================================ */
function GroupedBarLine({ c }: { c: ChartSpec }) {
  const n = c.labels.length;
  const barVals = c.bars.flatMap((b: any) => b.values).filter((v: any) => v != null);
  const [blo, bhi] = [0, Math.max(...barVals) * 1.1];
  const [llo, lhi] = bounds(c.line.values, 0.15);
  const yb = yScale(blo, bhi);
  const yl = yScale(llo, lhi);
  const nb = c.bars.length;
  const group = (IW / n) * 0.62;
  const bw = group / nb;
  const colors = [C.purple, C.teal];
  const fc = c.forecast_from != null ? c.forecast_from : n;
  const fx = fc < n ? xAt(fc - 0.5, n) : null;
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.line.name}>
        {fx != null && <rect x={fx} y={P.t} width={W - P.r - fx} height={IH} fill={C.amber} opacity="0.06" />}
        {fx != null && <text x={W - P.r - 4} y={P.t + 11} textAnchor="end" fontSize="8.5"
              fill={C.amberHi} fontWeight="600" letterSpacing="0.08em">FORECAST</text>}
        <Grid />
        <XLabels labels={c.labels} />
        <YLabels lo={blo} hi={bhi} side="left" />
        <YLabels lo={llo} hi={lhi} side="right" color={C.red} />
        {c.bars.map((b: any, bi: number) =>
          b.values.map((v: number | null, i: number) => v == null ? null : (
            <rect key={`${bi}-${i}`}
                  x={xAt(i, n) - group / 2 + bi * bw} y={yb(v)}
                  width={bw - 2} height={Math.max(0, yb(blo) - yb(v))}
                  rx="1.5" fill={colors[bi % colors.length]}
                  opacity={i >= fc ? 0.32 : 0.88} />
          )))}
        {/* line: solid over actuals, dashed over forecast */}
        <polyline points={polyline(c.line.values.map((v: number | null, i: number) => i < fc ? v : null), llo, lhi, n)}
                  fill="none" stroke={C.red} strokeWidth="2.2" strokeLinejoin="round" />
        {fc < n && (
          <polyline points={polyline(c.line.values.map((v: number | null, i: number) => i >= fc - 1 ? v : null), llo, lhi, n)}
                    fill="none" stroke={C.red} strokeWidth="2.2" strokeDasharray="5 3" strokeLinejoin="round" />
        )}
        {c.line.values.map((v: number | null, i: number) => v == null ? null :
          <circle key={i} cx={xAt(i, n)} cy={yl(v)} r="3" fill={C.red} opacity={i >= fc ? 0.5 : 1} />)}
      </svg>
      <Legend items={[
        ...c.bars.map((b: any, i: number) => ({ name: b.name, color: colors[i % colors.length] })),
        { name: c.line.name, color: C.red },
      ]} />
      {c.model_note && <p className="chart-note">{c.model_note}</p>}
    </div>
  );
}

/* ============================================================
   hbar_target — horizontal achievement bars + target marker
   ============================================================ */
function HBarTarget({ c }: { c: ChartSpec }) {
  const maxPct = Math.max(c.target, ...c.items.map((i: any) => i.pct)) * 1.12;
  const rowH = 34;
  const top = 16;
  const left = 150;
  const right = 30;
  const w = W - left - right;
  const x = (p: number) => left + (p / maxPct) * w;
  const h = top + c.items.length * rowH + 30;
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${h}`} className="chart-svg" role="img" aria-label={c.x_label}>
        {/* target line */}
        <line x1={x(c.target)} x2={x(c.target)} y1={top - 4} y2={top + c.items.length * rowH}
              stroke={C.axis} strokeDasharray="3 3" strokeWidth="1" />
        <text x={x(c.target)} y={top - 8} textAnchor="middle" fontSize="8.5"
              fill={C.axis}>{c.target_label || '100%'}</text>
        {c.items.map((it: any, i: number) => {
          const yy = top + i * rowH + 4;
          const below = it.pct < c.target;
          return (
            <g key={i}>
              <text x={left - 10} y={yy + 12} textAnchor="end" fontSize="10.5"
                    fill={C.ink}>{it.label}</text>
              <rect x={left} y={yy} width={Math.max(1, x(it.pct) - left)} height={18}
                    rx="2" fill={below ? C.amber : C.teal} opacity="0.9" />
              <text x={x(it.pct) + 6} y={yy + 13} fontSize="10"
                    fill={C.ink} style={{ fontFeatureSettings: '"tnum" 1' }}>{it.pct}%</text>
            </g>
          );
        })}
        <text x={left + w / 2} y={h - 6} textAnchor="middle" fontSize="9" fill={C.axis}>{c.x_label}</text>
      </svg>
    </div>
  );
}

/* ============================================================
   line — single series with optional point labels
   ============================================================ */
function SimpleLine({ c }: { c: ChartSpec }) {
  const n = c.labels.length;
  const [lo, hi] = bounds(c.values, 0.15);
  const y = yScale(lo, hi);
  return (
    <div className="chart-wrap">
      {c.subtitle && <div className="chart-subtitle">{c.subtitle}</div>}
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.y_label}>
        <Grid />
        <XLabels labels={c.labels} />
        <YLabels lo={lo} hi={hi} side="left" />
        <polyline points={polyline(c.values, lo, hi, n)} fill="none"
                  stroke={C.purple} strokeWidth="2" strokeLinejoin="round" />
        {c.values.map((v: number | null, i: number) => v == null ? null : (
          <g key={i}>
            <circle cx={xAt(i, n)} cy={y(v)} r="3" fill={C.purple} />
            {c.point_labels && (
              <text x={xAt(i, n)} y={y(v) - 8} textAnchor="middle" fontSize="9"
                    fill={C.ink} style={{ fontFeatureSettings: '"tnum" 1' }}>{fmtNum(v)}</text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

/* ============================================================
   bar — simple colored vertical bars with value labels
   ============================================================ */
function SimpleBar({ c }: { c: ChartSpec }) {
  const n = c.items.length;
  const vals = c.items.map((i: any) => i.value ?? 0);
  const hiCap = Math.max(...vals, c.threshold ?? 0) * 1.18;
  const [lo, hi] = [0, hiCap];
  const y = yScale(lo, hi);
  const bw = Math.min(70, (IW / n) * 0.5);
  const colorOf = (k: string) => k === 'amber' ? C.amber : k === 'red' ? C.red : C.teal;
  return (
    <div className="chart-wrap">
      {c.subtitle && <div className="chart-subtitle">{c.subtitle}</div>}
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.y_label}>
        <Grid />
        <YLabels lo={lo} hi={hi} side="left" />
        {c.threshold != null && (
          <>
            <line x1={P.l} x2={W - P.r} y1={y(c.threshold)} y2={y(c.threshold)}
                  stroke={C.axis} strokeWidth="1" strokeDasharray="3 3" />
            <text x={W - P.r} y={y(c.threshold) - 4} textAnchor="end" fontSize="8.5"
                  fill={C.axis}>{c.threshold === 100 ? '100% target' : c.threshold}</text>
          </>
        )}
        {c.items.map((it: any, i: number) => {
          const v = it.value ?? 0;
          return (
            <g key={i}>
              <rect x={xAt(i, n) - bw / 2} y={y(v)} width={bw}
                    height={Math.max(0, y(lo) - y(v))} rx="2.5"
                    fill={colorOf(it.color)} opacity="0.9" />
              <text x={xAt(i, n)} y={y(v) - 6} textAnchor="middle" fontSize="11"
                    fill={C.ink} style={{ fontFeatureSettings: '"tnum" 1' }}>{v}</text>
              {String(it.label).split('\n').map((ln: string, li: number) => (
                <text key={li} x={xAt(i, n)} y={H - 20 + li * 11} textAnchor="middle"
                      fontSize="9" fill={C.axis}>{ln}</text>
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ============================================================
   prob_track — categorical x, line + colored points (Bayesian)
   ============================================================ */
function ProbTrack({ c }: { c: ChartSpec }) {
  const pts = c.points;
  const n = pts.length;
  const [lo, hi] = bounds(pts.map((p: any) => p.p).concat([0.2, 0.7]), 0.1);
  const y = yScale(lo, hi);
  const colorOf = (k: string) => k === 'dry' ? C.red : k === 'pending' ? C.axis : C.teal;
  // solid line up to the last real point, dotted to the pending one
  const realIdx = pts.findIndex((p: any) => p.kind === 'pending');
  const lastReal = realIdx < 0 ? n - 1 : realIdx - 1;
  const solid = pts.slice(0, lastReal + 1);
  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label={c.y_label}>
        <Grid />
        <YLabels lo={lo} hi={hi} side="left" fmt={(v) => v.toFixed(2)} />
        <polyline points={solid.map((p: any, i: number) => `${xAt(i, n)},${y(p.p)}`).join(' ')}
                  fill="none" stroke={C.teal} strokeWidth="2" strokeLinejoin="round" />
        {realIdx > 0 && (
          <line x1={xAt(lastReal, n)} y1={y(pts[lastReal].p)}
                x2={xAt(realIdx, n)} y2={y(pts[realIdx].p)}
                stroke={C.axis} strokeWidth="1.4" strokeDasharray="3 3" />
        )}
        {pts.map((p: any, i: number) => (
          <g key={i}>
            <circle cx={xAt(i, n)} cy={y(p.p)} r={p.kind === 'pending' ? 4 : 3.4}
                    fill={p.kind === 'pending' ? 'var(--surface)' : colorOf(p.kind)}
                    stroke={colorOf(p.kind)} strokeWidth={p.kind === 'pending' ? 1.4 : 0} />
            <text x={xAt(i, n)} y={y(p.p) - 9} textAnchor="middle" fontSize="9.5"
                  fill={C.ink} style={{ fontFeatureSettings: '"tnum" 1' }}>
              {p.kind === 'pending' ? '?' : p.p.toFixed(2)}
            </text>
            {String(p.label).split('(').map((ln: string, li: number) => (
              <text key={li} x={xAt(i, n)} y={H - 22 + li * 10} textAnchor="middle"
                    fontSize="8" fill={C.axis}>{li === 1 ? '(' + ln : ln}</text>
            ))}
          </g>
        ))}
      </svg>
      {c.prior && <p className="chart-note">Prior {c.prior} ≈ 1-in-5 frontier base rate; posterior updated per well result.</p>}
    </div>
  );
}

/* ============================================================
   Cross-page predictive logic map (static diagram)
   ============================================================ */
export function LogicMap() {
  return (
    <div className="logic-map">
      <div className="logic-row">
        <div className="logic-node node-green">
          <b>Drilling &amp; workovers</b><span>intervention activity</span>
        </div>
        <div className="logic-arrow">→</div>
        <div className="logic-node node-blue">
          <b>Production</b><span>crude + gas volumes</span>
        </div>
      </div>
      <div className="logic-row">
        <div className="logic-node node-green">
          <b>Exploratory meterage</b><span>wells + metres</span>
        </div>
        <div className="logic-arrow">→</div>
        <div className="logic-node node-green">
          <b>Reserve accretion</b><span>MMToE added / yr</span>
        </div>
        <div className="logic-arrow">→</div>
        <div className="logic-node node-amber">
          <b>RRR</b><span>connective KPI</span>
        </div>
      </div>
      <div className="logic-row logic-row-scenario">
        <div className="logic-node node-dashed">
          <b>Andaman scenario</b><span>unbooked · if materialised</span>
        </div>
        <div className="logic-arrow logic-arrow-dashed">⤏</div>
      </div>
      <p className="chart-note">
        RRR is the connective KPI — an outcome on Production, the target the accretion
        model solves for on Exploration, and the number the Andaman scenario could reset.
        Solid arrows are fitted/derivable relationships; the dashed arrow is scenario-only
        and never enters KPI math (booked = false enforcement).
      </p>
    </div>
  );
}

/* ============================================================
   Predictive claims inventory (static table)
   ============================================================ */
const CLAIMS = [
  ['1', 'FY27 production forecast (decline + intervention regression)', 'Fitted model', '§Forecast'],
  ['2', 'Monte-Carlo RRR trajectory — accretion uplift needed by FY28', 'Scenario simulation', '§RRR fan'],
  ['3', 'Reserve Life Index: oil ~20 yrs, gas ~44 yrs', 'Derived arithmetic', '§Reserves'],
  ['4', 'Gas share of output crossing 50% (organic vs Andaman)', 'Scenario simulation', '§Gasification'],
  ['5', 'Intervention ROI: tonnes per workover / per dev well → FY27 plan', 'Fitted model', '§Forecast'],
  ['6', 'NELP/OALP commitment-risk scoring', 'Scenario simulation', '§Exploration'],
  ['7', 'Exploration effectiveness → wells needed for RRR ≥ 1.0', 'Fitted model', '§Effectiveness'],
  ['8', 'Bayesian basin probability, updated per Andaman well', 'Scenario simulation', '§Andaman'],
  ['9', 'Hypothetical booking sensitivities (25/50/75 BCM analogs)', 'Scenario simulation', '§Andaman'],
  ['10', 'First gas ~FY32+ (frontier timeline norm)', 'Derived arithmetic', '§Andaman'],
];
export function ClaimsTable() {
  return (
    <table className="claims-table">
      <thead>
        <tr><th>#</th><th>Predictive claim</th><th>Tier</th><th>Shown in</th></tr>
      </thead>
      <tbody>
        {CLAIMS.map(([n, claim, tier, where]) => (
          <tr key={n}>
            <td>{n}</td>
            <td>{claim}</td>
            <td><span className={'claim-tier ' + (tier.startsWith('Fitted') ? 'tier-fitted' :
              tier.startsWith('Scenario') ? 'tier-scenario' : 'tier-derived')}>{tier}</span></td>
            <td>{where}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
