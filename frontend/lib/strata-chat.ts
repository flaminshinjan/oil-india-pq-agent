/**
 * Strata's "Ask Strata" embedded chat.
 *
 * Each chat message can be a user bubble (just text) OR an AI bubble that's
 * a structured stream of blocks: prose text, tool-call cards, and a final
 * citations array. We mirror the legacy /chat message model so the AskDock
 * can reuse the same markdown + tool-chip + citation pill primitives.
 */

import { streamChat } from './api';
import type { AssistantBlock, WireEvent } from './types';

export interface Citation {
  filename: string;
  source: string;
  section?: string;
  session?: string;
  tool?: string;
}

export type AskMessage =
  | { role: 'user'; text: string; ts: number }
  | {
      role: 'ai';
      blocks: AssistantBlock[];
      citations: Citation[];
      streaming: boolean;
      ts: number;
    };

export interface Thread {
  id: string;
  title: string;
  messages: AskMessage[];
  ts: number;
}

/* v2 store — the on-disk shape changed (text → blocks) so we bump the
 * version key. v1 threads will be ignored on load (loss-of-history is fine
 * for a demo). */
const STORE_KEY = 'strata.chat.threads.v2';

/* ---------------- thread persistence ---------------- */

export function loadThreads(): Thread[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Thread[]) : [];
  } catch {
    return [];
  }
}

export function saveThreads(t: Thread[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORE_KEY, JSON.stringify(t));
  } catch {
    /* quota — user just loses old history */
  }
}

export function relTime(ts: number): string {
  const d = Math.floor((Date.now() - ts) / 1000);
  if (d < 60) return 'just now';
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}

/* ---------------- helpers ---------------- */

/** Flatten an AI message's blocks into plain text — used for the copy
 *  button + the conversation history we send back to the model. */
export function blocksToText(blocks: AssistantBlock[]): string {
  return blocks
    .filter((b): b is Extract<AssistantBlock, { kind: 'text' }> => b.kind === 'text')
    .map(b => b.text)
    .join('\n');
}

function toApiHistory(history: AskMessage[]) {
  return history.map(m =>
    m.role === 'user'
      ? { role: 'user' as const, content: m.text }
      : { role: 'assistant' as const, content: blocksToText(m.blocks) },
  );
}

/* ---------------- streaming primitive ---------------- */

/**
 * Stream the LLM's response through /api/chat, calling `onEvent` with each
 * wire event as it arrives. The caller folds those events into the AI
 * message (blocks + citations). Resolves when the stream completes.
 */
export async function askStrata(
  history: AskMessage[],
  question: string,
  onEvent: (ev: WireEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const messages = [
    ...toApiHistory(history),
    { role: 'user' as const, content: question },
  ];
  for await (const ev of streamChat(messages, signal)) {
    onEvent(ev);
  }
}

/* ---------------- event reducer (shared by AskDock) ---------------- */

/** Fold a single wire event into an AI AskMessage. Returns the new message
 *  (immutable update). The blocks model matches the legacy /chat exactly so
 *  the existing ToolRow + ReactMarkdown primitives render it unchanged. */
export function applyWireEvent(
  msg: Extract<AskMessage, { role: 'ai' }>,
  ev: WireEvent,
): Extract<AskMessage, { role: 'ai' }> {
  const blocks = [...msg.blocks];

  if (ev.type === 'text') {
    const tail = blocks[blocks.length - 1];
    if (tail && tail.kind === 'text') {
      blocks[blocks.length - 1] = { kind: 'text', text: tail.text + ev.delta };
    } else {
      blocks.push({ kind: 'text', text: ev.delta });
    }
    return { ...msg, blocks };
  }
  if (ev.type === 'tool_call') {
    blocks.push({
      kind: 'tool',
      id: ev.id,
      name: ev.name,
      args: ev.args || {},
      result: null,
      status: 'running',
    });
    return { ...msg, blocks };
  }
  if (ev.type === 'tool_result') {
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
    return { ...msg, blocks };
  }
  if (ev.type === 'done') {
    return { ...msg, blocks, citations: (ev.citations as Citation[]) || [], streaming: false };
  }
  if (ev.type === 'error') {
    return {
      ...msg,
      blocks: [
        ...blocks,
        { kind: 'text', text: `\n\n_Error: ${ev.message}_` },
      ],
      streaming: false,
    };
  }
  return msg;
}
