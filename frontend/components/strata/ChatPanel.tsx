'use client';
/**
 * ChatPanel — the persistent "Ask Strata" chat that lives in the left
 * column. The history view is a small popover anchored to the clock
 * button in the header (no longer takes over the whole chat area).
 */
import { useEffect, useRef, useState } from 'react';

import { Icon } from './Icon';
import { AskMessage } from './AskMessage';
import { VoiceButton } from './VoiceButton';
import {
  applyWireEvent,
  askStrata,
  loadThreads,
  relTime,
  saveThreads,
  type AskMessage as Msg,
  type Thread,
} from '@/lib/strata-chat';

import type { DomainKey } from './DomainSelector';

interface Props {
  chips: string[];
  /** Currently active dashboard — drives the suggestion-chip set and
   *  the implicit "what dashboard is the chairman looking at" hint
   *  sent to the voice pipeline. */
  domain?: DomainKey;
  /** Called when the user clicks a citation pill — opens the side
   *  panel preview at page level. */
  onOpenSource?: (filename: string) => void;
  /** Mobile sheet state — driven by the page so we can show a close
   *  button inside the chat header. Desktop ignores both. */
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

const CHIPS_BY_DOMAIN: Record<string, string[]> = {
  brief:       ['How are we tracking vs target?', 'Where are we losing against plan?', 'Biggest risk to reserves?'],
  production:  ['Are we hitting 4 MMT crude target?', 'Which state is short of plan?', 'What is dragging gas output?'],
  exploration: ['How many wells are we behind plan?', 'What is the Andaman status?', 'Where is the latest discovery?'],
  hse:         ['Which site has most PPE flags?', 'How long since last LTI?', 'What is our LTIFR trend?'],
  hr:          ['Where is attrition highest?', 'Open requisitions by function?', 'How are we tracking on diversity?'],
  procurement: ['What is OIL’s MSE procurement share?', 'How much went through GeM last year?', 'Any high-severity deviations in the demo PR?'],
  finance:     ['Show me the 5-year capex trend.', 'PBT FY25 vs FY24?', 'What’s the CSR spend trajectory?'],
};

function newId() {
  return 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

export function ChatPanel({ chips, domain, onOpenSource, mobileOpen, onMobileClose }: Props) {
  const [q, setQ] = useState('');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  // The user explicitly collapsed the expanded chat — we still want
  // the conversation visible in the small panel; "+ New chat" is the
  // only thing that should wipe messages.
  const [collapsedManually, setCollapsedManually] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const historyBtnRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);

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

  // Close the popover on outside click / Esc.
  useEffect(() => {
    if (!historyOpen) return;
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (popoverRef.current?.contains(target)) return;
      if (historyBtnRef.current?.contains(target)) return;
      setHistoryOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setHistoryOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [historyOpen]);

  const hasMessages = messages.length > 0;
  const isExpanded = hasMessages && !collapsedManually;

  async function ask(question: string) {
    let id = activeId;
    if (!id) {
      id = newId();
      setActiveId(id);
    }
    setHistoryOpen(false);
    setQ('');
    // Any new question re-expands the chat — the user is talking again.
    setCollapsedManually(false);

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
    setHistoryOpen(false);
    setCollapsedManually(false);
    setQ('');
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  /** Voice session pushes transcripts in here. Only finals become chat
   *  bubbles — the voice button's pulsing ring is sufficient feedback
   *  while the user is mid-sentence. */
  function onVoiceTranscript(text: string, role: 'user' | 'ai', final: boolean) {
    if (!final) return;
    if (!activeId) setActiveId(newId());
    if (role === 'user') {
      setMessages(m => [...m, { role: 'user', text, ts: Date.now(), via: 'voice' }]);
    } else {
      setMessages(m => [
        ...m,
        {
          role: 'ai',
          blocks: [{ kind: 'text', text }],
          citations: [],
          streaming: false,
          ts: Date.now(),
          via: 'voice',
        },
      ]);
    }
  }

  function openThread(t: Thread) {
    abortRef.current?.abort();
    setBusy(false);
    setActiveId(t.id);
    setMessages(t.messages);
    setHistoryOpen(false);
    setCollapsedManually(false);
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
    <aside
      className={
        'chat-pane'
        + (mobileOpen ? ' is-mobile-open' : '')
        + (isExpanded ? ' is-expanded' : '')
      }
    >
      <div className="chat-pane-head">
        <span className="chat-title">
          <span className="chat-glyph">
            <Icon name="spark" size={14} />
          </span>
          Ask Strata
        </span>
        <div className="chat-tools">
          {isExpanded && (
            <button
              className="chat-tool chat-tool-collapse"
              onClick={() => setCollapsedManually(true)}
              title="Collapse chat (keep history)"
              aria-label="Collapse chat"
            >
              <Icon name="close" size={16} />
            </button>
          )}
          {onMobileClose && (
            <button
              className="chat-tool chat-tool-mobile-close"
              onClick={onMobileClose}
              title="Close chat"
              aria-label="Close chat"
            >
              <Icon name="close" size={16} />
            </button>
          )}
          <button className="chat-tool" onClick={newChat} title="New chat">
            <Icon name="plus" size={16} />
          </button>
          <button
            ref={historyBtnRef}
            className={'chat-tool' + (historyOpen ? ' is-on' : '')}
            onClick={() => setHistoryOpen(v => !v)}
            title="History"
            aria-haspopup="dialog"
            aria-expanded={historyOpen}
          >
            <Icon name="clock" size={16} />
            {threads.length > 0 && (
              <span className="tool-badge">{threads.length}</span>
            )}
          </button>
        </div>

        {historyOpen && (
          <div
            className="history-pop"
            ref={popoverRef}
            role="dialog"
            aria-label="Conversation history"
          >
            <div className="history-pop-head">
              <span className="eyebrow">Recent conversations</span>
              <button
                className="ghost-btn"
                onClick={() => setHistoryOpen(false)}
                title="Close"
              >
                <Icon name="close" size={14} />
              </button>
            </div>
            <div className="history-pop-list">
              {threads.length === 0 ? (
                <div className="history-empty">
                  No past conversations yet. Anything you ask is saved here.
                </div>
              ) : (
                threads.map(t => (
                  <button
                    key={t.id}
                    className={
                      'history-row' + (t.id === activeId ? ' is-active' : '')
                    }
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
          </div>
        )}
      </div>

      <div className="chat-pane-body">
        {hasMessages ? (
          <div className="chat-scroll" ref={scrollRef}>
            {messages.map((m, i) => (
              <AskMessage key={i} msg={m} onOpenSource={onOpenSource} />
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
              {(CHIPS_BY_DOMAIN[domain || 'brief'] || chips).map(c => (
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
          <VoiceButton onTranscript={onVoiceTranscript} domain={domain} />
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
