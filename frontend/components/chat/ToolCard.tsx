'use client';
import { useState } from 'react';
import type { AssistantBlock } from '@/lib/types';

type ToolBlock = Extract<AssistantBlock, { kind: 'tool' }>;

type Hit = {
  filename?: string;
  source?: string;
  session?: string;
  kind?: string;
  section?: string;
  score?: number;
  excerpt?: string;
};

const NICE_NAMES: Record<string, string> = {
  search_pq_archive: 'Parliamentary archive',
  search_oil_india_data: 'Oil India data',
  list_available_sources: 'Available sources',
};

function shortName(name: string): string {
  return NICE_NAMES[name] ?? name;
}

function countOf(block: ToolBlock): number {
  if (!block.result) return 0;
  if (typeof block.result.count === 'number') return block.result.count as number;
  const r = block.result.results;
  return Array.isArray(r) ? r.length : 0;
}

/** A display group = one chip. Consecutive `compute` calls collapse into a
 *  single group so a turn with 12 calculations shows one "compute ×12" chip
 *  instead of twelve "compute 0" chips. */
type ToolGroup = { key: string; name: string; blocks: ToolBlock[] };

function groupTools(tools: ToolBlock[]): ToolGroup[] {
  const groups: ToolGroup[] = [];
  for (const t of tools) {
    const last = groups[groups.length - 1];
    if (t.name === 'compute' && last && last.name === 'compute') {
      last.blocks.push(t);
    } else {
      groups.push({ key: t.id, name: t.name, blocks: [t] });
    }
  }
  return groups;
}

/**
 * Row of compact tool chips, with one expanded detail panel at a time.
 * Receives a group of consecutive tool blocks from Message.tsx.
 */
export function ToolRow({ tools }: { tools: ToolBlock[] }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const groups = groupTools(tools);
  const open = groups.find(g => g.key === openId) ?? null;

  return (
    <div className="tool-row">
      <div className="tool-chips">
        {groups.map(g => (
          <ToolChip
            key={g.key}
            group={g}
            active={g.key === openId}
            onToggle={() => setOpenId(openId === g.key ? null : g.key)}
          />
        ))}
      </div>
      {open && <ToolDetail group={open} />}
    </div>
  );
}

function ToolChip({
  group,
  active,
  onToggle,
}: {
  group: ToolGroup;
  active: boolean;
  onToggle: () => void;
}) {
  const isCompute = group.name === 'compute';
  // Any block still running / any errored bubbles up to the chip.
  const running = group.blocks.some(b => b.status === 'running');
  const err = group.blocks.some(b => b.status === 'error');
  const label = shortName(group.name);
  // compute → number of calculations; search → result count of the (single) call.
  const count = isCompute ? group.blocks.length : countOf(group.blocks[0]);
  const countText = isCompute ? `×${count}` : String(count);
  const showCount = !running && (isCompute || count > 0);

  return (
    <button
      className={`tool-chip ${active ? 'tool-chip-active' : ''} ${running ? 'tool-chip-running' : ''} ${err ? 'tool-chip-error' : ''}`}
      onClick={() => !running && onToggle()}
      title={
        running ? 'Working…'
        : isCompute ? `${count} calculation${count === 1 ? '' : 's'}`
        : `${label} · ${count} result${count === 1 ? '' : 's'}`
      }
    >
      <span className="tool-chip-icon">
        {running ? <Spinner /> : err ? '!' : isCompute ? <ComputeIcon /> : <SearchIcon />}
      </span>
      <span className="tool-chip-name">{label}</span>
      {showCount && (
        <span className="tool-chip-count">{countText}</span>
      )}
    </button>
  );
}

function ToolDetail({ group }: { group: ToolGroup }) {
  // compute group → show every expression = result
  if (group.name === 'compute') {
    return (
      <div className="tool-detail">
        <div className="tool-computes">
          {group.blocks.map((b, i) => {
            const expr = (b.args?.expression as string) || '';
            const res = b.result?.result_rounded ?? b.result?.result;
            const e = b.status === 'error' ? (b.result?.error as string) : null;
            return (
              <div className="tool-compute-row" key={i}>
                <code className="tool-compute-expr">{expr}</code>
                <span className="tool-compute-eq">=</span>
                <span className={`tool-compute-res ${e ? 'tool-compute-err' : ''}`}>
                  {e ? e : String(res ?? '—')}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  const block = group.blocks[0];
  const results: Hit[] = Array.isArray(block.result?.results)
    ? (block.result!.results as Hit[])
    : [];
  const query = (block.args?.query as string) || '';

  return (
    <div className="tool-detail">
      {query && (
        <div className="tool-detail-query">
          <span className="tool-detail-label">Query</span>
          <span className="tool-detail-value">“{query}”</span>
        </div>
      )}

      {block.status === 'done' && results.length > 0 && (
        <div className="tool-hits">
          {results.map((r, i) => (
            <div className="tool-hit" key={i}>
              <div className="tool-hit-meta">
                <span className="tool-hit-file">{r.filename}</span>
                {typeof r.score === 'number' && (
                  <span className="score-pill">{Math.round(r.score * 100)}%</span>
                )}
              </div>
              <div className="tool-hit-meta-2">
                {r.session && <span>📁 {r.session}</span>}
                {r.kind && r.kind !== 'other' && <span>· {r.kind}</span>}
                {r.section && <span>· {r.section}</span>}
              </div>
              <div className="tool-hit-excerpt">{r.excerpt}</div>
            </div>
          ))}
        </div>
      )}

      {block.status === 'done' && block.name === 'list_available_sources' && (
        <pre className="tool-args" style={{ maxHeight: 320, overflow: 'auto' }}>
          {JSON.stringify(block.result?.groups ?? {}, null, 2)}
        </pre>
      )}

      {block.status === 'done' && results.length === 0 && block.name !== 'list_available_sources' && (
        <div className="tool-empty">No results.</div>
      )}

      {block.status === 'error' && (
        <div className="tool-error">
          {(block.result?.error as string) || 'Tool call failed.'}
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function ComputeIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="3" width="16" height="18" rx="2.5" />
      <line x1="8" y1="7" x2="16" y2="7" />
      <line x1="8" y1="12" x2="8" y2="12" />
      <line x1="12" y1="12" x2="12" y2="12" />
      <line x1="16" y1="12" x2="16" y2="12" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="12" y1="16" x2="12" y2="16" />
    </svg>
  );
}
