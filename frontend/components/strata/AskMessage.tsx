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
import { useEffect, useState } from 'react';
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
  /** True while a report-intent turn is still streaming and the PDF hasn't
   *  arrived yet — shows the "building your report" loader for the whole wait. */
  reportPending?: boolean;
}

export function AskMessage({ msg, onOpenSource, reportPending }: AskMessageProps) {
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
  return <AiMessage msg={msg} onOpenSource={onOpenSource} reportPending={reportPending} />;
}

function VoiceBadge() {
  return (
    <span className="voice-badge" title="Said aloud">
      <span className="voice-badge-pulse" />
      voice
    </span>
  );
}

function AiMessage({ msg, onOpenSource, reportPending }: { msg: Extract<AskMsg, { role: 'ai' }>; onOpenSource?: (f: string) => void; reportPending?: boolean }) {
  const blocks = msg.blocks;
  const fullText = blocksToText(blocks);
  // Show the building loader through the whole report turn — but not once the
  // generate_report block exists (renderBlocks handles that → its own loader,
  // then the download card).
  const hasReportBlock = blocks.some(b => b.kind === 'tool' && b.name === 'generate_report');
  const showBuilding = !!reportPending && msg.streaming && !hasReportBlock;

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
        {blocks.length === 0 && msg.streaming && !showBuilding ? (
          <div className="msg-bubble msg-typing">
            <span className="answer-typing"><i/><i/><i/></span>
          </div>
        ) : (
          <div className="msg-bubble msg-rich">
            {renderBlocks(blocks, msg.streaming)}
            {showBuilding && <ReportBuilding />}
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
      if (b.name === 'generate_report') {
        flush(`b${i}`);
        const rurl = (b.result as any)?.report_url;
        if (rurl) {
          out.push(
            <ReportDownload key={`rep-${i}`}
              url={rurl as string}
              filename={((b.result as any)?.filename as string) || 'digby-report.pdf'}
              title={((b.result as any)?.title as string) || 'Report'} />,
          );
        } else if (b.status === 'error') {
          out.push(
            <div className="report-building report-building-err" key={`rbe-${i}`}>
              Report generation failed — please try again.
            </div>,
          );
        } else {
          out.push(<ReportBuilding key={`rb-${i}`} />);
        }
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

const BUILD_MSGS = [
  'Gathering OIL data across every source…',
  'Cross-checking the figures…',
  'Computing year-on-year trends…',
  'Writing the analysis…',
  'Drawing charts & graphs…',
  'Laying out the tables…',
  'Typesetting your report…',
  'Adding the finishing touches…',
];

function ReportBuilding() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI(v => (v + 1) % BUILD_MSGS.length), 1500);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="report-building" role="status" aria-live="polite">
      <span className="report-building-ico" aria-hidden>
        <span className="report-building-spin" />
        <Icon name="image" size={15} />
      </span>
      <span className="report-building-text">
        <span className="report-building-title">Building your report</span>
        {/* key=i restarts the fade each message */}
        <span className="report-building-msg" key={i}>{BUILD_MSGS[i]}</span>
      </span>
      <span className="report-building-dots" aria-hidden><i/><i/><i/></span>
    </div>
  );
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
