'use client';
import { useCallback, useEffect, useState } from 'react';
import Chat from '@/components/Chat';
import { Sidebar } from '@/components/Sidebar';
import { useConversations } from '@/lib/storage';

type Health = {
  status?: string;
  model?: string;
  anthropic_key_set?: boolean;
  vector_store?: { pq?: number; db?: number; error?: string };
};

const MOBILE_BREAKPOINT = 760;

export default function Home() {
  const {
    hydrated,
    conversations,
    activeId,
    activeConversation,
    setActiveId,
    createConversation,
    updateConversation,
    deleteConversation,
    renameConversation,
  } = useConversations();

  const [health, setHealth] = useState<Health | null>(null);
  const [collapsed, setCollapsed] = useState(false);     // desktop collapse state
  const [mobileOpen, setMobileOpen] = useState(false);   // mobile drawer state

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'down' }));
  }, []);

  // Cmd/Ctrl + K = new chat
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        createConversation();
        setMobileOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [createConversation]);

  // Close the drawer if the viewport grows past mobile width.
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > MOBILE_BREAKPOINT && mobileOpen) {
        setMobileOpen(false);
      }
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [mobileOpen]);

  // Lock body scroll while the drawer is open so the conversation behind it
  // doesn't scroll under the user's finger.
  useEffect(() => {
    if (mobileOpen) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [mobileOpen]);

  const onNew = useCallback(() => {
    createConversation();
    setMobileOpen(false);
  }, [createConversation]);

  const onSelect = useCallback(
    (id: string) => {
      setActiveId(id);
      setMobileOpen(false);
    },
    [setActiveId],
  );

  const ready =
    health?.status === 'ok' &&
    health.anthropic_key_set &&
    (health.vector_store?.pq ?? 0) > 0;

  const status = !health
    ? 'loading…'
    : health.anthropic_key_set === false
      ? 'API key missing'
      : ready
        ? 'ready'
        : 'starting…';

  return (
    <div className={`app-shell ${mobileOpen ? 'app-shell-drawer-open' : ''}`}>
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={onSelect}
        onNew={onNew}
        onDelete={deleteConversation}
        onRename={renameConversation}
        collapsed={collapsed}
        onToggle={() => setCollapsed(c => !c)}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      {/* Tap-outside backdrop for the mobile drawer */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <main className="main">
        <header className="topbar">
          <button
            className="topbar-burger"
            onClick={() => setMobileOpen(true)}
            aria-label="Open conversation history"
          >
            <BurgerIcon />
          </button>

          <div className="topbar-title">
            <h1>{activeConversation?.title ?? 'Oil India PQ Assistant'}</h1>
            <span className="topbar-sub">
              Parliamentary-response drafting, grounded in OIL's archive
            </span>
          </div>
          <div className="topbar-status">
            <span className={`status-dot status-${ready ? 'ok' : 'warn'}`} />
            <span className="status-text">
              {ready
                ? `${health!.vector_store?.pq ?? 0} PQs · ${health!.vector_store?.db ?? 0} DB`
                : status}
            </span>
          </div>
        </header>

        {hydrated ? (
          <Chat
            conversation={activeConversation}
            onCreateConversation={createConversation}
            onUpdateConversation={updateConversation}
          />
        ) : (
          <div className="hydrating" />
        )}
      </main>
    </div>
  );
}

function BurgerIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}
