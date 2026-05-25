'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { streamChat } from '@/lib/api';
import type { AssistantBlock, Message, WireEvent } from '@/lib/types';
import { MessageView } from './Message';
import { Composer } from './Composer';
import type { Conversation } from '@/lib/storage';
import { deriveTitle } from '@/lib/storage';

const SUGGESTIONS = [
  'Draft a reply about Oil India\'s crude oil production over the last 5 years.',
  'How did OIL respond to questions on Kerala-Konkan offshore exploration?',
  'Summarise OIL\'s drilling performance for FY 2025-26.',
  'What discoveries has OIL made in the last 5 years?',
];

type Props = {
  conversation: Conversation | null;
  onCreateConversation: () => Conversation;
  onUpdateConversation: (id: string, mutate: (c: Conversation) => Conversation) => void;
};

export default function Chat({
  conversation,
  onCreateConversation,
  onUpdateConversation,
}: Props) {
  const messages = conversation?.messages ?? [];
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new content.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Only autoscroll if the user is near the bottom already.
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
    if (nearBottom) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [messages, busy]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;

      // Ensure we have a conversation to write into.
      let conv = conversation;
      if (!conv) {
        conv = onCreateConversation();
      }
      const convId = conv.id;

      const userMsg: Message = { role: 'user', content: trimmed };
      const placeholder: Message = {
        role: 'assistant',
        blocks: [],
        citations: [],
        streaming: true,
      };
      const baseMessages = [...conv.messages, userMsg, placeholder];

      onUpdateConversation(convId, c => ({
        ...c,
        messages: baseMessages,
        title:
          c.messages.length === 0 ? deriveTitle(baseMessages) : c.title,
        updatedAt: Date.now(),
      }));
      setBusy(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      const history = baseMessages
        .filter((_, idx) => idx < baseMessages.length - 1) // strip placeholder
        .map(m =>
          m.role === 'user'
            ? { role: 'user' as const, content: m.content }
            : {
                role: 'assistant' as const,
                content: m.blocks
                  .filter((b): b is Extract<AssistantBlock, { kind: 'text' }> => b.kind === 'text')
                  .map(b => b.text)
                  .join('\n'),
              },
        );

      try {
        for await (const ev of streamChat(history, ctrl.signal)) {
          onUpdateConversation(convId, c => ({
            ...c,
            messages: applyEvent(c.messages, ev),
            updatedAt: Date.now(),
          }));
        }
      } catch (e: any) {
        onUpdateConversation(convId, c => ({
          ...c,
          messages: applyEvent(c.messages, {
            type: 'error',
            message: String(e?.message ?? e),
          }),
        }));
      } finally {
        onUpdateConversation(convId, c => ({
          ...c,
          messages: c.messages.map((m, i, arr) =>
            i === arr.length - 1 && m.role === 'assistant'
              ? { ...m, streaming: false }
              : m,
          ),
        }));
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, conversation, onCreateConversation, onUpdateConversation],
  );

  const stop = () => abortRef.current?.abort();

  return (
    <div className="chat-main">
      <div className="conversation" ref={scrollRef}>
        <div className="conversation-inner">
          {messages.length === 0 ? (
            <Empty onPick={send} />
          ) : (
            messages.map((m, i) => <MessageView key={i} msg={m} />)
          )}
        </div>
      </div>
      <Composer busy={busy} onSend={send} onStop={stop} />
    </div>
  );
}

function Empty({ onPick }: { onPick: (s: string) => void }) {
  return (
    <div className="empty">
      <div className="empty-mark">OI</div>
      <h2>How can I help you today?</h2>
      <p>
        Ask about past parliamentary replies, production figures, drilling
        performance, reserves, and more — answers are grounded in OIL's own
        documents with sources cited.
      </p>
      <div className="suggestions">
        {SUGGESTIONS.map(s => (
          <button key={s} className="suggestion" onClick={() => onPick(s)}>
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function applyEvent(messages: Message[], ev: WireEvent): Message[] {
  if (messages.length === 0) return messages;
  const out = [...messages];
  const idx = out.length - 1;
  const last = out[idx];
  if (!last || last.role !== 'assistant') return messages;

  const blocks = [...last.blocks];

  if (ev.type === 'text') {
    const tail = blocks[blocks.length - 1];
    if (tail && tail.kind === 'text') {
      blocks[blocks.length - 1] = { kind: 'text', text: tail.text + ev.delta };
    } else {
      blocks.push({ kind: 'text', text: ev.delta });
    }
    out[idx] = { ...last, blocks };
  } else if (ev.type === 'tool_call') {
    blocks.push({
      kind: 'tool',
      id: ev.id,
      name: ev.name,
      args: ev.args || {},
      result: null,
      status: 'running',
    });
    out[idx] = { ...last, blocks };
  } else if (ev.type === 'tool_result') {
    const i = blocks.findIndex(b => b.kind === 'tool' && b.id === ev.id);
    if (i >= 0) {
      const t = blocks[i] as Extract<AssistantBlock, { kind: 'tool' }>;
      blocks[i] = {
        ...t,
        result: ev.result,
        status: ev.result?.error ? 'error' : 'done',
      };
    } else {
      blocks.push({
        kind: 'tool',
        id: ev.id,
        name: ev.name,
        args: {},
        result: ev.result,
        status: ev.result?.error ? 'error' : 'done',
      });
    }
    out[idx] = { ...last, blocks };
  } else if (ev.type === 'done') {
    out[idx] = { ...last, blocks, citations: ev.citations || [], streaming: false };
  } else if (ev.type === 'error') {
    blocks.push({ kind: 'text', text: `\n\n_Error: ${ev.message}_` });
    out[idx] = { ...last, blocks, streaming: false };
  }
  return out;
}
