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

/**
 * Row of compact tool chips, with one expanded detail panel at a time.
 * Receives a group of consecutive tool blocks from Message.tsx.
 */
export function ToolRow({ tools }: { tools: ToolBlock[] }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const open = tools.find(t => t.id === openId) ?? null;

  return (
    <div className="tool-row">
      <div className="tool-chips">
        {tools.map(t => (
          <ToolChip
            key={t.id}
            block={t}
            active={t.id === openId}
            onToggle={() => setOpenId(openId === t.id ? null : t.id)}
          />
        ))}
      </div>
      {open && <ToolDetail block={open} />}
    </div>
  );
}

function ToolChip({
  block,
  active,
  onToggle,
}: {
  block: ToolBlock;
  active: boolean;
  onToggle: () => void;
}) {
  const running = block.status === 'running';
  const err = block.status === 'error';
  const count = countOf(block);
  const label = shortName(block.name);

  return (
    <button
      className={`tool-chip ${active ? 'tool-chip-active' : ''} ${running ? 'tool-chip-running' : ''} ${err ? 'tool-chip-error' : ''}`}
      onClick={() => !running && onToggle()}
      title={running ? 'Searching…' : `${label} · ${count} result${count === 1 ? '' : 's'}`}
    >
      <span className="tool-chip-icon">
        {running ? <Spinner /> : err ? '!' : <SearchIcon />}
      </span>
      <span className="tool-chip-name">{label}</span>
      {!running && (
        <span className="tool-chip-count">{count}</span>
      )}
    </button>
  );
}

function ToolDetail({ block }: { block: ToolBlock }) {
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
