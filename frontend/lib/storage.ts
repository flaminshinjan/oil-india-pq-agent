'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Message } from './types';

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = 'oil-india-conversations.v1';
const ACTIVE_KEY = 'oil-india-active.v1';

/* ---------- low-level localStorage helpers ---------- */

function safeRead<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function safeWrite(key: string, value: unknown): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota errors — the user will just lose old history */
  }
}

/* ---------- utilities ---------- */

export function newId(): string {
  // Short, sortable, no external dep.
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

export function deriveTitle(messages: Message[]): string {
  const firstUser = messages.find(m => m.role === 'user');
  if (!firstUser) return 'New chat';
  const text = firstUser.content.trim().replace(/\s+/g, ' ');
  return text.length > 60 ? text.slice(0, 57) + '…' : text || 'New chat';
}

export function groupByDate(convos: Conversation[]): {
  label: string;
  items: Conversation[];
}[] {
  const now = new Date();
  const startOfDay = (d: Date) => {
    const c = new Date(d);
    c.setHours(0, 0, 0, 0);
    return c.getTime();
  };
  const today = startOfDay(now);
  const yesterday = today - 86400000;
  const sevenDaysAgo = today - 7 * 86400000;
  const thirtyDaysAgo = today - 30 * 86400000;

  const buckets: Record<string, Conversation[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 days': [],
    'Previous 30 days': [],
    Older: [],
  };

  for (const c of convos) {
    const t = c.updatedAt;
    if (t >= today) buckets.Today.push(c);
    else if (t >= yesterday) buckets.Yesterday.push(c);
    else if (t >= sevenDaysAgo) buckets['Previous 7 days'].push(c);
    else if (t >= thirtyDaysAgo) buckets['Previous 30 days'].push(c);
    else buckets.Older.push(c);
  }

  return Object.entries(buckets)
    .filter(([, v]) => v.length > 0)
    .map(([label, items]) => ({ label, items }));
}

/* ---------- hook ---------- */

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate from localStorage exactly once on the client.
  useEffect(() => {
    const stored = safeRead<Conversation[]>(STORAGE_KEY, []);
    const lastActive = safeRead<string | null>(ACTIVE_KEY, null);
    setConversations(stored.sort((a, b) => b.updatedAt - a.updatedAt));
    if (lastActive && stored.some(c => c.id === lastActive)) {
      setActiveIdState(lastActive);
    }
    setHydrated(true);
  }, []);

  // Persist on change (skip until hydrated to avoid wiping on first paint).
  const firstRun = useRef(true);
  useEffect(() => {
    if (!hydrated) return;
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    safeWrite(STORAGE_KEY, conversations);
  }, [conversations, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    safeWrite(ACTIVE_KEY, activeId);
  }, [activeId, hydrated]);

  const setActiveId = useCallback((id: string | null) => {
    setActiveIdState(id);
  }, []);

  const createConversation = useCallback((): Conversation => {
    const conv: Conversation = {
      id: newId(),
      title: 'New chat',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setConversations(prev => [conv, ...prev]);
    setActiveIdState(conv.id);
    return conv;
  }, []);

  const updateConversation = useCallback(
    (id: string, mutate: (c: Conversation) => Conversation) => {
      setConversations(prev => {
        const out = prev.map(c => (c.id === id ? mutate(c) : c));
        return out.sort((a, b) => b.updatedAt - a.updatedAt);
      });
    },
    [],
  );

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations(prev => prev.filter(c => c.id !== id));
      setActiveIdState(curr => (curr === id ? null : curr));
    },
    [],
  );

  const renameConversation = useCallback(
    (id: string, title: string) => {
      updateConversation(id, c => ({ ...c, title, updatedAt: Date.now() }));
    },
    [updateConversation],
  );

  const clearAll = useCallback(() => {
    setConversations([]);
    setActiveIdState(null);
  }, []);

  const activeConversation =
    conversations.find(c => c.id === activeId) ?? null;

  return {
    hydrated,
    conversations,
    activeId,
    activeConversation,
    setActiveId,
    createConversation,
    updateConversation,
    deleteConversation,
    renameConversation,
    clearAll,
  };
}
