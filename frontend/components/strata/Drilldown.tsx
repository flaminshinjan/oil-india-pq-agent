'use client';
/**
 * Drilldown — bottom-sheet detail panel.
 *
 * Slides up from the bottom of the viewport when a brief card is opened.
 * Covers ~88vh, the rest fades through a backdrop so the page underneath
 * stays visible. Closes on:
 *   - Esc
 *   - backdrop click
 *   - the explicit Close button
 *   - the small drag handle (click)
 *
 * Animated in with a 220 ms ease-out translate + backdrop fade, animated
 * out via the `is-closing` class (240 ms).
 */
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Icon } from './Icon';

export interface DrilldownRef {
  filename?: string;
  source?: string;
  section?: string;
}

export interface DrilldownSection {
  eyebrow?: string;
  title?: string;
  body: string;
  refs?: DrilldownRef[];
}

export interface DrilldownData {
  tag: string;
  eyebrow?: string;
  title: string;
  lead: string;
  sections: DrilldownSection[];
  sources: string[];
  agent?: string;
}

interface Props {
  data: DrilldownData;
  onClose: () => void;
  /** Optional handler to open a source PDF in the side panel. */
  onOpenSource?: (filename: string) => void;
}

export function Drilldown({ data, onClose, onOpenSource }: Props) {
  const [closing, setClosing] = useState(false);
  const [dragY, setDragY] = useState(0);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<{ startY: number; pointerId: number } | null>(null);

  const handleClose = () => {
    if (closing) return;
    setClosing(true);
    // Match the close animation duration in CSS (220 ms).
    window.setTimeout(onClose, 220);
  };

  // ---- Drag-down to dismiss ----
  // Pointer down on the handle (or top header area) starts the drag.
  // While dragging, we translate the sheet by the delta Y (only positive).
  // On release, if the drag exceeded 110 px OR the velocity was sharp, we
  // close; otherwise we snap back to 0.
  const onDragStart = (e: React.PointerEvent<HTMLElement>) => {
    if (closing) return;
    dragStateRef.current = { startY: e.clientY, pointerId: e.pointerId };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onDragMove = (e: React.PointerEvent<HTMLElement>) => {
    const st = dragStateRef.current;
    if (!st || st.pointerId !== e.pointerId) return;
    const dy = Math.max(0, e.clientY - st.startY);
    setDragY(dy);
  };
  const onDragEnd = (e: React.PointerEvent<HTMLElement>) => {
    const st = dragStateRef.current;
    if (!st || st.pointerId !== e.pointerId) return;
    const dy = Math.max(0, e.clientY - st.startY);
    dragStateRef.current = null;
    try { e.currentTarget.releasePointerCapture?.(e.pointerId); } catch {/* noop */}
    if (dy > 110) {
      handleClose();
    } else {
      setDragY(0);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={'sheet-portal' + (closing ? ' is-closing' : '')}
      role="dialog"
      aria-modal="true"
      aria-label={data.title}
    >
      <button
        className="sheet-backdrop"
        aria-label="Close detail"
        onClick={handleClose}
      />
      <div
        ref={sheetRef}
        className="sheet"
        onClick={e => e.stopPropagation()}
        style={dragY > 0 ? { transform: `translateY(${dragY}px)`, transition: 'none' } : undefined}
      >
        <div
          className="sheet-drag-zone"
          onPointerDown={onDragStart}
          onPointerMove={onDragMove}
          onPointerUp={onDragEnd}
          onPointerCancel={onDragEnd}
          role="button"
          tabIndex={-1}
          aria-label="Drag down to dismiss"
        >
          <span className="sheet-handle-bar" />
        </div>

        <header className="sheet-head">
          <div className="sheet-head-meta">
            <span className="tag sheet-tag">{data.tag}</span>
            {data.eyebrow && <span className="eyebrow">{data.eyebrow}</span>}
          </div>
          <button
            className="sheet-close"
            aria-label="Close"
            onClick={handleClose}
            title="Close (Esc)"
          >
            <Icon name="close" size={15} />
          </button>
        </header>

        <div className="sheet-body">
          <h1 className="serif sheet-title">{stripMd(data.title)}</h1>
          <div className="sheet-lead md-rich">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.lead}</ReactMarkdown>
          </div>

          {data.sections.length > 0 && (
            <section className="sheet-sections">
              {data.sections.map((s, i) => (
                <div className="sheet-block" key={i}>
                  {s.eyebrow && <span className="eyebrow">{s.eyebrow}</span>}
                  {s.title && (
                    <h2 className="serif sheet-section-title">{stripMd(s.title)}</h2>
                  )}
                  <div className="md-rich">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.body}</ReactMarkdown>
                  </div>
                  {s.refs && s.refs.length > 0 && (
                    <div className="sheet-section-refs">
                      {s.refs.map((r, j) =>
                        r.filename ? (
                          <button
                            type="button"
                            className="ref-chip ref-chip-button"
                            key={j}
                            title={`${r.filename}${r.source ? '\n' + r.source : ''}\nClick to preview`}
                            onClick={() => onOpenSource?.(r.filename!)}
                          >
                            {r.filename}
                          </button>
                        ) : null,
                      )}
                    </div>
                  )}
                </div>
              ))}
            </section>
          )}

          {data.sources.length > 0 && (
            <footer className="provenance sheet-prov">
              <span className="prov-label eyebrow">Every number above traces to a source</span>
              <ul className="prov-list">
                {data.sources.map(s => (
                  <li key={s}>
                    <span className="prov-dot" />
                    <button
                      type="button"
                      className="prov-file prov-file-button"
                      onClick={() => onOpenSource?.(s)}
                      title="Click to preview the source"
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </footer>
          )}
        </div>
      </div>
    </div>
  );
}

function stripMd(s: string): string {
  return s.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1');
}
