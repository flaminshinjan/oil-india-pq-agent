'use client';
/**
 * Side panel that previews one OIL source file.
 *
 *   /api/sources/file/<filename>  ← served by the backend (PDF inline,
 *                                    docx / xlsx as a download)
 *
 * PDFs use the browser's built-in viewer via an iframe (no react-pdf, no
 * worker setup). For non-PDF citations (docx, xlsx, etc.) we surface a
 * friendly card with a "download" + "open in new tab" CTA, because no
 * mainstream browser previews those types inline.
 */
import { useEffect, useMemo, useState } from 'react';

import { Icon } from './Icon';

interface Props {
  filename: string | null;
  onClose: () => void;
}

type Status = 'loading' | 'ready' | 'missing';

function extOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot + 1).toLowerCase();
}

function friendlyKind(ext: string): string {
  switch (ext) {
    case 'pdf':  return 'PDF';
    case 'docx': return 'Word document';
    case 'doc':  return 'Word document';
    case 'xlsx': return 'Excel workbook';
    case 'xls':  return 'Excel workbook';
    case 'csv':  return 'CSV table';
    case 'json': return 'JSON data file';
    default:     return ext ? ext.toUpperCase() + ' file' : 'document';
  }
}

export function SourcePreview({ filename, onClose }: Props) {
  const [status, setStatus] = useState<Status>('loading');
  const [sizeBytes, setSizeBytes] = useState<number | null>(null);

  const url = filename
    ? `/api/sources/file/${encodeURIComponent(filename)}`
    : '';
  const ext = useMemo(() => (filename ? extOf(filename) : ''), [filename]);
  const isPdf = ext === 'pdf';

  useEffect(() => {
    if (!filename) return;
    setStatus('loading');
    setSizeBytes(null);
    fetch(url, { method: 'HEAD' })
      .then(r => {
        if (!r.ok) {
          setStatus('missing');
          return;
        }
        const cl = r.headers.get('content-length');
        if (cl) setSizeBytes(Number(cl));
        setStatus('ready');
      })
      .catch(() => setStatus('missing'));
  }, [filename, url]);

  useEffect(() => {
    if (!filename) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [filename, onClose]);

  if (!filename) return null;

  return (
    <aside className="src-panel" role="complementary" aria-label="Source document">
      <header className="src-head">
        <div className="src-head-meta">
          <span className="eyebrow">Source · {friendlyKind(ext)}</span>
          <div className="src-head-name" title={filename}>{filename}</div>
        </div>
        <div className="src-head-actions">
          <a
            className="src-action"
            href={url}
            target="_blank"
            rel="noreferrer"
            title="Open in new tab"
          >
            <Icon name="arrow" size={14} />
          </a>
          <button className="src-close" onClick={onClose} aria-label="Close source preview">
            <Icon name="close" size={15} />
          </button>
        </div>
      </header>

      <div className="src-body">
        {status === 'loading' && (
          <div className="src-status">Loading {filename}…</div>
        )}

        {status === 'missing' && (
          <div className="src-card">
            <div className="src-card-glyph"><Icon name="spark" size={18} /></div>
            <h3 className="serif src-card-title">Source not bundled</h3>
            <p className="src-card-body">
              The chat agent cites <strong>{filename}</strong> from the
              search index, but the raw file isn’t served by this demo
              build.
            </p>
          </div>
        )}

        {status === 'ready' && isPdf && (
          <iframe
            className="src-iframe"
            src={url}
            title={filename}
          />
        )}

        {status === 'ready' && !isPdf && (
          <div className="src-card">
            <div className="src-card-glyph">{ext.toUpperCase().slice(0, 4)}</div>
            <h3 className="serif src-card-title">{friendlyKind(ext)}</h3>
            <p className="src-card-body">
              <strong>{filename}</strong>
              {sizeBytes != null && ` · ${formatBytes(sizeBytes)}`}
            </p>
            <p className="src-card-hint">
              {ext === 'docx' || ext === 'doc'
                ? 'Word documents can’t render inline in the browser. Download or open externally to read the full text.'
                : ext === 'xlsx' || ext === 'xls'
                ? 'Excel workbooks open best in their native app or Google Sheets.'
                : 'This file type doesn’t preview inline — download to view.'}
            </p>
            <div className="src-card-actions">
              <a
                className="src-card-cta src-card-cta-primary"
                href={url}
                download={filename}
              >
                <Icon name="arrow" size={13} /> Download
              </a>
              <a
                className="src-card-cta"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                Open in new tab
              </a>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}
