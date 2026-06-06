'use client';
/**
 * Layer-3 drill-down — full-viewport overlay that explains a brief card.
 *
 * The data is built dynamically from whichever signals back the card the
 * user clicked. Nothing is hardcoded — `lead` and each `section.body` come
 * straight from the LLM-generated signal text, and `sources` is the union
 * of every `refs[].filename` we touched.
 */
import { useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Icon } from './Icon';

export interface DrilldownRef {
  filename?: string;
  source?: string;
  section?: string;
}

export interface DrilldownSection {
  eyebrow?: string;       // "Drilling agent", "HSE feed", etc.
  title?: string;
  body: string;           // markdown
  refs?: DrilldownRef[];
}

export interface DrilldownData {
  tag: string;            // e.g. "Reserves · Drilling"
  eyebrow?: string;       // "Show me why" / "Open detail"
  title: string;
  lead: string;           // markdown — the headline body
  sections: DrilldownSection[];
  sources: string[];      // unique filenames cited anywhere
}

interface Props {
  data: DrilldownData;
  onClose: () => void;
}

export function Drilldown({ data, onClose }: Props) {
  // Esc to close, lock body scroll while open, scroll the overlay to top.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div className="layer3" role="dialog" aria-modal="true">
      <div className="l3-bar">
        <div className="l3-bar-in">
          <button className="back-link" onClick={onClose}>
            <span className="back-arr">
              <Icon name="arrow" size={15} />
            </span>{' '}
            Back to brief
          </button>
          <span className="tag l3-tag">{data.tag}</span>
        </div>
      </div>

      <div className="l3-col">
        <header className="l3-head">
          {data.eyebrow && <span className="eyebrow">{data.eyebrow}</span>}
          <h1 className="serif l3-title">{data.title}</h1>
          <div className="l3-lead">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.lead}</ReactMarkdown>
          </div>
        </header>

        {data.sections.length > 0 && (
          <section className="l3-sections">
            {data.sections.map((s, i) => (
              <div className="l3-block" key={i}>
                {s.eyebrow && <span className="eyebrow l3-section-eyebrow">{s.eyebrow}</span>}
                {s.title && <h2 className="serif l3-section-title">{s.title}</h2>}
                <div className="l3-note l3-section-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.body}</ReactMarkdown>
                </div>
                {s.refs && s.refs.length > 0 && (
                  <div className="l3-section-refs">
                    {s.refs.map((r, j) => (
                      <span className="ref-chip" key={j} title={r.source ?? ''}>
                        {r.filename}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </section>
        )}

        {data.sources.length > 0 && (
          <footer className="provenance">
            <span className="prov-label eyebrow">Every number above traces to a source</span>
            <ul className="prov-list">
              {data.sources.map(s => (
                <li key={s}>
                  <span className="prov-dot" />
                  <span className="prov-file">{s}</span>
                </li>
              ))}
            </ul>
          </footer>
        )}
      </div>
    </div>
  );
}
