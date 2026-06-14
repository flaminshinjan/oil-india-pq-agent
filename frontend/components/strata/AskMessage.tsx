'use client';
/**
 * Renders a single "Ask Digby" message inside the dock's chat-sheet.
 * - user → light bubble on the right (Strata's accent-tinted style)
 * - ai   → spark glyph + markdown body + tool chips + citation pills
 *
 * For the markdown body we lean on react-markdown + remark-gfm — same as
 * the legacy /chat — so tables, lists, **bold**, and `code` all render
 * properly. Tool chips and citation pills reuse the chat primitives.
 */
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type { AssistantBlock } from '@/lib/types';
import type { AskMessage as AskMsg, Citation } from '@/lib/strata-chat';
import { blocksToText } from '@/lib/strata-chat';

import { Icon } from './Icon';
import { ToolRow } from '../chat/ToolCard';

type ToolBlock = Extract<AssistantBlock, { kind: 'tool' }>;

interface AskMessageProps {
  msg: AskMsg;
  onOpenSource?: (filename: string) => void;
}

export function AskMessage({ msg, onOpenSource }: AskMessageProps) {
  if (msg.role === 'user') {
    return (
      <div className={'msg msg-user' + (msg.via === 'voice' ? ' is-voice' : '')}>
        <div className="msg-col">
          {msg.images && msg.images.length > 0 && (
            <div className="msg-images">
              {msg.images.map((url, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={i} src={url} alt={`attachment ${i + 1}`} className="msg-image" />
              ))}
            </div>
          )}
          {(msg.text || msg.via === 'voice') && (
            <div className="msg-bubble">
              {msg.via === 'voice' && <VoiceBadge />}
              {msg.text}
            </div>
          )}
        </div>
      </div>
    );
  }
  return <AiMessage msg={msg} onOpenSource={onOpenSource} />;
}

function VoiceBadge() {
  return (
    <span className="voice-badge" title="Said aloud">
      <span className="voice-badge-pulse" />
      voice
    </span>
  );
}

function AiMessage({ msg, onOpenSource }: { msg: Extract<AskMsg, { role: 'ai' }>; onOpenSource?: (f: string) => void }) {
  const blocks = msg.blocks;
  const fullText = blocksToText(blocks);

  return (
    <div className={'msg msg-ai' + (msg.via === 'voice' ? ' is-voice' : '')}>
      <span className="msg-mark"><Icon name="spark" size={14} /></span>
      <div className="msg-col">
        {msg.via === 'voice' && (
          <div className="msg-voice-tag">
            <span className="voice-badge-pulse" />
            spoken reply
          </div>
        )}
        {blocks.length === 0 && msg.streaming ? (
          <div className="msg-bubble msg-typing">
            <span className="answer-typing"><i/><i/><i/></span>
          </div>
        ) : (
          <div className="msg-bubble msg-rich">
            {renderBlocks(blocks, msg.streaming)}
          </div>
        )}

        {!msg.streaming && msg.citations.length > 0 && (
          <Citations citations={msg.citations} onOpenSource={onOpenSource} />
        )}

        {!msg.streaming && fullText && (
          <CopyBtn text={fullText} />
        )}
      </div>
    </div>
  );
}

/**
 * Walk blocks in order; group consecutive tool blocks into a single
 * ToolRow (same shape the legacy chat uses), interleaved with markdown
 * text blocks.
 */
function renderBlocks(blocks: AssistantBlock[], streaming: boolean) {
  const out: React.ReactNode[] = [];
  let toolBuf: ToolBlock[] = [];

  const flush = (k: string) => {
    if (toolBuf.length === 0) return;
    out.push(<ToolRow key={`tr-${k}`} tools={toolBuf} />);
    toolBuf = [];
  };

  blocks.forEach((b, i) => {
    if (b.kind === 'tool') {
      const rurl = (b.result as any)?.report_url;
      if (b.name === 'generate_report' && rurl) {
        flush(`b${i}`);
        out.push(
          <ReportDownload key={`rep-${i}`}
            url={rurl as string}
            filename={((b.result as any)?.filename as string) || 'digby-report.pdf'}
            title={((b.result as any)?.title as string) || 'Report'} />,
        );
      } else {
        toolBuf.push(b);
      }
    } else {
      flush(`b${i}`);
      out.push(
        <div className="msg-prose" key={`t-${i}`}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{b.text}</ReactMarkdown>
          {streaming && i === blocks.length - 1 && <span className="caret" />}
        </div>,
      );
    }
  });
  flush('tail');
  return out;
}

function ReportDownload({ url, filename, title }: { url: string; filename: string; title: string }) {
  return (
    <a className="report-dl" href={url} download={filename} target="_blank" rel="noopener noreferrer">
      <span className="report-dl-ico" aria-hidden>↓</span>
      <span className="report-dl-text">
        <span className="report-dl-title">{title}</span>
        <span className="report-dl-sub">PDF report · {filename} · click to download</span>
      </span>
    </a>
  );
}

function Citations({ citations, onOpenSource }: { citations: Citation[]; onOpenSource?: (f: string) => void }) {
  const [open, setOpen] = useState(false);
  const visible = open ? citations : citations.slice(0, 1);
  const hidden = citations.length - visible.length;

  return (
    <div className="cit-row">
      <span className="cit-row-label">Sources</span>
      {visible.map((c, i) => (
        <button
          key={i}
          className="cit cit-button"
          type="button"
          onClick={() => onOpenSource?.(c.filename)}
          title={`${c.filename}${c.buckets ? ' · ' + c.buckets : ''}${c.section ? ' · ' + c.section : ''}\nClick to preview`}
        >
          <span className="cit-name">{c.filename}</span>
          {c.buckets && (
            <span className="cit-buckets">
              {c.buckets.split(',').filter(Boolean).slice(0, 2).map(b => (
                <span key={b} className="cit-bucket">{b}</span>
              ))}
            </span>
          )}
        </button>
      ))}
      {hidden > 0 && (
        <button className="cit cit-more" onClick={() => setOpen(true)}>
          +{hidden} more
        </button>
      )}
      {open && citations.length > 1 && (
        <button className="cit cit-more" onClick={() => setOpen(false)}>
          hide
        </button>
      )}
    </div>
  );
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="msg-copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {/* ignore */}
      }}
    >
      <Icon name={copied ? 'check' : 'copy'} size={12} />
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}
