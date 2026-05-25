'use client';
import { useState } from 'react';
import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AssistantBlock, Message } from '@/lib/types';
import { ToolRow } from './ToolCard';

type ToolBlock = Extract<AssistantBlock, { kind: 'tool' }>;
type TextBlock = Extract<AssistantBlock, { kind: 'text' }>;

export function MessageView({ msg }: { msg: Message }) {
  if (msg.role === 'user') {
    return (
      <div className="msg msg-user">
        <div className="bubble">{msg.content}</div>
      </div>
    );
  }

  const fullText = msg.blocks
    .filter((b): b is TextBlock => b.kind === 'text')
    .map(b => b.text)
    .join('\n');

  return (
    <div className="msg msg-assistant">
      <div className="msg-avatar">OI</div>
      <div className="msg-body">
        {renderBlocks(msg.blocks, msg.streaming)}

        {msg.streaming && msg.blocks.length === 0 && (
          <div className="thinking">
            <div className="dots"><span /><span /><span /></div>
            <span>Thinking…</span>
          </div>
        )}

        {!msg.streaming && msg.citations.length > 0 && (
          <Citations citations={msg.citations} />
        )}

        {!msg.streaming && fullText && (
          <div className="msg-actions">
            <CopyButton text={fullText} />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Walk blocks in order; group consecutive tool blocks into a single ToolRow
 * so they render as a row of compact chips instead of one card per call.
 */
function renderBlocks(blocks: AssistantBlock[], streaming: boolean): ReactNode[] {
  const out: ReactNode[] = [];
  let toolBuf: ToolBlock[] = [];

  const flushTools = (keySeed: number) => {
    if (toolBuf.length === 0) return;
    out.push(<ToolRow key={`tools-${keySeed}`} tools={toolBuf} />);
    toolBuf = [];
  };

  blocks.forEach((b, i) => {
    if (b.kind === 'tool') {
      toolBuf.push(b);
    } else {
      flushTools(i);
      out.push(
        <div className="msg-text" key={`text-${i}`}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{b.text}</ReactMarkdown>
          {streaming && i === blocks.length - 1 && <span className="caret" />}
        </div>,
      );
    }
  });
  flushTools(blocks.length);
  return out;
}

function Citations({
  citations,
}: {
  citations: { filename: string; source: string; section?: string; session?: string }[];
}) {
  const [open, setOpen] = useState(false);
  const visible = open ? citations : citations.slice(0, 1);
  const hidden = citations.length - visible.length;

  return (
    <div className="citations">
      <span className="citations-label">Sources</span>
      <div className="citations-list">
        {visible.map((c, i) => (
          <span
            className="cit"
            key={i}
            title={`${c.filename}${c.section ? ' · ' + c.section : ''}\n${c.source}`}
          >
            <span className="cit-name">{c.filename}</span>
          </span>
        ))}
        {hidden > 0 && (
          <button className="cit cit-more" onClick={() => setOpen(true)} title={`Show ${hidden} more`}>
            +{hidden} more
          </button>
        )}
        {open && citations.length > 1 && (
          <button className="cit cit-more" onClick={() => setOpen(false)} title="Collapse">
            Hide
          </button>
        )}
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="msg-action"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {
          /* ignore */
        }
      }}
      title="Copy reply"
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}
