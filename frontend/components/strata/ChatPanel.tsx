'use client';
/**
 * ChatPanel — the persistent "Ask Strata" chat that lives in the left
 * column. Same wire model + rendering primitives as the legacy /chat and
 * the previous AskDock (markdown body via ReactMarkdown, tool chips via
 * the shared ToolRow, citation pills via AskMessage), just rehoused into
 * an always-open pane.
 *
 * Empty state shows suggestion chips and an empty-chat blurb. Once a
 * message is sent the empty state hides and the message column takes over.
 */
import { useEffect, useRef, useState } from 'react';

import { Icon } from './Icon';
import { AskMessage } from './AskMessage';
import {
  applyWireEvent,
  askStrata,
  loadThreads,
  relTime,
  saveThreads,
  type AskMessage as Msg,
  type Thread,
} from '@/lib/strata-chat';

interface Props {
  chips: string[];
}

type View = 'chat' | 'history';

function newId() {
  return 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function ChatPanel({ chips }: Props) {
  const [q, setQ] = useState('');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [view, setView] = useState<View>('chat');
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => setThreads(loadThreads()), []);

  useEffect(() => {
    if (!activeId || messages.length === 0) return;
    setThreads(prev => {
      const firstUser = messages.find(m => m.role === 'user');
      const title = (firstUser?.role === 'user' ? firstUser.text : 'Chat')
        .replace(/\s+/g, ' ')
        .slice(0, 60);
      const existing = prev.find(t => t.id === activeId);
      const updated: Thread = {
        id: activeId,
        title,
        messages,
        ts: existing ? existing.ts : Date.now(),
      };
      const next = [updated, ...prev.filter(t => t.id !== activeId)];
      saveThreads(next);
      return next;
    });
  }, [messages, activeId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  const hasMessages = messages.length > 0 || view === 'history';

  async function ask(question: string) {
    let id = activeId;
    if (!id) {
      id = newId();
      setActiveId(id);
    }
    setView('chat');
    setQ('');

    const historyBefore = messages;
    setMessages(m => [
      ...m,
      { role: 'user', text: question, ts: Date.now() },
      { role: 'ai', blocks: [], citations: [], streaming: true, ts: Date.now() },
    ]);
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await askStrata(
        historyBefore,
        question,
        ev =>
          setMessages(m => {
            if (m.length === 0) return m;
            const last = m[m.length - 1];
            if (last.role !== 'ai') return m;
            return [...m.slice(0, -1), applyWireEvent(last, ev)];
          }),
        ctrl.signal,
      );
    } catch (e: any) {
      setMessages(m => {
        if (m.length === 0) return m;
        const last = m[m.length - 1];
        if (last.role !== 'ai') return m;
        return [
          ...m.slice(0, -1),
          {
            ...last,
            blocks: [
              ...last.blocks,
              { kind: 'text', text: `\n\n_Error: ${String(e?.message ?? e)}_` },
            ],
            streaming: false,
          },
        ];
      });
    } finally {
      setMessages(m => {
        if (m.length === 0) return m;
        const last = m[m.length - 1];
        if (last.role !== 'ai' || !last.streaming) return m;
        return [...m.slice(0, -1), { ...last, streaming: false }];
      });
      setBusy(false);
      abortRef.current = null;
    }
  }

  function newChat() {
    abortRef.current?.abort();
    setBusy(false);
    setMessages([]);
    setActiveId(null);
    setView('chat');
    setQ('');
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  function openThread(t: Thread) {
    abortRef.current?.abort();
    setBusy(false);
    setActiveId(t.id);
    setMessages(t.messages);
    setView('chat');
  }

  function deleteThread(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    setThreads(prev => {
      const next = prev.filter(t => t.id !== id);
      saveThreads(next);
      return next;
    });
    if (id === activeId) newChat();
  }

  return (
    <aside className="chat-pane">
      <div className="chat-pane-head">
        {view === 'history' ? (
          <button className="chat-headbtn" onClick={() => setView('chat')}>
            <Icon name="back" size={15} /> Back to chat
          </button>
        ) : (
          <span className="chat-title">
            <span className="chat-glyph">
              <Icon name="spark" size={14} />
            </span>
            Ask Strata
          </span>
        )}
        <div className="chat-tools">
          <button className="chat-tool" onClick={newChat} title="New chat">
            <Icon name="plus" size={16} />
          </button>
          <button
            className={'chat-tool' + (view === 'history' ? ' is-on' : '')}
            onClick={() => setView(view === 'history' ? 'chat' : 'history')}
            title="History"
          >
            <Icon name="clock" size={16} />
            {threads.length > 0 && (
              <span className="tool-badge">{threads.length}</span>
            )}
          </button>
        </div>
      </div>

      <div className="chat-pane-body">
        {view === 'history' ? (
          <div className="chat-scroll history-scroll">
            {threads.length === 0 ? (
              <div className="history-empty">
                No past conversations yet. Anything you ask is saved here.
              </div>
            ) : (
              threads.map(t => (
                <button
                  key={t.id}
                  className={'history-row' + (t.id === activeId ? ' is-active' : '')}
                  onClick={() => openThread(t)}
                >
                  <span className="hr-glyph">
                    <Icon name="spark" size={13} />
                  </span>
                  <span className="hr-main">
                    <span className="hr-title">{t.title}</span>
                    <span className="hr-meta">
                      {t.messages.filter(m => m.role === 'user').length}{' '}
                      {t.messages.filter(m => m.role === 'user').length === 1
                        ? 'question'
                        : 'questions'}
                      {' · '}
                      {relTime(t.ts)}
                    </span>
                  </span>
                  <span
                    className="hr-del"
                    onClick={e => deleteThread(e, t.id)}
                    title="Delete"
                  >
                    <Icon name="trash" size={14} />
                  </span>
                </button>
              ))
            )}
          </div>
        ) : hasMessages ? (
          <div className="chat-scroll" ref={scrollRef}>
            {messages.map((m, i) => (
              <AskMessage key={i} msg={m} />
            ))}
          </div>
        ) : (
          <div className="chat-empty">
            <h3 className="serif chat-empty-title">Ask anything.</h3>
            <p className="chat-empty-sub">
              I can speak to production, reserves, safety, procurement, and
              workforce — grounded in OIL's own data, with sources cited.
            </p>
            <div className="chips">
              {chips.map(c => (
                <button key={c} className="chip" onClick={() => ask(c)}>
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <form
        className="chat-pane-form"
        onSubmit={e => {
          e.preventDefault();
          if (q.trim()) ask(q.trim());
        }}
      >
        <div className="askbar">
          <span className="ask-glyph">
            <Icon name="spark" size={16} />
          </span>
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder={hasMessages ? 'Ask a follow-up…' : 'Ask anything about the business…'}
            aria-label="Ask anything about the business"
          />
          <button
            type="submit"
            className="ask-send"
            aria-label="Ask"
            disabled={!q.trim() || busy}
          >
            <Icon name="send" size={17} />
          </button>
        </div>
        <p className="chat-pane-note">Advisory only — never acts without you</p>
      </form>
    </aside>
  );
}
